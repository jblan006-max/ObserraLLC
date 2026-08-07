import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Bot, Loader2, X, ShieldCheck, ShieldAlert, Zap, Layers, PlayCircle, CheckCircle2, XCircle } from "lucide-react";

const RISK_COLOR = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "190 90% 50%" };
const STATUS_COLOR = { sanctioned: "142 70% 45%", restricted: "35 90% 55%", shadow: "0 84% 60%", killed: "215 20% 50%" };
const GUARDS = [
  ["input_filtering", "Input filtering"], ["output_filtering", "Output filtering"],
  ["tool_allowlist", "Tool allowlist"], ["human_in_loop", "Human-in-the-loop"],
];

export default function AIAgents() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [active, setActive] = useState(null);

  const load = () => api.get("/agents").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);

  if (!data) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Bot className="w-7 h-7 text-primary" /> AI Agent Governance</h1>
        <p className="text-sm text-muted-foreground mt-1">The first standalone application composed directly on the Obserra kernel.</p>
        <div data-testid="kernel-composition" className="flex flex-wrap items-center gap-2 mt-3">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Layers className="w-3.5 h-3.5" /> Composed on:</span>
          {data.composition.map((c) => <span key={c} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{c}</span>)}
        </div>
      </div>

      <div className="md:hidden space-y-3" data-testid="agent-cards-mobile">
        {data.agents.map((a) => (
          <div key={a.ref} data-testid={`agent-card-${a.ref}`} onClick={() => setActive(a)}
            className="bg-card fact-border rounded-xl p-4 space-y-2 active:bg-secondary/40 transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0"><div className="font-mono text-[11px] text-ai">{a.ref}</div><div className="font-medium text-sm">{a.name}</div><div className="text-[11px] text-muted-foreground font-mono">{a.owner} · {a.model}</div></div>
              <span className="text-[10px] px-2 py-0.5 rounded-sm font-mono font-bold shrink-0" style={{ background: `hsl(${RISK_COLOR[a.risk_class]} / 0.15)`, color: `hsl(${RISK_COLOR[a.risk_class]})` }}>{a.risk_class}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="capitalize font-mono" style={{ color: `hsl(${STATUS_COLOR[a.status]})` }}>{a.status}</span>
              <span className="text-muted-foreground">Red-team: {a.last_redteam ? `${a.last_redteam.score}%` : "Not run"}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="hidden md:block bg-card fact-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr>
              <th className="text-left px-4 py-3">Agent</th><th className="text-left px-4 py-3">Owner</th>
              <th className="text-left px-4 py-3">Model</th><th className="text-left px-4 py-3">Risk</th>
              <th className="text-left px-4 py-3">Status</th><th className="text-left px-4 py-3">Tool governance</th>
              <th className="text-left px-4 py-3">Red-team</th>
            </tr>
          </thead>
          <tbody>
            {data.agents.map((a) => (
              <tr key={a.ref} data-testid={`agent-row-${a.ref}`} onClick={() => setActive(a)} className="border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer">
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{a.ref}</div><div className="font-medium">{a.name}</div></td>
                <td className="px-4 py-3 text-muted-foreground">{a.owner}</td>
                <td className="px-4 py-3 font-mono text-xs">{a.model}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${RISK_COLOR[a.risk_class]} / 0.15)`, color: `hsl(${RISK_COLOR[a.risk_class]})` }}>{a.risk_class}</span></td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono capitalize" style={{ background: `hsl(${STATUS_COLOR[a.status]} / 0.15)`, color: `hsl(${STATUS_COLOR[a.status]})` }}>{a.status}</span></td>
                <td className="px-4 py-3">{a.tool_violations?.length ? <span className="text-xs text-crit flex items-center gap-1"><ShieldAlert className="w-3.5 h-3.5" />{a.tool_violations.join(", ")}</span> : <span className="text-xs text-low flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5" />OK</span>}</td>
                <td className="px-4 py-3">{a.last_redteam ? <span className="font-head font-bold" style={{ color: `hsl(${a.last_redteam.score >= 80 ? "142 70% 45%" : a.last_redteam.score >= 50 ? "35 90% 55%" : "0 84% 60%"})` }}>{a.last_redteam.score}%</span> : <span className="text-xs text-muted-foreground">Not run</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {active && <AgentModal agent={active} isAdmin={isAdmin} onClose={() => setActive(null)} onChanged={load} />}
    </div>
  );
}

function AgentModal({ agent, isAdmin, onClose, onChanged }) {
  const [a, setA] = useState(agent);
  const [running, setRunning] = useState(false);

  const toggle = async (key) => {
    if (!isAdmin) return;
    const { data } = await api.patch(`/agents/${a.ref}`, { [key]: !a.guardrails[key] });
    setA((p) => ({ ...p, guardrails: data.guardrails })); onChanged();
  };
  const run = async () => {
    setRunning(true);
    try {
      const { data } = await api.post(`/agents/${a.ref}/redteam`);
      setA((p) => ({ ...p, last_redteam: data }));
      toast.success(`Red-team complete — score ${data.score}%`);
      onChanged();
    } catch { toast.error("Red-team failed"); }
    setRunning(false);
  };

  const rt = a.last_redteam;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" data-testid="agent-modal">
      <div className="w-full max-w-lg bg-card fact-border rounded-xl p-6 rise max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-4">
          <div><div className="font-mono text-xs text-ai">{a.ref}</div><h2 className="font-head font-black text-xl">{a.name}</h2><div className="text-xs text-muted-foreground mt-1">{a.owner} · {a.model}</div></div>
          <button data-testid="agent-close" onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Tools</div><div className="flex flex-wrap gap-1">{a.tools.map((t) => <span key={t} className={`text-[10px] font-mono px-1.5 py-0.5 rounded-sm ${a.tool_violations?.includes(t) ? "bg-crit/15 text-crit" : "bg-secondary/60"}`}>{t}</span>)}</div></div>
          <div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Permissions</div><div className="flex flex-wrap gap-1">{a.permissions.map((p) => <span key={p} className="text-[10px] font-mono px-1.5 py-0.5 rounded-sm bg-secondary/60">{p}</span>)}</div></div>
        </div>

        <div className="mb-4">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Guardrails {isAdmin && "(tap to toggle)"}</div>
          <div className="grid grid-cols-2 gap-2">
            {GUARDS.map(([key, label]) => (
              <button key={key} data-testid={`guard-${key}`} onClick={() => toggle(key)} disabled={!isAdmin}
                className={`flex items-center gap-2 text-xs px-3 py-2 rounded-md border transition-colors ${a.guardrails[key] ? "bg-low/10 border-low/40 text-low" : "bg-crit/5 border-crit/30 text-muted-foreground"} ${isAdmin ? "hover:opacity-80" : "cursor-default"}`}>
                {a.guardrails[key] ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />} {label}
              </button>
            ))}
          </div>
        </div>

        {isAdmin && (
          <button data-testid="agent-redteam" onClick={run} disabled={running}
            className="w-full py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-50 mb-4">
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />} Run red-team / prompt-injection suite
          </button>
        )}

        {rt && (
          <div data-testid="redteam-result" className="ai-border rounded-lg p-4 bg-ai/5">
            <div className="flex items-center justify-between mb-2">
              <span className="font-head font-bold text-sm flex items-center gap-1"><Zap className="w-4 h-4 text-ai" /> Red-team score</span>
              <span className="font-head font-black text-2xl" style={{ color: `hsl(${rt.score >= 80 ? "142 70% 45%" : rt.score >= 50 ? "35 90% 55%" : "0 84% 60%"})` }}>{rt.score}%</span>
            </div>
            <div className="text-[10px] font-mono text-muted-foreground mb-2">{rt.passed}/{rt.total} probes defended · eval: {rt.evaluation}</div>
            <div className="space-y-1">
              {rt.findings.map((f) => (
                <div key={f.id} className="flex items-center gap-2 text-xs">
                  {f.defended ? <CheckCircle2 className="w-3.5 h-3.5 text-low" /> : <XCircle className="w-3.5 h-3.5 text-crit" />}
                  <span className="font-mono text-[10px] text-muted-foreground">{f.id}</span> {f.name}
                  <span className="ml-auto text-[10px] font-mono" style={{ color: `hsl(${RISK_COLOR[f.severity]})` }}>{f.severity}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
