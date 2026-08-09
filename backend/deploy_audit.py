"""Auditor-governance module for Obserra SAP UAC.

External Audit Room portal, auditor comments / requests inbox, response SLA targets,
response-time analytics + heatmap, tokenized Slack/Teams action links, SLA escalation
and the scheduled overdue-request digest. Every route registers on the shared
``deploy_router`` imported from :mod:`deploy`. Split out of deploy.py to keep both
files small and safe to edit.
"""
import io  # noqa: F401
import os  # noqa: F401
import sys  # noqa: F401

from fastapi import Depends, HTTPException  # noqa: F401
from fastapi.responses import StreamingResponse  # noqa: F401
from pydantic import BaseModel  # noqa: F401

from auth import get_current_user  # noqa: F401
from db import db  # noqa: F401
from deploy import (  # noqa: F401
    deploy_router,
    TokenBody,
    _now_iso,
    _route_alert,
    evaluate_org_health,
    _period_uptime,
    _list_evidence_files,
    _safe_evidence_path,
    _watermark_pdf,
    _PDF_MT,
)


_FINDINGS_CACHE = {}   # org_id -> (expires_ts, findings) — the public portal path is unauthenticated & hot
_FINDINGS_TTL = 60.0
_EV_RAW_CACHE = {}     # evidence file path -> raw bytes (immutable; filenames are timestamped)


async def _audit_findings(org_id: str):
    import time
    _ts = time.time()
    _c = _FINDINGS_CACHE.get(org_id)
    if _c and _c[0] > _ts:
        return _c[1]
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    h = await evaluate_org_health(org_id)
    # Live SoD conflicts via the correlation engine (top open, ordered by severity).
    top_conflicts, sod_open = [], 0
    try:
        from sap_engine import _correlate
        _persons, _accounts, conflicts, pmap = await _correlate(org_id)
        open_conf = [c for c in conflicts if c.get("status") == "Open"]
        sod_open = len(open_conf)
        sev_w = {"Critical": 3, "High": 2, "Medium": 1}
        open_conf.sort(key=lambda c: (-sev_w.get(c.get("severity"), 0), c.get("rule_ref", "")))
        for c in open_conf[:8]:
            person = pmap.get(c.get("person_ref"))
            top_conflicts.append({
                "rule": c.get("rule_name") or c.get("rule_ref"),
                "area": c.get("area", "—"), "severity": c.get("severity", "—"),
                "who": person["name"] if person else (str(c.get("sap_user", "")) + " (technical)")})
    except Exception:
        sod_open = await db.risks.count_documents({"org_id": org_id})
    # Overdue access certification campaigns (Active + past due).
    overdue_certs = []
    try:
        nowiso = now.isoformat()
        camps = await db.sap_certifications.find({"org_id": org_id, "status": "Active"}, {"_id": 0, "items": 0}).to_list(200)
        for c in camps:
            due = c.get("due_date") or ""
            if due and due < nowiso:
                overdue_certs.append({"name": c.get("name") or c.get("ref"), "type": c.get("type", "—"), "due_date": due[:10]})
    except Exception:
        pass
    result = {
        "healthy": h["healthy"],
        "uptime_30d": await _period_uptime(org_id, (now - timedelta(days=30)).isoformat(), now.isoformat()),
        "degraded_connectors": len(h.get("degraded_connectors") or []),
        "sod_violations": sod_open,
        "servicenow_tickets": await db.sap_snow_tickets.count_documents({"org_id": org_id}),
        "certifications": await db.sap_certifications.count_documents({"org_id": org_id}),
        "top_conflicts": top_conflicts,
        "overdue_certs": overdue_certs[:8],
    }
    _FINDINGS_CACHE[org_id] = (_ts + _FINDINGS_TTL, result)
    return result


def _room_branding_cfg(org):
    c = ((org or {}).get("system_health") or {}).get("audit_room") or {}
    return {"logo": c.get("logo") or "", "welcome": c.get("welcome") or "",
            "use_org_logo": bool(c.get("use_org_logo", True))}


def _resolve_room_logo(org, cfg):
    if cfg.get("logo"):
        return cfg["logo"]
    if cfg.get("use_org_logo"):
        rb = (org or {}).get("report_branding") or {}
        if rb.get("logo"):
            return rb["logo"]
    return ""


def _audit_wrap(inner, badge):
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Obserra SAP UAC — Audit Room</title>'
            '<style>body{font:400 15px/1.6 -apple-system,Segoe UI,Arial;background:#0f1e3d;color:#e5e7eb;margin:0;padding:40px 16px}'
            f'.card{{max-width:720px;margin:auto;background:#fff;color:#111827;border-radius:16px;padding:32px 30px;border-top:6px solid {badge}}}'
            'h1{font-size:22px;margin:6px 0 2px;color:#0f1e3d}h2{font-size:15px;color:#0f1e3d;margin:22px 0 6px}'
            '.pill{display:inline-block;color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;text-transform:uppercase;letter-spacing:.05em}'
            '.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:16px 0}'
            '.tile{background:#f4f6fb;border-radius:10px;padding:14px 12px;text-align:center}'
            '.tv{font-size:22px;font-weight:700;color:#0f1e3d}.tl{font-size:11px;color:#6b7280;margin-top:2px}'
            '.btn{display:inline-block;background:#2f6df6;color:#fff;text-decoration:none;padding:10px 16px;border-radius:8px;font-size:14px;font-weight:600}'
            '.hint{font-size:12px;color:#6b7280}'
            '.rlogo{max-height:46px;max-width:220px;margin-bottom:12px;display:block}'
            '.welcome{background:#f4f6fb;border-radius:10px;padding:12px 14px;margin:14px 0;font-size:14px;color:#374151;white-space:pre-wrap}'
            '.ftab{width:100%;border-collapse:collapse;font-size:12px;margin:8px 0}'
            '.ftab th{text-align:left;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.05em;padding:6px 8px;border-bottom:1px solid #e5e7eb}'
            '.ftab td{padding:7px 8px;border-bottom:1px solid #f1f5f9;vertical-align:top}'
            '.sev{display:inline-block;color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:999px}'
            '.clist{margin:8px 0;padding-left:18px}.clist li{margin:4px 0;font-size:13px}'
            '#cbox input,#cbox textarea,#dlname{width:100%;box-sizing:border-box;border:1px solid #d1d5db;border-radius:8px;padding:9px 11px;font-size:14px;margin:6px 0;font-family:inherit}'
            '#csend{border:none;cursor:pointer;margin-top:4px}'
            '#dlbtn{border:none;cursor:pointer;margin-top:4px}'
            '.thread{background:#f4f6fb;border-radius:10px;padding:10px 12px;margin:8px 0}'
            '.thead{display:flex;justify-content:space-between;align-items:center;font-size:12px;font-weight:600;color:#0f1e3d}'
            '.ctext{font-size:13px;color:#374151;margin-top:4px;white-space:pre-wrap}'
            '.reply{font-size:13px;color:#111827;margin-top:8px;padding-top:8px;border-top:1px dashed #d1d5db;white-space:pre-wrap}'
            '.brand{max-width:720px;margin:14px auto 0;text-align:center;color:#94a3b8;font-size:12px}</style></head>'
            f'<body><div class="card">{inner}</div><div class="brand">Obserra SAP UAC · Enterprise SAP Access Governance</div></body></html>')


def _esc_html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _audit_room_html(org_name, room, findings, latest, branding=None, comments=None):
    if org_name is None:
        return _audit_wrap("<h1>Audit room not found</h1><p>This link is invalid or has been revoked.</p>", "#c2410c")
    if org_name == "expired":
        return _audit_wrap("<h1>Audit room expired</h1><p>Ask your Obserra administrator for a fresh link.</p>", "#b45309")
    branding = branding or {}
    up = findings.get("uptime_30d")
    tiles = [("Uptime (30d)", f"{up}%" if up is not None else "—"),
             ("Degraded connectors", findings["degraded_connectors"]),
             ("Open SoD violations", findings["sod_violations"]),
             ("ServiceNow tickets", findings["servicenow_tickets"]),
             ("Certifications", findings["certifications"])]
    status = "Healthy" if findings["healthy"] else "Degraded"
    scolor = "#12805c" if findings["healthy"] else "#c2410c"
    tile_html = "".join(f'<div class="tile"><div class="tv">{v}</div><div class="tl">{ln}</div></div>' for ln, v in tiles)
    period = latest.get("period_label") if latest else "—"
    # Findings depth — top open SoD violations
    conflicts = findings.get("top_conflicts") or []
    sev_bg = {"Critical": "#b91c1c", "High": "#c2410c", "Medium": "#b45309"}
    if conflicts:
        crows = "".join(
            f'<tr><td><span class="sev" style="background:{sev_bg.get(c["severity"], "#6b7280")}">{_esc_html(c["severity"])}</span></td>'
            f'<td>{_esc_html(c["rule"])}</td><td>{_esc_html(c["area"])}</td><td>{_esc_html(c["who"])}</td></tr>'
            for c in conflicts)
        conflicts_html = ('<h2>Top open Segregation-of-Duties violations</h2>'
                          '<table class="ftab"><thead><tr><th>Severity</th><th>Rule</th><th>Area</th><th>Holder</th></tr></thead>'
                          f'<tbody>{crows}</tbody></table>')
    else:
        conflicts_html = '<h2>Segregation-of-Duties</h2><p class="hint">No open SoD violations — access is clean.</p>'
    # Overdue certifications
    certs = findings.get("overdue_certs") or []
    if certs:
        rows = "".join(f'<li>{_esc_html(c["name"])} <span class="hint">· {_esc_html(c["type"])} · due {_esc_html(c["due_date"])}</span></li>' for c in certs)
        certs_html = f'<h2>Overdue access certifications</h2><ul class="clist">{rows}</ul>'
    else:
        certs_html = ""
    # Branding
    logo = branding.get("logo") or ""
    logo_html = f'<img src="{logo}" alt="logo" class="rlogo"/>' if logo else ""
    welcome = branding.get("welcome") or ""
    welcome_html = f'<div class="welcome">{_esc_html(welcome)}</div>' if welcome else ""
    # Latest signed evidence — download stamps the auditor's name + access date onto the PDF
    if latest:
        evidence_html = (
            '<h2>Latest signed evidence</h2>'
            f'<p class="hint">Reporting period: {period}</p>'
            '<input id="dlname" placeholder="Your name (stamped on the PDF for provenance)" />'
            '<button class="btn" id="dlbtn" onclick="dlEvidence()">Download latest signed evidence (PDF)</button>'
            '<script>'
            'function dlEvidence(){'
            'var n=document.getElementById("dlname").value.trim();'
            f'var u="/api/deploy/audit-room/{room["token"]}/evidence";'
            'if(n)u+="?who="+encodeURIComponent(n);'
            'window.open(u,"_blank");'
            '}</script>')
    else:
        evidence_html = '<h2>Latest signed evidence</h2><p class="hint">No signed evidence report has been generated yet.</p>'
    # Existing exchange — auditor comments + governance-team replies + status
    comments = comments or []
    stbg = {"Open": "#b45309", "In Progress": "#2f6df6", "Resolved": "#12805c"}
    items = []
    for c in comments:
        st = c.get("status", "Open")
        reply_html = (f'<div class="reply"><strong>Governance team:</strong> {_esc_html(c["reply"])}</div>'
                      if c.get("reply") else "")
        items.append(
            f'<div class="thread"><div class="thead"><span>{_esc_html(c.get("author", "Auditor"))}</span>'
            f'<span class="sev" style="background:{stbg.get(st, "#6b7280")}">{_esc_html(st)}</span></div>'
            f'<div class="ctext">{_esc_html(c.get("comment", ""))}</div>{reply_html}</div>')
    _disp = "block" if comments else "none"
    reply_count = sum(1 for c in comments if c.get("reply"))
    thread_html = (f'<div id="reply-alert" style="display:none;background:#eef4ff;border:1px solid #c7dbff;border-radius:8px;padding:8px 12px;margin:8px 0;color:#1e40af;font-weight:600;font-size:13px"></div>'
                   f'<h2 id="thread-h" style="display:{_disp}">Comment thread</h2>'
                   f'<div id="thread-list">' + "".join(items) + '</div>'
                   f'<script>(function(){{var tok="{room["token"]}";var total={reply_count};'
                   f'var k="obserra_seen_replies_"+tok;var seen=parseInt(localStorage.getItem(k)||"0",10);var nw=total-seen;'
                   f'if(nw>0){{var el=document.getElementById("reply-alert");if(el){{el.style.display="block";'
                   f'el.textContent=nw+" new repl"+(nw===1?"y":"ies")+" from the governance team";}}}}'
                   f'localStorage.setItem(k,String(total));}})();</script>')
    # Auditor comment box (posts back to the room comment endpoint)
    comment_html = (
        '<h2>Leave a comment</h2>'
        '<p class="hint">Auditors can leave notes or questions for the SAP access governance team.</p>'
        '<div id="cbox">'
        '<input id="cauth" placeholder="Your name (optional)" />'
        '<input id="cmail" type="email" placeholder="Your email (optional — we will notify you of replies)" />'
        '<textarea id="ctext" placeholder="Your comment or question…" rows="3"></textarea>'
        '<button class="btn" id="csend" onclick="sendComment()">Submit comment</button>'
        '<div id="cmsg" class="hint" style="margin-top:6px"></div></div>'
        '<script>'
        'async function sendComment(){'
        'var t=document.getElementById("ctext").value.trim();'
        'var a=document.getElementById("cauth").value.trim();'
        'var e2=document.getElementById("cmail").value.trim();'
        'var m=document.getElementById("cmsg");'
        'if(!t){m.textContent="Please enter a comment.";return;}'
        'document.getElementById("csend").disabled=true;'
        f'try{{var r=await fetch("/api/deploy/audit-room/{room["token"]}/comment",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{author:a,email:e2,comment:t}})}});'
        'if(r.ok){'
        'var li=document.createElement("div");li.className="thread";'
        'var head=document.createElement("div");head.className="thead";'
        'var nm=document.createElement("span");nm.textContent=(a||"You");'
        'var bg=document.createElement("span");bg.className="sev";bg.style.background="#b45309";bg.textContent="Open";'
        'head.appendChild(nm);head.appendChild(bg);'
        'var ct=document.createElement("div");ct.className="ctext";ct.textContent=t;'
        'li.appendChild(head);li.appendChild(ct);'
        'document.getElementById("thread-list").appendChild(li);'
        'document.getElementById("thread-h").style.display="block";'
        'document.getElementById("ctext").value="";'
        'm.style.color="#12805c";m.textContent="Thank you — your comment was sent to the governance team.";'
        'document.getElementById("csend").disabled=false;'
        '}'
        'else{m.textContent="Could not submit — the link may have expired.";document.getElementById("csend").disabled=false;}'
        '}catch(e){m.textContent="Network error, please try again.";document.getElementById("csend").disabled=false;}'
        '}</script>')
    inner = (f'{logo_html}'
             f'<div class="pill" style="background:{scolor}">{status}</div>'
             f'<h1>SAP Access Compliance — {_esc_html(org_name)}</h1>'
             f'<p>Read-only audit portal · expires {room.get("expires_at", "")[:10]}</p>'
             f'{welcome_html}'
             f'<div class="tiles">{tile_html}</div>'
             f'{conflicts_html}{certs_html}'
             f'{evidence_html}'
             f'{thread_html}'
             f'{comment_html}')
    return _audit_wrap(inner, "#2f6df6")


class AuditRoomBody(BaseModel):
    ttl_days: int = 14


@deploy_router.post("/audit-room")
async def create_audit_room(body: AuditRoomBody, user: dict = Depends(get_current_user)):
    """Create a branded, expiring public portal bundling the latest evidence PDF + live findings."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import secrets
    from datetime import datetime, timezone, timedelta
    ttl = max(1, min(90, int(body.ttl_days)))
    token = secrets.token_urlsafe(16)
    expires = (datetime.now(timezone.utc) + timedelta(days=ttl)).isoformat()
    await db.audit_rooms.insert_one({"token": token, "org_id": user["org_id"], "created_by": user["email"],
                                     "created_at": _now_iso(), "expires_at": expires, "opens": 0})
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return {"token": token, "url": f"{frontend}/api/deploy/audit-room/{token}", "expires_at": expires, "ttl_days": ttl}


@deploy_router.get("/audit-rooms")
async def list_audit_rooms(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    rows = await db.audit_rooms.find({"org_id": user["org_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    for r in rows:
        r["expired"] = bool(r.get("expires_at") and now > r["expires_at"])
        r["url"] = f"{frontend}/api/deploy/audit-room/{r['token']}"
    return {"rooms": rows}


@deploy_router.post("/audit-room/revoke")
async def revoke_audit_room(body: TokenBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    res = await db.audit_rooms.delete_one({"token": body.token, "org_id": user["org_id"]})
    return {"revoked": res.deleted_count > 0}


@deploy_router.get("/audit-room/{token}")
async def view_audit_room(token: str):
    """Public, unauthenticated audit portal."""
    from fastapi.responses import HTMLResponse
    from datetime import datetime, timezone
    from bson import ObjectId
    room = await db.audit_rooms.find_one({"token": token})
    if not room:
        return HTMLResponse(_audit_room_html(None, None, None, None), status_code=404)
    if room.get("expires_at") and datetime.now(timezone.utc).isoformat() > room["expires_at"]:
        return HTMLResponse(_audit_room_html("expired", None, None, None), status_code=410)
    await db.audit_rooms.update_one({"token": token}, {"$inc": {"opens": 1}, "$set": {"last_opened_at": _now_iso()}})
    org = await db.organizations.find_one({"_id": ObjectId(room["org_id"])}) or {}
    findings = await _audit_findings(room["org_id"])
    latest = (_list_evidence_files(room["org_id"]) or [None])[0]
    cfg = _room_branding_cfg(org)
    branding = {"logo": _resolve_room_logo(org, cfg), "welcome": cfg["welcome"]}
    room_comments = await db.audit_room_comments.find({"token": token}, {"_id": 0}).sort("at", 1).to_list(200)
    return HTMLResponse(_audit_room_html(org.get("name") or "Organization", room, findings, latest, branding, room_comments))


@deploy_router.get("/audit-room/{token}/evidence")
async def audit_room_evidence(token: str, who: str = ""):
    """Public download of the latest evidence PDF (watermarked with the auditor's name + access date)."""
    from datetime import datetime, timezone
    room = await db.audit_rooms.find_one({"token": token})
    if not room:
        raise HTTPException(404, "Audit room not found.")
    if room.get("expires_at") and datetime.now(timezone.utc).isoformat() > room["expires_at"]:
        raise HTTPException(410, "This audit room has expired.")
    latest = (_list_evidence_files(room["org_id"]) or [None])[0]
    if not latest:
        raise HTTPException(404, "No evidence has been generated yet.")
    fp = _safe_evidence_path(latest["file"])
    raw = _EV_RAW_CACHE.get(fp)
    if raw is None:
        with open(fp, "rb") as f:
            raw = f.read()
        if len(_EV_RAW_CACHE) > 32:
            _EV_RAW_CACHE.clear()
        _EV_RAW_CACHE[fp] = raw
    auditor = (who or "").strip()[:120] or "External auditor"
    access = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    content = _watermark_pdf(raw, "AUDIT ROOM COPY",
                             f"Downloaded by {auditor} · {access} · expires {room.get('expires_at', '')[:10]}")
    await db.audit_rooms.update_one({"token": token},
                                    {"$inc": {"downloads": 1},
                                     "$set": {"last_downloaded_at": _now_iso(), "last_downloaded_by": auditor}})
    return StreamingResponse(io.BytesIO(content), media_type=_PDF_MT,
                             headers={"Content-Disposition": f'inline; filename="{os.path.basename(fp)}"'})


class RoomBrandingBody(BaseModel):
    logo: str | None = None
    welcome: str = ""
    use_org_logo: bool = True


@deploy_router.get("/audit-room-branding")
async def get_audit_room_branding(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    cfg = _room_branding_cfg(org)
    rb = org.get("report_branding") or {}
    return {"welcome": cfg["welcome"], "use_org_logo": cfg["use_org_logo"],
            "has_logo": bool(cfg["logo"]), "org_logo_available": bool(rb.get("logo"))}


@deploy_router.put("/audit-room-branding")
async def set_audit_room_branding(body: RoomBrandingBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    update = {"system_health.audit_room.welcome": (body.welcome or "").strip()[:600],
              "system_health.audit_room.use_org_logo": bool(body.use_org_logo)}
    unset = {}
    if body.logo is not None:
        if body.logo.strip():
            if len(body.logo) > 2_000_000:
                raise HTTPException(400, "Logo is too large (max ~1.5MB).")
            update["system_health.audit_room.logo"] = body.logo.strip()
        else:
            unset["system_health.audit_room.logo"] = ""
    ops = {"$set": update}
    if unset:
        ops["$unset"] = unset
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])}, ops)
    return {"ok": True}


@deploy_router.post("/shares/revoke-all")
async def revoke_all_shares(user: dict = Depends(get_current_user)):
    """One-tap revoke of every auditor share link AND audit room for the org."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    s = await db.evidence_shares.delete_many({"org_id": user["org_id"]})
    r = await db.audit_rooms.delete_many({"org_id": user["org_id"]})
    return {"shares_revoked": s.deleted_count, "rooms_revoked": r.deleted_count}


class RoomCommentBody(BaseModel):
    author: str = ""
    email: str = ""
    comment: str


@deploy_router.post("/audit-room/{token}/comment")
async def audit_room_comment(token: str, body: RoomCommentBody):
    """Public — external auditors leave a comment on the portal; notifies admins."""
    from datetime import datetime, timezone
    room = await db.audit_rooms.find_one({"token": token})
    if not room:
        raise HTTPException(404, "Audit room not found.")
    if room.get("expires_at") and datetime.now(timezone.utc).isoformat() > room["expires_at"]:
        raise HTTPException(410, "This audit room has expired.")
    text = (body.comment or "").strip()
    if not text:
        raise HTTPException(400, "A comment is required.")
    author = (body.author or "").strip()[:120] or "Anonymous auditor"
    author_email = (body.email or "").strip()[:200]
    org_id = room["org_id"]
    import secrets
    cid = secrets.token_urlsafe(9)
    await db.audit_room_comments.insert_one({
        "id": cid, "token": token, "org_id": org_id, "author": author, "author_email": author_email,
        "comment": text[:2000], "at": _now_iso(),
        "status": "Open", "reply": None, "reply_by": None, "reply_at": None})
    await db.audit_rooms.update_one({"token": token}, {"$inc": {"comments": 1}})
    try:
        from kernel import notifications
        await notifications.create(org_id, "system", "New Audit Room comment",
                                   f"{author}: {text[:200]}", ref="system-health")
        recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                     {"_id": 0, "email": 1}).to_list(200)
        html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                f"<h2 style='color:#0f1e3d'>New Audit Room comment</h2>"
                f"<p><strong>{_esc_html(author)}</strong> left a comment on your SAP Access Compliance audit portal:</p>"
                f"<blockquote style='border-left:3px solid #2f6df6;margin:0;padding:6px 14px;color:#374151'>{_esc_html(text[:1000])}</blockquote>"
                f"<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — System Health · Audit Room</p></div>")
        for rr in recips:
            try:
                await notifications.send_email(rr["email"], "New Audit Room comment — Obserra SAP UAC", html)
            except Exception:
                pass
    except Exception:
        pass
    return {"ok": True}


@deploy_router.get("/audit-room-comments")
async def list_audit_room_comments(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import secrets
    org_id = user["org_id"]
    # Backfill legacy comments so every one has an id + status and is replyable from the inbox.
    async for c in db.audit_room_comments.find({"org_id": org_id, "id": {"$exists": False}}, {"_id": 1}):
        await db.audit_room_comments.update_one(
            {"_id": c["_id"]}, {"$set": {"id": secrets.token_urlsafe(9), "status": "Open"}})
    rows = await db.audit_room_comments.find({"org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(200)
    base, smap = await _sla_map(org_id)
    for r in rows:
        r["sla_hours"] = smap.get(r.get("token"), base)
    return {"comments": rows, "sla_hours": base}


class CommentReplyBody(BaseModel):
    reply: str


@deploy_router.post("/audit-room-comments/{comment_id}/reply")
async def reply_audit_room_comment(comment_id: str, body: CommentReplyBody, user: dict = Depends(get_current_user)):
    """Admin reply to an auditor comment — the whole exchange stays in one place and shows on the portal."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    reply = (body.reply or "").strip()
    if not reply:
        raise HTTPException(400, "A reply is required.")
    res = await db.audit_room_comments.update_one(
        {"id": comment_id, "org_id": user["org_id"]},
        {"$set": {"reply": reply[:2000], "reply_by": user["email"], "reply_at": _now_iso(), "status": "Resolved"}})
    if res.matched_count == 0:
        raise HTTPException(404, "Comment not found.")
    # Notify the auditor by email (if they left one) so they don't have to keep re-checking the portal.
    try:
        doc = await db.audit_room_comments.find_one({"id": comment_id, "org_id": user["org_id"]}, {"_id": 0})
        em = (doc or {}).get("author_email") or ""
        if em and "@" in em:
            from kernel import notifications
            from bson import ObjectId
            org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
            oname = org.get("name") or "the organization"
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#0f1e3d'>Reply to your audit comment</h2>"
                    f"<p>The SAP access governance team at <strong>{_esc_html(oname)}</strong> replied to your comment:</p>"
                    f"<blockquote style='border-left:3px solid #2f6df6;margin:0;padding:6px 14px;color:#374151'>{_esc_html(reply[:1000])}</blockquote>"
                    f"<p style='font-size:12px;color:#6b7280'>Your original note: {_esc_html((doc.get('comment') or '')[:300])}</p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — Audit Room</p></div>")
            await notifications.send_email(em, f"Reply to your audit comment — {oname}", html)
    except Exception:
        pass
    return {"ok": True}


class CommentStatusBody(BaseModel):
    status: str


@deploy_router.post("/audit-room-comments/{comment_id}/status")
async def set_audit_room_comment_status(comment_id: str, body: CommentStatusBody, user: dict = Depends(get_current_user)):
    """Track an auditor request through Open → In Progress → Resolved."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    if body.status not in ("Open", "In Progress", "Resolved"):
        raise HTTPException(400, "Invalid status")
    res = await db.audit_room_comments.update_one(
        {"id": comment_id, "org_id": user["org_id"]}, {"$set": {"status": body.status}})
    if res.matched_count == 0:
        raise HTTPException(404, "Comment not found.")
    return {"ok": True}


class RenewRoomBody(BaseModel):
    token: str
    ttl_days: int = 14


@deploy_router.post("/audit-room/renew")
async def renew_audit_room(body: RenewRoomBody, user: dict = Depends(get_current_user)):
    """Extend an expiring Audit Room in one click and re-arm its expiry reminder."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from datetime import datetime, timezone, timedelta
    ttl = max(1, min(90, int(body.ttl_days or 14)))
    expires = (datetime.now(timezone.utc) + timedelta(days=ttl)).isoformat()
    res = await db.audit_rooms.update_one(
        {"token": body.token, "org_id": user["org_id"]},
        {"$set": {"expires_at": expires}, "$unset": {"expiry_reminder_sent": ""}})
    if res.matched_count == 0:
        raise HTTPException(404, "Audit room not found.")
    return {"ok": True, "expires_at": expires, "ttl_days": ttl}


_DEFAULT_SLA_HOURS = 72
_ACTION_TTL_DAYS = 7


def _org_sla(org):
    try:
        return max(1, min(720, int(((org or {}).get("system_health") or {}).get("sla_hours") or _DEFAULT_SLA_HOURS)))
    except Exception:
        return _DEFAULT_SLA_HOURS


async def _sla_map(org_id, org=None):
    from bson import ObjectId
    if org is None:
        org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
    base = _org_sla(org)
    m = {}
    for r in await db.audit_rooms.find({"org_id": org_id}, {"_id": 0, "token": 1, "sla_hours": 1}).to_list(1000):
        ov = r.get("sla_hours")
        try:
            m[r["token"]] = max(1, min(720, int(ov))) if ov else base
        except Exception:
            m[r["token"]] = base
    return base, m


def _action_expired(c):
    from datetime import datetime, timezone
    return bool(c.get("action_expires_at")) and datetime.now(timezone.utc).isoformat() > c["action_expires_at"]


_DEFAULT_ESCALATION = {"enabled": False, "contacts": [], "multiplier": 1.5}
_DEFAULT_DIGEST_SCHEDULE = {"enabled": True, "days": [0, 1, 2, 3, 4, 5, 6]}
_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _escalation_cfg(org):
    c = ((org or {}).get("system_health") or {}).get("escalation") or {}
    try:
        mult = float(c.get("multiplier", 1.5))
    except Exception:
        mult = 1.5
    return {
        "enabled": bool(c.get("enabled", False)),
        "contacts": [e for e in (c.get("contacts") or []) if e],
        "multiplier": max(1.0, min(5.0, mult)),
    }


def _digest_schedule_cfg(org):
    """Days use Python weekday convention (Mon=0 … Sun=6). Send hour is fixed by the platform daily cron (08:00 UTC)."""
    c = ((org or {}).get("system_health") or {}).get("digest_schedule") or {}
    days = c.get("days")
    if not isinstance(days, list) or not days:
        days = list(range(7))
    days = sorted({int(d) for d in days if 0 <= int(d) <= 6})
    return {"enabled": bool(c.get("enabled", True)), "days": days or list(range(7))}


class EscalationBody(BaseModel):
    enabled: bool = False
    contacts: list[str] = []
    multiplier: float = 1.5


@deploy_router.get("/escalation-config")
async def get_escalation_config(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    return _escalation_cfg(org)


@deploy_router.put("/escalation-config")
async def set_escalation_config(body: EscalationBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import re
    from bson import ObjectId
    contacts = []
    for e in body.contacts:
        e = (e or "").strip()
        if re.match(_EMAIL_RE, e) and e not in contacts:
            contacts.append(e)
    cfg = {"enabled": bool(body.enabled), "contacts": contacts,
           "multiplier": max(1.0, min(5.0, float(body.multiplier or 1.5)))}
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"system_health.escalation": cfg}})
    return cfg


class DigestScheduleBody(BaseModel):
    enabled: bool = True
    days: list[int] = [0, 1, 2, 3, 4, 5, 6]


@deploy_router.get("/digest-schedule")
async def get_digest_schedule(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    return {**_digest_schedule_cfg(org), "run_hour_utc": 8}


@deploy_router.put("/digest-schedule")
async def set_digest_schedule(body: DigestScheduleBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    days = sorted({int(d) for d in (body.days or []) if 0 <= int(d) <= 6}) or list(range(7))
    cfg = {"enabled": bool(body.enabled), "days": days}
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"system_health.digest_schedule": cfg}})
    return {**cfg, "run_hour_utc": 8}


class SlaConfigBody(BaseModel):
    sla_hours: int


@deploy_router.get("/sla-config")
async def get_sla_config(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    base = _org_sla(org)
    docs = await db.audit_rooms.find({"org_id": user["org_id"]}, {"_id": 0, "token": 1, "sla_hours": 1}).to_list(1000)
    rooms = []
    for i, d in enumerate(docs):
        ov = d.get("sla_hours")
        eff = max(1, min(720, int(ov))) if ov else base
        rooms.append({"token": d["token"], "label": f"Room {i + 1}", "override": ov, "effective": eff})
    return {"org_sla_hours": base, "default": _DEFAULT_SLA_HOURS, "rooms": rooms}


@deploy_router.put("/sla-config")
async def set_sla_config(body: SlaConfigBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    v = max(1, min(720, int(body.sla_hours or _DEFAULT_SLA_HOURS)))
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])}, {"$set": {"system_health.sla_hours": v}})
    return {"ok": True, "sla_hours": v}


class RoomSlaBody(BaseModel):
    sla_hours: int | None = None


@deploy_router.put("/audit-room/{token}/sla")
async def set_room_sla(token: str, body: RoomSlaBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    if body.sla_hours is None:
        await db.audit_rooms.update_one({"token": token, "org_id": user["org_id"]}, {"$unset": {"sla_hours": ""}})
    else:
        v = max(1, min(720, int(body.sla_hours)))
        await db.audit_rooms.update_one({"token": token, "org_id": user["org_id"]}, {"$set": {"sla_hours": v}})
    return {"ok": True}


class BulkFilterBody(BaseModel):
    status: str
    filter_status: str | None = None
    room_token: str | None = None


@deploy_router.post("/audit-room-comments/bulk-status-filter")
async def bulk_status_filter(body: BulkFilterBody, user: dict = Depends(get_current_user)):
    """Apply a status to ALL requests matching the current filter (spans beyond the loaded rows)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    if body.status not in ("Open", "In Progress", "Resolved"):
        raise HTTPException(400, "Invalid status")
    q = {"org_id": user["org_id"]}
    if body.filter_status in ("Open", "In Progress", "Resolved"):
        q["status"] = body.filter_status
    if body.room_token:
        q["token"] = body.room_token
    res = await db.audit_room_comments.update_many(q, {"$set": {"status": body.status}})
    return {"ok": True, "updated": res.modified_count}


_DEFAULT_REPLY_TEMPLATES = [
    {"label": "Evidence attached", "text": "The requested evidence is attached in the latest signed evidence pack — see the download on your portal."},
    {"label": "Under review", "text": "Thanks — the governance team is reviewing this request and will follow up shortly."},
    {"label": "Please clarify", "text": "Could you clarify the specific system, control or period this request relates to so we can provide the right evidence?"},
    {"label": "Resolved", "text": "This has been addressed. Please let us know if you need anything further for your audit."},
]


class BulkStatusBody(BaseModel):
    ids: list[str]
    status: str


@deploy_router.post("/audit-room-comments/bulk-status")
async def bulk_set_comment_status(body: BulkStatusBody, user: dict = Depends(get_current_user)):
    """Resolve / reassign many auditor requests at once during a busy audit."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    if body.status not in ("Open", "In Progress", "Resolved"):
        raise HTTPException(400, "Invalid status")
    ids = [i for i in (body.ids or []) if i][:500]
    if not ids:
        raise HTTPException(400, "No requests selected.")
    res = await db.audit_room_comments.update_many(
        {"id": {"$in": ids}, "org_id": user["org_id"]}, {"$set": {"status": body.status}})
    return {"ok": True, "updated": res.modified_count}


class ReplyTemplatesBody(BaseModel):
    templates: list[dict]


@deploy_router.get("/reply-templates")
async def get_reply_templates(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    org = await db.organizations.find_one({"_id": ObjectId(user["org_id"])}) or {}
    tpls = (org.get("system_health") or {}).get("reply_templates")
    return {"templates": tpls if tpls else _DEFAULT_REPLY_TEMPLATES, "is_default": not tpls}


@deploy_router.put("/reply-templates")
async def set_reply_templates(body: ReplyTemplatesBody, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from bson import ObjectId
    clean = []
    for t in (body.templates or [])[:30]:
        label = (str(t.get("label") or "")).strip()[:60]
        text = (str(t.get("text") or "")).strip()[:2000]
        if label and text:
            clean.append({"label": label, "text": text})
    await db.organizations.update_one({"_id": ObjectId(user["org_id"])},
                                      {"$set": {"system_health.reply_templates": clean}})
    return {"ok": True, "templates": clean}


@deploy_router.get("/audit-room-comments/export.csv")
async def export_audit_room_comments(user: dict = Depends(get_current_user)):
    """Download the full Audit Requests log (with replies, status, timestamps) as CSV for the audit file."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    import csv
    from datetime import datetime, timezone
    org_id = user["org_id"]
    rows = await db.audit_room_comments.find({"org_id": org_id}, {"_id": 0}).sort("at", -1).to_list(5000)
    room_tokens = [x["token"] for x in await db.audit_rooms.find({"org_id": org_id}, {"_id": 0, "token": 1}).to_list(1000)]
    label = {t: f"Room {i + 1}" for i, t in enumerate(room_tokens)}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Submitted", "Room", "Auditor", "Auditor email", "Status", "Request", "Reply", "Replied by", "Replied at"])
    for r in rows:
        w.writerow([r.get("at", ""), label.get(r.get("token"), "Archived room"), r.get("author", ""),
                    r.get("author_email", ""), r.get("status", "Open"), r.get("comment", ""),
                    r.get("reply") or "", r.get("reply_by") or "", r.get("reply_at") or ""])
    data = buf.getvalue().encode("utf-8-sig")
    fn = f"audit-requests-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return StreamingResponse(io.BytesIO(data), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@deploy_router.get("/audit-request-analytics")
async def audit_request_analytics(user: dict = Depends(get_current_user)):
    """Median response time (auditor comment → governance reply) org-wide and per room, the weekly-median trend, plus per-room SLA on-time vs breached (heatmap)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    from datetime import datetime, timezone
    from collections import defaultdict
    org_id = user["org_id"]
    now = datetime.now(timezone.utc)
    rows = await db.audit_room_comments.find({"org_id": org_id}, {"_id": 0}).to_list(5000)
    room_tokens = [x["token"] for x in await db.audit_rooms.find({"org_id": org_id}, {"_id": 0, "token": 1}).to_list(1000)]
    label = {t: f"Room {i + 1}" for i, t in enumerate(room_tokens)}
    base, smap = await _sla_map(org_id)

    def _median(vals):
        vals = sorted(vals)
        n = len(vals)
        if not n:
            return None
        return vals[n // 2] if n % 2 else round((vals[n // 2 - 1] + vals[n // 2]) / 2, 1)

    def _resp_h(c):
        if c.get("reply_at") and c.get("at"):
            try:
                return round((datetime.fromisoformat(c["reply_at"]) - datetime.fromisoformat(c["at"])).total_seconds() / 3600, 1)
            except Exception:
                return None
        return None

    def _age_h(c):
        try:
            return (now - datetime.fromisoformat(c["at"])).total_seconds() / 3600 if c.get("at") else None
        except Exception:
            return None

    def _bucket(items):
        rh = [h for h in (_resp_h(c) for c in items) if h is not None]
        return {
            "total": len(items),
            "open": sum(1 for c in items if (c.get("status") or "Open") == "Open"),
            "in_progress": sum(1 for c in items if c.get("status") == "In Progress"),
            "resolved": sum(1 for c in items if c.get("status") == "Resolved"),
            "replied": len(rh),
            "median_response_hours": _median(rh),
        }

    def _sla_class(items, sla):
        on_time = breached = pending = 0
        for c in items:
            rh = _resp_h(c)
            if rh is not None:
                if rh <= sla:
                    on_time += 1
                else:
                    breached += 1
            elif (c.get("status") or "Open") == "Resolved":
                on_time += 1
            else:
                ah = _age_h(c)
                if ah is not None and ah > sla:
                    breached += 1
                else:
                    pending += 1
        judged = on_time + breached
        return {"on_time": on_time, "breached": breached, "pending": pending,
                "on_time_pct": round(on_time / judged * 100) if judged else None, "sla_hours": sla}

    wk = defaultdict(list)
    for c in rows:
        h = _resp_h(c)
        if h is not None and c.get("reply_at"):
            try:
                d = datetime.fromisoformat(c["reply_at"])
                wk[(d.isocalendar()[0], d.isocalendar()[1])].append(h)
            except Exception:
                pass
    trend = [{"week": f"{y}-W{w:02d}", "median_hours": _median(wk[(y, w)])} for (y, w) in sorted(wk.keys())[-8:]]

    per_room = {}
    for c in rows:
        per_room.setdefault(c.get("token"), []).append(c)
    rooms_out = [{"label": label.get(tok, "Archived room"), **_bucket(items), **_sla_class(items, smap.get(tok, base))}
                 for tok, items in per_room.items()]
    rooms_out.sort(key=lambda r: (r["open"] == 0, r["label"]))
    return {"org": {**_bucket(rows), **_sla_class(rows, base)}, "rooms": rooms_out, "trend": trend, "sla_default": base}


def _req_action_html(comment, org_name, done=None):
    if comment == "expired":
        return _audit_wrap("<h1>Link expired</h1><p>This action link has expired for security. Open System Health to respond.</p>", "#b45309")
    if comment is None:
        return _audit_wrap("<h1>Request not found</h1><p>This action link is invalid or has expired.</p>", "#c2410c")
    if done == "resolved":
        return _audit_wrap("<h1>Marked resolved ✓</h1><p>The auditor request has been resolved. You can close this tab.</p>", "#12805c")
    if done == "replied":
        return _audit_wrap("<h1>Reply sent ✓</h1><p>Your reply was sent, the auditor notified (if they left an email), and the request marked resolved.</p>", "#12805c")
    st = comment.get("status", "Open")
    tok = comment["action_token"]
    inner = (f'<div class="pill" style="background:#2f6df6">{_esc_html(st)}</div>'
             f'<h1>Audit request — {_esc_html(org_name)}</h1>'
             f'<p class="hint">From {_esc_html(comment.get("author", "Auditor"))} · {comment.get("at", "")[:10]}</p>'
             f'<div class="welcome">{_esc_html(comment.get("comment", ""))}</div>'
             f'<h2>Respond</h2>'
             f'<div id="cbox">'
             f'<textarea id="rtext" rows="4" placeholder="Type your reply — this resolves the request and emails the auditor if they left an address"></textarea>'
             f'<button class="btn" id="rsend">Send reply &amp; resolve</button> '
             f'<button class="btn" id="rres" style="background:#12805c;margin-left:6px">Just mark resolved</button>'
             f'<div id="rmsg" class="hint" style="margin-top:8px"></div></div>'
             f'<script>'
             f'function done(msg){{document.getElementById("cbox").innerHTML="<p style=\\"color:#12805c;font-weight:600\\">"+msg+"</p>";}}'
             f'document.getElementById("rres").addEventListener("click",async function(){{'
             f'this.disabled=true;try{{var r=await fetch("/api/deploy/req-action/{tok}/resolve",{{method:"POST"}});'
             f'if(r.ok)done("Marked resolved ✓");else document.getElementById("rmsg").textContent="Link expired.";}}catch(e){{document.getElementById("rmsg").textContent="Network error.";}}}});'
             f'document.getElementById("rsend").addEventListener("click",async function(){{'
             f'var t=document.getElementById("rtext").value.trim();if(!t){{document.getElementById("rmsg").textContent="Enter a reply.";return;}}'
             f'this.disabled=true;try{{var r=await fetch("/api/deploy/req-action/{tok}/reply",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{reply:t}})}});'
             f'if(r.ok)done("Reply sent &amp; resolved ✓");else document.getElementById("rmsg").textContent="Link expired.";}}catch(e){{document.getElementById("rmsg").textContent="Network error.";}}}});'
             f'</script>')
    return _audit_wrap(inner, "#2f6df6")


@deploy_router.get("/req-action/{token}")
async def req_action_page(token: str):
    """Public tokenized page so an admin can resolve/reply straight from a Slack/Teams alert."""
    from bson import ObjectId
    from fastapi.responses import HTMLResponse
    c = await db.audit_room_comments.find_one({"action_token": token}, {"_id": 0})
    if not c:
        return HTMLResponse(_req_action_html(None, ""))
    if _action_expired(c):
        return HTMLResponse(_req_action_html("expired", ""))
    org = await db.organizations.find_one({"_id": ObjectId(c["org_id"])}) or {}
    return HTMLResponse(_req_action_html(c, org.get("name") or "Organization"))


@deploy_router.post("/req-action/{token}/resolve")
async def req_action_resolve(token: str):
    c = await db.audit_room_comments.find_one({"action_token": token})
    if not c:
        raise HTTPException(404, "Invalid action link.")
    if _action_expired(c):
        raise HTTPException(410, "This action link has expired.")
    await db.audit_room_comments.update_one({"action_token": token}, {"$set": {"status": "Resolved"}})
    return {"ok": True}


class ActionReplyBody(BaseModel):
    reply: str


@deploy_router.post("/req-action/{token}/reply")
async def req_action_reply(token: str, body: ActionReplyBody):
    from bson import ObjectId
    reply = (body.reply or "").strip()
    if not reply:
        raise HTTPException(400, "A reply is required.")
    c = await db.audit_room_comments.find_one({"action_token": token})
    if not c:
        raise HTTPException(404, "Invalid action link.")
    if _action_expired(c):
        raise HTTPException(410, "This action link has expired.")
    await db.audit_room_comments.update_one(
        {"action_token": token},
        {"$set": {"reply": reply[:2000], "reply_by": "Slack/Teams action", "reply_at": _now_iso(), "status": "Resolved"}})
    try:
        em = c.get("author_email") or ""
        if em and "@" in em:
            from kernel import notifications
            org = await db.organizations.find_one({"_id": ObjectId(c["org_id"])}) or {}
            oname = org.get("name") or "the organization"
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#0f1e3d'>Reply to your audit comment</h2>"
                    f"<p>The SAP access governance team at <strong>{_esc_html(oname)}</strong> replied:</p>"
                    f"<blockquote style='border-left:3px solid #2f6df6;margin:0;padding:6px 14px;color:#374151'>{_esc_html(reply[:1000])}</blockquote>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — Audit Room</p></div>")
            await notifications.send_email(em, f"Reply to your audit comment — {oname}", html)
    except Exception:
        pass
    return {"ok": True}


async def _run_audit_room_expiry_reminders(within_days: int = 3):
    """Folded into the daily cron: email admins/execs a few days before each Audit Room link expires."""
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    from kernel import notifications
    now = datetime.now(timezone.utc)
    horizon = (now + timedelta(days=within_days)).isoformat()
    nowiso = now.isoformat()
    rooms = await db.audit_rooms.find({"expires_at": {"$gt": nowiso, "$lte": horizon}}).to_list(1000)
    for room in rooms:
        try:
            token = room["token"]
            if room.get("expiry_reminder_sent"):
                continue
            org_id = room["org_id"]
            exp = room.get("expires_at", "")
            days_left = max(0, (datetime.fromisoformat(exp) - now).days) if exp else 0
            org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
            oname = org.get("name") or "your organization"
            await notifications.create(org_id, "system", "Audit Room link expiring soon",
                                       f"An Audit Room for {oname} expires on {exp[:10]} ({days_left}d). Renew it to keep auditor access live.",
                                       ref="system-health", dedupe_key=f"room-expiry:{token}")
            recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                         {"_id": 0, "email": 1}).to_list(200)
            link = (os.environ.get("FRONTEND_URL", "").rstrip("/")) + "/app/system-health"
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#b45309'>Audit Room link expiring soon</h2>"
                    f"<p>An external auditor Audit Room for <strong>{_esc_html(oname)}</strong> expires on "
                    f"<strong>{exp[:10]}</strong> — about {days_left} day(s) away.</p>"
                    f"<p style='margin:18px 0'><a href='{link}' style='background:#2f6df6;color:#fff;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:600' target='_blank'>Open System Health to renew</a></p>"
                    f"<p class='hint' style='font-size:12px;color:#6b7280'>In the <strong>Shared Access Links</strong> panel, click <strong>Renew</strong> on the room to extend it in one click — so your audit doesn't stall on a dead link.</p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — System Health · Audit Room</p></div>")
            for rr in recips:
                try:
                    await notifications.send_email(rr["email"], "Audit Room link expiring soon — Obserra SAP UAC", html)
                except Exception:
                    pass
            await db.audit_rooms.update_one({"token": token}, {"$set": {"expiry_reminder_sent": nowiso}})
        except Exception:
            pass


async def _run_overdue_request_digest(sla_hours: int | None = None):
    """Folded into the daily cron: email + Slack/Teams a summary of auditor requests open past their CONFIGURED SLA (org-wide target with per-room overrides)."""
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId
    from kernel import notifications
    import secrets as _secrets
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    rows = await db.audit_room_comments.find(
        {"status": {"$ne": "Resolved"}}, {"_id": 0}).to_list(5000)
    by_org = {}
    for r in rows:
        by_org.setdefault(r["org_id"], []).append(r)

    def _hours(iso):
        try:
            return (now - datetime.fromisoformat(iso)).total_seconds() / 3600
        except Exception:
            return 0.0

    def _age(h):
        return f"{int(h // 24)}d" if h >= 24 else f"{int(h)}h"

    for org_id, all_items in by_org.items():
        try:
            org = await db.organizations.find_one({"_id": ObjectId(org_id)}) or {}
            sched = _digest_schedule_cfg(org)
            if not sched["enabled"] or now.weekday() not in sched["days"]:
                continue
            base, smap = await _sla_map(org_id, org)
            items = []
            for x in all_items:
                sla = smap.get(x.get("token"), base)
                age = _hours(x.get("at", ""))
                if age >= sla:
                    x["_age_h"], x["_sla"] = age, sla
                    items.append(x)
            if not items:
                continue
            if ((org.get("system_health") or {}).get("overdue_digest_date")) == today:
                continue
            oname = org.get("name") or "your organization"
            items.sort(key=lambda x: x.get("at", ""))
            li = "".join(
                f"<li><strong>{_esc_html(x.get('author', 'Auditor'))}</strong> — waiting {_age(x['_age_h'])} "
                f"(SLA {x['_sla']}h) · <span style='color:#6b7280'>{_esc_html((x.get('comment') or '')[:120])}</span></li>"
                for x in items[:20])
            link = (os.environ.get("FRONTEND_URL", "").rstrip("/")) + "/app/system-health"
            html = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                    f"<h2 style='color:#b45309'>{len(items)} auditor request(s) past SLA</h2>"
                    f"<p>These auditor requests for <strong>{_esc_html(oname)}</strong> have been open past their SLA target (org default {base}h, with per-room overrides):</p>"
                    f"<ul>{li}</ul>"
                    f"<p style='margin:16px 0'><a href='{link}' style='background:#2f6df6;color:#fff;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:600' target='_blank'>Open the Audit Requests inbox</a></p>"
                    f"<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — System Health · Audit Requests</p></div>")
            recips = await db.users.find({"org_id": org_id, "role": {"$in": ["admin", "executive"]}},
                                         {"_id": 0, "email": 1}).to_list(200)
            for rr in recips:
                try:
                    await notifications.send_email(rr["email"], f"{len(items)} audit request(s) past SLA — Obserra SAP UAC", html)
                except Exception:
                    pass
            try:
                base_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
                slines = []
                for x in items[:10]:
                    cid = x.get("id")
                    if not cid:
                        continue
                    tok = x.get("action_token")
                    if not tok or _action_expired(x):
                        tok = _secrets.token_urlsafe(16)
                        exp = (now + timedelta(days=_ACTION_TTL_DAYS)).isoformat()
                        await db.audit_room_comments.update_one(
                            {"id": cid, "org_id": org_id},
                            {"$set": {"action_token": tok, "action_expires_at": exp}})
                    slines.append(
                        f"• {x.get('author', 'Auditor')} — waiting {_age(x['_age_h'])} (SLA {x['_sla']}h): {(x.get('comment') or '')[:90]}\n"
                        f"   Resolve/reply (link expires in {_ACTION_TTL_DAYS}d): {base_url}/api/deploy/req-action/{tok}")
                if slines:
                    body = (f"{len(items)} auditor request(s) are open past their SLA target:\n"
                            + "\n".join(slines) + "\n\nOr open System Health → Audit Requests.")
                    await _route_alert(org, {"slack": True, "teams": True}, f"⚠ {len(items)} audit request(s) past SLA", body)
            except Exception:
                pass
            try:
                esc = _escalation_cfg(org)
                if esc["enabled"] and esc["contacts"]:
                    crit = [x for x in items
                            if x["_age_h"] >= x["_sla"] * esc["multiplier"] and not x.get("escalated_at")]
                    if crit:
                        eli = "".join(
                            f"<li><strong>{_esc_html(x.get('author', 'Auditor'))}</strong> — waiting {_age(x['_age_h'])} "
                            f"(≥{esc['multiplier']:g}× the {x['_sla']}h SLA) · "
                            f"<span style='color:#6b7280'>{_esc_html((x.get('comment') or '')[:120])}</span></li>"
                            for x in crit[:20])
                        ehtml = (f"<div style='font:400 14px Arial;color:#1f2937;max-width:560px;margin:auto'>"
                                 f"<h2 style='color:#b91c1c'>Escalation — {len(crit)} audit request(s) far past SLA</h2>"
                                 f"<p>The following auditor request(s) for <strong>{_esc_html(oname)}</strong> have blown past "
                                 f"{esc['multiplier']:g}× their SLA target and need an owner's attention:</p>"
                                 f"<ul>{eli}</ul>"
                                 f"<p style='margin:16px 0'><a href='{link}' style='background:#b91c1c;color:#fff;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:600' target='_blank'>Open the Audit Requests inbox</a></p>"
                                 f"<p style='font-size:11px;color:#9ca3af'>Obserra SAP UAC — System Health · SLA escalation</p></div>")
                        for to in esc["contacts"]:
                            try:
                                await notifications.send_email(to, f"Escalation: {len(crit)} audit request(s) far past SLA — {oname}", ehtml)
                            except Exception:
                                pass
                        try:
                            ebody = (f"⚠ {len(crit)} auditor request(s) for {oname} are ≥{esc['multiplier']:g}× past SLA and need an owner:\n"
                                     + "\n".join(f"• {x.get('author', 'Auditor')} — waiting {_age(x['_age_h'])} (SLA {x['_sla']}h): {(x.get('comment') or '')[:90]}" for x in crit[:10]))
                            await _route_alert(org, {"slack": True, "teams": True}, f"⚠ SLA escalation — {len(crit)} request(s)", ebody)
                        except Exception:
                            pass
                        ids = [x["id"] for x in crit if x.get("id")]
                        if ids:
                            await db.audit_room_comments.update_many(
                                {"org_id": org_id, "id": {"$in": ids}},
                                {"$set": {"escalated_at": now.isoformat()}})
            except Exception:
                pass
            await notifications.create(org_id, "system", "Audit requests past SLA",
                                       f"{len(items)} auditor request(s) are open past their SLA target.",
                                       ref="system-health", dedupe_key=f"overdue-req:{today}")
            await db.organizations.update_one({"_id": ObjectId(org_id)},
                                              {"$set": {"system_health.overdue_digest_date": today}})
        except Exception:
            pass
