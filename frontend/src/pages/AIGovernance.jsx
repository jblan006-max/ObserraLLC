import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ConfidenceBadge, FreshnessBadge, DataTypeBadge } from "@/components/badges";
import { Loader2, Cpu, AlertOctagon, Ban, Eye } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { AISystemModal } from "@/components/AISystemModal";

const riskClassColor = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };

function EvalBar({ label, value }) {
  const c = value >= 80 ? "hsl(142 70% 45%)" : value >= 65 ? "hsl(35 90% 55%)" : "hsl(15 80% 55%)";
  return (
    <div>
      <div className="flex justify-between text-[10px] text-muted-foreground mb-1"><span>{label}</span><span className="font-mono">{value || "—"}</span></div>
      <div className="h-1.5 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${value}%`, background: c }} /></div>
    </div>
  );
}

export default function AIGovernance() {
  const { mode } = useAuth();
  const isExec = mode === "executive";
  const [systems, setSystems] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState(null);

  const load = () => {
    api.get("/ai-systems").then((r) => setSystems(r.data));
    api.get("/ai-incidents").then((r) => setIncidents(r.data));
  };
  useEffect(() => { load(); }, []);

  const sanction = async (ref) => {
    await api.patch(`/ai-systems/${ref}`, { status: "sanctioned" });
    toast.success(`${ref} sanctioned & brought under governance`);
    load();
  };

  if (!systems) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  const shadow = systems.filter((s) => s.status === "shadow");

  return (
    <div className="rise space-y-5">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight">AI Governance Suite</h1>
        <p className="text-sm text-muted-foreground mt-1">{isExec ? "AI governance posture — sanctioned vs shadow AI and the governance actions awaiting decision." : "Inventory, NIST AI RMF mapping, model cards, evaluations & incident management. Sanctioned + shadow-AI discovery."}</p>
      </div>

      {shadow.length > 0 && (
        <div className="ai-border rounded-lg p-4 flex items-center gap-3 bg-ai/5">
          <Eye className="w-5 h-5 text-ai" />
          <div className="flex-1 text-sm"><span className="font-semibold text-ai">{shadow.length} shadow AI</span> tool(s) discovered processing organizational data — governance action required.</div>
        </div>
      )}

      <Tabs defaultValue="inventory">
        <TabsList className="bg-card">
          <TabsTrigger value="inventory" data-testid="tab-inventory">Inventory & Model Cards</TabsTrigger>
          <TabsTrigger value="incidents" data-testid="tab-incidents">AI Incidents</TabsTrigger>
        </TabsList>

        <TabsContent value="inventory" className="mt-4">
          <div className="grid md:grid-cols-2 gap-4">
            {systems.map((s) => (
              <div key={s.ref} data-testid={`ai-system-${s.ref}`} onClick={() => setSelected(s)}
                className={`rounded-lg p-5 cursor-pointer hover:-translate-y-0.5 transition-transform duration-200 ${s.status === "shadow" ? "ai-border" : "bg-card fact-border"}`}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-muted-foreground" />
                      <span className="font-head font-bold">{s.name}</span>
                    </div>
                    <div className="text-[11px] font-mono text-muted-foreground mt-1">{s.ref} · {s.type} · {s.provider}</div>
                  </div>
                  <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${riskClassColor[s.risk_class]} / 0.15)`, color: `hsl(${riskClassColor[s.risk_class]})` }}>{s.risk_class}</span>
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground mb-3">
                  <span>Use case: <span className="text-foreground">{s.use_case}</span></span>
                  <span>NIST: <span className="text-foreground">{s.nist_profile}</span></span>
                  <span>Owner: <span className="text-foreground">{s.owner}</span></span>
                </div>

                {s.status === "shadow" ? (
                  isExec
                    ? <div className="w-full py-2 rounded-md bg-ai/10 border border-ai/30 text-ai font-head font-bold text-sm text-center">Governance decision required</div>
                    : <button data-testid={`sanction-${s.ref}`} onClick={(e) => { e.stopPropagation(); sanction(s.ref); }}
                      className="w-full py-2 rounded-md bg-ai text-background font-head font-bold text-sm hover:opacity-90 transition-opacity">
                      Bring under governance
                    </button>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <EvalBar label="Bias" value={s.eval.bias} />
                      <EvalBar label="Safety" value={s.eval.safety} />
                      <EvalBar label="Security" value={s.eval.security} />
                      <EvalBar label="Explainability" value={s.eval.explainability} />
                    </div>
                    <div className="flex items-center justify-between pt-3 border-t border-border">
                      <div className="flex items-center gap-3">
                        <span className={`text-[10px] font-mono uppercase ${s.drift === "warning" ? "text-high" : "text-low"}`}>Drift: {s.drift}</span>
                        <span className="text-[10px] font-mono text-muted-foreground">Halluc: {s.hallucination_rate ?? "—"}%</span>
                      </div>
                      <ConfidenceBadge value={s.confidence} />
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="incidents" className="mt-4 space-y-3">
          {incidents.map((i) => (
            <div key={i.ref} data-testid={`incident-${i.ref}`} className="bg-card fact-border rounded-lg p-4 flex items-center gap-4">
              {i.severity === "Critical" ? <Ban className="w-5 h-5 text-crit" /> : <AlertOctagon className="w-5 h-5 text-high" />}
              <div className="flex-1">
                <div className="font-medium text-sm">{i.title}</div>
                <div className="text-[11px] font-mono text-muted-foreground">{i.ref} · {i.system} · governance mode: <span className="text-ai">{i.mode}</span></div>
              </div>
              <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${riskClassColor[i.severity]} / 0.15)`, color: `hsl(${riskClassColor[i.severity]})` }}>{i.severity}</span>
              <span className="text-xs px-2.5 py-1 rounded-md bg-secondary/60">{i.status}</span>
            </div>
          ))}
        </TabsContent>
      </Tabs>

      <AISystemModal system={selected} onClose={() => setSelected(null)} onChanged={load} />
    </div>
  );
}
