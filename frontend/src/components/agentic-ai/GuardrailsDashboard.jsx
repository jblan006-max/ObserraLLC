import { CheckCircle2, Loader2, PlayCircle, ShieldCheck, XCircle } from "lucide-react";
import { DataClassBadge, EmptyState, Panel, ProgressBar, StatusPill } from "@/components/agentic-ai/shared";
import { guardrailDistribution } from "@/lib/agenticAIModels";

export default function GuardrailsDashboard({
  agents,
  isAdmin,
  busyRef,
  onToggleGuard,
  onRunRedteam,
  onSelectAgent,
}) {
  const guards = guardrailDistribution(agents || []);

  return (
    <div className="space-y-5">
      <Panel
        title="Enterprise guardrail coverage"
        subtitle="Coverage is FACT from current records. Existing red-team results are explicitly shown as a HEURISTIC BASELINE."
        testid="agentic-guardrail-coverage"
      >
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
          {guards.map((guard) => (
            <div key={guard.key} className="rounded-xl border border-border bg-secondary/20 p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="font-head font-bold">{guard.label}</div>
                <DataClassBadge kind="FACT" />
              </div>
              <div className="font-head font-black text-3xl mt-3">{guard.pct}%</div>
              <div className="text-xs text-muted-foreground mt-1">
                {guard.active}/{guard.total} agents
              </div>
              <div className="mt-3">
                <ProgressBar
                  value={guard.pct}
                  accent={guard.pct >= 80 ? "142 70% 45%" : guard.pct >= 60 ? "35 90% 55%" : "0 84% 60%"}
                />
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title="Agent guardrails and heuristic red-team baseline"
        subtitle="Changing a guardrail updates the existing Obserra governance record. It does not claim runtime enforcement in an external AI platform."
        testid="agentic-redteam"
      >
        {(agents || []).length === 0 ? (
          <EmptyState
            title="No agents registered"
            text="Register agents before evaluating guardrails or running the existing heuristic baseline."
          />
        ) : (
          <div className="space-y-3">
            {(agents || []).map((agent) => (
              <div key={agent.ref} className="rounded-xl border border-border bg-secondary/20 p-4">
                <div className="grid xl:grid-cols-[1.2fr_1.6fr_.8fr] gap-4">
                  <button onClick={() => onSelectAgent(agent)} className="text-left">
                    <div className="font-mono text-[10px] text-ai">{agent.ref}</div>
                    <div className="font-head font-bold mt-1">{agent.name}</div>
                    <div className="text-xs text-muted-foreground mt-1">{agent.owner} · {agent.model}</div>
                    <div className="flex gap-1.5 mt-2">
                      <StatusPill value={agent.risk_class} />
                      <StatusPill value={agent.status} />
                    </div>
                  </button>

                  <div className="grid grid-cols-2 gap-2">
                    {[
                      ["input_filtering", "Input filtering"],
                      ["output_filtering", "Output filtering"],
                      ["tool_allowlist", "Tool allowlist"],
                      ["human_in_loop", "Human approval"],
                    ].map(([key, label]) => {
                      const enabled = Boolean(agent.guardrails?.[key]);
                      return (
                        <button
                          key={key}
                          onClick={() => isAdmin && onToggleGuard(agent, key)}
                          disabled={!isAdmin || busyRef === agent.ref}
                          className={`flex items-center gap-2 px-3 py-2 rounded-md border text-xs text-left disabled:opacity-60 ${
                            enabled
                              ? "bg-low/10 border-low/30 text-low"
                              : "bg-crit/5 border-crit/25 text-muted-foreground"
                          }`}
                        >
                          {enabled ? (
                            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5 shrink-0" />
                          )}
                          {label}
                        </button>
                      );
                    })}
                  </div>

                  <div>
                    <div className="rounded-lg bg-card border border-border p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-[9px] font-mono uppercase text-muted-foreground">Red-team</div>
                        <DataClassBadge kind="HEURISTIC BASELINE" />
                      </div>
                      <div className="font-head font-black text-2xl mt-2">
                        {agent.last_redteam ? `${agent.last_redteam.score}%` : "Not run"}
                      </div>
                      {agent.last_redteam && (
                        <div className="text-[10px] text-muted-foreground mt-1">
                          {agent.last_redteam.passed}/{agent.last_redteam.total} probes defended
                        </div>
                      )}
                    </div>
                    {isAdmin && (
                      <button
                        onClick={() => onRunRedteam(agent)}
                        disabled={busyRef === agent.ref}
                        className="w-full mt-2 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold flex items-center justify-center gap-1.5 disabled:opacity-50"
                      >
                        {busyRef === agent.ref ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <PlayCircle className="w-3.5 h-3.5" />
                        )}
                        Run heuristic baseline
                      </button>
                    )}
                  </div>
                </div>

                {agent.last_redteam?.findings?.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-border">
                    <div className="grid md:grid-cols-2 xl:grid-cols-5 gap-2">
                      {agent.last_redteam.findings.map((finding) => (
                        <div
                          key={finding.id}
                          className={`rounded-lg border p-2.5 ${
                            finding.defended
                              ? "border-low/25 bg-low/5"
                              : "border-crit/25 bg-crit/5"
                          }`}
                        >
                          <div className="flex items-center gap-1.5">
                            {finding.defended ? (
                              <ShieldCheck className="w-3.5 h-3.5 text-low" />
                            ) : (
                              <XCircle className="w-3.5 h-3.5 text-crit" />
                            )}
                            <span className="font-mono text-[9px] text-muted-foreground">{finding.id}</span>
                          </div>
                          <div className="text-xs mt-1.5">{finding.name}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}