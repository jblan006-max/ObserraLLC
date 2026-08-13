"""Iteration 160 - CRA Risk Correlation new features:
- Risk Acceptance & Waivers (POST/DELETE /api/cra/risk-waiver)
- Owner Reassignment Bulk (POST /api/cra/risk-owner/bulk)
- Board Risk Memo (GET /api/cra/risk-memo)
- Digest Preview (GET /api/cra/risk-owner-digest/preview)
- Burndown on public link (GET /api/cra-public/exec-overview/{token})
"""
import os, time, pytest, requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["FRONTEND_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return s


# ---- Risk Correlation baseline ----

def test_risk_correlation_health(admin):
    r = admin.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "overall" in data
    assert "risks" in data
    assert isinstance(data["risks"], list)
    assert "waived" in data
    print(f"Active risks={len(data['risks'])} idx={data['overall'].get('index')} waived_count={data['overall'].get('waived_count')}")


# ---- Board Risk Memo ----

def test_risk_memo(admin):
    r = admin.get(f"{BASE_URL}/api/cra/risk-memo", timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "memo" in data and isinstance(data["memo"], str) and len(data["memo"]) > 20
    assert "facts" in data
    assert "generated_at" in data
    # Should mention index or target somewhere per grounding
    txt = data["memo"].lower()
    assert ("index" in txt) or ("target" in txt) or ("risk" in txt)
    print("MEMO:", data["memo"][:200])


# ---- Digest Preview ----

def test_digest_preview_owners(admin):
    r = admin.get(f"{BASE_URL}/api/cra/risk-owner-digest/preview", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "owners" in data
    assert isinstance(data["owners"], list)
    print("Owners:", data["owners"])


def test_digest_preview_html(admin):
    r = admin.get(f"{BASE_URL}/api/cra/risk-owner-digest/preview", timeout=30)
    owners = r.json().get("owners") or []
    if not owners:
        pytest.skip("no owners")
    email = owners[0]["email"]
    r2 = admin.get(f"{BASE_URL}/api/cra/risk-owner-digest/preview",
                   params={"owner_email": email}, timeout=30)
    assert r2.status_code == 200
    data = r2.json()
    assert "html" in data
    assert "<" in data["html"]  # html-ish


# ---- Waiver: accept -> active decreases -> revoke -> restored ----

def test_waiver_lifecycle(admin):
    r = admin.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30).json()
    active_before = len(r["risks"])
    idx_before = r["overall"].get("index")
    assert active_before > 0
    target_risk = r["risks"][0]
    key = target_risk["key"]

    # Accept/Waive
    w = admin.post(f"{BASE_URL}/api/cra/risk-waiver",
                   json={"risk_key": key, "risk_title": target_risk.get("title", ""),
                         "reason": "TEST_iter160 accepted risk", "expires": "2026-12-31"},
                   timeout=30)
    assert w.status_code in (200, 201), w.text

    r2 = admin.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30).json()
    active_after = len(r2["risks"])
    idx_after = r2["overall"].get("index")
    waived_count = r2["overall"].get("waived_count", 0)
    keys_after = {x["key"] for x in r2["risks"]}
    assert key not in keys_after, "waived risk still active"
    assert active_after == active_before - 1
    assert waived_count >= 1
    # index should decrease or stay same (never increase)
    if idx_before is not None and idx_after is not None:
        assert idx_after <= idx_before

    # waived section
    waived = r2.get("waived") or []
    assert any(x["key"] == key for x in waived)
    match = next(x for x in waived if x["key"] == key)
    assert "waiver" in match
    assert "reason" in match["waiver"]

    # Revoke
    d = admin.delete(f"{BASE_URL}/api/cra/risk-waiver/{key}", timeout=30)
    assert d.status_code in (200, 204), d.text

    r3 = admin.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30).json()
    assert len(r3["risks"]) == active_before
    assert key in {x["key"] for x in r3["risks"]}


# ---- Bulk owner reassign ----

def test_bulk_owner_reassign(admin):
    r = admin.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30).json()
    if len(r["risks"]) < 2:
        pytest.skip("need >=2 risks")
    keys = [r["risks"][0]["key"], r["risks"][1]["key"]]
    # capture original owners
    original = {x["key"]: (x.get("owner"), x.get("owner_email"), x.get("due_date")) for x in r["risks"] if x["key"] in keys}

    payload = {"keys": keys, "owner": "TEST_BulkOwner", "owner_email": "bulk@test.local"}
    b = admin.post(f"{BASE_URL}/api/cra/risk-owner/bulk", json=payload, timeout=30)
    assert b.status_code == 200, b.text

    r2 = admin.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30).json()
    got = {x["key"]: x for x in r2["risks"] if x["key"] in keys}
    for k in keys:
        assert got[k].get("owner") == "TEST_BulkOwner", f"{k} not updated: {got[k].get('owner')}"

    # Restore originals to avoid polluting demo (Dana Ruiz / Ops Team must be preserved)
    for k, (own, mail, due) in original.items():
        admin.post(f"{BASE_URL}/api/cra/risk-owner/bulk",
                   json={"keys": [k], "owner": own or "", "owner_email": mail or "", "due_date": due or ""},
                   timeout=30)


def test_bulk_shift_days(admin):
    r = admin.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30).json()
    if not r["risks"]:
        pytest.skip("no risks")
    k = r["risks"][0]["key"]
    before_due = r["risks"][0].get("due_date")
    resp = admin.post(f"{BASE_URL}/api/cra/risk-owner/bulk",
                      json={"keys": [k], "shift_days": 7}, timeout=30)
    assert resp.status_code == 200, resp.text
    r2 = admin.get(f"{BASE_URL}/api/cra/risk-correlation", timeout=30).json()
    after_due = next(x for x in r2["risks"] if x["key"] == k).get("due_date")
    print(f"due before={before_due} after={after_due}")
    # if there was a due date, it should have shifted
    if before_due:
        assert after_due != before_due
        # shift back
        admin.post(f"{BASE_URL}/api/cra/risk-owner/bulk",
                   json={"keys": [k], "shift_days": -7}, timeout=30)


# ---- Public exec overview burndown ----

def test_public_exec_overview_burndown(admin):
    # Mint a share link
    r = admin.post(f"{BASE_URL}/api/cra/exec-overview-link", timeout=30)
    assert r.status_code in (200, 201), f"share mint failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("share_token") or r.json().get("url","").split("/")[-1]
    assert tok, r.text

    # Public GET (no auth)
    anon = requests.Session()
    p = anon.get(f"{BASE_URL}/api/cra-public/exec-overview/{tok}", timeout=30)
    assert p.status_code == 200, p.text
    data = p.json()
    assert "burndown" in data, "burndown missing from public payload"
    b = data["burndown"]
    assert "target" in b
    # KNOWN BUG (reported to main agent): risk.top_risks in public payload leaks product names + owners.
    # Burndown itself is clean (target/current/gap only).
    for k in ("target", "current", "gap"):
        assert k in b
    print("burndown:", b)


# ---- Auth guard on admin endpoints ----

def test_waiver_requires_auth():
    anon = requests.Session()
    r = anon.post(f"{BASE_URL}/api/cra/risk-waiver",
                  json={"risk_key": "rk_test", "reason": "x", "expires": "2026-12-31"}, timeout=30)
    assert r.status_code in (401, 403)


def test_bulk_requires_auth():
    anon = requests.Session()
    r = anon.post(f"{BASE_URL}/api/cra/risk-owner/bulk",
                  json={"keys": ["rk_test"], "owner": "x"}, timeout=30)
    assert r.status_code in (401, 403)


def test_memo_requires_auth():
    anon = requests.Session()
    r = anon.get(f"{BASE_URL}/api/cra/risk-memo", timeout=30)
    assert r.status_code in (401, 403)
