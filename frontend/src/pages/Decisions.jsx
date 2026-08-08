import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ConfidenceBadge, DataTypeBadge } from "@/components/badges";
import { AIInsight } from "@/components/AIInsight";
import { StatCard, CardShell, EmptyState, BarList, Spinner } from "@/components/dash";
import { Loader2, GitBranch, CheckCircle2, FileText, Activity, Target, ListChecks, Layers } from "lucide-react";
import { SimulationModal } from "@/components/SimulationModal";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "@/components/ui/dialog";

const ACCENT = "280 82% 64%"; // Decisions → violet

export default function Decisions() {
  const [recs, setRecs] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [riskMap, setRiskMap] = useState({});
  const [an, setAn] = useState(null);
  const [active, setActive] = useState(null);
  const [chosen, setChosen] = useState("");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [simRisk, setSimRisk] = useState(null);

  const load = () => {
    api.get("/recommendations").then((r) => setRecs(r.data));
    api.get("/decisions").then((r) => setDecisions(r.data));
    api.get("/dash/decisions").then((r) => setAn(r.data)).catch(() => setAn(null));
    api.get("/risks").then((r) => {
      const map = {}; r.data.forEach((x) => { map[x.ref] = { residual: x.residual, inherent: x.inherent }; });
      setRiskMap(map);
    });
  };
  useEffect(() => { load(); }, []);

  const decide = async () => {
    if (!chosen.trim()) { toast.error("Pick an option"); return; }
    setBusy(true);
    try {
      await api.post(`/recommendations/${active.ref}/decide`, { rec_ref: active.ref, chosen, rationale });
      toast.success("Decision recorded & audited");
      setActive(null); setChosen(""); setRationale("");
      load();
    } catch { toast.error("Failed to record decision"); }
    setBusy(false);
  };

  if (!recs) return <Spinner />;
  const t = an?.totals || {};
  const cov = an?.coverage || {};

  return (
    <div className="rise space-y-5" data-testid="decisions-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2" style={{ color: `hsl(${ACCENT})` }}><GitBranch className="w-7 h-7" strokeWidth={1.5} /> Recommendations &amp; Decisions</h1>
        <p className="text-sm text-muted-foreground mt-1">Evidence-backed AI recommendations flow into an auditable decision register — options, approvals, rationale &amp; outcomes.</p>
      </div>

      {/* KPI row — always present */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard testid="dec-kpi-recs" label="Recommendations" value={t.recommendations ?? recs.length} accent={ACCENT} sub="AI-generated" />
        <StatCard testid="dec-kpi-pending" label="Pending" value={t.pending ?? 0} accent="35 90% 55%" sub="awaiting decision" />
        <StatCard testid="dec-kpi-decided" label="Decided" value={t.decided ?? 0} accent={ACCENT} sub="approved / deferred" />
        <StatCard testid="dec-kpi-applied" label="Applied" value={t.applied ?? 0} accent="142 70% 45%" sub="executed" />
        <StatCard testid="dec-kpi-decisions" label="Decisions logged" value={t.decisions ?? decisions.length} accent={ACCENT} sub="in register" />
        <StatCard testid="dec-kpi-conf" label="Avg confidence" value={`${Math.round((t.avg_confidence ?? 0) * 100)}%`} accent={ACCENT} sub="model certainty" />
      </div>

      <AIInsight dashboard="Recommendations & Decisions" accent={ACCENT} />

      {/* Analytics cards — always present */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <CardShell testid="dec-status" title="Recommendation pipeline" icon={ListChecks} accent={ACCENT}>
          <BarList items={an?.rec_status || []} accent={ACCENT} empty="No recommendations yet — they generate from live risk & scan findings." />
        </CardShell>
        <CardShell testid="dec-category" title="Recommendations by risk area" icon={Layers} accent={ACCENT}>
          <BarList items={an?.by_category || []} accent={ACCENT} empty="No mapped recommendations yet." />
        </CardShell>
        <CardShell testid="dec-coverage" title="Remediation coverage" icon={Target} accent={ACCENT}>
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="font-head font-black text-5xl tracking-tight" style={{ color: `hsl(${cov.pct >= 70 ? "142 70% 45%" : cov.pct >= 40 ? "35 90% 55%" : "0 84% 60%"})` }}>{cov.pct ?? 0}%</div>
            <div className="text-xs text-muted-foreground mt-2">{cov.covered ?? 0} of {cov.open_risks ?? 0} open risks have an active recommendation</div>
            <div className="w-full h-2 rounded-full bg-secondary/60 overflow-hidden mt-3"><div className="h-full rounded-full" style={{ width: `${cov.pct ?? 0}%`, background: `hsl(${ACCENT})` }} /></div>
          </div>
        </CardShell>
      </div>

      <div>
        <h2 className="font-head font-bold text-lg mb-3">Recommendation engine</h2>
        {recs.length === 0 ? (
          <CardShell testid="dec-recs-empty" title="Recommendation engine" accent={ACCENT}>
            <EmptyState icon={Activity} text="No recommendations yet. Run a live scan or connect a source — the engine proposes evidence-backed fixes here." />
          </CardShell>
        ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {recs.map((r) => (
            <div key={r.ref} data-testid={`rec-${r.ref}`} className="ai-border rounded-lg p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs text-ai">{r.ref} → {r.risk_ref}</span>
                <DataTypeBadge type="ai_recommendation" />
              </div>
              <div className="font-medium mb-2">{r.title}</div>
              <div className="text-xs text-muted-foreground mb-3">{r.predicted_impact}</div>
              <div className="text-[11px] text-muted-foreground mb-3">Evidence: {r.evidence?.join(" · ")}</div>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <ConfidenceBadge value={r.confidence} />
                  <button data-testid={`simulate-${r.ref}`} onClick={() => setSimRisk({ ref: r.risk_ref, title: r.title, ...(riskMap[r.risk_ref] || { residual: 12, inherent: 20 }) })}
                    className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-secondary/60 hover:bg-secondary transition-colors">
                    <Activity className="w-3.5 h-3.5" /> Simulate
                  </button>
                </div>
                {r.status === "Pending" ? (
                  <Dialog open={active?.ref === r.ref} onOpenChange={(o) => { setActive(o ? r : null); setChosen(""); setRationale(""); }}>
                    <DialogTrigger asChild>
                      <button data-testid={`decide-${r.ref}`} className="text-xs font-head font-bold px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity">Make decision</button>
                    </DialogTrigger>
                    <DialogContent className="bg-card border-border">
                      <DialogHeader><DialogTitle className="font-head">Decision · {r.ref}</DialogTitle></DialogHeader>
                      <div className="space-y-3">
                        <p className="text-sm text-muted-foreground">{r.title}</p>
                        <div className="space-y-2">
                          {[r.title, "Defer to next cycle", "Accept the risk"].map((opt) => (
                            <button key={opt} onClick={() => setChosen(opt)}
                              className={`w-full text-left text-sm px-3 py-2 rounded-md border transition-colors ${chosen === opt ? "border-primary bg-primary/10" : "border-border hover:border-primary/40"}`}>{opt}</button>
                          ))}
                        </div>
                        <textarea data-testid="decision-rationale" value={rationale} onChange={(e) => setRationale(e.target.value)} placeholder="Rationale…" rows={3}
                          className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
                      </div>
                      <DialogFooter>
                        <button data-testid="decision-submit" onClick={decide} disabled={busy}
                          className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
                          {busy && <Loader2 className="w-4 h-4 animate-spin" />} Record decision
                        </button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                ) : (
                  <span className="text-xs flex items-center gap-1 text-low"><CheckCircle2 className="w-3.5 h-3.5" /> Decided</span>
                )}
              </div>
            </div>
          ))}
        </div>
        )}
      </div>

      <div>
        <h2 className="font-head font-bold text-lg mb-3 flex items-center gap-2"><GitBranch className="w-4 h-4" /> Decision register</h2>
        <div className="space-y-3">
          {decisions.length === 0 && <EmptyState icon={FileText} text="No decisions recorded yet — approve a recommendation above to start the auditable register." />}
          {decisions.map((d) => (
            <div key={d.ref} data-testid={`decision-${d.ref}`} className="bg-card fact-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs text-muted-foreground">{d.ref} · linked {d.linked_rec}</span>
                <span className="text-xs px-2 py-0.5 rounded-sm bg-low/15 text-low">{d.status}</span>
              </div>
              <div className="font-medium text-sm">{d.title}</div>
              <div className="text-xs text-muted-foreground mt-1">Chosen: <span className="text-foreground">{d.chosen}</span> · Approver: {d.approver}</div>
              <div className="text-xs text-muted-foreground mt-1">{d.rationale}</div>
              <div className="text-[11px] text-muted-foreground mt-2 flex items-center gap-1"><FileText className="w-3 h-3" /> Outcome: {d.outcome}</div>
            </div>
          ))}
        </div>
      </div>

      <SimulationModal risk={simRisk} onClose={() => setSimRisk(null)} />
    </div>
  );
}
