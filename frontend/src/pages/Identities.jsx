import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Users, ShieldAlert, KeyRound, ShieldCheck } from "lucide-react";

const RATE = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "190 90% 50%", Low: "142 70% 45%" };
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—");
const Chip = ({ v }) => <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${RATE[v] || "220 10% 55%"} / 0.15)`, color: `hsl(${RATE[v] || "220 10% 55%"})` }}>{v}</span>;

export default function Identities() {
  const [d, setD] = useState(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [le, setLe] = useState("all");
  const [rating, setRating] = useState("all");
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const load = useCallback(async () => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (status !== "all") p.set("status", status);
    if (le !== "all") p.set("legal_entity", le);
    if (rating !== "all") p.set("rating", rating);
    const { data } = await api.get(`/sap/identities?${p.toString()}`);
    setD(data);
  }, [q, status, le, rating]);
  useEffect(() => { load(); }, [load]);

  const open = async (ref) => {
    setLoadingDetail(true); setDetail({ loading: true });
    try { const { data } = await api.get(`/sap/identities/${ref}`); setDetail(data); }
    catch { setDetail(null); }
    setLoadingDetail(false);
  };

  if (!d) return <Spinner />;

  return (
    <div className="space-y-6" data-testid="identities-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="identities-title">Identities</h1>
        <p className="text-sm text-muted-foreground mt-1">Canonical identities correlated across ADP / IZ8 / AD / Entra / SAP with live access-risk scoring.</p>
      </div>

      <div className="bg-card fact-border rounded-xl">
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background/50 px-2.5 h-9 flex-1 min-w-[180px]">
            <Search className="w-3.5 h-3.5 text-muted-foreground" />
            <input data-testid="id-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email, ref…" className="bg-transparent text-sm outline-none w-full" />
          </div>
          <Select value={rating} onValueChange={setRating}><SelectTrigger data-testid="id-filter-rating" className="w-[130px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All ratings</SelectItem><SelectItem value="Critical">Critical</SelectItem><SelectItem value="High">High</SelectItem><SelectItem value="Medium">Medium</SelectItem><SelectItem value="Low">Low</SelectItem></SelectContent></Select>
          <Select value={status} onValueChange={setStatus}><SelectTrigger data-testid="id-filter-status" className="w-[130px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All statuses</SelectItem><SelectItem value="Active">Active</SelectItem><SelectItem value="Leave">Leave</SelectItem><SelectItem value="Terminated">Terminated</SelectItem></SelectContent></Select>
          <Select value={le} onValueChange={setLe}><SelectTrigger data-testid="id-filter-le" className="w-[130px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All entities</SelectItem>{d.legal_entities.map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent></Select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="id-table">
            <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
              <th className="p-3">Risk</th><th className="p-3">Name</th><th className="p-3">Dept</th><th className="p-3">Type</th><th className="p-3">Entity</th><th className="p-3">Accounts</th><th className="p-3">SoD</th><th className="p-3">Status</th><th className="p-3">MFA</th>
            </tr></thead>
            <tbody>
              {d.identities.map((r) => (
                <tr key={r.ref} onClick={() => open(r.ref)} className="border-b border-border/50 hover:bg-secondary/40 cursor-pointer" data-testid={`id-row-${r.ref}`}>
                  <td className="p-3"><span className="font-head font-black text-lg" style={{ color: `hsl(${RATE[r.rating]})` }}>{r.score}</span></td>
                  <td className="p-3"><div className="font-medium">{r.name}</div><div className="text-[10px] font-mono text-muted-foreground">{r.ref} · {r.email}</div></td>
                  <td className="p-3 text-xs">{r.department}</td>
                  <td className="p-3 text-xs">{r.worker_type}</td>
                  <td className="p-3 text-xs font-mono">{r.legal_entity}</td>
                  <td className="p-3 text-xs">{r.accounts}</td>
                  <td className="p-3 text-xs">{r.open_conflicts > 0 ? <span className="text-crit font-semibold">{r.open_conflicts}</span> : "0"}</td>
                  <td className="p-3"><Chip v={r.status === "Terminated" ? "Critical" : r.status === "Leave" ? "Medium" : "Low"} />{" "}<span className="text-[10px] text-muted-foreground">{r.status}</span></td>
                  <td className="p-3 text-xs">{r.mfa ? <span className="text-low">✓</span> : <span className="text-crit">✕</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-3xl max-h-[86vh] overflow-y-auto" data-testid="id-detail">
          {loadingDetail || detail?.loading ? <div className="py-16"><Spinner /></div> : detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  <span className="font-head font-black text-2xl" style={{ color: `hsl(${RATE[detail.risk.rating]})` }}>{detail.risk.score}</span>
                  {detail.person.name} <Chip v={detail.risk.rating} />
                </DialogTitle>
              </DialogHeader>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm mb-4">
                <div><span className="text-muted-foreground text-xs">Department</span><div>{detail.person.department} · {detail.person.job_title}</div></div>
                <div><span className="text-muted-foreground text-xs">Employment</span><div>{detail.person.status} · {detail.person.worker_type}</div></div>
                <div><span className="text-muted-foreground text-xs">Legal entity</span><div>{detail.person.legal_entity_name} ({detail.person.country})</div></div>
                <div><span className="text-muted-foreground text-xs">HR authority</span><div>{detail.person.hr_authority} · match {Math.round(detail.person.match_confidence * 100)}%</div></div>
              </div>

              <Section title="Access Risk Factors" icon={ShieldAlert}>
                <div className="space-y-1.5">{detail.risk.factors.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm"><span className="font-mono text-crit w-8">+{f.points}</span><span className="font-medium w-40 shrink-0">{f.factor}</span><span className="text-muted-foreground text-xs">{f.detail}</span></div>
                ))}{detail.risk.factors.length === 0 && <p className="text-xs text-muted-foreground">No elevated risk factors.</p>}</div>
              </Section>

              <Section title={`SAP Accounts (${detail.accounts.length})`} icon={KeyRound}>
                {detail.accounts.map((a) => (
                  <div key={a.ref} className="p-2.5 rounded-lg bg-secondary/30 mb-2">
                    <div className="flex items-center justify-between text-sm"><span className="font-mono">{a.sap_user} <span className="text-muted-foreground">· {a.system}/{a.client}</span></span><span className="text-[10px] text-muted-foreground">{a.lock_state} · last login {fmtDate(a.last_login)}</span></div>
                    <div className="flex flex-wrap gap-1 mt-1.5">{a.roles.map((r) => <span key={r.ref} className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${r.functions.length ? "bg-secondary" : "bg-secondary/50 text-muted-foreground"}`} title={r.functions.join(", ")}>{r.name}</span>)}</div>
                  </div>
                ))}
              </Section>

              {detail.sod_conflicts.length > 0 && (
                <Section title={`SoD Conflicts (${detail.sod_conflicts.length})`} icon={ShieldAlert}>
                  {detail.sod_conflicts.map((c) => (
                    <div key={c.conflict_ref} className="flex items-center gap-2 text-sm mb-1"><Chip v={c.severity} />{c.rule_name} <span className="text-[10px] text-muted-foreground">({c.a_via_roles.join(",")} ✕ {c.b_via_roles.join(",")})</span></div>
                  ))}
                </Section>
              )}

              <Section title={`HR Provenance & Reconciliation · ${detail.hr_state}`} icon={ShieldCheck}>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <HrCol title="ADP" rec={detail.hr_sources.adp} />
                  <HrCol title="IZ8 HR" rec={detail.hr_sources.iz8} />
                </div>
                {detail.hr_conflicts.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {detail.hr_conflicts.map((c, i) => (
                      <div key={i} className="text-xs flex items-center gap-2"><span className={`font-mono px-1.5 py-0.5 rounded ${c.security_hold ? "bg-crit/15 text-crit" : "bg-amber/15 text-amber"}`}>{c.state}</span><span className="font-medium">{c.field}:</span> ADP=<span className="font-mono">{String(c.adp_value)}</span> vs IZ8=<span className="font-mono">{String(c.iz8_value)}</span></div>
                    ))}
                  </div>
                )}
              </Section>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

const Section = ({ title, icon: Icon, children }) => (
  <div className="mb-4 border-t border-border pt-3">
    <div className="flex items-center gap-2 mb-2">{Icon && <Icon className="w-4 h-4 text-primary" />}<h3 className="font-head font-bold text-sm">{title}</h3></div>
    {children}
  </div>
);
const HrCol = ({ title, rec }) => (
  <div className="rounded-lg bg-secondary/30 p-2.5">
    <div className="font-mono text-[10px] uppercase text-muted-foreground mb-1">{title} · {rec.source_id}</div>
    {["employment_status", "termination_date", "manager", "legal_entity", "worker_type"].map((f) => (
      <div key={f} className="flex justify-between"><span className="text-muted-foreground">{f}</span><span className="font-mono">{String(rec[f] ?? "—")}</span></div>
    ))}
  </div>
);
