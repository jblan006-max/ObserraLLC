import { AlertOctagon, ShieldAlert } from "lucide-react";
import { EmptyState, Panel, StatusPill } from "@/components/agentic-ai/shared";
import { useDeepDive } from "@/context/DeepDiveContext";
import { incidentDeepDive } from "@/lib/agenticDeepDive";

export default function IncidentsDashboard({ incidents, workflows }) {
  const { openDeepDive, warm } = useDeepDive();
  return (
    <div className="space-y-5">
      <Panel
        title="AI security incident intelligence"
        subtitle="Current AI incident records from the existing Obserra AI governance backend."
        testid="agentic-incidents"
      >
        {(incidents || []).length === 0 ? (
          <EmptyState
            title="No AI incidents recorded"
            text="No AI governance incidents are present in the existing backend for this organization."
          />
        ) : (
          <div className="space-y-3">
            {(incidents || []).map((incident, index) => (
              <div
                key={incident.ref || incident.id || index}
                onMouseEnter={() => warm(incidentDeepDive(incident))}
                onClick={() => openDeepDive(incidentDeepDive(incident))}
                data-testid={`incident-${incident.ref || incident.id || index}`}
                className="rounded-xl border border-border bg-secondary/20 p-4 cursor-pointer hover:bg-secondary/40 transition-colors"
              >
                <div className="grid xl:grid-cols-[1.4fr_.8fr_.8fr_.8fr] gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <AlertOctagon className="w-4 h-4 text-crit" />
                      <div className="font-mono text-[10px] text-ai">{incident.ref || incident.id || "AI-INCIDENT"}</div>
                    </div>
                    <div className="font-head font-bold mt-2">{incident.title || incident.name || "AI governance incident"}</div>
                    {incident.system && <div className="text-xs text-muted-foreground mt-1">System: {incident.system}</div>}
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Severity</div>
                    <div className="mt-2"><StatusPill value={incident.severity || "Unknown"} /></div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Mode</div>
                    <div className="mt-2"><StatusPill value={incident.mode || "Observe"} /></div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Status</div>
                    <div className="mt-2"><StatusPill value={incident.status || "Open"} /></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Governance workflows"
        subtitle="Related shared-kernel workflow records available to the current tenant."
        testid="agentic-workflows"
      >
        {(workflows || []).length === 0 ? (
          <div className="text-sm text-muted-foreground">No workflows are currently returned by the shared workflow API.</div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {(workflows || []).slice(0, 12).map((workflow, index) => (
              <div key={workflow.id || workflow.ref || index} className="rounded-lg border border-border p-3">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-ai" />
                  <div className="font-head font-bold text-sm">{workflow.title || workflow.type || "Workflow"}</div>
                </div>
                <div className="text-[10px] text-muted-foreground mt-2">
                  {workflow.status || "Unknown status"}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}