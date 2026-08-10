import { CheckCircle2, Database, ShieldCheck, XCircle } from "lucide-react";
import { DataClassBadge, Panel } from "@/components/agentic-ai/shared";

const SOURCE_LABEL = {
  agents: "AI Agent Governance",
  analytics: "AI Analytics",
  systems: "AI System Inventory",
  incidents: "AI Incidents",
  workflows: "Workflow Engine",
  connectorHealth: "Connector Health",
};

export default function DefensibilityDashboard({ data, sourceStatus }) {
  const connectors = data?.connectorHealth?.connectors || [];
  const summary = data?.connectorHealth?.summary || {};

  return (
    <div className="space-y-5">
      <div className="grid xl:grid-cols-3 gap-5">
        <Panel
          title="Data source status"
          subtitle="Unavailable sources are surfaced rather than replaced with synthetic data."
          testid="agentic-source-status"
        >
          <div className="space-y-2">
            {Object.entries(sourceStatus || {}).map(([key, status]) => (
              <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="flex items-center gap-2 min-w-0">
                  {status.ok ? (
                    <CheckCircle2 className="w-4 h-4 text-low shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-crit shrink-0" />
                  )}
                  <div>
                    <div className="text-sm font-medium">{SOURCE_LABEL[key] || key}</div>
                    {!status.ok && <div className="text-[10px] text-muted-foreground">{status.error}</div>}
                  </div>
                </div>
                <span className={`text-[10px] font-mono ${status.ok ? "text-low" : "text-crit"}`}>
                  {status.ok ? "LIVE" : "UNAVAILABLE"}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Evidence classification"
          subtitle="The app explicitly separates source facts from derived intelligence."
          testid="agentic-evidence-class"
        >
          <div className="space-y-4">
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="FACT" />
              <p className="text-xs text-muted-foreground mt-2">
                Agent inventory, tools, permissions, guardrails, governance status, AI systems, incidents, usage analytics and connector health returned by the existing backend.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="MODELLED" />
              <p className="text-xs text-muted-foreground mt-2">
                Agent risk score, delegated authority tier and action-capable tool classification calculated in the browser from existing records.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="HEURISTIC BASELINE" />
              <p className="text-xs text-muted-foreground mt-2">
                Existing red-team results are deterministic checks against recorded guardrails. They are not live adversarial runtime tests.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="AI RECOMMENDATION" />
              <p className="text-xs text-muted-foreground mt-2">
                Obserra Advisor interpretation, analysis and recommended executive actions.
              </p>
            </div>
          </div>
        </Panel>

        <Panel
          title="Runtime enforcement boundary"
          subtitle="Governance state is not confused with external runtime control."
          testid="agentic-runtime-boundary"
        >
          <div className="space-y-3 text-sm">
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Toggling a guardrail updates the existing Obserra governance record.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Sanctioning a system updates its governance status in Obserra.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              No external model, agent runtime or cloud service is claimed to be blocked unless a connected execution control verifies that action.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Future live red-team and kill-switch capabilities require explicit runtime connectors.
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        title="Connector health context"
        subtitle={`${summary.healthy || 0} healthy · ${summary.degraded || 0} degraded. Existing connector health only.`}
        testid="agentic-connectors"
      >
        {connectors.length === 0 ? (
          <div className="py-8 text-center">
            <Database className="w-8 h-8 text-muted-foreground mx-auto" />
            <div className="text-sm text-muted-foreground mt-2">No connector health records are available.</div>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {connectors.map((connector) => (
              <div key={`${connector.id}:${connector.name}`} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="font-head font-bold text-sm">{connector.name}</div>
                    <div className="text-[10px] text-muted-foreground mt-1">{connector.category}</div>
                  </div>
                  <span className={`text-[10px] font-mono ${connector.health === "healthy" ? "text-low" : connector.health === "degraded" ? "text-high" : "text-muted-foreground"}`}>
                    {connector.health || connector.state || "unknown"}
                  </span>
                </div>
                <div className="text-[10px] text-muted-foreground mt-3">
                  Last checked: {connector.checked_at ? new Date(connector.checked_at).toLocaleString() : "not available"}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}