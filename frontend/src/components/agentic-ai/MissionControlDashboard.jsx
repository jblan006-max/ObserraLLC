import {
  AlertOctagon,
  Bot,
  EyeOff,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  Workflow,
  Zap,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricCard, Panel, ProgressBar, StatusPill } from "@/components/agentic-ai/shared";
import { authorityDistribution, guardrailDistribution } from "@/lib/agenticAIModels";

const AUTH_COLORS = {
  Autonomous: "hsl(0 84% 60%)",
  "Approval Required": "hsl(35 90% 55%)",
  "Tool Assisted": "hsl(266 85% 66%)",
  Observe: "hsl(142 70% 45%)",
  Disabled: "hsl(215 20% 50%)",
};

export default function MissionControlDashboard({ data, onOpenTab, onSelectAgent }) {
  const summary = data.agentSummary || {};
  const systems = data.systemSummary || {};
  const incidents = data.incidentSummary || {};
  const auth = authorityDistribution(data.agents || []);
  const guards = guardrailDistribution(data.agents || []);
  const topAgents = (data.agents || []).slice(0, 6);
  const owasp = data.analytics?.owasp_llm || [];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 xl:grid-cols-6 gap-4">
        <MetricCard
          label="Registered agents"
          value={summary.total || 0}
          sub={`${summary.sanctioned || 0} sanctioned`}
          kind="FACT"
          icon={Bot}
          onClick={() => onOpenTab("inventory")}
        />
        <MetricCard
          label="Modeled agent risk"
          value={`${summary.averageRisk || 0}/100`}
          sub="Derived from current risk class, authority, guardrails and findings"
          kind="MODELLED"
          icon={ShieldAlert}
          accent="0 84% 60%"
          onClick={() => onOpenTab("inventory")}
        />
        <MetricCard
          label="Autonomous agents"
          value={summary.autonomous || 0}
          sub={`${summary.approvalRequired || 0} require approval`}
          kind="MODELLED"
          icon={Zap}
          accent="35 90% 55%"
          onClick={() => onOpenTab("authority")}
        />
        <MetricCard
          label="Shadow AI"
          value={systems.shadow || 0}
          sub={`${systems.total || 0} AI systems recorded`}
          kind="FACT"
          icon={EyeOff}
          accent="0 84% 60%"
          onClick={() => onOpenTab("shadow")}
        />
        <MetricCard
          label="Guardrail gaps"
          value={summary.weakGuardrails || 0}
          sub={`${summary.noHumanApproval || 0} lack human approval`}
          kind="MODELLED"
          icon={ShieldCheck}
          accent="266 85% 66%"
          onClick={() => onOpenTab("guardrails")}
        />
        <MetricCard
          label="Open AI incidents"
          value={incidents.open || 0}
          sub={`${incidents.critical || 0} critical · ${incidents.high || 0} high`}
          kind="FACT"
          icon={AlertOctagon}
          accent="15 80% 55%"
          onClick={() => onOpenTab("incidents")}
        />
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <Panel
          title="Delegated machine authority"
          subtitle="MODELLED authority tier derived from each existing agent's tools and human approval guardrail."
          testid="agentic-authority-chart"
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={auth} margin={{ left: 0, right: 8, top: 10 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                <XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={28} />
                <Tooltip
                  contentStyle={{
                    background: "#0A0E17",
                    border: "1px solid rgba(255,255,255,.12)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar
                  dataKey="value"
                  fill="hsl(266 85% 66%)"
                  radius={[5, 5, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          title="Enterprise guardrail coverage"
          subtitle="FACT coverage from the current agent guardrail records."
          testid="agentic-guardrail-summary"
        >
          <div className="space-y-4">
            {guards.map((guard) => (
              <button
                key={guard.key}
                onClick={() => onOpenTab("guardrails")}
                className="w-full text-left"
              >
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span>{guard.label}</span>
                  <span className="font-mono text-muted-foreground">
                    {guard.active}/{guard.total} · {guard.pct}%
                  </span>
                </div>
                <ProgressBar
                  value={guard.pct}
                  accent={guard.pct >= 80 ? "142 70% 45%" : guard.pct >= 60 ? "35 90% 55%" : "0 84% 60%"}
                />
              </button>
            ))}
          </div>

          <div className="mt-5 rounded-lg bg-secondary/30 p-3">
            <div className="flex items-center gap-2 text-sm font-head font-bold">
              <UserCheck className="w-4 h-4 text-ai" />
              Human approval coverage
            </div>
            <div className="text-xs text-muted-foreground mt-2">
              {Math.max(0, (summary.total || 0) - (summary.noHumanApproval || 0))} of {summary.total || 0} agents currently record the human in the loop guardrail.
            </div>
          </div>
        </Panel>

        <Panel
          title="OWASP LLM posture"
          subtitle="Existing analytics coverage. Monitored does not mean blocked."
          testid="agentic-owasp"
        >
          {owasp.length === 0 ? (
            <div className="text-sm text-muted-foreground">No OWASP LLM analytics are available.</div>
          ) : (
            <div className="space-y-2">
              {owasp.slice(0, 10).map((item) => (
                <div key={item.code} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                  <div className="min-w-0">
                    <div className="font-mono text-[10px] text-ai">{item.code}</div>
                    <div className="text-xs truncate">{item.name}</div>
                  </div>
                  <StatusPill value={item.status} />
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel
        title="Highest risk AI agents"
        subtitle="Prioritized using the client-side modeled risk score. Click an agent for evidence and AI analysis."
        testid="agentic-top-agents"
      >
        {topAgents.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            No agents are registered in the current organization.
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {topAgents.map((agent) => (
              <button
                key={agent.ref}
                onClick={() => onSelectAgent(agent)}
                className="text-left rounded-xl border border-border bg-secondary/20 p-4 hover:bg-secondary/40 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-[10px] text-ai">{agent.ref}</div>
                    <div className="font-head font-bold mt-1">{agent.name}</div>
                    <div className="text-[11px] text-muted-foreground mt-1">
                      {agent.owner} · {agent.model}
                    </div>
                  </div>
                  <div className="font-head font-black text-2xl">{agent.modeledRisk}</div>
                </div>
                <div className="flex flex-wrap gap-1.5 mt-3">
                  <StatusPill value={agent.risk_class} />
                  <StatusPill value={agent.status} />
                  <StatusPill value={agent.authority} />
                </div>
                <div className="text-[10px] text-muted-foreground mt-3">
                  Guardrails {agent.guardrailCoverage.pct}% · {(agent.actionTools || []).length} action-capable tool(s)
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Operational control loop"
        subtitle="This app reuses existing workflows and governance states. Runtime enforcement is only claimed when an execution connector can verify it."
        testid="agentic-control-loop"
      >
        <div className="grid md:grid-cols-4 gap-3">
          <div className="rounded-lg bg-secondary/30 p-3">
            <Workflow className="w-4 h-4 text-ai" />
            <div className="text-[9px] font-mono uppercase text-muted-foreground mt-2">Workflows</div>
            <div className="font-head font-black text-2xl mt-1">{data.workflows?.length || 0}</div>
          </div>
          <div className="rounded-lg bg-secondary/30 p-3">
            <ShieldAlert className="w-4 h-4 text-crit" />
            <div className="text-[9px] font-mono uppercase text-muted-foreground mt-2">Tool violations</div>
            <div className="font-head font-black text-2xl mt-1">{summary.toolViolations || 0}</div>
          </div>
          <div className="rounded-lg bg-secondary/30 p-3">
            <ShieldCheck className="w-4 h-4 text-low" />
            <div className="text-[9px] font-mono uppercase text-muted-foreground mt-2">Sanctioned</div>
            <div className="font-head font-black text-2xl mt-1">{summary.sanctioned || 0}</div>
          </div>
          <div className="rounded-lg bg-secondary/30 p-3">
            <Zap className="w-4 h-4 text-high" />
            <div className="text-[9px] font-mono uppercase text-muted-foreground mt-2">Low red-team baseline</div>
            <div className="font-head font-black text-2xl mt-1">{summary.lowRedteam || 0}</div>
          </div>
        </div>
      </Panel>
    </div>
  );
}