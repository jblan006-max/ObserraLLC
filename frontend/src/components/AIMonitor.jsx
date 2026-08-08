import { Bot, ShieldCheck, Eye, Filter, Lock, Brain, Activity, ArrowDown } from "lucide-react";
import { CardShell } from "@/components/dash";

// Live "monitoring & control techniques applied to an AI system and its inputs/outputs".
// Each control layer reflects real guardrail coverage / governance state so leadership
// sees the AI is actively being monitored.
function Chip({ icon: Icon, label, desc, n, total, accent }) {
  const pct = total ? Math.round((n / total) * 100) : 0;
  const on = n > 0;
  return (
    <div data-testid={`ai-monitor-${label.replace(/[^a-zA-Z0-9]/g, "-").toLowerCase()}`}
      className={`rounded-lg p-3 border transition-colors ${on ? "" : "opacity-70"}`}
      style={{ borderColor: on ? `hsl(${accent} / 0.4)` : "hsl(215 15% 35% / 0.4)", background: on ? `hsl(${accent} / 0.06)` : "transparent" }}>
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 text-xs font-head font-bold min-w-0"><Icon className="w-3.5 h-3.5 shrink-0" style={{ color: `hsl(${accent})` }} /> <span className="truncate">{label}</span></div>
        <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded-full shrink-0 ${on ? "bg-low/15 text-low" : "bg-secondary/60 text-muted-foreground"}`}>{on ? "LIVE" : "OFF"}</span>
      </div>
      <div className="text-[10px] text-muted-foreground leading-tight">{desc}</div>
      {total > 0 && <div className="text-[10px] font-mono mt-1" style={{ color: `hsl(${accent})` }}>{n}/{total} systems · {pct}%</div>}
    </div>
  );
}

export function AIMonitor({ guardCov = {}, agentTotal = 0, sanctioned = 0, systems = 0, shadow = 0, accent = "350 89% 60%" }) {
  const g = (k) => guardCov[k] || 0;
  const Node = ({ label, sub }) => (
    <div className="rounded-lg px-4 py-3 text-center text-white w-full" style={{ background: "#1e1b3a", border: `1px solid hsl(${accent} / 0.3)` }}>
      <div className="font-head font-bold text-sm">{label}</div>
      <div className="text-[10px] text-white/60">{sub}</div>
    </div>
  );
  return (
    <CardShell testid="ai-monitoring" title="AI monitoring & control techniques" icon={Activity} accent={accent}
      right={<span className="text-[10px] font-mono text-muted-foreground">{sanctioned} governed · {shadow} shadow</span>}>
      <div className="rounded-xl border border-dashed border-muted-foreground/25 p-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-center">
          <div className="space-y-2">
            <Chip icon={Filter} label="Input detectors" desc="Filter malicious / prompt-injection inputs" n={g("input_filtering")} total={agentTotal} accent={accent} />
            <Chip icon={Brain} label="Internal-state monitors" desc="Model activations / drift on governed systems" n={sanctioned} total={systems} accent={accent} />
          </div>
          <div className="space-y-2 flex flex-col items-center">
            <Node label="Inputs" sub="user queries" />
            <ArrowDown className="w-4 h-4 text-muted-foreground" />
            <Node label="General-purpose AI system" sub="chatbot / agents" />
            <ArrowDown className="w-4 h-4 text-muted-foreground" />
            <Node label="Outputs" sub="responses / actions" />
          </div>
          <div className="space-y-2">
            <Chip icon={Brain} label="Chain-of-thought monitors" desc="Check model reasoning before output" n={g("output_filtering")} total={agentTotal} accent={accent} />
            <Chip icon={ShieldCheck} label="Output detectors" desc="Validate & filter harmful responses" n={g("output_filtering")} total={agentTotal} accent={accent} />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
          <Chip icon={Eye} label="Human oversight" desc="Human-in-the-loop for high-risk output & accountability" n={g("human_in_loop")} total={agentTotal} accent={accent} />
          <Chip icon={Lock} label="Sandboxing / tool allow-list" desc="Prevent the system acting on the outside world" n={g("tool_allowlist")} total={agentTotal} accent={accent} />
        </div>
      </div>
      <p className="text-[11px] text-muted-foreground mt-2 flex items-center gap-1"><Bot className="w-3 h-3" /> Coverage reflects live guardrails on registered AI agents — raise coverage on AI Agents to harden monitoring.</p>
    </CardShell>
  );
}
