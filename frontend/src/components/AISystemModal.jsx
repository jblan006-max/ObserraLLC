import { useState } from "react";
import { X, Cpu, ShieldOff, Ban, RotateCcw, Check, Loader2, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { SourceBadge, FreshnessBadge, ConfidenceBadge, DataTypeBadge } from "@/components/badges";

const riskClassColor = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };

const FRAMEWORKS = [
  { name: "NIST AI RMF", controls: ["Govern", "Map", "Measure", "Manage"] },
  { name: "ISO/IEC 42001", controls: ["AI Policy", "Impact Assessment", "Lifecycle", "Monitoring"] },
  { name: "EU AI Act", controls: ["Risk Class", "Transparency", "Human Oversight", "Logging"] },
  { name: "OWASP LLM Top 10", controls: ["Prompt Injection", "Data Leakage", "Output Handling", "Model DoS"] },
  { name: "NIST SSDF", controls: ["Secure Dev", "Supply Chain", "Review"] },
  { name: "SOC 2 · ISO 27001 · GDPR", controls: ["Access", "Confidentiality", "Data Protection"] },
];

function coverage(system) {
  const e = system.eval || {};
  const avg = ((e.bias || 0) + (e.safety || 0) + (e.security || 0) + (e.explainability || 0)) / 4;
  if (system.status === "shadow") return "gap";
  if (avg >= 80) return "covered";
  if (avg >= 60) return "partial";
  return "gap";
}
const covMeta = { covered: { label: "Covered", hsl: "142 70% 45%" }, partial: { label: "Partial", hsl: "35 90% 55%" }, gap: { label: "Gap", hsl: "0 84% 60%" } };

function EvalBar({ label, value }) {
  const c = value >= 80 ? "hsl(142 70% 45%)" : value >= 65 ? "hsl(35 90% 55%)" : "hsl(15 80% 55%)";
  return (
    <div><div className="flex justify-between text-[11px] text-muted-foreground mb-1"><span>{label}</span><span className="font-mono">{value || "—"}</span></div>
      <div className="h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${value}%`, background: c }} /></div></div>
  );
}

export function AISystemModal({ system, onClose, onChanged }) {
  const [busy, setBusy] = useState("");
  if (!system) return null;
  const cov = coverage(system);

  const govern = async (action) => {
    setBusy(action);
    try {
      const { data } = await api.post(`/ai-systems/${system.ref}/govern`, { action });
      toast.success(data.message, { duration: 5000 });
      onChanged?.();
      onClose();
    } catch { toast.error("Governance action failed"); }
    setBusy("");
  };

  const ACTIONS = [
    { id: "kill", label: "Kill switch", icon: Ban, cls: "bg-crit/15 border-crit/40 text-crit hover:bg-crit/25" },
    { id: "restrict", label: "Restrict", icon: ShieldOff, cls: "bg-high/15 border-high/40 text-high hover:bg-high/25" },
    { id: "rollback", label: "Rollback", icon: RotateCcw, cls: "bg-secondary/60 border-border text-foreground hover:bg-secondary" },
    { id: "sanction", label: "Sanction", icon: ShieldCheck, cls: "bg-low/15 border-low/40 text-low hover:bg-low/25" },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div data-testid="ai-model-card" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-3xl max-h-[85vh] bg-card border border-border rounded-xl flex flex-col rise overflow-hidden">
        <div className="flex items-start justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <span className="w-10 h-10 rounded-md bg-primary/15 border border-primary/30 flex items-center justify-center"><Cpu className="w-5 h-5 text-primary" /></span>
            <div>
              <div className="font-head font-bold text-lg">{system.name}</div>
              <div className="text-[11px] font-mono text-muted-foreground">{system.ref} · {system.type} · {system.provider}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${riskClassColor[system.risk_class]} / 0.15)`, color: `hsl(${riskClassColor[system.risk_class]})` }}>{system.risk_class}</span>
            <button data-testid="model-card-close" onClick={onClose} className="p-1.5 rounded-md hover:bg-secondary"><X className="w-4 h-4" /></button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <Tabs defaultValue="overview">
            <TabsList className="bg-secondary/50">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="evals">Evaluations</TabsTrigger>
              <TabsTrigger value="frameworks" data-testid="tab-frameworks">Framework Mapping</TabsTrigger>
              <TabsTrigger value="govern" data-testid="tab-govern">Governance</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[["Use case", system.use_case], ["Owner", system.owner], ["NIST Profile", system.nist_profile], ["Status", system.status], ["Governance mode", system.governance_mode || "observe"], ["Drift", system.drift]].map(([k, v]) => (
                  <div key={k} className="rounded-md bg-secondary/30 border border-border p-3"><div className="text-[10px] text-muted-foreground uppercase font-mono">{k}</div><div className="mt-0.5">{v}</div></div>
                ))}
              </div>
              <div className="flex items-center gap-4 pt-2 border-t border-border">
                <SourceBadge source={system.provider} /><FreshnessBadge freshness={system.freshness} /><ConfidenceBadge value={system.confidence} /><DataTypeBadge type={system.data_type} />
              </div>
            </TabsContent>

            <TabsContent value="evals" className="mt-4">
              <div className="grid md:grid-cols-2 gap-4">
                <EvalBar label="Bias / Fairness" value={system.eval?.bias} />
                <EvalBar label="Safety" value={system.eval?.safety} />
                <EvalBar label="Security" value={system.eval?.security} />
                <EvalBar label="Explainability" value={system.eval?.explainability} />
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                <div className="rounded-md bg-secondary/30 border border-border p-3"><div className="text-[10px] text-muted-foreground uppercase font-mono">Hallucination rate</div><div className="font-head font-bold text-lg">{system.hallucination_rate ?? "—"}%</div></div>
                <div className="rounded-md bg-secondary/30 border border-border p-3"><div className="text-[10px] text-muted-foreground uppercase font-mono">Drift status</div><div className={`font-head font-bold text-lg ${system.drift === "warning" ? "text-high" : "text-low"}`}>{system.drift}</div></div>
              </div>
            </TabsContent>

            <TabsContent value="frameworks" className="mt-4 space-y-3">
              <p className="text-xs text-muted-foreground">Cross-framework coverage derived from this system's evaluations and governance status. Implementing one control cascades coverage across mapped frameworks.</p>
              {FRAMEWORKS.map((f) => {
                const m = covMeta[cov];
                return (
                  <div key={f.name} className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-head font-semibold text-sm">{f.name}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm" style={{ background: `hsl(${m.hsl} / 0.15)`, color: `hsl(${m.hsl})` }}>{m.label}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {f.controls.map((c) => (
                        <span key={c} className="text-[10px] font-mono px-2 py-1 rounded-sm border" style={{ borderColor: `hsl(${m.hsl} / 0.4)`, color: `hsl(${m.hsl})` }}>{c}</span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </TabsContent>

            <TabsContent value="govern" className="mt-4">
              <p className="text-xs text-muted-foreground mb-3">Human-in-the-loop governance controls. Actions are audited immutably.</p>
              <div className="grid grid-cols-2 gap-3">
                {ACTIONS.map((a) => (
                  <button key={a.id} data-testid={`govern-${a.id}`} disabled={!!busy} onClick={() => govern(a.id)}
                    className={`flex items-center justify-center gap-2 py-3 rounded-lg border font-head font-bold text-sm transition-colors disabled:opacity-50 ${a.cls}`}>
                    {busy === a.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <a.icon className="w-4 h-4" />} {a.label}
                  </button>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
