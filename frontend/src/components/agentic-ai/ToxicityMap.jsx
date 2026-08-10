import { useState } from "react";
import { AlertTriangle, ArrowRight, Bot, Database, KeyRound, Loader2, ShieldOff } from "lucide-react";
import { toast } from "sonner";
import { useDeepDive } from "@/context/DeepDiveContext";
import { Panel } from "@/components/agentic-ai/shared";
import { toxicityModel } from "@/lib/agenticToxicity";
import { agentDeepDive } from "@/lib/agenticDeepDive";
import { api } from "@/lib/api";

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

function cellTone(edges, resource) {
  const es = (edges || []).filter((e) => e.resource === resource);
  if (!es.length) return null;
  if (es.some((e) => e.danger)) return "0 84% 60%";
  if (es.some((e) => e.permission === "write")) return "35 90% 55%";
  return "190 80% 50%";
}

export default function ToxicityMap({ agents, isAdmin, onReload }) {
  const { openDeepDive, warm } = useDeepDive();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const model = toxicityModel(agents || []);
  const nodes = model.nodes;
  const resources = [...new Set(nodes.flatMap((n) => (n.edges || []).map((e) => e.resource)))];

  const neutralise = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/agents/runtime/enforce-bulk", { action: "suspend", selector: "toxic" });
      toast.success(`Neutralised ${data.count} toxic agent(s) — suspended in the control plane.`);
      setConfirm(false);
      onReload && onReload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Bulk enforcement failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title="Tool Toxicity Map"
      subtitle="Agent → Tool → Permission → Resource. Toxic capability combinations — action or dangerous tools without the matching guardrail — are flagged in red. Click any agent for the full analysis."
      testid="agentic-toxicity-map"
      actions={
        <div className="flex items-center gap-2 text-[10px] font-mono">
          <span className="px-2 py-1 rounded-full bg-crit/10 text-crit border border-crit/25">{model.toxic} toxic</span>
          <span className="px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">{nodes.length} agents</span>
          {isAdmin && model.toxic > 0 && !confirm && (
            <button
              data-testid="toxicity-neutralise-btn"
              onClick={() => setConfirm(true)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-crit/15 border border-crit/30 text-crit font-head font-bold hover:bg-crit/25 transition-colors"
            >
              <ShieldOff className="w-3.5 h-3.5" /> Neutralise {model.toxic} toxic
            </button>
          )}
          {isAdmin && confirm && (
            <span className="inline-flex items-center gap-1.5">
              <span className="text-crit">Suspend {model.toxic} agent(s)?</span>
              <button
                data-testid="toxicity-neutralise-confirm"
                disabled={busy}
                onClick={neutralise}
                className="px-2 py-1 rounded-md bg-crit text-white font-head font-bold disabled:opacity-50 inline-flex items-center gap-1"
              >
                {busy && <Loader2 className="w-3 h-3 animate-spin" />} Confirm
              </button>
              <button
                data-testid="toxicity-neutralise-cancel"
                disabled={busy}
                onClick={() => setConfirm(false)}
                className="px-2 py-1 rounded-md border border-border text-muted-foreground"
              >
                Cancel
              </button>
            </span>
          )}
        </div>
      }
    >
      {nodes.length === 0 ? (
        <div className="text-sm text-muted-foreground">No agents to map.</div>
      ) : (
        <div className="space-y-5">
          <div className="overflow-x-auto" data-testid="toxicity-heatmap">
            <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">
              Blast-radius heatmap — resource exposure by agent
            </div>
            <table className="w-full border-separate" style={{ borderSpacing: "3px" }}>
              <thead>
                <tr>
                  <th className="text-left text-[10px] font-mono text-muted-foreground font-normal p-1">Agent</th>
                  {resources.map((r) => (
                    <th key={r} className="text-[9px] font-mono text-muted-foreground font-normal p-1 whitespace-nowrap">{r}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {nodes.map((n) => (
                  <tr key={n.ref}>
                    <td className="text-xs font-head font-bold pr-2 whitespace-nowrap max-w-[170px] truncate">
                      <button onClick={() => openDeepDive(agentDeepDive(n))} onMouseEnter={() => warm(agentDeepDive(n))} className="hover:text-ai transition-colors text-left">
                        {n.name}
                      </button>
                    </td>
                    {resources.map((r) => {
                      const tone = cellTone(n.edges, r);
                      return (
                        <td key={r} className="p-0">
                          <button
                            onClick={() => openDeepDive(agentDeepDive(n))}
                            data-testid={`toxicity-cell-${n.ref}-${r.replace(/[^A-Za-z]+/g, "")}`}
                            title={`${n.name} · ${r}${tone ? "" : " · no access"}`}
                            className="w-full h-7 rounded transition-transform hover:scale-110"
                            style={{
                              background: tone ? `hsl(${tone} / 0.85)` : "hsl(var(--secondary) / 0.4)",
                              border: tone ? `1px solid hsl(${tone})` : "1px solid hsl(var(--border))",
                            }}
                          />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center gap-3 mt-2 text-[9px] font-mono text-muted-foreground flex-wrap">
              <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: "hsl(0 84% 60%)" }} /> danger</span>
              <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: "hsl(35 90% 55%)" }} /> write</span>
              <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: "hsl(190 80% 50%)" }} /> read</span>
              <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded border border-border" style={{ background: "hsl(var(--secondary))" }} /> no access</span>
            </div>
          </div>

          <div className="space-y-2.5">
            {nodes.map((n) => {
              const lv = LEVEL[n.toxicity.level] || LEVEL.none;
              const perms = [...new Set((n.edges || []).map((e) => e.permission))];
              const nodeResources = [...new Set((n.edges || []).map((e) => e.resource))];
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
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-head font-bold text-xs" style={{ background: `hsl(${lv.c} / 0.14)`, color: `hsl(${lv.c})` }}>
                      <Bot className="w-3.5 h-3.5" /> {n.name}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <div className="flex flex-wrap gap-1">
                      {(n.edges || []).map((e) => (
                        <Chip key={e.tool} label={e.tool} solid={e.danger || e.action} tone={e.danger ? "0 84% 60%" : e.action ? "35 90% 55%" : "215 20% 60%"} />
                      ))}
                      {(n.edges || []).length === 0 && <span className="text-[10px] text-muted-foreground">No tools</span>}
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="inline-flex items-center gap-1">
                      <KeyRound className="w-3 h-3 text-muted-foreground" />
                      {perms.map((p) => (<Chip key={p} label={p} tone={p === "write" ? "0 84% 60%" : "190 80% 50%"} />))}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="inline-flex items-center gap-1 flex-wrap">
                      <Database className="w-3 h-3 text-muted-foreground" />
                      {nodeResources.map((r) => (<Chip key={r} label={r} tone="266 70% 66%" />))}
                    </span>
                    <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded-full shrink-0" style={{ background: `hsl(${lv.c} / 0.14)`, color: `hsl(${lv.c})` }}>
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
        </div>
      )}
    </Panel>
  );
}
