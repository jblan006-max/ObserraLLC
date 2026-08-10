import { KeyRound, ShieldAlert, UserCheck, Wrench, Zap } from "lucide-react";
import { EmptyState, Panel, StatusPill } from "@/components/agentic-ai/shared";
import ToxicityMap from "@/components/agentic-ai/ToxicityMap";

export default function AuthorityDashboard({ agents, onSelectAgent }) {
  const actionAgents = (agents || []).filter((agent) => (agent.actionTools || []).length > 0);
  const autonomous = (agents || []).filter((agent) => agent.authority === "Autonomous");
  const violations = (agents || []).filter((agent) => (agent.tool_violations || []).length > 0);

  return (
    <div className="space-y-5">
      <ToxicityMap agents={agents} />
      <div className="grid xl:grid-cols-3 gap-4">
        <div className="bg-card fact-border rounded-xl p-4">
          <Zap className="w-4 h-4 text-crit" />
          <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">Autonomous</div>
          <div className="font-head font-black text-3xl mt-1">{autonomous.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Action-capable tools without human approval guardrail</div>
        </div>
        <div className="bg-card fact-border rounded-xl p-4">
          <Wrench className="w-4 h-4 text-ai" />
          <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">Action-capable agents</div>
          <div className="font-head font-black text-3xl mt-1">{actionAgents.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Derived from existing agent tool names</div>
        </div>
        <div className="bg-card fact-border rounded-xl p-4">
          <ShieldAlert className="w-4 h-4 text-high" />
          <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">Tool violations</div>
          <div className="font-head font-black text-3xl mt-1">{violations.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Existing backend tool governance violations</div>
        </div>
      </div>

      <Panel
        title="Delegated authority register"
        subtitle="Shows what each agent can do with its currently recorded tool set and whether human approval is recorded."
        testid="agentic-authority-register"
      >
        {(agents || []).length === 0 ? (
          <EmptyState
            title="No AI agents"
            text="No delegated authority can be modeled until agents are registered."
          />
        ) : (
          <div className="space-y-3">
            {(agents || []).map((agent) => (
              <button
                key={agent.ref}
                onClick={() => onSelectAgent(agent)}
                className="w-full text-left rounded-xl border border-border bg-secondary/20 p-4 hover:bg-secondary/40"
              >
                <div className="grid xl:grid-cols-[1.4fr_.8fr_1fr_1fr] gap-4">
                  <div>
                    <div className="font-mono text-[10px] text-ai">{agent.ref}</div>
                    <div className="font-head font-bold mt-1">{agent.name}</div>
                    <div className="text-xs text-muted-foreground mt-1">{agent.owner} · {agent.model}</div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Modeled authority</div>
                    <div className="mt-2"><StatusPill value={agent.authority} /></div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground flex items-center gap-1">
                      <Wrench className="w-3 h-3" /> Action tools
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {(agent.actionTools || []).length ? (
                        agent.actionTools.slice(0, 5).map((tool) => (
                          <span key={tool} className="px-2 py-0.5 rounded bg-crit/10 text-crit text-[10px] font-mono">
                            {tool}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-muted-foreground">None detected</span>
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground flex items-center gap-1">
                      <UserCheck className="w-3 h-3" /> Human approval
                    </div>
                    <div className="mt-2">
                      <StatusPill value={agent.guardrails?.human_in_loop ? "Recorded" : "Missing"} />
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid xl:grid-cols-2 gap-5">
        <Panel
          title="Tool intelligence"
          subtitle="Current tools from the existing agent records."
          testid="agentic-tools"
        >
          <div className="space-y-3">
            {actionAgents.slice(0, 10).map((agent) => (
              <div key={agent.ref} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-head font-bold text-sm">{agent.name}</div>
                    <div className="text-[10px] font-mono text-muted-foreground">{agent.ref}</div>
                  </div>
                  <StatusPill value={agent.authority} />
                </div>
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {(agent.tools || []).map((tool) => (
                    <span
                      key={tool}
                      className={`px-2 py-1 rounded text-[10px] font-mono ${
                        agent.actionTools.includes(tool)
                          ? "bg-crit/10 text-crit"
                          : "bg-secondary text-muted-foreground"
                      }`}
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Permission intelligence"
          subtitle="Current permission strings associated with registered AI agents."
          testid="agentic-permissions"
        >
          <div className="space-y-3">
            {(agents || []).slice(0, 10).map((agent) => (
              <div key={agent.ref} className="rounded-lg border border-border p-3">
                <div className="flex items-center gap-2">
                  <KeyRound className="w-4 h-4 text-ai" />
                  <div className="font-head font-bold text-sm">{agent.name}</div>
                </div>
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {(agent.permissions || []).length ? (
                    agent.permissions.map((permission) => (
                      <span
                        key={permission}
                        className="px-2 py-1 rounded bg-secondary text-muted-foreground text-[10px] font-mono"
                      >
                        {permission}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground">No permissions recorded.</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}