import { useEffect, useState } from "react";
import { X, Loader2, TrendingDown, DollarSign, Activity } from "lucide-react";
import { api } from "@/lib/api";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString();

export function SimulationModal({ risk, onClose }) {
  const [target, setTarget] = useState(null);
  const [sim, setSim] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (risk) setTarget(Math.max(3, (risk.residual || 12) - 4)); }, [risk]);

  useEffect(() => {
    if (!risk || target == null) return;
    setLoading(true);
    const t = setTimeout(async () => {
      try { const { data } = await api.post("/simulate", { risk_ref: risk.ref, target_residual: target }); setSim(data); }
      catch { setSim(null); }
      setLoading(false);
    }, 250);
    return () => clearTimeout(t);
  }, [risk, target]);

  if (!risk) return null;

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div data-testid="simulation-modal" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg bg-card border border-border rounded-xl flex flex-col rise overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2"><Activity className="w-4 h-4 text-ai" /><span className="font-head font-bold">Decision Simulation · {risk.ref}</span></div>
          <button data-testid="sim-close" onClick={onClose} className="p-1.5 rounded-md hover:bg-secondary"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-5">
          <div className="text-sm">{risk.title}</div>
          <div>
            <div className="flex justify-between text-xs text-muted-foreground mb-2">
              <span>Target residual after treatment</span>
              <span className="font-mono text-foreground">{target} <span className="text-muted-foreground">/ inherent {risk.inherent}</span></span>
            </div>
            <input data-testid="sim-slider" type="range" min={1} max={risk.inherent} value={target ?? 1}
              onChange={(e) => setTarget(Number(e.target.value))} className="w-full accent-ai" />
          </div>

          {loading || !sim ? (
            <div className="flex items-center justify-center h-32"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-secondary/30 border border-border p-4"><div className="text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1"><TrendingDown className="w-3 h-3 text-low" /> Expected risk reduction</div><div className="font-head font-black text-2xl text-low">{fmt(sim.expected_reduction)}</div><div className="text-[10px] text-muted-foreground">exposure/yr avoided</div></div>
                <div className="rounded-lg bg-secondary/30 border border-border p-4"><div className="text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1"><DollarSign className="w-3 h-3" /> Estimated cost</div><div className="font-head font-black text-2xl">{fmt(sim.estimated_cost)}</div><div className="text-[10px] text-muted-foreground">to reach target</div></div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                {[["Exposure before", fmt(sim.exposure_before)], ["Exposure after", fmt(sim.exposure_after)], ["ROI", sim.roi != null ? `${sim.roi}×` : "—"]].map(([k, v]) => (
                  <div key={k} className="rounded-md bg-secondary/30 border border-border p-2.5"><div className="text-[9px] font-mono uppercase text-muted-foreground">{k}</div><div className="font-head font-bold">{v}</div></div>
                ))}
              </div>
              <div className="ai-border rounded-lg p-3 text-sm">
                <span className="text-ai font-semibold">Projection:</span> reaching residual {sim.target_residual} lifts the health index ~+{sim.health_delta} pts{sim.payback_months ? `, payback ≈ ${sim.payback_months} months` : ""}. <span className="text-muted-foreground">Estimate — not committed.</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
