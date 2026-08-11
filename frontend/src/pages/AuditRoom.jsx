import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { ShieldCheck, Bot, Ban, PauseCircle, PlayCircle, FileText, AlertTriangle, Loader2, MessageSquare, Send, CheckCircle2, Paperclip, BadgeCheck, Bell } from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const STATUS_TONE = { killed: "0 84% 60%", restricted: "35 90% 55%", sanctioned: "142 70% 45%", shadow: "0 84% 60%" };

function Thread({ token, q, onPosted }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const msgs = q.messages && q.messages.length ? q.messages : [{ role: "auditor", by: q.author, text: q.text, at: q.at }, ...(q.reply ? [{ role: "admin", by: "Governance team", text: q.reply, at: q.reply_at }] : [])];
  const post = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try { await api.post(`/agents/public/evidence-room/${token}/comment/${q.id}/message`, { author: q.author, text }); setText(""); setOpen(false); onPosted(); }
    catch { /* inline */ } finally { setBusy(false); }
  };
  return (
    <div data-testid={`audit-room-thread-${q.id}`} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-center gap-2 flex-wrap mb-2">
        <span className="font-head font-bold text-sm">{q.author || "External auditor"}</span>
        <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: q.status === "Resolved" ? "hsl(142 70% 45% / 0.15)" : q.status === "Answered" ? "hsl(190 90% 55% / 0.15)" : "hsl(35 90% 55% / 0.15)", color: q.status === "Resolved" ? "hsl(142 70% 45%)" : q.status === "Answered" ? "hsl(190 90% 55%)" : "hsl(35 90% 55%)" }}>{q.status || "Open"}</span>
      </div>
      <div className="space-y-1.5">
        {msgs.map((m, i) => {
          const admin = m.role === "admin";
          return (
            <div key={i} className={`rounded-md p-2 text-sm ${admin ? "bg-ai/10 border-l-2 border-ai/50 ml-4" : "bg-white/[0.04]"}`}>
              <div className="text-[10px] font-mono uppercase tracking-wider text-white/40 flex items-center gap-1.5">
                {admin ? <ShieldCheck className="w-3 h-3 text-ai" /> : <MessageSquare className="w-3 h-3" />}
                {admin ? "Governance reply" : m.by || "Auditor"} · {fmtDT(m.at)}
                {m.attachment && <span className="inline-flex items-center gap-1 text-ai"><Paperclip className="w-3 h-3" /> {m.attachment}</span>}
              </div>
              <p className="text-white/80 mt-1">{m.text}</p>
            </div>
          );
        })}
      </div>
      {open ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input data-testid={`audit-room-followup-input-${q.id}`} autoFocus value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") post(); }} placeholder="Add a follow-up…" className="flex-1 min-w-[200px] bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2 text-sm outline-none focus:border-ai/60" />
          <button data-testid={`audit-room-followup-send-${q.id}`} onClick={post} disabled={busy || !text.trim()} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-ai text-[#050810] font-head font-bold text-sm disabled:opacity-40">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Send</button>
          <button onClick={() => { setOpen(false); setText(""); }} className="px-2 py-2 rounded-lg border border-white/10 text-xs text-white/50">Cancel</button>
        </div>
      ) : (
        <button data-testid={`audit-room-followup-btn-${q.id}`} onClick={() => setOpen(true)} className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-mono text-ai underline"><Send className="w-3 h-3" /> Add a follow-up</button>
      )}
    </div>
  );
}

export default function AuditRoom() {
  const { token } = useParams();
  const [snap, setSnap] = useState(null);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dlName, setDlName] = useState("");
  const [comments, setComments] = useState([]);
  const [cName, setCName] = useState("");
  const [cEmail, setCEmail] = useState("");
  const [cText, setCText] = useState("");
  const [cPriority, setCPriority] = useState("normal");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [sha, setSha] = useState("");
  const [integrity, setIntegrity] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [subEmail, setSubEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);
  const [subBusy, setSubBusy] = useState(false);

  const loadComments = () => api.get(`/agents/public/evidence-room/${token}/comments`).then(({ data }) => setComments(data.comments || [])).catch(() => {});
  useEffect(() => {
    api.get(`/agents/public/evidence-room/${token}`)
      .then(({ data }) => { setSnap(data.snapshot); setMeta({ created_at: data.created_at, expires_at: data.expires_at }); setSha(data.snapshot_sha256 || ""); setSubscribed(!!data.digest_subscribed); })
      .catch((e) => setError(e?.response?.data?.detail || "This auditor room link is invalid or has expired."))
      .finally(() => setLoading(false));
    loadComments();
  }, [token]);

  const verifyIntegrity = async () => {
    setVerifying(true);
    try { const { data } = await api.get(`/agents/public/evidence-room/${token}/integrity`); setIntegrity(data); }
    catch { setIntegrity({ verified: false, error: true }); }
    finally { setVerifying(false); }
  };

  const subscribeDigest = async () => {
    if (!subEmail.trim() || !subEmail.includes("@")) return;
    setSubBusy(true);
    try { await api.post(`/agents/public/evidence-room/${token}/subscribe`, { email: subEmail }); setSubscribed(true); setSubEmail(""); }
    catch { /* inline */ } finally { setSubBusy(false); }
  };

  const pdfUrl = `${process.env.REACT_APP_BACKEND_URL}/api/agents/public/evidence-room/${token}/pack.pdf${dlName ? `?who=${encodeURIComponent(dlName)}` : ""}`;

  const submitQuestion = async () => {
    if (!cText.trim()) return;
    setSubmitting(true);
    try { await api.post(`/agents/public/evidence-room/${token}/comment`, { author: cName, email: cEmail, text: cText, priority: cPriority }); setCText(""); setCPriority("normal"); setSent(true); loadComments(); }
    catch { /* inline */ } finally { setSubmitting(false); }
  };

  if (loading) return <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-ai" /></div>;
  if (error) return (
    <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center p-6" data-testid="audit-room-error">
      <div className="max-w-md text-center space-y-3"><AlertTriangle className="w-10 h-10 mx-auto text-crit" /><h1 className="font-head font-black text-2xl">Auditor room unavailable</h1><p className="text-sm text-white/60">{error}</p></div>
    </div>
  );

  const c = snap.counts || {};
  return (
    <div className="min-h-screen bg-[#050810] text-white" data-testid="audit-room">
      <div className="max-w-4xl mx-auto px-5 py-10 space-y-8">
        <header className="space-y-2">
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/40">OBSERRA · READ-ONLY AUDITOR ROOM</span>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight">AI Enforcement Evidence Pack</h1>
          <p className="text-sm text-white/60">{snap.org_name || "Organization"} · generated {fmtDT(snap.generated_at)} · link expires {fmtDT(meta?.expires_at)}</p>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <input data-testid="audit-room-dl-name" value={dlName} onChange={(e) => setDlName(e.target.value)} placeholder="Your name (stamped on the PDF)" className="bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-ai/60 w-56" />
            <a href={pdfUrl} data-testid="audit-room-download" className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ai text-[#050810] font-head font-bold text-sm hover:opacity-90 transition-opacity"><FileText className="w-4 h-4" /> Download signed PDF</a>
            <button data-testid="audit-room-verify" onClick={verifyIntegrity} disabled={verifying} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-white/15 text-sm font-head font-bold hover:bg-white/[0.06] transition-colors disabled:opacity-50">{verifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <BadgeCheck className="w-4 h-4 text-ai" />} Verify integrity</button>
            {integrity && (integrity.verified
              ? <span data-testid="audit-room-integrity-ok" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-head font-bold" style={{ background: "hsl(142 70% 45% / 0.14)", color: "hsl(142 70% 55%)" }}><BadgeCheck className="w-4 h-4" /> Untampered · {integrity.short}</span>
              : <span data-testid="audit-room-integrity-bad" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-head font-bold" style={{ background: "hsl(0 84% 60% / 0.14)", color: "hsl(0 84% 66%)" }}><AlertTriangle className="w-4 h-4" /> Altered — do not rely</span>)}
          </div>
          <p className="text-[11px] text-white/30">Each download is watermarked with your name + timestamp, a QR back to this live room, and a "Verified by Obserra" integrity seal. Click <span className="text-white/50">Verify integrity</span> to re-hash the evidence live (SHA-256){sha ? ` · ${sha.slice(0, 12)}` : ""}.</p>
        </header>

        <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4" data-testid="audit-room-attestation">
          <div className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-1.5 flex items-center gap-1.5"><ShieldCheck className="w-3 h-3" /> Attestation</div>
          <p className="text-sm text-white/80">Runtime connector: <span className="text-ai font-mono">{snap.connector}</span>. Every enforcement below carries an immutable runtime receipt written to the Defensibility Ledger.</p>
        </section>

        <section className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="audit-room-counts">
          {[{ label: "Governed agents", value: c.agents || 0, tone: "190 90% 55%" }, { label: "Toxic", value: c.toxic || 0, tone: "0 84% 60%" }, { label: "Killed", value: c.killed || 0, tone: "0 84% 60%" }, { label: "Enforcements", value: c.events || 0, tone: "142 70% 45%" }].map((s) => (
            <div key={s.label} className="rounded-xl border border-white/10 bg-white/[0.03] p-4"><div className="font-head font-black text-3xl" style={{ color: `hsl(${s.tone})` }}>{s.value}</div><div className="text-[11px] text-white/50 mt-1">{s.label}</div></div>
          ))}
        </section>

        <section className="space-y-2" data-testid="audit-room-agents">
          <h2 className="font-head font-bold text-lg flex items-center gap-2"><Bot className="w-4 h-4 text-ai" /> AI agent toxicity snapshot</h2>
          <div className="rounded-xl border border-white/10 overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-white/40 border-b border-white/10 bg-white/[0.02]"><th className="p-2.5">Agent</th><th className="p-2.5">Status</th><th className="p-2.5">Toxic combination</th></tr></thead>
              <tbody>
                {(snap.agents || []).map((a) => (
                  <tr key={a.ref} className="border-b border-white/5" data-testid={`audit-room-agent-${a.ref}`}>
                    <td className="p-2.5"><span className="font-head font-bold">{a.name}</span> <span className="font-mono text-[10px] text-white/40">{a.ref}</span></td>
                    <td className="p-2.5"><span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${STATUS_TONE[a.status] || "215 15% 55%"} / 0.15)`, color: `hsl(${STATUS_TONE[a.status] || "215 15% 65%"})` }}>{a.status}</span></td>
                    <td className="p-2.5 text-xs text-white/70">{(a.tool_violations || []).length ? a.tool_violations.join(", ") : "none detected"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-2" data-testid="audit-room-trail">
          <h2 className="font-head font-bold text-lg">Runtime enforcement audit trail</h2>
          {(snap.events || []).length === 0 ? <div className="text-sm text-white/50">No enforcement actions recorded.</div> : (
            <div className="space-y-2">
              {(snap.events || []).map((e, i) => {
                const Icon = e.action === "kill" ? Ban : e.action === "resume" ? PlayCircle : PauseCircle;
                const rc = e.receipt || {};
                const unreachable = e.runtime === "external-webhook" && !e.external_ok;
                return (
                  <div key={i} data-testid={`audit-room-event-${i}`} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Icon className="w-4 h-4 shrink-0 text-ai" />
                      <span className="font-head font-bold">{e.name || e.ref}</span>
                      <span className="font-mono text-[10px] text-ai">{e.verb || e.action}</span>
                      <span className="text-xs text-white/50">· {e.by} · via {e.source}</span>
                      <span className="ml-auto font-mono text-[10px]" style={{ color: unreachable ? "hsl(0 84% 60%)" : "hsl(142 70% 45%)" }}>{e.runtime === "external-webhook" ? (e.external_ok ? "runtime ✓" : "⚠ never reached runtime") : "control-plane"}</span>
                    </div>
                    <div className="text-[11px] font-mono text-white/50 mt-1.5">{fmtDT(e.at)}{rc.status_code != null && ` · HTTP ${rc.status_code} · ${rc.latency_ms}ms · ${rc.attempts} attempt(s) · ${rc.signed ? "signed" : "unsigned"}`}</div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section className="space-y-3" data-testid="audit-room-questions">
          <h2 className="font-head font-bold text-lg flex items-center gap-2"><MessageSquare className="w-4 h-4 text-ai" /> Auditor questions</h2>
          <p className="text-[12px] text-white/50">Ask a read-only question — it lands in the governance team's inbox. Their replies (and any signed evidence attached) appear here, and you can add follow-ups.</p>

          {comments.length > 0 && (
            <div className="space-y-2" data-testid="audit-room-thread">
              {comments.map((q) => <Thread key={q.id} token={token} q={q} onPosted={loadComments} />)}
            </div>
          )}

          {sent ? (
            <div data-testid="audit-room-question-sent" className="rounded-lg border border-low/30 bg-low/5 p-3 flex items-center gap-2 text-sm text-white/80"><CheckCircle2 className="w-4 h-4 text-low" /> Thanks — your question was sent to the governance team.<button className="ml-auto text-[11px] font-mono text-ai underline" onClick={() => setSent(false)}>Ask another</button></div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-2">
              <div className="flex flex-wrap gap-2">
                <input data-testid="audit-room-q-name" value={cName} onChange={(e) => setCName(e.target.value)} placeholder="Your name" className="flex-1 min-w-[160px] bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-ai/60" />
                <input data-testid="audit-room-q-email" value={cEmail} onChange={(e) => setCEmail(e.target.value)} placeholder="Email (optional — for the reply)" className="flex-1 min-w-[160px] bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-ai/60" />
                <select data-testid="audit-room-q-priority" value={cPriority} onChange={(e) => setCPriority(e.target.value)} className="bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-ai/60 text-white/80 cursor-pointer">
                  <option value="low">Low priority</option>
                  <option value="normal">Normal priority</option>
                  <option value="high">High priority</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
              <textarea data-testid="audit-room-q-text" value={cText} onChange={(e) => setCText(e.target.value)} placeholder="Your question about this evidence…" rows={3} className="w-full bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-ai/60 resize-none" />
              <button data-testid="audit-room-q-submit" onClick={submitQuestion} disabled={submitting || !cText.trim()} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ai text-[#050810] font-head font-bold text-sm hover:opacity-90 transition-opacity disabled:opacity-40">{submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Send question</button>
            </div>
          )}
        </section>

        <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4" data-testid="audit-room-subscribe">
          <div className="flex items-center gap-2 mb-1.5"><Bell className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Weekly summary</h2></div>
          {subscribed ? (
            <p data-testid="audit-room-subscribed" className="text-sm text-white/70 flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-low" /> You'll get a weekly email summary of new evidence and answered questions in this room.</p>
          ) : (
            <>
              <p className="text-[12px] text-white/50 mb-2">Get a weekly email summary of new evidence and answered questions in this room. No account needed.</p>
              <div className="flex flex-wrap gap-2">
                <input data-testid="audit-room-sub-email" value={subEmail} onChange={(e) => setSubEmail(e.target.value)} placeholder="you@auditfirm.com" className="flex-1 min-w-[200px] bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-ai/60" />
                <button data-testid="audit-room-sub-btn" onClick={subscribeDigest} disabled={subBusy || !subEmail.includes("@")} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-ai/40 text-ai font-head font-bold text-sm hover:bg-ai/10 transition-colors disabled:opacity-40">{subBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bell className="w-4 h-4" />} Email me weekly</button>
              </div>
            </>
          )}
        </section>

        <footer className="text-center text-[11px] text-white/30 pt-6 border-t border-white/10">Read-only evidence — generated by Obserra Control Intelligence. Link expires {fmtDT(meta?.expires_at)}.</footer>
      </div>
    </div>
  );
}
