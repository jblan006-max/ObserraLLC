import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Calendar, CheckCircle2, Clock, Copy, Database, DoorOpen, Download, Eye, FileText, Globe, Loader2, MessageSquare, Paperclip, PlayCircle, Plus, RefreshCw, Send, Settings2, ShieldCheck, Terminal, Trash2, X, XCircle, Zap } from "lucide-react";
import { WorldMapThumb } from "./WorldMapThumb";
import { toast } from "sonner";
import { DataClassBadge, Panel } from "@/components/agentic-ai/shared";
import { useDeepDive } from "@/context/DeepDiveContext";
import { api } from "@/lib/api";
import { Link, useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { LineChart, Line, ResponsiveContainer, Tooltip as RTooltip } from "recharts";

const SOURCE_LABEL = { agents: "AI Agent Governance", analytics: "AI Analytics", systems: "AI System Inventory", incidents: "AI Incidents", workflows: "Workflow Engine", connectorHealth: "Connector Health" };
const fmtDT = (s) => (s ? new Date(s).toLocaleDateString(undefined, { dateStyle: "medium" }) : "—");
const fmtDTT = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const copyText = async (t) => { try { await navigator.clipboard.writeText(t); toast.success("Copied"); } catch { toast.error("Copy failed"); } };
const BACKEND = process.env.REACT_APP_BACKEND_URL;
const RATING_PILL = { Critical: "bg-crit/15 text-crit", High: "bg-high/15 text-high", Medium: "bg-med/15 text-med", Low: "bg-low/10 text-low" };

// Obserra-standard deep-dive for an external auditor room — sharing-risk rating + score, live
// readiness facets, and AI recommendations/fixes (grounded in the room's frozen evidence snapshot).
function roomDeepDive(room) {
  const r = room.readiness || {};
  const openOnly = Math.max(0, (r.open_questions || 0) - (r.overdue_questions || 0));
  const recs = [];
  if (r.toxic_active > 0) recs.push(`${r.toxic_active} toxic agent(s) are still active in this shared evidence pack — Suspend or Kill them from the Toxicity Map before external auditors review.`);
  if (r.overdue_questions > 0) recs.push(`${r.overdue_questions} auditor question(s) are past their SLA — reply now to avoid an audit gap.`);
  if (openOnly > 0) recs.push(`${openOnly} open auditor question(s) awaiting a first reply.`);
  if (!room.expired && r.days_left != null && r.days_left <= 2) recs.push(`This room expires in ${r.days_left} day(s) — Renew it if the audit is ongoing.`);
  if (room.expired) recs.push("This room link has expired — Renew to restore auditor access, or Revoke to close it out.");
  if (!recs.length) recs.push("Evidence pack is clean and signed — ready to share. Keep the room fresh with a periodic Renew and answer any auditor questions within SLA.");
  return {
    accent: "190 90% 55%",
    refLabel: "AUDITOR ROOM",
    title: `Auditor room readiness${r.org_name ? ` · ${r.org_name}` : ""}`,
    rating: r.rating,
    score: r.risk_score,
    facets: [
      { label: "Sharing risk", value: `${r.rating || "Low"} · ${r.risk_score ?? 0}/100` },
      { label: "Toxic agents active", value: r.toxic_active ?? 0 },
      { label: "Governed agents", value: r.agents ?? 0 },
      { label: "Agents killed", value: r.killed ?? 0 },
      { label: "Enforcement events", value: r.events ?? 0 },
      { label: "Open questions", value: r.open_questions ?? 0 },
      { label: "Overdue questions", value: r.overdue_questions ?? 0 },
      { label: "Link expires", value: room.expired ? "expired" : (r.days_left != null ? `${r.days_left} day(s)` : fmtDT(room.expires_at)) },
      { label: "Opens · downloads", value: `${room.opens || 0} · ${room.downloads || 0}` },
      { label: "Weekly subscribers", value: r.subscribers ?? 0 },
    ],
    complianceRefs: ["NIST AI RMF", "ISO 42001", "SOC 2", "EU AI Act"],
    recommendedActions: recs,
    explainTitle: "External auditor room readiness",
    explainKind: "auditor evidence room readiness ai governance defensibility",
    explainContext: { url: room.url, expires_at: room.expires_at, expired: room.expired, ...r },
  };
}

function DigestPreviewModal({ onClose }) {
  const [data, setData] = useState(null);
  const [sending, setSending] = useState(false);
  useEffect(() => { api.get("/agents/runtime/board-evidence-digest/preview").then(({ data }) => setData(data)).catch((e) => toast.error(e.response?.data?.detail || "Preview failed")); }, []);
  const send = async () => {
    setSending(true);
    try { const { data } = await api.post("/agents/runtime/board-evidence-digest/send"); toast.success(data.sent ? `Digest emailed to ${data.sent} recipient(s).` : "No recipients found."); onClose(); }
    catch (e) { toast.error(e.response?.data?.detail || "Send failed."); }
    finally { setSending(false); }
  };
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" data-testid="digest-preview-modal" onClick={onClose}>
      <div className="w-full max-w-2xl max-h-[88vh] overflow-y-auto rounded-2xl border border-border bg-card shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border sticky top-0 bg-card">
          <div className="flex items-center gap-2"><FileText className="w-4 h-4 text-ai" /><span className="font-head font-bold">Board digest preview</span></div>
          <button data-testid="digest-preview-close" onClick={onClose} className="p-1.5 rounded-md hover:bg-secondary"><X className="w-4 h-4" /></button>
        </div>
        {!data ? (
          <div className="p-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-ai" /></div>
        ) : (
          <div className="p-5 space-y-4">
            <div className="text-xs text-muted-foreground">Subject: <span className="text-foreground font-medium">{data.subject}</span></div>
            <div data-testid="digest-preview-recipients" className="text-xs">
              <span className="text-muted-foreground">Recipients: </span>
              {(data.recipients || []).length ? data.recipients.join(", ") : <span className="text-high">none configured (falls back to admins & execs)</span>}
            </div>
            <div className="rounded-lg border border-border bg-white p-3 max-h-[42vh] overflow-y-auto" data-testid="digest-preview-body" dangerouslySetInnerHTML={{ __html: data.html }} />
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <a data-testid="digest-preview-pdf" href={`${BACKEND}/api/agents/runtime/board-evidence-digest/preview.pdf`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-head font-bold hover:bg-secondary transition-colors"><FileText className="w-3.5 h-3.5" /> View attached PDF</a>
              <button data-testid="digest-preview-send" onClick={send} disabled={sending} className="ml-auto inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Send now</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AccessLog({ token, endpoint, exportBase }) {
  const [log, setLog] = useState(null);
  useEffect(() => { api.get(endpoint || `/agents/runtime/evidence-room/${token}/access-log`).then(({ data }) => setLog(data)).catch(() => setLog({ access: [] })); }, [token, endpoint]);
  if (!log) return <div className="p-3 flex justify-center"><Loader2 className="w-4 h-4 animate-spin text-ai" /></div>;
  const base = process.env.REACT_APP_BACKEND_URL;
  const geoPts = (log.access || []).filter((a) => typeof a.geo_lat === "number" && typeof a.geo_lon === "number").map((a) => ({ lat: a.geo_lat, lon: a.geo_lon, kind: a.kind, anomaly: a.anomaly, label: `${a.kind === "download" ? (a.who || "download") : "opened"}${a.geo ? " · " + a.geo : ""}${a.device ? " · " + a.device : ""}` }));
  return (
    <div className="mt-2 rounded-lg border border-border bg-background/40 p-2.5" data-testid={`access-log-${token}`}>
      <div className="flex items-center gap-2 mb-1.5">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Chain of custody — {log.opens} open(s) · {log.downloads} download(s)</div>
        {exportBase && (
          <div className="ml-auto flex items-center gap-1.5">
            <a data-testid={`access-log-csv-${token}`} href={`${base}/api${exportBase}.csv`} className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-border text-[10px] hover:bg-secondary transition-colors"><Download className="w-3 h-3" /> CSV</a>
            <a data-testid={`access-log-pdf-${token}`} href={`${base}/api${exportBase}.pdf`} className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-border text-[10px] hover:bg-secondary transition-colors"><FileText className="w-3 h-3" /> PDF</a>
          </div>
        )}
      </div>
      {geoPts.length > 0 && <div className="mb-2" data-testid={`access-log-map-wrap-${token}`}><WorldMapThumb points={geoPts} /></div>}
      {(!log.access || log.access.length === 0) ? (
        <div className="text-xs text-muted-foreground">No access recorded yet.</div>
      ) : (
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {log.access.map((a, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              {a.kind === "download" ? <Download className="w-3 h-3 text-ai shrink-0" /> : <Eye className="w-3 h-3 text-muted-foreground shrink-0" />}
              <span className="font-medium">{a.kind === "download" ? (a.who || "download") : "opened"}</span>
              {a.anomaly && <span data-testid={`access-anomaly-${i}`} className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-crit/15 text-crit"><AlertTriangle className="w-3 h-3" /> {a.anomaly_reason || "unusual"}</span>}
              {a.geo && <span className="text-muted-foreground">{a.geo}</span>}
              {a.device && <span className="text-muted-foreground">· {a.device}</span>}
              {a.ip && <span className="text-muted-foreground/60 font-mono text-[10px]">{a.ip}</span>}
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">{fmtDTT(a.at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AuditorRoomCard() {
  const [rooms, setRooms] = useState([]);
  const [busy, setBusy] = useState(false);
  const [latest, setLatest] = useState(null);
  const [logOpen, setLogOpen] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [poc, setPoc] = useState(null);
  const [pocBusy, setPocBusy] = useState(false);
  const { openDeepDive } = useDeepDive();
  const load = () => api.get("/agents/runtime/evidence-rooms").then(({ data }) => setRooms(data.rooms || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/agents/runtime/evidence-room", { days: 14 });
      setLatest(data);
      try { await navigator.clipboard.writeText(data.url); toast.success("Auditor room link created & copied"); } catch { toast.success("Auditor room link created"); }
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not create auditor room."); }
    finally { setBusy(false); }
  };
  const revoke = async (token) => {
    if (!window.confirm("Revoke this auditor room link? External auditors will lose access immediately.")) return;
    try { await api.post("/agents/runtime/evidence-room/revoke", { token }); if (latest?.token === token) setLatest(null); toast.success("Auditor room revoked"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Revoke failed."); }
  };
  const renew = async (token) => {
    try { const { data } = await api.post("/agents/runtime/evidence-room/renew", { token, days: 14 }); toast.success(`Renewed — now expires ${fmtDT(data.expires_at)}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Renew failed."); }
  };
  const runPoc = async () => {
    setPocBusy(true);
    try {
      const { data } = await api.post("/agents/runtime/proof-of-control");
      setPoc(data);
      try { await navigator.clipboard.writeText(data.url); } catch { /* ignore */ }
      toast.success(data.controlled ? "Proof-of-Control confirmed — link created & copied." : "Link created, but the runtime did not confirm control.");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not create the Proof-of-Control link. Enable the Live Enforcement Simulator or wire a runtime webhook first."); }
    finally { setPocBusy(false); }
  };

  return (
    <>
      {showPreview && <DigestPreviewModal onClose={() => setShowPreview(false)} />}
      <Panel
        title="Read-only Auditor Room"
        subtitle="Generate an expiring, no-login link for external auditors to view the live AI Enforcement Evidence Pack, download a watermarked signed PDF (org logo + QR back to this room), and ask questions. Every open & download is logged for chain of custody."
        testid="agentic-auditor-room"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button data-testid="digest-preview-btn" onClick={() => setShowPreview(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors"><FileText className="w-3.5 h-3.5" /> Preview &amp; send board digest</button>
            <button data-testid="proof-of-control-btn" onClick={runPoc} disabled={pocBusy} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors disabled:opacity-50">{pocBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />} Board Proof-of-Control</button>
            <button data-testid="auditor-room-create-btn" onClick={create} disabled={busy} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Create auditor room</button>
          </div>
        }
      >
        {poc && (
          <div data-testid="proof-of-control-result" className={`mb-4 rounded-lg border p-3 ${poc.controlled ? "border-low/30 bg-low/5" : "border-crit/30 bg-crit/5"}`}>
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider mb-1.5">
              {poc.controlled ? <ShieldCheck className="w-3 h-3 text-low" /> : <XCircle className="w-3 h-3 text-crit" />}
              <span className={poc.controlled ? "text-low" : "text-crit"}>{poc.controlled ? "Control confirmed" : "Control not confirmed"} · fresh signed receipt · HTTP {poc.receipt?.status_code || "—"} · {poc.receipt?.latency_ms}ms · {poc.receipt?.signed ? "signed" : "unsigned"}</span>
            </div>
            <p className="text-[11px] text-muted-foreground mb-2">One auditor link bundling this fresh kill-switch receipt with the sealed AI Enforcement Evidence Pack. Share it with your board.</p>
            <div className="flex items-center gap-2">
              <input readOnly data-testid="proof-of-control-url" value={poc.url} onFocus={(e) => e.target.select()} className="flex-1 min-w-0 bg-secondary/50 rounded-md px-2.5 py-2 text-xs font-mono outline-none" />
              <button data-testid="proof-of-control-copy" onClick={() => copyText(poc.url)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors shrink-0"><Copy className="w-3.5 h-3.5" /> Copy</button>
            </div>
            <div className="mt-3 flex items-center gap-3" data-testid="proof-of-control-qr">
              <div className="bg-white p-2 rounded-lg shrink-0"><QRCodeSVG value={poc.url} size={92} level="M" /></div>
              <div className="text-[11px] text-muted-foreground">Scan to open the auditor room — drop this QR straight into your board deck.</div>
            </div>
          </div>
        )}
        {latest && (
          <div data-testid="auditor-room-latest" className="mb-4 rounded-lg border border-ai/30 bg-ai/5 p-3">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-ai mb-1.5"><DoorOpen className="w-3 h-3" /> New link — share with your auditor · expires {fmtDT(latest.expires_at)}</div>
            <div className="flex items-center gap-2">
              <input readOnly data-testid="auditor-room-latest-url" value={latest.url} onFocus={(e) => e.target.select()} className="flex-1 min-w-0 bg-secondary/50 rounded-md px-2.5 py-2 text-xs font-mono outline-none" />
              <button data-testid="auditor-room-latest-copy" onClick={() => copyText(latest.url)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors shrink-0"><Copy className="w-3.5 h-3.5" /> Copy</button>
            </div>
          </div>
        )}
        {rooms.length === 0 ? (
          <div className="text-sm text-muted-foreground" data-testid="auditor-room-empty">No active auditor rooms. Create one to share a read-only evidence link with an external auditor.</div>
        ) : (
          <div className="space-y-2" data-testid="auditor-room-list">
            {rooms.map((room) => (
              <div key={room.token} data-testid={`auditor-room-${room.token}`} className="rounded-lg border border-border bg-secondary/20 px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <DoorOpen className={`w-4 h-4 shrink-0 ${room.expired ? "text-muted-foreground" : "text-ai"}`} />
                  <span className="font-mono text-xs truncate max-w-[32%]">{room.url}</span>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${room.expired ? "bg-crit/10 text-crit" : "bg-low/10 text-low"}`}>{room.expired ? "expired" : `expires ${fmtDT(room.expires_at)}`}</span>
                  {room.readiness && <span data-testid={`auditor-room-readiness-pill-${room.token}`} className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${RATING_PILL[room.readiness.rating] || "bg-low/10 text-low"}`}>{room.readiness.rating} {room.readiness.risk_score}</span>}
                  <span className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1"><Eye className="w-3 h-3" /> {room.opens}</span>
                  <span className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1"><Download className="w-3 h-3" /> {room.downloads || 0}</span>
                  <div className="ml-auto flex items-center gap-1.5">
                    <button data-testid={`auditor-room-readiness-${room.token}`} onClick={() => openDeepDive(roomDeepDive(room))} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-ai/30 text-ai text-xs hover:bg-ai/10 transition-colors"><ShieldCheck className="w-3 h-3" /> Readiness</button>
                    <button data-testid={`auditor-room-log-${room.token}`} onClick={() => setLogOpen(logOpen === room.token ? null : room.token)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"><Activity className="w-3 h-3" /> Log</button>
                    <button data-testid={`auditor-room-renew-${room.token}`} onClick={() => renew(room.token)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"><RefreshCw className="w-3 h-3" /> Renew</button>
                    <button data-testid={`auditor-room-copy-${room.token}`} onClick={() => copyText(room.url)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"><Copy className="w-3 h-3" /> Copy</button>
                    <button data-testid={`auditor-room-revoke-${room.token}`} onClick={() => revoke(room.token)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-crit/30 text-crit text-xs hover:bg-crit/10 transition-colors"><Trash2 className="w-3 h-3" /> Revoke</button>
                  </div>
                </div>
                {logOpen === room.token && <AccessLog token={room.token} />}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </>
  );
}

const PRIORITY_TONE = { urgent: "bg-crit/15 text-crit", high: "bg-high/15 text-high", normal: "bg-secondary/60 text-muted-foreground", low: "bg-ai/10 text-ai" };

// Share Center — every shared detail-card link with live view/download counts, a Board-digest attach
// toggle, copy/open, and one-click Revoke. Mirrors the Auditor Room manager; polls for live engagement.
function ShareCenterCard() {
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [logOpen, setLogOpen] = useState(null);
  const load = () => api.get("/agents/runtime/card-shares").then(({ data }) => setCards(data.cards || [])).catch(() => {}).finally(() => setLoading(false));
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, []);
  const revoke = async (token) => {
    if (!window.confirm("Revoke this shared card link? Anyone with the link will lose access immediately.")) return;
    try { await api.post("/agents/runtime/card-share/revoke", { token }); toast.success("Shared card revoked"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Revoke failed."); }
  };
  const renew = async (token) => {
    try { const { data } = await api.post("/agents/runtime/card-share/renew", { token, days: 14 }); toast.success(`Renewed — now expires ${fmtDT(data.expires_at)}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Renew failed."); }
  };
  const toggleAttach = async (card) => {
    try { await api.post("/agents/runtime/card-share/attach", { token: card.token, attach: !card.attach_to_board }); toast.success(!card.attach_to_board ? "Card will ride along with the board digest" : "Card removed from the board digest"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Update failed."); }
  };
  return (
    <Panel title="Share Center" subtitle="Every shared detail-card link — live view & download counts, chain-of-custody access log, Renew/Revoke, and a toggle to attach any card to the monthly Board Evidence Digest email." testid="agentic-share-center"
      actions={<button data-testid="share-center-refresh" onClick={load} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-head font-bold hover:bg-secondary transition-colors"><RefreshCw className="w-3.5 h-3.5" /> Refresh</button>}>
      {loading && cards.length === 0 ? (
        <div className="py-6 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-ai" /></div>
      ) : cards.length === 0 ? (
        <div className="text-sm text-muted-foreground" data-testid="share-center-empty">No shared cards yet. Open any detail card and click “Share this card” to mint an expiring, watermarked auditor link.</div>
      ) : (
        <div className="space-y-2" data-testid="share-center-list">
          {cards.map((card) => (
            <div key={card.token} data-testid={`share-card-${card.token}`} className="rounded-lg border border-border bg-secondary/20 px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <FileText className={`w-4 h-4 shrink-0 ${card.expired ? "text-muted-foreground" : "text-ai"}`} />
                <span className="font-head font-bold text-sm truncate max-w-[22%]">{card.title}</span>
                {card.ref && <span className="font-mono text-[10px] text-muted-foreground">{card.ref}</span>}
                {card.rating && <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${RATING_PILL[card.rating] || "bg-low/10 text-low"}`}>{card.rating}</span>}
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${card.expired ? "bg-crit/10 text-crit" : "bg-low/10 text-low"}`}>{card.expired ? "expired" : `expires ${fmtDT(card.expires_at)}`}</span>
                <span data-testid={`share-card-opens-${card.token}`} className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1"><Eye className="w-3 h-3" /> {card.opens} viewed</span>
                <span data-testid={`share-card-downloads-${card.token}`} className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1"><Download className="w-3 h-3" /> {card.downloads} downloaded</span>
                <div className="ml-auto flex items-center gap-1.5">
                  <button data-testid={`share-card-attach-${card.token}`} onClick={() => toggleAttach(card)} className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs transition-colors ${card.attach_to_board ? "border-ai/50 text-ai bg-ai/10" : "border-border hover:bg-secondary"}`}>{card.attach_to_board ? <CheckCircle2 className="w-3 h-3" /> : <Paperclip className="w-3 h-3" />} Board digest</button>
                  <button data-testid={`share-card-log-${card.token}`} onClick={() => setLogOpen(logOpen === card.token ? null : card.token)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"><Activity className="w-3 h-3" /> Log</button>
                  <button data-testid={`share-card-renew-${card.token}`} onClick={() => renew(card.token)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"><RefreshCw className="w-3 h-3" /> Renew</button>
                  <button data-testid={`share-card-copy-${card.token}`} onClick={() => copyText(card.url)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"><Copy className="w-3 h-3" /> Copy</button>
                  <a data-testid={`share-card-open-${card.token}`} href={card.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"><DoorOpen className="w-3 h-3" /> Open</a>
                  <button data-testid={`share-card-revoke-${card.token}`} onClick={() => revoke(card.token)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-crit/30 text-crit text-xs hover:bg-crit/10 transition-colors"><Trash2 className="w-3 h-3" /> Revoke</button>
                </div>
              </div>
              {logOpen === card.token && <AccessLog token={card.token} endpoint={`/agents/runtime/card-share/${card.token}/access-log`} exportBase={`/agents/runtime/card-share/${card.token}/access-log`} />}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function GovernanceSettingsCard() {
  const [s, setS] = useState(null);
  const [recips, setRecips] = useState("");
  const [oncall, setOncall] = useState("");
  const [trusted, setTrusted] = useState("");
  const [trustedIps, setTrustedIps] = useState("");
  const [tauds, setTauds] = useState("");
  const [alertEmails, setAlertEmails] = useState("");
  const [alertWebhook, setAlertWebhook] = useState("");
  const [snoozeHours, setSnoozeHours] = useState("24");
  const [snoozing, setSnoozing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [auditRecips, setAuditRecips] = useState("");
  const [snoozeStart, setSnoozeStart] = useState("");
  const [snoozeEnd, setSnoozeEnd] = useState("");
  const [testing, setTesting] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [snoozeReason, setSnoozeReason] = useState("");
  const [scheduleReason, setScheduleReason] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const hydrate = (data) => { setS(data); setRecips((data.board_digest_recipients || []).join(", ")); setOncall((data.auditor_oncall_rotation || []).join(", ")); setTrusted((data.trusted_countries || []).join(", ")); setTrustedIps((data.trusted_ip_ranges || []).join(", ")); setTauds((data.trusted_auditors || []).join(", ")); setAlertEmails((data.alert_channel_emails || []).join(", ")); setAlertWebhook(data.alert_channel_webhook || ""); setAuditRecips((data.audit_digest_recipients || []).join(", ")); };
  useEffect(() => { api.get("/agents/runtime/governance-settings").then(({ data }) => hydrate(data)).catch(() => {}); }, []);
  const doSnooze = async (hours) => {
    setSnoozing(true);
    try {
      const { data } = await api.post("/agents/runtime/alerts/snooze", { hours: Number(hours) || 0, reason: snoozeReason });
      setS((prev) => ({ ...prev, snooze_alerts_until: data.snooze_alerts_until || "", snooze_reason: data.snooze_reason || "" }));
      if (Number(hours) > 0) setSnoozeReason("");
      toast.success(Number(hours) > 0 ? `Instant alerts muted for ${hours}h` : "Instant alerts resumed");
    } catch (e) { toast.error(e.response?.data?.detail || "Snooze failed."); }
    finally { setSnoozing(false); }
  };
  const doTest = async () => {
    setTesting(true);
    try {
      const { data } = await api.post("/agents/runtime/alerts/test", {});
      const parts = [];
      if (data.emails?.length) parts.push(`${data.emails.length} email(s)`);
      if (data.webhook) parts.push("webhook"); else if (data.chat_fallback) parts.push("org chat");
      toast.success(parts.length ? `Test alert sent to ${parts.join(" + ")}` : "Test alert dispatched (no channels configured)");
    } catch (e) { toast.error(e.response?.data?.detail || "Test failed."); }
    finally { setTesting(false); }
  };
  const doSchedule = async (clear) => {
    setScheduling(true);
    try {
      const body = clear ? { start: "", end: "" } : { start: snoozeStart ? new Date(snoozeStart).toISOString() : "", end: snoozeEnd ? new Date(snoozeEnd).toISOString() : "", reason: scheduleReason };
      const { data } = await api.post("/agents/runtime/alerts/snooze-schedule", body);
      setS((prev) => ({ ...prev, snooze_window_start: data.snooze_window_start || "", snooze_window_end: data.snooze_window_end || "", snooze_window_reason: data.snooze_window_reason || "" }));
      if (clear) { setSnoozeStart(""); setSnoozeEnd(""); setScheduleReason(""); }
      toast.success(clear ? "Scheduled mute window cleared" : "Mute window scheduled");
    } catch (e) { toast.error(e.response?.data?.detail || "Schedule failed."); }
    finally { setScheduling(false); }
  };
  const sendAuditDigest = async () => {
    try {
      const { data } = await api.post("/agents/runtime/audit-digest/send", {});
      toast.success(data.changes ? `Digest sent (${data.changes} change(s), ${data.sent} recipient(s))` : "No control changes in the last 7 days");
    } catch (e) { toast.error(e.response?.data?.detail || "Send failed."); }
  };
  const loadPreview = async () => {
    if (previewOpen) { setPreviewOpen(false); return; }
    setPreviewOpen(true); setPreviewData(null);
    try {
      const { data } = await api.get("/agents/runtime/audit-digest/preview");
      setPreviewData(data);
    } catch (e) { toast.error("Could not load preview."); setPreviewOpen(false); }
  };
  const downloadDigestPdf = async () => {
    try {
      const { data } = await api.get("/agents/runtime/audit-digest.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url; a.download = "obserra-control-change-digest.pdf";
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success("Digest PDF downloaded");
    } catch (e) { toast.error("Could not download PDF."); }
  };
  const emailCount = alertEmails.split(",").map((x) => x.trim()).filter(Boolean).length;
  const channelSummary = `${emailCount ? `${emailCount} email(s)` : "all admins & execs"} · ${alertWebhook.trim() ? (/hooks\.slack\.com/i.test(alertWebhook) ? "Slack ✓" : /office\.com|azure\.com/i.test(alertWebhook) ? "Teams ✓" : "webhook ✓") : "org chat"}`;
  if (!s) return null;
  const sbp = s.auditor_question_sla_by_priority || {};
  const setSbp = (k, v) => setS({ ...s, auditor_question_sla_by_priority: { ...sbp, [k]: v } });
  const saveAll = async () => {
    setSaving(true);
    try {
      const normal = Number(sbp.normal ?? s.auditor_question_sla_hours) || 48;
      const { data } = await api.put("/agents/runtime/governance-settings", {
        board_digest_day: Number(s.board_digest_day) || 1,
        board_digest_recipients: recips.split(",").map((x) => x.trim()).filter(Boolean),
        board_digest_enabled: !!s.board_digest_enabled,
        auditor_question_sla_hours: normal,
        auditor_question_escalation_to: s.auditor_question_escalation_to || "",
        auditor_question_sla_by_priority: {
          urgent: Number(sbp.urgent) || 4, high: Number(sbp.high) || 12, normal, low: Number(sbp.low) || 96,
        },
        auditor_question_escalation_multiplier: Number(s.auditor_question_escalation_multiplier) || 2,
        auditor_oncall_rotation: oncall.split(",").map((x) => x.trim()).filter(Boolean),
        card_engagement_cadence: s.card_engagement_cadence || "instant",
        trusted_countries: trusted.split(",").map((x) => x.trim()).filter(Boolean),
        trusted_ip_ranges: trustedIps.split(",").map((x) => x.trim()).filter(Boolean),
        trusted_auditors: tauds.split(",").map((x) => x.trim()).filter(Boolean),
        unusual_access_threshold: Number(s.unusual_access_threshold) || 1,
        instant_suspicious_alerts: !!s.instant_suspicious_alerts,
        alert_channel_emails: alertEmails.split(",").map((x) => x.trim()).filter(Boolean),
        alert_channel_webhook: alertWebhook.trim(),
        audit_digest_enabled: !!s.audit_digest_enabled,
        audit_digest_recipients: auditRecips.split(",").map((x) => x.trim()).filter(Boolean),
      });
      hydrate(data); toast.success("Governance settings saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed."); }
    finally { setSaving(false); }
  };
  const fld = "mt-1.5 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary";
  const lbl = "text-[11px] font-mono uppercase tracking-wider text-muted-foreground";
  return (
    <Panel title="Governance settings" subtitle="Board-digest schedule + recipients, per-priority auditor-question SLAs, an escalation multiplier, and a weekly on-call rotation for the second approver." testid="agentic-governance-settings"
      actions={<button data-testid="gov-save" onClick={saveAll} disabled={saving} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Settings2 className="w-3.5 h-3.5" />} Save</button>}>
      <div className="grid md:grid-cols-2 gap-4">
        <label className="block"><span className={lbl}>Board digest — day of month</span><input data-testid="gov-digest-day" type="number" min={1} max={28} value={s.board_digest_day} onChange={(e) => setS({ ...s, board_digest_day: e.target.value })} className={fld} /></label>
        <label className="block"><span className={lbl}>Escalation multiplier (× the SLA)</span><input data-testid="gov-escalation-mult" type="number" min={1} max={20} step="0.5" value={s.auditor_question_escalation_multiplier} onChange={(e) => setS({ ...s, auditor_question_escalation_multiplier: e.target.value })} className={fld} /></label>
      </div>
      <div className="mt-4">
        <span className={lbl}>Auditor-question SLA by priority (hours)</span>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-1.5">
          <label className="block"><span className="text-[10px] font-mono text-crit">URGENT</span><input data-testid="gov-sla-urgent" type="number" min={1} max={4320} value={sbp.urgent ?? 4} onChange={(e) => setSbp("urgent", e.target.value)} className={fld} /></label>
          <label className="block"><span className="text-[10px] font-mono text-high">HIGH</span><input data-testid="gov-sla-high" type="number" min={1} max={4320} value={sbp.high ?? 12} onChange={(e) => setSbp("high", e.target.value)} className={fld} /></label>
          <label className="block"><span className="text-[10px] font-mono text-muted-foreground">NORMAL</span><input data-testid="gov-sla-hours" type="number" min={1} max={4320} value={sbp.normal ?? s.auditor_question_sla_hours} onChange={(e) => setSbp("normal", e.target.value)} className={fld} /></label>
          <label className="block"><span className="text-[10px] font-mono text-ai">LOW</span><input data-testid="gov-sla-low" type="number" min={1} max={4320} value={sbp.low ?? 96} onChange={(e) => setSbp("low", e.target.value)} className={fld} /></label>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        <label className="block"><span className={lbl}>On-call rotation (comma-separated emails — rotates weekly)</span><input data-testid="gov-oncall" value={oncall} onChange={(e) => setOncall(e.target.value)} placeholder="ciso@company.com, deputy@company.com" className={fld} /></label>
        <label className="block"><span className={lbl}>Fallback second approver (blank = executives)</span><input data-testid="gov-escalation-to" value={s.auditor_question_escalation_to || ""} onChange={(e) => setS({ ...s, auditor_question_escalation_to: e.target.value })} placeholder="ciso@company.com" className={fld} /></label>
        <label className="block md:col-span-2"><span className={lbl}>Board digest recipients (comma-separated emails — blank = all admins &amp; execs)</span><input data-testid="gov-digest-recipients" value={recips} onChange={(e) => setRecips(e.target.value)} placeholder="board@company.com, ciso@company.com" className={fld} /></label>
        <label className="flex items-center gap-2 md:col-span-2 cursor-pointer"><input data-testid="gov-digest-enabled" type="checkbox" checked={!!s.board_digest_enabled} onChange={(e) => setS({ ...s, board_digest_enabled: e.target.checked })} className="w-4 h-4 accent-ai" /><span className="text-sm">Send the monthly board evidence digest automatically</span></label>
        <label className="block md:col-span-2"><span className={lbl}>Shared-card engagement digest cadence</span>
          <select data-testid="gov-card-cadence" value={s.card_engagement_cadence || "instant"} onChange={(e) => setS({ ...s, card_engagement_cadence: e.target.value })} className={fld}>
            <option value="instant">Instant — ping me the first time each card is opened or downloaded</option>
            <option value="weekly">Weekly — a Monday summary of last week's card activity</option>
            <option value="off">Off — no engagement notifications</option>
          </select>
        </label>
        <label className="block md:col-span-2"><span className={lbl}>Trusted access countries (comma-separated — opens from these won't raise a "new country" anomaly)</span><input data-testid="gov-trusted-countries" value={trusted} onChange={(e) => setTrusted(e.target.value)} placeholder="United States, United Kingdom, Canada" className={fld} /><span className="block text-[11px] text-muted-foreground mt-1">Match the country names shown in your access logs. New-device alerts still fire from any location.</span></label>
        <label className="block md:col-span-2"><span className={lbl}>Trusted networks — IP ranges (comma-separated IPs or CIDRs — accesses from these never raise an anomaly)</span><input data-testid="gov-trusted-networks" value={trustedIps} onChange={(e) => setTrustedIps(e.target.value)} placeholder="203.0.113.0/24, 198.51.100.7" className={fld} /><span className="block text-[11px] text-muted-foreground mt-1">Add your office egress IPs / VPN ranges so trusted-network access is never flagged.</span></label>
        <label className="block md:col-span-2"><span className={lbl}>Trusted auditors (comma-separated emails — their opens never show as suspicious, even from abroad)</span><input data-testid="gov-trusted-auditors" value={tauds} onChange={(e) => setTauds(e.target.value)} placeholder="auditor@bigfour.com, examiner@regulator.gov" className={fld} /><span className="block text-[11px] text-muted-foreground mt-1">Use the auditor's login / download email exactly as it appears in the access log.</span></label>
        <label className="block md:col-span-2"><span className={lbl}>Unusual-access alert threshold (min outside-trusted accesses to trigger the weekly note)</span><input data-testid="gov-unusual-threshold" type="number" min={1} max={1000} value={s.unusual_access_threshold ?? 1} onChange={(e) => setS({ ...s, unusual_access_threshold: e.target.value })} className={fld} /><span className="block text-[11px] text-muted-foreground mt-1">Quiet weeks below this count stay silent — no noise for the board.</span></label>
        <label className="flex items-start gap-2 md:col-span-2 cursor-pointer"><input data-testid="gov-instant-alerts" type="checkbox" checked={!!s.instant_suspicious_alerts} onChange={(e) => setS({ ...s, instant_suspicious_alerts: e.target.checked })} className="accent-ai w-4 h-4 mt-0.5" /><span className="text-sm">Instant alerts — email + Slack/Teams the moment an access lands from outside every trusted zone (not just the weekly note)</span></label>
        <label className="block md:col-span-2"><span className={lbl}>Alert channel — emails (comma-separated — instant alerts go only to these; blank = all admins &amp; execs)</span><input data-testid="gov-alert-emails" value={alertEmails} onChange={(e) => setAlertEmails(e.target.value)} placeholder="soc@company.com, ciso@company.com" className={fld} /><span className="block text-[11px] text-muted-foreground mt-1">Route instant suspicious-access alerts to your security team instead of every admin.</span></label>
        <label className="block md:col-span-2"><span className={lbl}>Alert channel — Slack/Teams webhook URL (blank = your org's configured chat webhook)</span><input data-testid="gov-alert-webhook" value={alertWebhook} onChange={(e) => setAlertWebhook(e.target.value)} placeholder="https://hooks.slack.com/services/… or https://outlook.office.com/webhook/…" className={fld} /><span className="block text-[11px] text-muted-foreground mt-1">Slack vs Teams is auto-detected from the URL. Applies to instant alerts only.</span></label>
        <div className="md:col-span-2" data-testid="gov-alert-test-row">
          <button data-testid="gov-alert-test" onClick={doTest} disabled={testing} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-secondary text-foreground text-xs font-head font-bold border border-border disabled:opacity-50">{testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Send test alert</button>
          <span className="ml-2 text-[11px] text-muted-foreground">Fires a sample alert through the channels above so you can confirm delivery.</span>
          <div className="mt-2 text-[11px] font-mono text-muted-foreground" data-testid="gov-alert-channels-status">channels: {channelSummary}</div>
        </div>
        <div className="md:col-span-2 rounded-md border border-border/60 bg-secondary/30 p-3" data-testid="gov-snooze">
          {s.snooze_alerts_until && new Date(s.snooze_alerts_until) > new Date() ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm text-high" data-testid="gov-snooze-status">Instant alerts muted until {new Date(s.snooze_alerts_until).toLocaleString()}{s.snooze_reason ? ` · ${s.snooze_reason}` : ""} · logged to the audit trail</span>
              <button data-testid="gov-snooze-resume" onClick={() => doSnooze(0)} disabled={snoozing} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{snoozing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null} Resume alerts now</button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm">Snooze instant alerts during a known audit push (logged to the audit trail):</span>
              <select data-testid="gov-snooze-hours" value={snoozeHours} onChange={(e) => setSnoozeHours(e.target.value)} className="bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary">
                <option value="1">1 hour</option>
                <option value="8">8 hours</option>
                <option value="24">24 hours</option>
              </select>
              <input data-testid="gov-snooze-reason" value={snoozeReason} onChange={(e) => setSnoozeReason(e.target.value)} placeholder="Reason (required — e.g. SOC2 fieldwork)" className="bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary min-w-[180px]" />
              <button data-testid="gov-snooze-btn" onClick={() => doSnooze(snoozeHours)} disabled={snoozing || !snoozeReason.trim()} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-secondary text-foreground text-xs font-head font-bold border border-border disabled:opacity-50">{snoozing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null} Snooze alerts</button>
            </div>
          )}
          <div className="border-t border-border/60 pt-3 mt-3" data-testid="gov-snooze-schedule">
            {s.snooze_window_start && s.snooze_window_end && new Date(s.snooze_window_end) > new Date() ? (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm text-med" data-testid="gov-snooze-window-status">Scheduled mute window: {new Date(s.snooze_window_start).toLocaleString()} → {new Date(s.snooze_window_end).toLocaleString()}{s.snooze_window_reason ? ` · ${s.snooze_window_reason}` : ""}</span>
                <button data-testid="gov-snooze-window-clear" onClick={() => doSchedule(true)} disabled={scheduling} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-secondary text-foreground text-xs font-head font-bold border border-border disabled:opacity-50">Clear scheduled window</button>
              </div>
            ) : (
              <div className="flex flex-wrap items-end gap-2">
                <label className="block"><span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Mute from</span><input data-testid="gov-snooze-window-start" type="datetime-local" value={snoozeStart} onChange={(e) => setSnoozeStart(e.target.value)} className="mt-1 block bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>
                <label className="block"><span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Until</span><input data-testid="gov-snooze-window-end" type="datetime-local" value={snoozeEnd} onChange={(e) => setSnoozeEnd(e.target.value)} className="mt-1 block bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>
                <label className="block"><span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Reason (required)</span><input data-testid="gov-snooze-window-reason" value={scheduleReason} onChange={(e) => setScheduleReason(e.target.value)} placeholder="e.g. PCI audit week" className="mt-1 block bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>
                <button data-testid="gov-snooze-schedule-btn" onClick={() => doSchedule(false)} disabled={scheduling || !snoozeStart || !snoozeEnd || !scheduleReason.trim()} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-secondary text-foreground text-xs font-head font-bold border border-border disabled:opacity-50">{scheduling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Calendar className="w-3.5 h-3.5" />} Schedule mute window</button>
              </div>
            )}
          </div>
        </div>
        <label className="flex items-start gap-2 md:col-span-2 cursor-pointer"><input data-testid="gov-audit-digest-enabled" type="checkbox" checked={!!s.audit_digest_enabled} onChange={(e) => setS({ ...s, audit_digest_enabled: e.target.checked })} className="accent-ai w-4 h-4 mt-0.5" /><span className="text-sm">Weekly control-change digest — email the board a Monday rollup of who relaxed controls (trusted-rule edits, snoozes, governance changes) with the sealed audit PDF attached</span></label>
        <label className="block md:col-span-2"><span className={lbl}>Control-change digest recipients (comma-separated — blank = board digest recipients or admins &amp; execs)</span><input data-testid="gov-audit-digest-recipients" value={auditRecips} onChange={(e) => setAuditRecips(e.target.value)} placeholder="board@company.com, audit-committee@company.com" className={fld} /><span className="block text-[11px] text-muted-foreground mt-1"><button type="button" data-testid="gov-audit-digest-send" onClick={sendAuditDigest} className="text-ai hover:underline">Send now</button> to email this week's digest immediately.</span></label>
        <div className="md:col-span-2" data-testid="gov-audit-digest-preview-wrap">
          <button type="button" data-testid="gov-audit-digest-preview" onClick={loadPreview} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-secondary text-foreground text-xs font-head font-bold border border-border">{previewOpen ? "Hide preview" : "Preview this week's digest"}</button>
          {previewOpen && (
            <div className="mt-2 rounded-md border border-border/60 bg-secondary/20 p-3" data-testid="gov-audit-digest-preview-panel">
              {!previewData ? <span className="text-sm text-muted-foreground">Loading…</span> : (
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[11px] font-mono text-muted-foreground uppercase tracking-wider">{previewData.changes} change(s) · would email {previewData.recipients?.length || 0} recipient(s)</span>
                    <button type="button" data-testid="gov-audit-digest-download-pdf" onClick={downloadDigestPdf} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-secondary text-foreground text-[11px] font-head font-bold border border-border">Download PDF</button>
                  </div>
                  {previewData.changes === 0 ? <span className="text-sm text-muted-foreground">No control changes in the last 7 days.</span> : (
                    <ul className="space-y-1.5 max-h-64 overflow-auto">
                      {previewData.rows.map((r, i) => (
                        <li key={i} data-testid={`gov-digest-preview-row-${i}`} className="text-[13px]">
                          <span className="font-mono text-[11px] text-muted-foreground">{(r.ts || "").slice(0, 16).replace("T", " ")} UTC</span> · <span className="text-ai">{r.action}</span> <span className="text-muted-foreground">by {r.actor || "system"}</span>
                          <div className="text-muted-foreground text-[12px]">{r.detail}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <SnapshotRetire />
    </Panel>
  );
}

function SnapshotRetire() {
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => { api.get("/agents/runtime/snapshot-status").then(({ data }) => setSt(data)).catch(() => {}); };
  useEffect(() => { load(); }, []);
  const retire = async () => {
    if (!window.confirm("Permanently remove the demo SNAPSHOT seed data? This only runs once a live source is connected.")) return;
    setBusy(true);
    try {
      const { data } = await api.post("/agents/runtime/retire-snapshots");
      toast.success(`Retired ${data.retired} demo snapshot record(s).`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not retire snapshot data.");
    }
    setBusy(false);
  };
  if (!st) return null;
  const live = st.live_source_connected;
  return (
    <div data-testid="gov-snapshot-retire" className="mt-5 pt-4 border-t border-border flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2">
        <Database className="w-4 h-4 text-muted-foreground" />
        <div>
          <div className="text-sm font-head font-bold">Demo snapshot data</div>
          <div className="text-[11px] text-muted-foreground">{st.snapshot_incidents} SNAPSHOT record(s) present · live source {live ? `connected (${st.live_source || "source"})` : "not connected"}</div>
        </div>
      </div>
      <button data-testid="gov-retire-snapshots" onClick={retire} disabled={busy || !live}
        title={live ? "Purge demo snapshot seed data" : "Connect a live enterprise source first"}
        className={`ml-auto inline-flex items-center gap-1.5 px-3 py-2 rounded-md border text-xs font-head font-bold transition-colors disabled:opacity-50 ${live ? "border-crit/50 text-crit hover:bg-crit/10" : "border-border text-muted-foreground"}`}>
        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} Retire demo snapshots
      </button>
    </div>
  );
}

function Msg({ m }) {
  const admin = m.role === "admin";
  return (
    <div className={`rounded-md p-2 text-sm ${admin ? "bg-ai/5 border-l-2 border-ai/40 ml-4" : "bg-secondary/30"}`}>
      <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{admin ? <ShieldCheck className="w-3 h-3 text-ai" /> : <MessageSquare className="w-3 h-3" />}{admin ? "Governance" : m.by || "Auditor"} · {fmtDTT(m.at)}{m.attachment && <span className="inline-flex items-center gap-1 text-ai"><Paperclip className="w-3 h-3" /> {m.attachment}</span>}</div>
      <p className="mt-1">{m.text}</p>
    </div>
  );
}

function AuditorQuestionsCard() {
  const [comments, setComments] = useState([]);
  const [sla, setSla] = useState(null);
  const [replyFor, setReplyFor] = useState(null);
  const [replyText, setReplyText] = useState("");
  const [attach, setAttach] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/agents/runtime/evidence-room-comments").then(({ data }) => { setComments(data.comments || []); setSla(data.sla_hours); }).catch(() => {});
  useEffect(() => { load(); }, []);
  const sendReply = async (id) => {
    if (!replyText.trim()) return;
    setBusy(true);
    try { await api.post("/agents/runtime/evidence-room-comments/reply", { id, reply: replyText, attach_pdf: attach }); toast.success(attach ? "Reply sent with the signed evidence PDF." : "Reply sent — auditor notified if they left an email."); setReplyFor(null); setReplyText(""); setAttach(false); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not send reply."); }
    finally { setBusy(false); }
  };
  const setStatus = async (id, status) => { try { await api.post("/agents/runtime/evidence-room-comments/status", { id, status }); load(); } catch (e) { toast.error(e.response?.data?.detail || "Could not update status."); } };
  const setPriority = async (id, priority) => { try { await api.post("/agents/runtime/evidence-room-comments/status", { id, priority }); load(); } catch (e) { toast.error(e.response?.data?.detail || "Could not update priority."); } };
  const open = comments.filter((c) => c.status !== "Resolved").length;
  const overdue = comments.filter((c) => c.overdue).length;
  const escalated = comments.filter((c) => c.escalated).length;

  return (
    <Panel title="Auditor questions" subtitle="A two-way audit workspace — auditors' questions, your threaded replies (optionally with the signed evidence PDF), per-priority SLA + on-call escalation, and status. The full Q&A trail is exported into the board digest." testid="agentic-auditor-questions"
      actions={<div className="flex items-center gap-1.5">{sla != null && <span className="text-[10px] font-mono px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">Normal SLA {sla}h</span>}{escalated > 0 && <span data-testid="auditor-questions-escalated" className="text-[10px] font-mono px-2 py-1 rounded-full bg-crit/15 text-crit">{escalated} escalated</span>}{overdue > 0 && <span data-testid="auditor-questions-overdue" className="text-[10px] font-mono px-2 py-1 rounded-full bg-crit/10 text-crit">{overdue} overdue</span>}<span className="text-[10px] font-mono px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">{open} open</span></div>}>
      {comments.length === 0 ? (
        <div className="text-sm text-muted-foreground" data-testid="auditor-questions-empty">No auditor questions yet. They appear here when an auditor asks a question in a room.</div>
      ) : (
        <div className="space-y-3" data-testid="auditor-questions-list">
          {comments.map((q) => {
            const msgs = q.messages && q.messages.length ? q.messages : [{ role: "auditor", by: q.author, text: q.text, at: q.at }, ...(q.reply ? [{ role: "admin", text: q.reply, at: q.reply_at }] : [])];
            return (
              <div key={q.id} data-testid={`auditor-question-${q.id}`} className="rounded-lg border border-border bg-secondary/10 p-3">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <span className="font-head font-bold text-sm">{q.author}</span>
                  {q.author_email && <span className="text-[10px] font-mono text-muted-foreground">{q.author_email}</span>}
                  <span data-testid={`auditor-question-priority-${q.id}`} className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${PRIORITY_TONE[q.priority] || PRIORITY_TONE.normal}`}>{(q.priority || "normal").toUpperCase()}{q.sla_hours ? ` · ${q.sla_hours}h` : ""}</span>
                  <select data-testid={`auditor-question-priority-select-${q.id}`} value={q.priority || "normal"} onChange={(e) => setPriority(q.id, e.target.value)} className="text-[10px] font-mono bg-secondary/60 rounded px-1.5 py-0.5 outline-none cursor-pointer">
                    <option value="low">low</option><option value="normal">normal</option><option value="high">high</option><option value="urgent">urgent</option>
                  </select>
                  {q.escalated && <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-crit/15 text-crit">escalated</span>}
                  {q.overdue && !q.escalated && <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-crit/10 text-crit">overdue</span>}
                  <span className={`ml-auto text-[10px] font-mono px-2 py-0.5 rounded-full ${q.status === "Resolved" ? "bg-low/10 text-low" : q.status === "Answered" ? "bg-ai/10 text-ai" : "bg-high/10 text-high"}`}>{q.status || "Open"}</span>
                </div>
                <div className="space-y-1.5">{msgs.map((m, i) => <Msg key={i} m={m} />)}</div>
                {replyFor === q.id ? (
                  <div className="mt-2 space-y-2">
                    <textarea data-testid={`auditor-question-reply-input-${q.id}`} autoFocus value={replyText} onChange={(e) => setReplyText(e.target.value)} rows={2} placeholder="Type a reply…" className="w-full bg-secondary/50 rounded-md px-2.5 py-2 text-sm outline-none focus:ring-1 focus:ring-primary resize-none" />
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="flex items-center gap-1.5 text-xs cursor-pointer"><input data-testid={`auditor-question-attach-${q.id}`} type="checkbox" checked={attach} onChange={(e) => setAttach(e.target.checked)} className="w-3.5 h-3.5 accent-ai" /> Attach signed evidence PDF</label>
                      <button data-testid={`auditor-question-reply-send-${q.id}`} onClick={() => sendReply(q.id)} disabled={busy || !replyText.trim()} className="ml-auto inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Reply</button>
                      <button onClick={() => { setReplyFor(null); setReplyText(""); setAttach(false); }} className="px-2 py-2 rounded-md border border-border text-xs text-muted-foreground">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 flex items-center gap-1.5">
                    <button data-testid={`auditor-question-reply-btn-${q.id}`} onClick={() => { setReplyFor(q.id); setReplyText(""); setAttach(false); }} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border text-xs hover:bg-secondary transition-colors"><Send className="w-3 h-3" /> Reply</button>
                    {q.status === "Resolved" ? (
                      <button data-testid={`auditor-question-reopen-${q.id}`} onClick={() => setStatus(q.id, "Open")} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border text-xs hover:bg-secondary transition-colors"><RefreshCw className="w-3 h-3" /> Reopen</button>
                    ) : (
                      <button data-testid={`auditor-question-resolve-${q.id}`} onClick={() => setStatus(q.id, "Resolved")} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-low/30 text-low text-xs hover:bg-low/10 transition-colors"><CheckCircle2 className="w-3 h-3" /> Resolve</button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

function RuntimePlaybooksCard() {
  const [pb, setPb] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState(null);
  useEffect(() => { api.get("/agents/runtime/webhook/playbooks").then(({ data }) => setPb(data)).catch(() => {}); }, []);
  if (!pb) return null;
  const payloadStr = JSON.stringify({ payload: pb.payload, headers: pb.headers }, null, 2);
  const webhookUrl = pb.webhook_url || "";
  const secret = pb.signing_secret || "";
  const secretLiteral = secret ? JSON.stringify(secret) : '"<your signing secret>"';
  const verifySnippet =
`import hmac, hashlib
# Obserra HMAC verification — signature = sha256 over "<timestamp>." + raw request body
OBSERRA_WEBHOOK_SECRET = ${secretLiteral}
def verify_obserra(raw_body: bytes, ts: str, sig: str) -> bool:
    expected = "sha256=" + hmac.new(OBSERRA_WEBHOOK_SECRET.encode(), (ts + ".").encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig or "")`;
  const prefilled = (p) =>
`# Obserra -> ${p.name} enforcement receiver — prefilled for your org (one paste)
# Obserra POSTs signed Suspend / Kill / Resume events to:
#   ${webhookUrl || "<connect a webhook or enable the Live Enforcement Simulator>"}
${verifySnippet}

# In your HTTP handler:
#   raw = await request.body()
#   if not verify_obserra(raw, request.headers["X-Obserra-Timestamp"], request.headers["X-Obserra-Signature"]):
#       return Response(status_code=401)
#   evt = json.loads(raw)   # {"agent_ref","action","mode",...}
${p.example}`;
  const testPing = async () => {
    setTesting(true); setResult(null);
    try { const { data } = await api.post("/agents/runtime/webhook/test"); setResult(data); if (data.ok) toast.success(`Runtime received the test enforcement — HTTP ${data.status_code} · ${data.latency_ms}ms`); else toast.error(`No 2xx from runtime — ${data.status_code || data.error || "unreachable"}`); }
    catch (e) { setResult({ ok: false, error: e.response?.data?.detail || "failed" }); toast.error(e.response?.data?.detail || "No agent runtime webhook configured."); }
    finally { setTesting(false); }
  };
  return (
    <Panel title="Runtime enforcement playbooks" subtitle="Obserra dispatches this signed webhook on every Suspend / Kill / Resume. Copy a per-provider adapter — prefilled with your own webhook URL + signing secret — so wiring a real runtime is one paste, then send a test enforcement to confirm it lands." testid="agentic-runtime-playbooks">
      <div className="rounded-lg border border-ai/25 bg-ai/[0.03] p-3 mb-3" data-testid="runtime-adapter-prefill">
        <div className="flex items-center gap-2 flex-wrap mb-1.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-ai">Your prefilled receiver</span>
          {pb.managed === "simulator" && <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-low/10 text-low border border-low/25">built-in simulator</span>}
          <button data-testid="adapter-copy-skeleton" onClick={() => copyText(verifySnippet)} className="ml-auto inline-flex items-center gap-1 px-2 py-1 rounded border border-ai/40 text-ai text-xs hover:bg-ai/10 transition-colors"><Copy className="w-3 h-3" /> Copy verify()</button>
        </div>
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-[10px] font-mono text-muted-foreground shrink-0">POST URL</span>
          <input readOnly data-testid="adapter-webhook-url" value={webhookUrl || "— connect a webhook or enable the simulator —"} onFocus={(e) => e.target.select()} className="flex-1 min-w-0 bg-secondary/50 rounded px-2 py-1.5 text-[11px] font-mono outline-none" />
        </div>
        <div className="text-[10px] font-mono text-muted-foreground">Signing secret: {secret ? `${"\u2022".repeat(10)} (embedded in the copied adapters below)` : "not set — enable the simulator or save a webhook secret"}</div>
      </div>
      <div className="rounded-lg border border-border bg-secondary/20 p-3 mb-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Signed webhook contract</span>
          <button data-testid="playbook-copy-payload" onClick={() => copyText(payloadStr)} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"><Copy className="w-3 h-3" /> Copy</button>
        </div>
        <pre className="text-[11px] font-mono whitespace-pre-wrap text-muted-foreground overflow-x-auto">{payloadStr}</pre>
      </div>
      <div className="space-y-2" data-testid="playbooks-list">
        {(pb.playbooks || []).map((p) => (
          <div key={p.id} data-testid={`playbook-${p.id}`} className="rounded-lg border border-border">
            <button onClick={() => setOpenId(openId === p.id ? null : p.id)} className="w-full flex items-center gap-2 px-3 py-2.5 text-left"><Terminal className="w-4 h-4 text-ai shrink-0" /><span className="font-head font-bold text-sm">{p.name}</span><span className="ml-auto text-[10px] font-mono text-muted-foreground">{openId === p.id ? "hide" : "view"}</span></button>
            {openId === p.id && (
              <div className="px-3 pb-3 space-y-2">
                <p className="text-xs text-muted-foreground">{p.blurb}</p>
                <div className="grid sm:grid-cols-3 gap-2">{Object.entries(p.map || {}).map(([k, v]) => (<div key={k} className="rounded border border-border p-2"><div className="text-[10px] font-mono uppercase text-ai">{k}</div><div className="text-[11px] text-muted-foreground mt-1">{v}</div></div>))}</div>
                <div className="rounded bg-secondary/30 p-2">
                  <div className="flex items-center justify-between mb-1"><span className="text-[10px] font-mono uppercase text-muted-foreground">prefilled adapter — verify() + your secret + action mapping</span><button data-testid={`playbook-copy-prefilled-${p.id}`} onClick={() => copyText(prefilled(p))} className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-ai/40 text-ai text-[10px] hover:bg-ai/10 transition-colors"><Copy className="w-3 h-3" /> Copy prefilled receiver</button></div>
                  <pre className="text-[11px] font-mono whitespace-pre-wrap overflow-x-auto max-h-72 overflow-y-auto">{prefilled(p)}</pre>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <a href={p.docs} target="_blank" rel="noreferrer" className="text-[11px] font-mono text-ai underline">Provider docs →</a>
                  <button data-testid={`playbook-test-${p.id}`} onClick={testPing} disabled={testing} className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors disabled:opacity-50">{testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />} Send test enforcement</button>
                </div>
                {result && (
                  <div data-testid="playbook-test-result" className={`text-[11px] font-mono rounded-md px-3 py-2 border ${result.ok ? "bg-low/10 border-low/25 text-low" : "bg-crit/10 border-crit/25 text-crit"}`}>
                    {result.ok ? `Runtime received it — HTTP ${result.status_code} · ${result.latency_ms}ms · ${result.attempts} try · ${result.signed ? "signed" : "unsigned"}` : `Not delivered — ${result.status_code || result.error || "unreachable"}`}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function KillReplayDrillCard({ agents = [] }) {
  const [drills, setDrills] = useState([]);
  const [agentRef, setAgentRef] = useState("");
  const [notify, setNotify] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sched, setSched] = useState(null);
  const [savingSched, setSavingSched] = useState(false);
  const pickable = (agents || []).filter((a) => a.ref && a.status !== "killed");
  const load = () => api.get("/agents/runtime/fire-drills").then(({ data }) => setDrills(data.drills || [])).catch(() => {});
  useEffect(() => { load(); api.get("/agents/runtime/governance-settings").then(({ data }) => setSched(data)).catch(() => {}); }, []);
  useEffect(() => { if (!agentRef && pickable.length) setAgentRef(pickable[0].ref); }, [agents]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async () => {
    if (!agentRef) { toast.error("Pick an agent to drill."); return; }
    setBusy(true);
    try { const { data } = await api.post("/agents/runtime/fire-drill", { agent_ref: agentRef, notify }); const d = data.drill; toast.success(d.controlled ? `Control confirmed — ${d.agent_name} suspended (${d.suspend_ms}ms) & resumed (${d.resume_ms}ms).` : "Drill ran, but the runtime did not confirm control."); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Fire-drill failed."); }
    finally { setBusy(false); }
  };
  const saveSched = async () => {
    setSavingSched(true);
    try { const { data } = await api.put("/agents/runtime/governance-settings", { fire_drill_enabled: !!sched.fire_drill_enabled, fire_drill_day: Number(sched.fire_drill_day) || 1, fire_drill_agent_ref: sched.fire_drill_agent_ref || "" }); setSched(data); toast.success("Fire-drill schedule saved"); }
    catch (e) { toast.error(e.response?.data?.detail || "Save failed."); }
    finally { setSavingSched(false); }
  };
  const fld = "mt-1.5 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary";
  const lbl = "text-[11px] font-mono uppercase tracking-wider text-muted-foreground";
  return (
    <Panel title="Kill Replay Drill" subtitle="Prove your kill-switch actually fires — run a Suspend → Resume replay against any agent (timed, signed, receipted) and optionally email the board a proof-of-control receipt. Schedule a monthly fire-drill so control is proven on autopilot." testid="agentic-fire-drill"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <select data-testid="fire-drill-agent" value={agentRef} onChange={(e) => setAgentRef(e.target.value)} className="text-xs font-mono bg-secondary/60 border border-border rounded-md px-2 py-1.5 outline-none cursor-pointer max-w-[180px]">
            {pickable.length === 0 && <option value="">No agents</option>}
            {pickable.map((a) => <option key={a.ref} value={a.ref}>{a.name} ({a.ref})</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-xs cursor-pointer"><input data-testid="fire-drill-notify" type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} className="w-3.5 h-3.5 accent-ai" /> Email board</label>
          <button data-testid="fire-drill-run" onClick={run} disabled={busy || !agentRef} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />} Run fire-drill now</button>
        </div>
      }>
      {sched && (
        <div className="rounded-lg border border-border bg-secondary/20 p-3 mb-4" data-testid="fire-drill-schedule">
          <div className="flex items-center gap-2 mb-2"><Calendar className="w-4 h-4 text-ai" /><span className="font-head font-bold text-sm">Scheduled monthly fire-drill</span>
            <button data-testid="fire-drill-schedule-save" onClick={saveSched} disabled={savingSched} className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors disabled:opacity-50">{savingSched ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Settings2 className="w-3.5 h-3.5" />} Save schedule</button>
          </div>
          <div className="grid sm:grid-cols-3 gap-3">
            <label className="flex items-center gap-2 cursor-pointer"><input data-testid="fire-drill-enabled" type="checkbox" checked={!!sched.fire_drill_enabled} onChange={(e) => setSched({ ...sched, fire_drill_enabled: e.target.checked })} className="w-4 h-4 accent-ai" /><span className="text-sm">Enabled</span></label>
            <label className="block"><span className={lbl}>Day of month</span><input data-testid="fire-drill-day" type="number" min={1} max={28} value={sched.fire_drill_day || 1} onChange={(e) => setSched({ ...sched, fire_drill_day: e.target.value })} className={fld} /></label>
            <label className="block"><span className={lbl}>Agent</span>
              <select data-testid="fire-drill-schedule-agent" value={sched.fire_drill_agent_ref || ""} onChange={(e) => setSched({ ...sched, fire_drill_agent_ref: e.target.value })} className={fld}>
                <option value="">First active agent</option>
                {pickable.map((a) => <option key={a.ref} value={a.ref}>{a.name} ({a.ref})</option>)}
              </select>
            </label>
          </div>
        </div>
      )}
      {drills.length > 0 && (() => {
        const susVals = drills.map((x) => x.suspend_ms).filter((v) => typeof v === "number");
        const resVals = drills.map((x) => x.resume_ms).filter((v) => typeof v === "number");
        const avgSus = susVals.length ? Math.round(susVals.reduce((a, b) => a + b, 0) / susVals.length) : null;
        const avgRes = resVals.length ? Math.round(resVals.reduce((a, b) => a + b, 0) / resVals.length) : null;
        return (
        <div className="rounded-lg border border-border bg-secondary/10 p-3 mb-3" data-testid="fire-drill-trend">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Drill trend · last {drills.length}</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-low/10 text-low" data-testid="fire-drill-rate">{Math.round((100 * drills.filter((x) => x.controlled).length) / drills.length)}% control-confirmed</span>
            {avgSus != null && <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-secondary/60 text-muted-foreground">avg suspend {avgSus}ms</span>}
            {avgRes != null && <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-secondary/60 text-muted-foreground">avg resume {avgRes}ms</span>}
            <Link to="/app/control-assurance" data-testid="fire-drill-assurance-link" className="ml-auto text-[11px] font-mono text-ai underline">Control Assurance →</Link>
          </div>
          {drills.length >= 2 && (
            <div style={{ height: 48 }} data-testid="fire-drill-sparkline">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={[...drills].reverse().map((x, i) => ({ i, ms: x.total_ms }))} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                  <RTooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 11 }} labelFormatter={() => ""} formatter={(v) => [`${v}ms`, "round-trip"]} />
                  <Line type="monotone" dataKey="ms" stroke="hsl(190 80% 50%)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
        );
      })()}
      {drills.length === 0 ? (
        <div className="text-sm text-muted-foreground" data-testid="fire-drill-empty">No fire-drills yet. Run one to produce a timed, signed proof-of-control receipt.</div>
      ) : (
        <div className="space-y-2" data-testid="fire-drill-list">
          {drills.map((d, i) => (
            <div key={i} data-testid={`fire-drill-${i}`} className="flex items-center gap-2 flex-wrap rounded-lg border border-border bg-secondary/10 px-3 py-2.5 text-xs">
              {d.controlled ? <ShieldCheck className="w-4 h-4 text-low shrink-0" /> : <XCircle className="w-4 h-4 text-crit shrink-0" />}
              <span className="font-head font-bold">{d.agent_name}</span>
              <span className="font-mono text-muted-foreground">{d.agent_ref}</span>
              {d.scheduled && <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-ai/10 text-ai">scheduled</span>}
              <span className="text-[10px] font-mono text-muted-foreground">suspend {d.suspend_ms}ms · resume {d.resume_ms}ms</span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${d.signed ? "bg-low/10 text-low" : "bg-secondary/60 text-muted-foreground"}`}>{d.signed ? "signed" : "unsigned"}</span>
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">{fmtDTT(d.at)}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function TrustSuggestionBanner() {
  const [params, setParams] = useSearchParams();
  const token = params.get("trust");
  const [sug, setSug] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!token) { setSug(null); return; }
    api.get(`/agents/runtime/trust-suggestion/${token}`).then(({ data }) => setSug(data)).catch(() => setSug({ error: true }));
  }, [token]);
  if (!token || !sug) return null;
  const dismiss = () => { const p = new URLSearchParams(params); p.delete("trust"); setParams(p, { replace: true }); setSug(null); };
  if (sug.error) return (
    <div className="rounded-lg border border-crit/40 bg-crit/10 p-4 flex items-center justify-between gap-3" data-testid="trust-suggestion-banner">
      <span className="text-sm text-crit">This trust link is invalid or has expired.</span>
      <button data-testid="trust-suggestion-dismiss" onClick={dismiss} className="text-xs text-muted-foreground hover:text-foreground">Dismiss</button>
    </div>
  );
  const label = sug.kind === "country" ? `Add “${sug.value}” to trusted countries` : `Trust auditor ${sug.value}`;
  const apply = async () => {
    setBusy(true);
    try {
      await api.post(`/agents/runtime/trust-suggestion/${token}/apply`, {});
      toast.success(sug.already ? "Already trusted" : `${label} — done`);
      setTimeout(() => { window.location.href = window.location.pathname; }, 700);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not apply.");
      setBusy(false);
    }
  };
  return (
    <div className="rounded-lg border border-ai/40 bg-ai/10 p-4 flex flex-wrap items-center justify-between gap-3" data-testid="trust-suggestion-banner">
      <div className="flex items-center gap-2 min-w-0">
        <ShieldCheck className="w-4 h-4 text-ai shrink-0" />
        <span className="text-sm">One-click from an alert: <strong>{label}</strong>{sug.used ? " (already applied)" : ""}?</span>
      </div>
      <div className="flex items-center gap-2">
        <button data-testid="trust-suggestion-apply" onClick={apply} disabled={busy || sug.used} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />} {sug.used ? "Applied" : "Confirm & add"}</button>
        <button data-testid="trust-suggestion-dismiss" onClick={dismiss} className="text-xs text-muted-foreground hover:text-foreground">Dismiss</button>
      </div>
    </div>
  );
}

export default function DefensibilityDashboard({ data, sourceStatus, isAdmin }) {
  const connectors = data?.connectorHealth?.connectors || [];
  const summary = data?.connectorHealth?.summary || {};
  return (
    <div className="space-y-5">
      {isAdmin && <TrustSuggestionBanner />}
      {isAdmin && <AuditorRoomCard />}
      {isAdmin && <ShareCenterCard />}
      {isAdmin && <GovernanceSettingsCard />}
      {isAdmin && <AuditorQuestionsCard />}
      {isAdmin && <RuntimePlaybooksCard />}
      {isAdmin && <KillReplayDrillCard agents={data?.agents || []} />}

      <div className="grid xl:grid-cols-3 gap-5">
        <Panel title="Data source status" subtitle="Unavailable sources are surfaced rather than replaced with synthetic data." testid="agentic-source-status">
          <div className="space-y-2">
            {Object.entries(sourceStatus || {}).map(([key, status]) => (
              <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="flex items-center gap-2 min-w-0">
                  {status.ok ? <CheckCircle2 className="w-4 h-4 text-low shrink-0" /> : <XCircle className="w-4 h-4 text-crit shrink-0" />}
                  <div><div className="text-sm font-medium">{SOURCE_LABEL[key] || key}</div>{!status.ok && <div className="text-[10px] text-muted-foreground">{status.error}</div>}</div>
                </div>
                <span className={`text-[10px] font-mono ${status.ok ? "text-low" : "text-crit"}`}>{status.ok ? "LIVE" : "UNAVAILABLE"}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Evidence classification" subtitle="The app explicitly separates source facts from derived intelligence." testid="agentic-evidence-class">
          <div className="space-y-4">
            <div className="rounded-lg border border-border p-4"><DataClassBadge kind="FACT" /><p className="text-xs text-muted-foreground mt-2">Agent inventory, tools, permissions, guardrails, governance status, AI systems, incidents, usage analytics and connector health returned by the existing backend.</p></div>
            <div className="rounded-lg border border-border p-4"><DataClassBadge kind="MODELLED" /><p className="text-xs text-muted-foreground mt-2">Agent risk score, delegated authority tier and action-capable tool classification calculated in the browser from existing records.</p></div>
            <div className="rounded-lg border border-border p-4"><DataClassBadge kind="HEURISTIC BASELINE" /><p className="text-xs text-muted-foreground mt-2">Existing red-team results are deterministic checks against recorded guardrails. They are not live adversarial runtime tests.</p></div>
            <div className="rounded-lg border border-border p-4"><DataClassBadge kind="AI RECOMMENDATION" /><p className="text-xs text-muted-foreground mt-2">Obserra Advisor interpretation, analysis and recommended executive actions.</p></div>
          </div>
        </Panel>

        <Panel title="Runtime enforcement boundary" subtitle="Governance state is not confused with external runtime control." testid="agentic-runtime-boundary">
          <div className="space-y-3 text-sm">
            <div className="flex gap-2"><ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />Toggling a guardrail updates the existing Obserra governance record.</div>
            <div className="flex gap-2"><ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />Sanctioning a system updates its governance status in Obserra.</div>
            <div className="flex gap-2"><ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />A Suspend / Kill is dispatched to the external agent runtime when a webhook is connected (HMAC-signed, retried) — the runtime receipt is recorded; otherwise it is enforced in the control plane only. See the Runtime enforcement playbooks above.</div>
            <div className="flex gap-2"><ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />Future live red-team capabilities require explicit runtime connectors.</div>
          </div>
        </Panel>
      </div>

      <Panel title="Connector health context" subtitle={`${summary.healthy || 0} healthy · ${summary.degraded || 0} degraded. Existing connector health only.`} testid="agentic-connectors">
        {connectors.length === 0 ? (
          <div className="py-8 text-center"><Database className="w-8 h-8 text-muted-foreground mx-auto" /><div className="text-sm text-muted-foreground mt-2">No connector health records are available.</div></div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {connectors.map((connector) => (
              <div key={`${connector.id}:${connector.name}`} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2"><div><div className="font-head font-bold text-sm">{connector.name}</div><div className="text-[10px] text-muted-foreground mt-1">{connector.category}</div></div><span className={`text-[10px] font-mono ${connector.health === "healthy" ? "text-low" : connector.health === "degraded" ? "text-high" : "text-muted-foreground"}`}>{connector.health || connector.state || "unknown"}</span></div>
                <div className="text-[10px] text-muted-foreground mt-3">Last checked: {connector.checked_at ? new Date(connector.checked_at).toLocaleString() : "not available"}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
