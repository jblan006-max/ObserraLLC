import { useNavigate } from "react-router-dom";
import {
  AlertOctagon, ArrowRight, Bot, EyeOff, Gauge, ShieldAlert, ShieldCheck, Wrench, Zap,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAgenticAIData } from "@/hooks/useAgenticAIData";
import { useDeepDive } from "@/context/DeepDiveContext";
import { useAuth } from "@/context/AuthContext";
import {
  DataClassBadge, EmptyState, ErrorBanner, LoadingState, MetricCard, Panel, ProgressBar, StatusPill,
} from "@/components/agentic-ai/shared";
import { authorityDistribution, guardrailDistribution } from "@/lib/agenticAIModels";
import { toxicityModel } from "@/lib/agenticToxicity";
import { agentDeepDive, incidentDeepDive, systemDeepDive } from "@/lib/agenticDeepDive";
import BoardBriefControl from "@/components/agentic-ai/BoardBriefControl";
import { AIInsight } from "@/components/AIInsight";

const ACCENT = "330 81% 60%";

export default function AIExecutiveOverview() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const navigate = useNavigate();
  const { openDeepDive, warm } = useDeepDive();
  const { data, loading, error, reload, refreshing } = useAgenticAIData();

  if (loading && !data) return <LoadingState />;

  const summary = data?.agentSummary || {};
  const sys = data?.systemSummary || {};
  const inc = data?.incidentSummary || {};
  const tox = toxicityModel(data?.agents || []);
  const auth = authorityDistribution(data?.agents || []);
  const guards = guardrailDistribution(data?.agents || []);
  const topAgents = (data?.agents || []).slice(0, 6);
  const toxicAgents = tox.nodes.filter((n) => n.toxicity.toxic).slice(0, 6);
  const shadowSystems = (data?.systems || []).filter((s) => s.status === "shadow").slice(0, 6);
  const openIncidents = (data?.incidents || [])
    .filter((i) => !["closed", "resolved", "remediated"].includes(String(i.status || "").toLowerCase()))
    .slice(0, 6);

  const goTab = (tab) => {
    localStorage.setItem("agentic-ai-security-tab", tab);
    navigate("/app/agentic-ai-security");
  };

  const kpis = [
    { label: "Registered agents", value: summary.total ?? 0, sub: `${summary.critical || 0} critical · ${summary.high || 0} high`, icon: Bot, kind: "FACT", tab: "inventory" },
    { label: "Modeled avg risk", value: `${summary.averageRisk ?? 0}/100`, sub: "Weighted across the estate", icon: Gauge, kind: "MODELLED", accent: "0 84% 60%", tab: "inventory" },
    { label: "Autonomous agents", value: summary.autonomous ?? 0, sub: `${summary.noHumanApproval || 0} without human approval`, icon: Zap, kind: "MODELLED", accent: "0 84% 60%", tab: "authority" },
    { label: "Toxic combinations", value: tox.toxic, sub: `${tox.critical} critical pattern(s)`, icon: ShieldAlert, kind: "MODELLED", accent: "0 84% 60%", tab: "authority" },
    { label: "Shadow AI systems", value: sys.shadow ?? 0, sub: `${sys.total || 0} systems tracked`, icon: EyeOff, kind: "FACT", accent: "0 84% 60%", tab: "shadow" },
    { label: "Guardrail gaps", value: summary.weakGuardrails ?? 0, sub: "Agents below 75% coverage", icon: ShieldCheck, kind: "MODELLED", accent: "35 90% 55%", tab: "guardrails" },
    { label: "Tool violations", value: summary.toolViolations ?? 0, sub: "Dangerous tool, no allowlist", icon: Wrench, kind: "FACT", accent: "35 90% 55%", tab: "authority" },
    { label: "Open AI incidents", value: inc.open ?? 0, sub: `${inc.critical || 0} critical`, icon: AlertOctagon, kind: "FACT", accent: "35 90% 55%", tab: "incidents" },
  ];

  return (
    <div className="rise space-y-6" data-testid="ai-executive-overview">
      <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-head font-black text-3xl tracking-tight">Executive Overview</h1>
            <span className="px-2 py-1 rounded-full border border-ai/25 bg-ai/10 text-ai text-[10px] font-mono">AI SECURITY ROLLUP</span>
            <span data-testid="overview-version-badge" className="px-2 py-1 rounded-full border border-border bg-secondary/60 text-muted-foreground text-[10px] font-mono font-bold">v1</span>
          </div>
          <p className="text-sm text-muted-foreground mt-2 max-w-3xl">
            A single board-ready rollup of the whole Agentic AI Security estate — modelled agent risk, delegated
            autonomy, toxic capability combinations, shadow AI exposure, guardrail gaps and open incidents. Every card
            drills into the Control Plane or opens a full deep-dive.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isAdmin && <BoardBriefControl />}
          <button
            data-testid="open-control-plane-btn"
            onClick={() => navigate("/app/agentic-ai-security")}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"
          >
            Open Control Plane <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onRetry={reload} refreshing={refreshing} />

      <AIInsight dashboard="Agentic AI Security — Executive Overview" accent={ACCENT} auto slug="agentic-ai-security" />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {kpis.map((k) => (
          <MetricCard
            key={k.label}
            label={k.label}
            value={k.value}
            sub={k.sub}
            icon={k.icon}
            kind={k.kind}
            accent={k.accent || ACCENT}
            onClick={() => goTab(k.tab)}
            testid={`overview-kpi-${k.tab}-${k.label.toLowerCase().replace(/[^a-z]+/g, "-")}`}
          />
        ))}
      </div>

      <div className="grid xl:grid-cols-3 gap-4">
        <Panel title="Delegated machine authority" subtitle="How much autonomy agents hold" testid="overview-authority-chart">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={auth} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} interval={0} angle={-18} textAnchor="end" height={48} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]} fill={`hsl(${ACCENT})`} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Guardrail coverage" subtitle="Enterprise defensive controls" testid="overview-guardrail-coverage" actions={<DataClassBadge kind="MODELLED" />}>
          <div className="space-y-4">
            {guards.map((g) => (
              <div key={g.key}>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="text-muted-foreground">{g.label}</span>
                  <span className="font-mono font-bold">{g.active}/{g.total} · {g.pct}%</span>
                </div>
                <ProgressBar value={g.pct} accent={g.pct >= 75 ? "142 70% 45%" : g.pct >= 50 ? "35 90% 55%" : "0 84% 60%"} />
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Highest-risk agents" subtitle="Modelled agent risk · click for deep-dive" testid="overview-top-agents">
          <div className="space-y-2">
            {topAgents.length === 0 && <EmptyState title="No agents" text="Register agents in the Control Plane." />}
            {topAgents.map((a) => (
              <button
                key={a.ref}
                onMouseEnter={() => warm(agentDeepDive(a))}
                onClick={() => openDeepDive(agentDeepDive(a))}
                data-testid={`overview-agent-${a.ref}`}
                className="w-full text-left flex items-center gap-3 rounded-lg border border-border bg-secondary/20 p-2.5 hover:bg-secondary/40 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-head font-bold truncate">{a.name}</div>
                  <div className="text-[10px] font-mono text-muted-foreground">{a.ref} · {a.owner}</div>
                </div>
                <StatusPill value={a.authority} />
                <div className="font-head font-black text-lg tabular-nums" style={{ color: `hsl(${a.modeledRisk >= 70 ? "0 84% 60%" : a.modeledRisk >= 45 ? "35 90% 55%" : "142 70% 45%"})` }}>{a.modeledRisk}</div>
              </button>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid xl:grid-cols-3 gap-4">
        <Panel title="Toxic capability combinations" subtitle="Dangerous tool + permission + weak guardrail" testid="overview-toxic-combos" actions={<DataClassBadge kind="MODELLED" />}>
          <div className="space-y-2">
            {toxicAgents.length === 0 && <EmptyState title="No toxic combinations" text="No agent currently combines dangerous capabilities without the matching guardrail." />}
            {toxicAgents.map((n) => (
              <button
                key={n.ref}
                onMouseEnter={() => warm(agentDeepDive(n))}
                onClick={() => openDeepDive(agentDeepDive(n))}
                data-testid={`overview-toxic-${n.ref}`}
                className="w-full text-left rounded-lg border border-crit/25 bg-crit/5 p-2.5 hover:bg-crit/10 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-crit shrink-0" />
                  <span className="text-sm font-head font-bold truncate flex-1">{n.name}</span>
                  <span className="text-[10px] font-mono text-crit uppercase">{n.toxicity.level}</span>
                </div>
                <div className="text-[11px] text-muted-foreground mt-1 line-clamp-2">{n.toxicity.reasons.join(" · ")}</div>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="Shadow AI queue" subtitle="Unsanctioned AI to review" testid="overview-shadow-queue">
          <div className="space-y-2">
            {shadowSystems.length === 0 && <EmptyState title="Queue clear" text="Run discovery in the Shadow AI tab to populate this queue." />}
            {shadowSystems.map((s) => (
              <button
                key={s.ref || s.name}
                onMouseEnter={() => warm(systemDeepDive(s))}
                onClick={() => openDeepDive(systemDeepDive(s))}
                data-testid={`overview-shadow-${s.ref || s.name}`}
                className="w-full text-left flex items-center gap-3 rounded-lg border border-crit/20 bg-crit/5 p-2.5 hover:bg-crit/10 transition-colors"
              >
                <EyeOff className="w-4 h-4 text-crit shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-head font-bold truncate">{s.name}</div>
                  <div className="text-[10px] font-mono text-muted-foreground truncate">{s.provider || "Unknown"} · {s.owner || "Unassigned"}</div>
                </div>
                <StatusPill value={s.risk_class} />
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="Open AI incidents" subtitle="Active security events" testid="overview-incidents">
          <div className="space-y-2">
            {openIncidents.length === 0 && <EmptyState title="No open incidents" text="No active AI security incidents." />}
            {openIncidents.map((i) => (
              <button
                key={i.ref || i.id}
                onMouseEnter={() => warm(incidentDeepDive(i))}
                onClick={() => openDeepDive(incidentDeepDive(i))}
                data-testid={`overview-incident-${i.ref || i.id}`}
                className="w-full text-left flex items-center gap-3 rounded-lg border border-border bg-secondary/20 p-2.5 hover:bg-secondary/40 transition-colors"
              >
                <AlertOctagon className="w-4 h-4 text-high shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-head font-bold truncate">{i.title || i.name || "Incident"}</div>
                  <div className="text-[10px] font-mono text-muted-foreground">{i.status || "Open"} · {i.mode || "Observe"}</div>
                </div>
                <StatusPill value={i.severity} />
              </button>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
