import { AlertTriangle, ArrowRight, Bot, Database, KeyRound } from "lucide-react";
import { useDeepDive } from "@/context/DeepDiveContext";
import { Panel } from "@/components/agentic-ai/shared";
import { toxicityModel } from "@/lib/agenticToxicity";
import { agentDeepDive } from "@/lib/agenticDeepDive";

const LEVEL = {
  critical: { c: "0 84% 60%", label: "Toxic · critical" },
  high: { c: "15 80% 55%", label: "Toxic · high" },
  medium: { c: "35 90% 55%", label: "Elevated" },
  none: { c: "142 70% 45%", label: "Contained" },
};

function Chip({ label, tone = "215 20% 60%", solid }) {
  return (
    <span
      className="px-2 py-0.5 rounded text-[10px] font-mono whitespace-nowrap"
      style={{
        background: `hsl(${tone} / ${solid ? 0.18 : 0.1})`,
        color: `hsl(${tone})`,
        border: `1px solid hsl(${tone} / 0.3)`,
      }}
    >
      {label}
    </span>
  );
}

export default function ToxicityMap({ agents }) {
  const { openDeepDive, warm } = useDeepDive();
  const model = toxicityModel(agents || []);
  const nodes = model.nodes;

  return (
    <Panel
      title="Tool Toxicity Map"
      subtitle="Agent → Tool → Permission → Resource. Toxic capability combinations — action or dangerous tools without the matching guardrail — are flagged in red. Click any agent for the full analysis."
      testid="agentic-toxicity-map"
      actions={
        <div className="flex items-center gap-2 text-[10px] font-mono">
          <span className="px-2 py-1 rounded-full bg-crit/10 text-crit border border-crit/25">{model.toxic} toxic</span>
          <span className="px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">{nodes.length} agents</span>
        </div>
      }
    >
      {nodes.length === 0 ? (
        <div className="text-sm text-muted-foreground">No agents to map.</div>
      ) : (
        <div className="space-y-2.5">
          {nodes.map((n) => {
            const lv = LEVEL[n.toxicity.level] || LEVEL.none;
            const perms = [...new Set((n.edges || []).map((e) => e.permission))];
            const resources = [...new Set((n.edges || []).map((e) => e.resource))];
            return (
              <button
                key={n.ref}
                onMouseEnter={() => warm(agentDeepDive(n))}
                onClick={() => openDeepDive(agentDeepDive(n))}
                data-testid={`toxicity-agent-${n.ref}`}
                className="w-full text-left rounded-xl border p-3 hover:bg-secondary/30 transition-colors"
                style={{
                  borderColor: `hsl(${lv.c} / ${n.toxicity.toxic ? 0.5 : 0.2})`,
                  background: n.toxicity.toxic ? `hsl(${lv.c} / 0.05)` : undefined,
                }}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-head font-bold text-xs"
                    style={{ background: `hsl(${lv.c} / 0.14)`, color: `hsl(${lv.c})` }}
                  >
                    <Bot className="w-3.5 h-3.5" /> {n.name}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                  <div className="flex flex-wrap gap-1">
                    {(n.edges || []).map((e) => (
                      <Chip
                        key={e.tool}
                        label={e.tool}
                        solid={e.danger || e.action}
                        tone={e.danger ? "0 84% 60%" : e.action ? "35 90% 55%" : "215 20% 60%"}
                      />
                    ))}
                    {(n.edges || []).length === 0 && <span className="text-[10px] text-muted-foreground">No tools</span>}
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                  <span className="inline-flex items-center gap-1">
                    <KeyRound className="w-3 h-3 text-muted-foreground" />
                    {perms.map((p) => (
                      <Chip key={p} label={p} tone={p === "write" ? "0 84% 60%" : "190 80% 50%"} />
                    ))}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                  <span className="inline-flex items-center gap-1 flex-wrap">
                    <Database className="w-3 h-3 text-muted-foreground" />
                    {resources.map((r) => (
                      <Chip key={r} label={r} tone="266 70% 66%" />
                    ))}
                  </span>
                  <span
                    className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded-full shrink-0"
                    style={{ background: `hsl(${lv.c} / 0.14)`, color: `hsl(${lv.c})` }}
                  >
                    {lv.label}
                  </span>
                </div>
                {n.toxicity.reasons.length > 0 && (
                  <div className="flex items-start gap-1.5 mt-2 text-[11px] text-crit">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span>{n.toxicity.reasons.join(" · ")}</span>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </Panel>
  );
}
