import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ConfidenceBadge, DataTypeBadge } from "@/components/badges";
import { Loader2, GitBranch, CheckCircle2, FileText, Activity } from "lucide-react";
import { SimulationModal } from "@/components/SimulationModal";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "@/components/ui/dialog";

export default function Decisions() {
  const [recs, setRecs] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [riskMap, setRiskMap] = useState({});
  const [active, setActive] = useState(null);
  const [chosen, setChosen] = useState("");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [simRisk, setSimRisk] = useState(null);

  const load = () => {
    api.get("/recommendations").then((r) => setRecs(r.data));
    api.get("/decisions").then((r) => setDecisions(r.data));
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

  if (!recs) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight">Recommendations & Decisions</h1>
        <p className="text-sm text-muted-foreground mt-1">Evidence-backed recommendations flow into a decision register with options, approvals, rationale & outcomes.</p>
      </div>

      <div>
        <h2 className="font-head font-bold text-lg mb-3">Recommendation Engine</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {recs.map((r) => (
            <div key={r.ref} data-testid={`rec-${r.ref}`} className="ai-border rounded-lg p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs text-ai">{r.ref} → {r.risk_ref}</span>
                <DataTypeBadge type="ai_recommendation" />
              </div>
              <div className="font-medium mb-2">{r.title}</div>
              <div className="text-xs text-muted-foreground mb-3">{r.predicted_impact}</div>
              <div className="text-[11px] text-muted-foreground mb-3">
                Evidence: {r.evidence?.join(" · ")}
              </div>
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
                        <textarea data-testid="decision-rationale" value={rationale} onChange={(e) => setRationale(e.target.value)}
                          placeholder="Rationale…" rows={3}
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
      </div>

      <div>
        <h2 className="font-head font-bold text-lg mb-3 flex items-center gap-2"><GitBranch className="w-4 h-4" /> Decision Register</h2>
        <div className="space-y-3">
          {decisions.length === 0 && <p className="text-sm text-muted-foreground">No decisions recorded yet.</p>}
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
