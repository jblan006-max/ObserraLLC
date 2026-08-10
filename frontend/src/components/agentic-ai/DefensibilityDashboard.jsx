import { useEffect, useState } from "react";
import { Activity, CheckCircle2, Clock, Copy, Database, DoorOpen, Download, Eye, FileText, Loader2, MessageSquare, Paperclip, Plus, RefreshCw, Send, Settings2, ShieldCheck, Terminal, Trash2, X, XCircle, Zap } from "lucide-react";
import { toast } from "sonner";
import { DataClassBadge, Panel } from "@/components/agentic-ai/shared";
import { api } from "@/lib/api";

const SOURCE_LABEL = { agents: "AI Agent Governance", analytics: "AI Analytics", systems: "AI System Inventory", incidents: "AI Incidents", workflows: "Workflow Engine", connectorHealth: "Connector Health" };
const fmtDT = (s) => (s ? new Date(s).toLocaleDateString(undefined, { dateStyle: "medium" }) : "—");
const fmtDTT = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const copyText = async (t) => { try { await navigator.clipboard.writeText(t); toast.success("Copied"); } catch { toast.error("Copy failed"); } };
const BACKEND = process.env.REACT_APP_BACKEND_URL;

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

function AccessLog({ token }) {
  const [log, setLog] = useState(null);
  useEffect(() => { api.get(`/agents/runtime/evidence-room/${token}/access-log`).then(({ data }) => setLog(data)).catch(() => setLog({ access: [] })); }, [token]);
  if (!log) return <div className="p-3 flex justify-center"><Loader2 className="w-4 h-4 animate-spin text-ai" /></div>;
  return (
    <div className="mt-2 rounded-lg border border-border bg-background/40 p-2.5" data-testid={`access-log-${token}`}>
      <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">Chain of custody — {log.opens} open(s) · {log.downloads} download(s)</div>
      {(!log.access || log.access.length === 0) ? (
        <div className="text-xs text-muted-foreground">No access recorded yet.</div>
      ) : (
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {log.access.map((a, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              {a.kind === "download" ? <Download className="w-3 h-3 text-ai shrink-0" /> : <Eye className="w-3 h-3 text-muted-foreground shrink-0" />}
              <span className="font-medium">{a.kind === "download" ? (a.who || "download") : "opened"}</span>
              <span className="text-muted-foreground">{a.ip || ""}</span>
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
            <button data-testid="auditor-room-create-btn" onClick={create} disabled={busy} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Create auditor room</button>
          </div>
        }
      >
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
                  <span className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1"><Eye className="w-3 h-3" /> {room.opens}</span>
                  <span className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1"><Download className="w-3 h-3" /> {room.downloads || 0}</span>
                  <div className="ml-auto flex items-center gap-1.5">
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

function GovernanceSettingsCard() {
  const [s, setS] = useState(null);
  const [recips, setRecips] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { api.get("/agents/runtime/governance-settings").then(({ data }) => { setS(data); setRecips((data.board_digest_recipients || []).join(", ")); }).catch(() => {}); }, []);
  if (!s) return null;
  const saveAll = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/agents/runtime/governance-settings", {
        board_digest_day: Number(s.board_digest_day) || 1,
        board_digest_recipients: recips.split(",").map((x) => x.trim()).filter(Boolean),
        board_digest_enabled: !!s.board_digest_enabled,
        auditor_question_sla_hours: Number(s.auditor_question_sla_hours) || 48,
        auditor_question_escalation_hours: Number(s.auditor_question_escalation_hours) || 96,
        auditor_question_escalation_to: s.auditor_question_escalation_to || "",
      });
      setS(data); setRecips((data.board_digest_recipients || []).join(", ")); toast.success("Governance settings saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed."); }
    finally { setSaving(false); }
  };
  const fld = "mt-1.5 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary";
  const lbl = "text-[11px] font-mono uppercase tracking-wider text-muted-foreground";
  return (
    <Panel title="Governance settings" subtitle="Board-digest schedule + recipients, and the auditor-question response SLA + second-approver escalation." testid="agentic-governance-settings"
      actions={<button data-testid="gov-save" onClick={saveAll} disabled={saving} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Settings2 className="w-3.5 h-3.5" />} Save</button>}>
      <div className="grid md:grid-cols-2 gap-4">
        <label className="block"><span className={lbl}>Board digest — day of month</span><input data-testid="gov-digest-day" type="number" min={1} max={28} value={s.board_digest_day} onChange={(e) => setS({ ...s, board_digest_day: e.target.value })} className={fld} /></label>
        <label className="block"><span className={lbl}>Auditor-question SLA (hours)</span><input data-testid="gov-sla-hours" type="number" min={1} max={720} value={s.auditor_question_sla_hours} onChange={(e) => setS({ ...s, auditor_question_sla_hours: e.target.value })} className={fld} /></label>
        <label className="block"><span className={lbl}>Escalation after (hours)</span><input data-testid="gov-escalation-hours" type="number" min={1} max={2160} value={s.auditor_question_escalation_hours} onChange={(e) => setS({ ...s, auditor_question_escalation_hours: e.target.value })} className={fld} /></label>
        <label className="block"><span className={lbl}>Escalate to (second approver email — blank = executives)</span><input data-testid="gov-escalation-to" value={s.auditor_question_escalation_to || ""} onChange={(e) => setS({ ...s, auditor_question_escalation_to: e.target.value })} placeholder="ciso@company.com" className={fld} /></label>
        <label className="block md:col-span-2"><span className={lbl}>Board digest recipients (comma-separated emails — blank = all admins &amp; execs)</span><input data-testid="gov-digest-recipients" value={recips} onChange={(e) => setRecips(e.target.value)} placeholder="board@company.com, ciso@company.com" className={fld} /></label>
        <label className="flex items-center gap-2 md:col-span-2 cursor-pointer"><input data-testid="gov-digest-enabled" type="checkbox" checked={!!s.board_digest_enabled} onChange={(e) => setS({ ...s, board_digest_enabled: e.target.checked })} className="w-4 h-4 accent-ai" /><span className="text-sm">Send the monthly board evidence digest automatically</span></label>
      </div>
    </Panel>
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
  const open = comments.filter((c) => c.status !== "Resolved").length;
  const overdue = comments.filter((c) => c.overdue).length;
  const escalated = comments.filter((c) => c.escalated).length;

  return (
    <Panel title="Auditor questions" subtitle="A two-way audit workspace — auditors' questions, your threaded replies (optionally with the signed evidence PDF), SLA + second-approver escalation, and status. The full Q&A trail is exported into the board digest." testid="agentic-auditor-questions"
      actions={<div className="flex items-center gap-1.5">{sla != null && <span className="text-[10px] font-mono px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">SLA {sla}h</span>}{escalated > 0 && <span data-testid="auditor-questions-escalated" className="text-[10px] font-mono px-2 py-1 rounded-full bg-crit/15 text-crit">{escalated} escalated</span>}{overdue > 0 && <span data-testid="auditor-questions-overdue" className="text-[10px] font-mono px-2 py-1 rounded-full bg-crit/10 text-crit">{overdue} overdue</span>}<span className="text-[10px] font-mono px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">{open} open</span></div>}>
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
  const testPing = async () => {
    setTesting(true); setResult(null);
    try { const { data } = await api.post("/agents/runtime/webhook/test"); setResult(data); if (data.ok) toast.success(`Runtime received the test enforcement — HTTP ${data.status_code} · ${data.latency_ms}ms`); else toast.error(`No 2xx from runtime — ${data.status_code || data.error || "unreachable"}`); }
    catch (e) { setResult({ ok: false, error: e.response?.data?.detail || "failed" }); toast.error(e.response?.data?.detail || "No agent runtime webhook configured."); }
    finally { setTesting(false); }
  };
  return (
    <Panel title="Runtime enforcement playbooks" subtitle="Obserra dispatches this signed webhook on every Suspend / Kill / Resume. Use a per-provider adapter to map it to your agent runtime's stop API, then send a test enforcement to confirm it lands." testid="agentic-runtime-playbooks">
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
                  <div className="flex items-center justify-between mb-1"><span className="text-[10px] font-mono uppercase text-muted-foreground">adapter</span><button data-testid={`playbook-copy-${p.id}`} onClick={() => copyText(p.example)} className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-border text-[10px] hover:bg-secondary"><Copy className="w-3 h-3" /> Copy</button></div>
                  <pre className="text-[11px] font-mono whitespace-pre-wrap overflow-x-auto">{p.example}</pre>
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

export default function DefensibilityDashboard({ data, sourceStatus, isAdmin }) {
  const connectors = data?.connectorHealth?.connectors || [];
  const summary = data?.connectorHealth?.summary || {};
  return (
    <div className="space-y-5">
      {isAdmin && <AuditorRoomCard />}
      {isAdmin && <GovernanceSettingsCard />}
      {isAdmin && <AuditorQuestionsCard />}
      {isAdmin && <RuntimePlaybooksCard />}

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
