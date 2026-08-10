import { useState } from "react";
import { Ban, Loader2, PauseCircle, PlayCircle, ShieldAlert, X } from "lucide-react";
import { AIExplain } from "@/components/AIExplain";
import { DataClassBadge, StatusPill } from "@/components/agentic-ai/shared";

export default function AgentDetailModal({
  agent,
  isAdmin,
  busy,
  onClose,
  onEnforce,
}) {
  const [tab, setTab] = useState("evidence");
  if (!agent) return null;

  const context = {
    ref: agent.ref,
    name: agent.name,
    owner: agent.owner,
    model: agent.model,
    risk_class: agent.risk_class,
    modeled_risk_score: agent.modeledRisk,
    modeled_authority: agent.authority,
    status: agent.status,
    tools: agent.tools,
    permissions: agent.permissions,
    tool_violations: agent.tool_violations,
    guardrails: agent.guardrails,
    heuristic_redteam: agent.last_redteam,
    risk_factors: agent.riskFactors,
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/65 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-4xl max-h-[92vh] overflow-y-auto bg-card fact-border rounded-xl">
        <div className="sticky top-0 z-10 bg-card border-b border-border px-5 py-4 flex items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[10px] text-ai">{agent.ref}</div>
            <h2 className="font-head font-black text-2xl mt-1">{agent.name}</h2>
            <div className="text-xs text-muted-foreground mt-1">{agent.owner} · {agent.model}</div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              <StatusPill value={agent.risk_class} />
              <StatusPill value={agent.status} />
              <StatusPill value={agent.authority} />
              <DataClassBadge kind="MODELLED" />
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-md hover:bg-secondary">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div className="grid md:grid-cols-4 gap-3">
            <div className="rounded-lg bg-secondary/30 p-3">
              <div className="text-[9px] font-mono uppercase text-muted-foreground">Modeled risk</div>
              <div className="font-head font-black text-2xl mt-1">{agent.modeledRisk}/100</div>
            </div>
            <div className="rounded-lg bg-secondary/30 p-3">
              <div className="text-[9px] font-mono uppercase text-muted-foreground">Guardrails</div>
              <div className="font-head font-black text-2xl mt-1">{agent.guardrailCoverage.pct}%</div>
            </div>
            <div className="rounded-lg bg-secondary/30 p-3">
              <div className="text-[9px] font-mono uppercase text-muted-foreground">Action tools</div>
              <div className="font-head font-black text-2xl mt-1">{agent.actionTools?.length || 0}</div>
            </div>
            <div className="rounded-lg bg-secondary/30 p-3">
              <div className="text-[9px] font-mono uppercase text-muted-foreground">Red-team baseline</div>
              <div className="font-head font-black text-2xl mt-1">
                {agent.last_redteam ? `${agent.last_redteam.score}%` : "—"}
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setTab("evidence")}
              className={`px-3 py-2 rounded-md text-xs font-head font-bold ${tab === "evidence" ? "bg-primary text-primary-foreground" : "bg-secondary"}`}
            >
              Evidence
            </button>
            <button
              onClick={() => setTab("analysis")}
              className={`px-3 py-2 rounded-md text-xs font-head font-bold ${tab === "analysis" ? "bg-primary text-primary-foreground" : "bg-secondary"}`}
            >
              AI Analysis
            </button>
          </div>

          {tab === "evidence" ? (
            <div className="grid xl:grid-cols-2 gap-5">
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Tools</div>
                <div className="flex flex-wrap gap-1.5">
                  {(agent.tools || []).map((tool) => (
                    <span
                      key={tool}
                      className={`px-2 py-1 rounded text-[10px] font-mono ${
                        agent.actionTools?.includes(tool)
                          ? "bg-crit/10 text-crit"
                          : "bg-secondary text-muted-foreground"
                      }`}
                    >
                      {tool}
                    </span>
                  ))}
                </div>

                <div className="text-[10px] font-mono uppercase text-muted-foreground mt-5 mb-2">Permissions</div>
                <div className="flex flex-wrap gap-1.5">
                  {(agent.permissions || []).map((permission) => (
                    <span key={permission} className="px-2 py-1 rounded bg-secondary text-muted-foreground text-[10px] font-mono">
                      {permission}
                    </span>
                  ))}
                </div>

                <div className="text-[10px] font-mono uppercase text-muted-foreground mt-5 mb-2">Modeled risk factors</div>
                <ul className="space-y-2">
                  {(agent.riskFactors || []).length ? (
                    agent.riskFactors.map((factor) => (
                      <li key={factor} className="text-sm flex items-start gap-2">
                        <ShieldAlert className="w-4 h-4 text-high shrink-0 mt-0.5" />
                        {factor}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-muted-foreground">No additional modeled factors.</li>
                  )}
                </ul>
              </div>

              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Guardrails</div>
                <div className="space-y-2">
                  {[
                    ["input_filtering", "Input filtering"],
                    ["output_filtering", "Output filtering"],
                    ["tool_allowlist", "Tool allowlist"],
                    ["human_in_loop", "Human approval"],
                  ].map(([key, label]) => (
                    <div key={key} className="flex items-center justify-between rounded-lg border border-border px-3 py-2.5">
                      <span className="text-sm">{label}</span>
                      <StatusPill value={agent.guardrails?.[key] ? "Recorded" : "Missing"} />
                    </div>
                  ))}
                </div>

                {agent.last_redteam && (
                  <>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mt-5 mb-2 flex items-center justify-between">
                      <span>Red-team evidence</span>
                      <DataClassBadge kind="HEURISTIC BASELINE" />
                    </div>
                    <div className="space-y-2">
                      {(agent.last_redteam.findings || []).map((finding) => (
                        <div key={finding.id} className="rounded-lg border border-border px-3 py-2">
                          <div className="text-[10px] font-mono text-ai">{finding.id}</div>
                          <div className="text-sm mt-1">{finding.name}</div>
                          <div className="mt-1"><StatusPill value={finding.defended ? "Defended" : "Gap"} /></div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          ) : (
            <AIExplain
              title={`${agent.name} AI agent security`}
              kind="agentic ai security delegated authority tools permissions guardrails"
              context={context}
              accent="330 81% 60%"
            />
          )}

          {isAdmin && (
            <div className="border-t border-border pt-4">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">
                Runtime enforcement — Kill Switch
              </div>
              {agent.enforcement && (
                <div className="mb-3 rounded-lg border border-ai/25 bg-ai/5 p-3 text-xs" data-testid="agent-enforcement-status">
                  <div className="flex items-center gap-2 font-head font-bold">
                    <ShieldAlert className="w-3.5 h-3.5 text-ai" />
                    {agent.enforcement.enforced ? "Enforcement active" : "Enforcement lifted"} · mode {agent.enforcement.mode}
                    <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                      {agent.enforcement.runtime === "external-webhook"
                        ? (agent.enforcement.external_ok ? "dispatched to runtime" : "runtime dispatch failed")
                        : "control-plane"}
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-1">{agent.enforcement.note}</p>
                </div>
              )}
              <p className="text-xs text-muted-foreground mb-3">
                Suspend restricts the agent, Kill blocks it, Resume returns it to sanctioned. Each action flips the agent
                runtime status, is written to the Defensibility Ledger and alerts Slack/Teams. When an agent-runtime
                webhook is connected, the command is also dispatched to the external execution environment.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  data-testid="agent-enforce-suspend"
                  onClick={() => onEnforce(agent, "suspend")}
                  disabled={busy || agent.status === "restricted"}
                  className="px-3 py-2 rounded-md border border-high/40 bg-high/10 text-high text-xs font-head font-bold disabled:opacity-50 inline-flex items-center gap-1.5"
                >
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PauseCircle className="w-3.5 h-3.5" />}
                  Suspend
                </button>
                <button
                  data-testid="agent-enforce-kill"
                  onClick={() => onEnforce(agent, "kill")}
                  disabled={busy || agent.status === "killed"}
                  className="px-3 py-2 rounded-md border border-crit/40 bg-crit/10 text-crit text-xs font-head font-bold disabled:opacity-50 inline-flex items-center gap-1.5"
                >
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Ban className="w-3.5 h-3.5" />}
                  Kill
                </button>
                <button
                  data-testid="agent-enforce-resume"
                  onClick={() => onEnforce(agent, "resume")}
                  disabled={busy || agent.status === "sanctioned"}
                  className="px-3 py-2 rounded-md border border-low/40 bg-low/10 text-low text-xs font-head font-bold disabled:opacity-50 inline-flex items-center gap-1.5"
                >
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />}
                  Resume
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}