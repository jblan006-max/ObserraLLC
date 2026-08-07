import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ShieldCheck, Loader2, AlertTriangle, Clock, FileDown, TrendingDown } from "lucide-react";

const statusHsl = { Passing: "142 70% 45%", Drifting: "35 90% 55%", Failing: "0 84% 60%", "Evidence Stale": "15 80% 55%" };

export default function ControlMonitoring() {
  const [controls, setControls] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api.get("/controls").then((r) => setControls(r.data));
    api.get("/controls/compliance").then((r) => setCompliance(r.data.frameworks)).catch(() => {});
  }, []);

  const pack = async (id) => {
    setBusy(id);
    try {
      const res = await api.post("/reports/evidence-pack", { control_id: id }, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `evidence-pack-${id}.pdf`; a.click();
      URL.revokeObjectURL(url);
      toast.success(`Evidence pack generated for ${id}`);
    } catch { toast.error("Could not generate pack"); }
    setBusy("");
  };

  if (!controls) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const flagged = controls.filter((c) => c.stale || c.drift || c.status === "Failing");

  return (
    <div className="rise space-y-5">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><ShieldCheck className="w-7 h-7 text-primary" /> Continuous Control Monitoring</h1>
        <p className="text-sm text-muted-foreground mt-1">Control effectiveness, maturity, evidence freshness & drift — auto-flagged the moment proof goes stale.</p>
      </div>

      {flagged.length > 0 && (
        <div className="rounded-lg p-4 flex items-center gap-3 border border-high/40 bg-high/5">
          <AlertTriangle className="w-5 h-5 text-high" />
          <div className="text-sm"><span className="font-semibold text-high">{flagged.length} control(s) need attention</span> — expired evidence or effectiveness drift detected.</div>
        </div>
      )}

      {compliance && compliance.length > 0 && (
        <div data-testid="compliance-panel">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-3">Framework alignment · NIST · ISO · SOC 2 · CISA</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {compliance.map((f) => {
              const col = f.coverage >= 75 ? "142 70% 45%" : f.coverage >= 55 ? "35 90% 55%" : "0 84% 60%";
              return (
                <div key={f.framework} data-testid={`compliance-${f.framework.replace(/[^a-zA-Z0-9]/g, "-")}`} className="bg-card fact-border rounded-xl p-4">
                  <div className="text-xs font-head font-bold truncate">{f.framework}</div>
                  <div className="font-head font-black text-2xl mt-1" style={{ color: `hsl(${col})` }}>{f.coverage}%</div>
                  <div className="text-[10px] text-muted-foreground">{f.passing}/{f.controls} controls passing</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="bg-card fact-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3">Control</th><th className="text-left px-4 py-3">Framework</th><th className="text-left px-4 py-3">Effectiveness</th><th className="text-left px-4 py-3">Maturity</th><th className="text-left px-4 py-3">Evidence</th><th className="text-left px-4 py-3">Status</th><th className="text-left px-4 py-3">Owner</th><th className="text-left px-4 py-3">Pack</th></tr>
          </thead>
          <tbody>
            {controls.map((c) => (
              <tr key={c.control_id} data-testid={`control-${c.control_id}`} className="border-b border-border/60 hover:bg-secondary/40 transition-colors">
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{c.control_id}</div><div className="font-medium">{c.name}</div><div className="text-[10px] text-muted-foreground">{c.category}</div></td>
                <td className="px-4 py-3 text-xs">
                  <div className="font-medium">{c.framework}</div>
                  {c.frameworks && Object.keys(c.frameworks).length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1 max-w-[220px]">
                      {Object.entries(c.frameworks).map(([fw, refs]) => (
                        <span key={fw} data-testid={`control-framework-tag-${fw.replace(/[^a-zA-Z0-9]/g, "-")}`} title={refs.join(", ")} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{fw}</span>
                      ))}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 w-40">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${c.effectiveness}%`, background: c.effectiveness >= 75 ? "hsl(142 70% 45%)" : c.effectiveness >= 55 ? "hsl(35 90% 55%)" : "hsl(0 84% 60%)" }} /></div>
                    <span className="font-mono text-xs w-8">{c.effectiveness}%</span>
                  </div>
                  {c.drift && <span className="text-[10px] text-high flex items-center gap-0.5 mt-0.5"><TrendingDown className="w-3 h-3" />{c.drift_delta} pts drift</span>}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{c.maturity}/5</td>
                <td className="px-4 py-3">
                  <span className={`flex items-center gap-1 text-[11px] font-mono ${c.stale ? "text-crit" : c.days_to_expiry < 14 ? "text-med" : "text-muted-foreground"}`}>
                    <Clock className="w-3 h-3" />{c.stale ? `expired ${-c.days_to_expiry}d` : `${c.days_to_expiry}d left`}
                  </span>
                </td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${statusHsl[c.status]} / 0.15)`, color: `hsl(${statusHsl[c.status]})` }}>{c.status}</span></td>
                <td className="px-4 py-3 text-xs">{c.owner}</td>
                <td className="px-4 py-3">
                  <button data-testid={`pack-${c.control_id}`} disabled={busy === c.control_id} onClick={() => pack(c.control_id)}
                    className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors disabled:opacity-50">
                    {busy === c.control_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />} Pack
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">Evidence packs map one control across its aligned frameworks (NIST CSF/800-53/SSDF/AI RMF, EU AI Act, GDPR, SOC 2, ISO 27001/42001) as a downloadable PDF.</p>
    </div>
  );
}
