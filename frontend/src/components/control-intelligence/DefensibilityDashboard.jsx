import { CheckCircle2, Database, ShieldCheck, XCircle } from "lucide-react";
import { DataClassBadge, Panel } from "@/components/control-intelligence/shared";

const SOURCE_LABEL = {
  controls: "Control Monitoring",
  compliance: "Control Compliance",
  crosswalk: "Framework Crosswalk",
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
          subtitle="Missing source data is shown as unavailable rather than replaced."
          testid="control-intel-source-status"
        >
          <div className="space-y-2">
            {Object.entries(sourceStatus || {}).map(([key, status]) => (
              <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="flex items-center gap-2">
                  {status.ok ? (
                    <CheckCircle2 className="w-4 h-4 text-low" />
                  ) : (
                    <XCircle className="w-4 h-4 text-crit" />
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
          subtitle="Control Intelligence separates source facts from calculations and recommendations."
          testid="control-intel-classification"
        >
          <div className="space-y-4">
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="FACT" />
              <p className="text-xs text-muted-foreground mt-2">
                Control status, effectiveness, maturity, owner, evidence expiry, framework coverage, crosswalk mappings and history records returned by the current backend.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="MODELLED" />
              <p className="text-xs text-muted-foreground mt-2">
                Control health score, priority score, evidence state grouping and cross-framework convergence ranking calculated in the browser.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="AI RECOMMENDATION" />
              <p className="text-xs text-muted-foreground mt-2">
                Obserra Advisor explanations and recommended control actions.
              </p>
            </div>
          </div>
        </Panel>

        <Panel
          title="Governance boundary"
          subtitle="This standalone application composes on existing services."
          testid="control-intel-boundary"
        >
          <div className="space-y-3 text-sm">
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              No new backend service or database collection is introduced.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Evidence pack and control log exports use existing report APIs.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Control notes use the existing control history and notes APIs.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Framework intelligence uses the existing compliance and crosswalk APIs.
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        title="Connector health context"
        subtitle={`${summary.healthy || 0} healthy · ${summary.degraded || 0} degraded. Existing connector health only.`}
        testid="control-intel-connectors"
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
                <div className="font-head font-bold text-sm">{connector.name}</div>
                <div className="text-[10px] text-muted-foreground mt-1">{connector.category}</div>
                <div className="text-[10px] font-mono mt-2">
                  {connector.health || connector.state || "unknown"}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
