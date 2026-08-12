import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Siren, ShieldCheck, Clock3, AlertTriangle, Gavel, Landmark, Loader2, RefreshCw, Activity } from "lucide-react";

const SEV = {
  Critical: "0 84% 60%",
  High: "15 80% 55%",
  Medium: "35 90% 55%",
  Low: "142 70% 45%",
};
const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const money = (n) => (n == null ? null : n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}k` : `$${Math.round(n)}`);

function timeLeft(iso) {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  const past = ms < 0;
  const a = Math.abs(ms);
  const h = Math.floor(a / 3.6e6);
  const m = Math.floor((a % 3.6e6) / 6e4);
  const label = h >= 24 ? `${Math.floor(h / 24)}d ${h % 24}h` : `${h}h ${m}m`;
  return { label, past };
}

export default function CrisisSnapshot() {
  const { token } = useParams();
  const [snap, setSnap] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/crisis/public/snapshot/${token}`);
      setSnap(data);
      setError(null);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(e?.response?.data?.detail || "This snapshot link is invalid or has expired.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [load]);

  if (loading) return <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-ai" /></div>;
  if (error) return (
    <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center p-6" data-testid="crisis-snapshot-error">
      <div className="max-w-md text-center space-y-3"><AlertTriangle className="w-10 h-10 mx-auto text-crit" /><h1 className="font-head font-black text-2xl">Snapshot unavailable</h1><p className="text-sm text-white/60">{error}</p></div>
    </div>
  );

  const c = snap.case || {};
  const sev = SEV[c.severity] || "190 80% 50%";
  const fin = money(c.financial_exposure);
  return (
    <div className="min-h-screen bg-[#050810] text-white" data-testid="crisis-snapshot" style={{ ["--sev"]: sev }}>
      <div className="max-w-2xl mx-auto px-5 py-8 space-y-6">
        <header className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/40">{snap.org_name} · Board Crisis Snapshot</span>
            <span className="inline-flex items-center gap-1.5 text-[10px] font-mono text-ai"><Activity className="w-3 h-3" />LIVE</span>
          </div>
          <div className="flex items-start gap-3">
            <Siren className="w-7 h-7 shrink-0" style={{ color: `hsl(${sev})` }} />
            <div>
              <div className="text-[11px] font-mono text-white/40">{c.ref}</div>
              <h1 className="font-head font-black text-2xl sm:text-3xl tracking-tight leading-tight" data-testid="crisis-snapshot-title">{c.title}</h1>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            <span className="px-2 py-1 rounded-full text-[10px] font-mono uppercase font-bold" style={{ background: `hsl(${sev} / 0.15)`, color: `hsl(${sev})`, border: `1px solid hsl(${sev} / 0.4)` }}>{c.severity} severity</span>
            <span className="px-2 py-1 rounded-full text-[10px] font-mono uppercase bg-white/5 border border-white/10 text-white/70">{c.status}</span>
            <span className="px-2 py-1 rounded-full text-[10px] font-mono uppercase bg-white/5 border border-white/10 text-white/70">Phase: {c.phase}</span>
          </div>
          <p className="text-xs text-white/40">Started {fmtDT(c.started_at)} · Updated {fmtDT(c.updated_at)}{updatedAt ? ` · refreshed ${updatedAt.toLocaleTimeString()}` : ""}</p>
        </header>

        {c.summary && <p className="text-sm text-white/70 leading-relaxed bg-white/[0.03] border border-white/10 rounded-xl p-4" data-testid="crisis-snapshot-summary">{c.summary}</p>}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="Contained" value={`${snap.contained_pct ?? 0}%`} accent={sev} testid="crisis-snapshot-contained" />
          <Stat label="Pending decisions" value={snap.counts?.pending_decisions ?? 0} testid="crisis-snapshot-pending" />
          <Stat label="Open actions" value={snap.counts?.open_actions ?? 0} />
          <Stat label="Financial exposure" value={fin || "—"} />
        </div>

        <Section icon={Gavel} title="Executive decisions awaiting approval" testid="crisis-snapshot-decisions">
          {(snap.pending_decisions || []).length === 0 ? (
            <Empty text="No decisions are currently awaiting executive approval." />
          ) : snap.pending_decisions.map((d, i) => {
            const t = timeLeft(d.due_at);
            return (
              <div key={i} className="bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="font-head font-bold text-sm">{d.title}</div>
                  {t && <span className={`shrink-0 text-[10px] font-mono px-2 py-0.5 rounded-full ${t.past ? "bg-crit/20 text-crit" : "bg-white/5 text-white/60"}`}>{t.past ? "SLA breached" : `SLA ${t.label}`}</span>}
                </div>
                <div className="text-[11px] text-white/40 mt-0.5">Owner: {d.owner || "Unassigned"} · {d.priority}{d.business_impact ? ` · ${d.business_impact}` : ""}</div>
              </div>
            );
          })}
        </Section>

        <Section icon={Clock3} title="Latest timeline" testid="crisis-snapshot-timeline">
          {(snap.timeline || []).length === 0 ? <Empty text="No timeline events yet." /> : (
            <ol className="space-y-2">{snap.timeline.map((e, i) => {
              const s = SEV[e.severity] || "190 80% 50%";
              return (
                <li key={i} className="flex items-start gap-3">
                  <span className="mt-1.5 w-2 h-2 rounded-full shrink-0" style={{ background: `hsl(${s})` }} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{e.title}</div>
                    <div className="text-[10px] font-mono text-white/40">{e.kind} · {e.source} · {fmtDT(e.occurred_at)}</div>
                  </div>
                </li>
              );
            })}</ol>
          )}
        </Section>

        <Section icon={Landmark} title="Regulatory timers" testid="crisis-snapshot-regulatory">
          {(snap.regulatory || []).length === 0 ? <Empty text="No regulatory obligations tracked for this incident." /> : snap.regulatory.map((o, i) => {
            const t = timeLeft(o.deadline_at);
            return (
              <div key={i} className="flex items-center justify-between gap-3 bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2">
                <div className="min-w-0"><div className="text-sm font-medium truncate">{o.regulation}</div><div className="text-[10px] font-mono text-white/40">{o.jurisdiction} · {o.status}</div></div>
                {t && <span className={`shrink-0 text-[10px] font-mono px-2 py-0.5 rounded-full ${t.past ? "bg-crit/20 text-crit" : "bg-high/15 text-high"}`}>{t.past ? "overdue" : t.label}</span>}
              </div>
            );
          })}
        </Section>

        <footer className="pt-2 text-center text-[10px] font-mono text-white/30 flex items-center justify-center gap-1.5">
          <ShieldCheck className="w-3 h-3" />Read-only live snapshot · Obserra Cyber Crisis Commander · link expires {fmtDT(snap.expires_at)}
        </footer>
      </div>
    </div>
  );
}

const Stat = ({ label, value, accent, testid }) => (
  <div className="bg-white/[0.03] border border-white/10 rounded-xl px-3 py-3" data-testid={testid}>
    <div className="text-[9px] font-mono uppercase tracking-widest text-white/40">{label}</div>
    <div className="font-head font-black text-xl mt-1" style={accent ? { color: `hsl(${accent})` } : undefined}>{value}</div>
  </div>
);

const Section = ({ icon: Icon, title, children, testid }) => (
  <section className="space-y-2" data-testid={testid}>
    <h2 className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-white/50"><Icon className="w-3.5 h-3.5" />{title}</h2>
    <div className="space-y-2">{children}</div>
  </section>
);

const Empty = ({ text }) => <div className="text-xs text-white/40 bg-white/[0.02] border border-white/10 rounded-lg px-3 py-3">{text}</div>;
