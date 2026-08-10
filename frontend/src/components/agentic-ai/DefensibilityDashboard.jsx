import { useEffect, useState } from "react";
import { CheckCircle2, Clock, Copy, Database, DoorOpen, FileText, Loader2, MessageSquare, Plus, RefreshCw, Send, ShieldCheck, Trash2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { DataClassBadge, Panel } from "@/components/agentic-ai/shared";
import { api } from "@/lib/api";

const SOURCE_LABEL = {
  agents: "AI Agent Governance",
  analytics: "AI Analytics",
  systems: "AI System Inventory",
  incidents: "AI Incidents",
  workflows: "Workflow Engine",
  connectorHealth: "Connector Health",
};

const fmtDT = (s) => (s ? new Date(s).toLocaleDateString(undefined, { dateStyle: "medium" }) : "—");
const fmtDTT = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");

// Read-only, expiring Auditor Room — generate a shareable no-login link external auditors open to view
// the live AI Enforcement Evidence Pack + signed PDF. Renew / revoke; one-tap board evidence digest. Admin only.
function AuditorRoomCard() {
  const [rooms, setRooms] = useState([]);
  const [busy, setBusy] = useState(false);
  const [digestBusy, setDigestBusy] = useState(false);
  const [latest, setLatest] = useState(null);

  const load = () =>
    api.get("/agents/runtime/evidence-rooms").then(({ data }) => setRooms(data.rooms || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const copy = async (url) => {
    try { await navigator.clipboard.writeText(url); toast.success("Link copied"); }
    catch { toast.error("Copy failed — select and copy manually."); }
  };

  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/agents/runtime/evidence-room", { days: 14 });
      setLatest(data);
      try { await navigator.clipboard.writeText(data.url); toast.success("Auditor room link created & copied"); }
      catch { toast.success("Auditor room link created"); }
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not create auditor room.");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (token) => {
    if (!window.confirm("Revoke this auditor room link? External auditors will lose access immediately.")) return;
    try {
      await api.post("/agents/runtime/evidence-room/revoke", { token });
      if (latest?.token === token) setLatest(null);
      toast.success("Auditor room revoked");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Revoke failed.");
    }
  };

  const renew = async (token) => {
    try {
      const { data } = await api.post("/agents/runtime/evidence-room/renew", { token, days: 14 });
      toast.success(`Renewed — now expires ${fmtDT(data.expires_at)}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Renew failed.");
    }
  };

  const sendDigest = async () => {
    setDigestBusy(true);
    try {
      const { data } = await api.post("/agents/runtime/board-evidence-digest/send");
      toast.success(data.sent ? `Board evidence digest emailed to ${data.sent} recipient(s) with the signed PDF.` : "No recipients found to email.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not send the board digest.");
    } finally {
      setDigestBusy(false);
    }
  };

  return (
    <Panel
      title="Read-only Auditor Room"
      subtitle="Generate an expiring, no-login link for external auditors to view the live AI Enforcement Evidence Pack (agent toxicity snapshot, runtime enforcement audit trail), download a watermarked signed PDF, and leave questions. Every open is tracked."
      testid="agentic-auditor-room"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <button
            data-testid="board-digest-btn"
            onClick={sendDigest}
            disabled={digestBusy}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors disabled:opacity-50"
          >
            {digestBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />}
            Email board digest
          </button>
          <button
            data-testid="auditor-room-create-btn"
            onClick={create}
            disabled={busy}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            Create auditor room
          </button>
        </div>
      }
    >
      {latest && (
        <div
          data-testid="auditor-room-latest"
          className="mb-4 rounded-lg border border-ai/30 bg-ai/5 p-3"
        >
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-ai mb-1.5">
            <DoorOpen className="w-3 h-3" /> New link — share with your auditor · expires {fmtDT(latest.expires_at)}
          </div>
          <div className="flex items-center gap-2">
            <input
              readOnly
              data-testid="auditor-room-latest-url"
              value={latest.url}
              onFocus={(e) => e.target.select()}
              className="flex-1 min-w-0 bg-secondary/50 rounded-md px-2.5 py-2 text-xs font-mono outline-none"
            />
            <button
              data-testid="auditor-room-latest-copy"
              onClick={() => copy(latest.url)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors shrink-0"
            >
              <Copy className="w-3.5 h-3.5" /> Copy
            </button>
          </div>
        </div>
      )}

      {rooms.length === 0 ? (
        <div className="text-sm text-muted-foreground" data-testid="auditor-room-empty">
          No active auditor rooms. Create one to share a read-only evidence link with an external auditor.
        </div>
      ) : (
        <div className="space-y-2" data-testid="auditor-room-list">
          {rooms.map((room) => (
            <div
              key={room.token}
              data-testid={`auditor-room-${room.token}`}
              className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-secondary/20 px-3 py-2.5"
            >
              <DoorOpen className={`w-4 h-4 shrink-0 ${room.expired ? "text-muted-foreground" : "text-ai"}`} />
              <span className="font-mono text-xs truncate max-w-[38%]">{room.url}</span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${room.expired ? "bg-crit/10 text-crit" : "bg-low/10 text-low"}`}>
                {room.expired ? "expired" : `expires ${fmtDT(room.expires_at)}`}
              </span>
              <span className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1">
                <Clock className="w-3 h-3" /> {room.opens} open(s)
              </span>
              <div className="ml-auto flex items-center gap-1.5">
                <button
                  data-testid={`auditor-room-renew-${room.token}`}
                  onClick={() => renew(room.token)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"
                >
                  <RefreshCw className="w-3 h-3" /> Renew
                </button>
                <button
                  data-testid={`auditor-room-copy-${room.token}`}
                  onClick={() => copy(room.url)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"
                >
                  <Copy className="w-3 h-3" /> Copy
                </button>
                <button
                  data-testid={`auditor-room-revoke-${room.token}`}
                  onClick={() => revoke(room.token)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded border border-crit/30 text-crit text-xs hover:bg-crit/10 transition-colors"
                >
                  <Trash2 className="w-3 h-3" /> Revoke
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

// Auditor questions inbox — read-only questions left by external auditors on the public room; reply inline.
function AuditorQuestionsCard() {
  const [comments, setComments] = useState([]);
  const [replyFor, setReplyFor] = useState(null);
  const [replyText, setReplyText] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.get("/agents/runtime/evidence-room-comments").then(({ data }) => setComments(data.comments || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const sendReply = async (id) => {
    if (!replyText.trim()) return;
    setBusy(true);
    try {
      await api.post("/agents/runtime/evidence-room-comments/reply", { id, reply: replyText });
      toast.success("Reply sent — the auditor is notified if they left an email.");
      setReplyFor(null);
      setReplyText("");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not send reply.");
    } finally {
      setBusy(false);
    }
  };

  const open = comments.filter((c) => c.status !== "Resolved").length;

  return (
    <Panel
      title="Auditor questions"
      subtitle="Read-only questions external auditors left in an Auditor Room. Reply and it appears back on their portal (and by email if they provided one)."
      testid="agentic-auditor-questions"
      actions={<span className="text-[10px] font-mono px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">{open} open</span>}
    >
      {comments.length === 0 ? (
        <div className="text-sm text-muted-foreground" data-testid="auditor-questions-empty">
          No auditor questions yet. They appear here when an auditor asks a question in a room.
        </div>
      ) : (
        <div className="space-y-2" data-testid="auditor-questions-list">
          {comments.map((q) => (
            <div key={q.id} data-testid={`auditor-question-${q.id}`} className="rounded-lg border border-border bg-secondary/20 p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <MessageSquare className="w-3.5 h-3.5 text-ai shrink-0" />
                <span className="font-head font-bold text-sm">{q.author}</span>
                {q.author_email && <span className="text-[10px] font-mono text-muted-foreground">{q.author_email}</span>}
                <span className="text-[10px] font-mono text-muted-foreground">{fmtDTT(q.at)}</span>
                <span className={`ml-auto text-[10px] font-mono px-2 py-0.5 rounded-full ${q.status === "Resolved" ? "bg-low/10 text-low" : "bg-high/10 text-high"}`}>{q.status || "Open"}</span>
              </div>
              <p className="text-sm mt-1.5">{q.text}</p>
              {q.reply ? (
                <div className="mt-2 pl-3 border-l-2 border-ai/40">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-ai/70 flex items-center gap-1"><ShieldCheck className="w-3 h-3" /> Your reply · {q.reply_by}</div>
                  <p className="text-sm text-muted-foreground mt-1">{q.reply}</p>
                </div>
              ) : replyFor === q.id ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <input
                    data-testid={`auditor-question-reply-input-${q.id}`}
                    autoFocus
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") sendReply(q.id); }}
                    placeholder="Type a reply…"
                    className="flex-1 min-w-[200px] bg-secondary/50 rounded-md px-2.5 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                  />
                  <button
                    data-testid={`auditor-question-reply-send-${q.id}`}
                    onClick={() => sendReply(q.id)}
                    disabled={busy || !replyText.trim()}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
                  >
                    {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Reply
                  </button>
                  <button onClick={() => { setReplyFor(null); setReplyText(""); }} className="px-2 py-2 rounded-md border border-border text-xs text-muted-foreground">Cancel</button>
                </div>
              ) : (
                <button
                  data-testid={`auditor-question-reply-btn-${q.id}`}
                  onClick={() => { setReplyFor(q.id); setReplyText(""); }}
                  className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border text-xs hover:bg-secondary transition-colors"
                >
                  <Send className="w-3 h-3" /> Reply
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

export default function DefensibilityDashboard({ data, sourceStatus, isAdmin }) {
  const connectors = data?.connectorHealth?.connectors || [];
  const summary = data?.connectorHealth?.summary || {};

  return (
    <div className="space-y-5">
      {isAdmin && <AuditorRoomCard />}
      {isAdmin && <AuditorQuestionsCard />}

      <div className="grid xl:grid-cols-3 gap-5">
        <Panel
          title="Data source status"
          subtitle="Unavailable sources are surfaced rather than replaced with synthetic data."
          testid="agentic-source-status"
        >
          <div className="space-y-2">
            {Object.entries(sourceStatus || {}).map(([key, status]) => (
              <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="flex items-center gap-2 min-w-0">
                  {status.ok ? (
                    <CheckCircle2 className="w-4 h-4 text-low shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-crit shrink-0" />
                  )}
                  <div>
                    <div className="text-sm font-medium">{SOURCE_LABEL[key] || key}</div>
                    {!status.ok && <div className="text-[10px] text-muted-foreground">{status.error}</div>}
                  </div>
                </div>
                <span className={`text-[10px] font-mono ${status.ok ? "text-low" : "text-crit"}`}>
                  {status.ok ? "LIVE" : "UNAVAILABLE"}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Evidence classification"
          subtitle="The app explicitly separates source facts from derived intelligence."
          testid="agentic-evidence-class"
        >
          <div className="space-y-4">
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="FACT" />
              <p className="text-xs text-muted-foreground mt-2">
                Agent inventory, tools, permissions, guardrails, governance status, AI systems, incidents, usage analytics and connector health returned by the existing backend.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="MODELLED" />
              <p className="text-xs text-muted-foreground mt-2">
                Agent risk score, delegated authority tier and action-capable tool classification calculated in the browser from existing records.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="HEURISTIC BASELINE" />
              <p className="text-xs text-muted-foreground mt-2">
                Existing red-team results are deterministic checks against recorded guardrails. They are not live adversarial runtime tests.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="AI RECOMMENDATION" />
              <p className="text-xs text-muted-foreground mt-2">
                Obserra Advisor interpretation, analysis and recommended executive actions.
              </p>
            </div>
          </div>
        </Panel>

        <Panel
          title="Runtime enforcement boundary"
          subtitle="Governance state is not confused with external runtime control."
          testid="agentic-runtime-boundary"
        >
          <div className="space-y-3 text-sm">
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Toggling a guardrail updates the existing Obserra governance record.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Sanctioning a system updates its governance status in Obserra.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              A Suspend / Kill is dispatched to the external agent runtime when an agent-runtime webhook is connected (HMAC-signed, retried) — the runtime receipt is recorded; otherwise it is enforced in the control plane only.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Future live red-team capabilities require explicit runtime connectors.
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        title="Connector health context"
        subtitle={`${summary.healthy || 0} healthy · ${summary.degraded || 0} degraded. Existing connector health only.`}
        testid="agentic-connectors"
      >
        {connectors.length === 0 ? (
          <div className="py-8 text-center">
            <Database className="w-8 h-8 text-muted-foreground mx-auto" />
            <div className="text-sm text-muted-foreground mt-2">No connector health records are available.</div>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {connectors.map((connector) => (
              <div key={`${connector.id}:${connector.name}`} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="font-head font-bold text-sm">{connector.name}</div>
                    <div className="text-[10px] text-muted-foreground mt-1">{connector.category}</div>
                  </div>
                  <span className={`text-[10px] font-mono ${connector.health === "healthy" ? "text-low" : connector.health === "degraded" ? "text-high" : "text-muted-foreground"}`}>
                    {connector.health || connector.state || "unknown"}
                  </span>
                </div>
                <div className="text-[10px] text-muted-foreground mt-3">
                  Last checked: {connector.checked_at ? new Date(connector.checked_at).toLocaleString() : "not available"}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
