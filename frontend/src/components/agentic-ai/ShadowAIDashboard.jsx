import { CheckCircle2, EyeOff, Loader2, Radar, ShieldCheck } from "lucide-react";
import { EmptyState, Panel, StatusPill } from "@/components/agentic-ai/shared";
import { useDeepDive } from "@/context/DeepDiveContext";
import { systemDeepDive } from "@/lib/agenticDeepDive";

export default function ShadowAIDashboard({
  systems,
  analytics,
  isAdmin,
  busySystem,
  onSanction,
  onDiscover,
  discovering,
  onReload,
}) {
  const { openDeepDive, warm } = useDeepDive();
  const shadowSystems = (systems || []).filter((system) => system.status === "shadow");
  const sanctioned = (systems || []).filter((system) => system.status === "sanctioned");

  return (
    <div className="space-y-5">
      <div className="grid xl:grid-cols-3 gap-4">
        <div className="bg-card fact-border rounded-xl p-4">
          <EyeOff className="w-4 h-4 text-crit" />
          <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">Shadow AI</div>
          <div className="font-head font-black text-3xl mt-1">{shadowSystems.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Unsanctioned systems in the existing AI system inventory</div>
        </div>
        <div className="bg-card fact-border rounded-xl p-4">
          <ShieldCheck className="w-4 h-4 text-low" />
          <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">Sanctioned AI</div>
          <div className="font-head font-black text-3xl mt-1">{sanctioned.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Governed AI system records</div>
        </div>
        <div className="bg-card fact-border rounded-xl p-4">
          <CheckCircle2 className="w-4 h-4 text-ai" />
          <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">AI queries observed</div>
          <div className="font-head font-black text-3xl mt-1">{(analytics?.totals?.queries || 0).toLocaleString()}</div>
          <div className="text-xs text-muted-foreground mt-1">Existing Obserra advisor telemetry</div>
        </div>
      </div>

      <Panel
        title="Shadow AI review queue"
        subtitle="Discovery auto-populates unsanctioned AI across the estate. Sanctioning updates the AI system governance status. It does not automatically configure an external provider."
        testid="agentic-shadow-ai"
        actions={isAdmin ? (
          <button
            data-testid="shadow-discover-btn"
            onClick={onDiscover}
            disabled={discovering}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
          >
            {discovering ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Radar className="w-3.5 h-3.5" />}
            Run discovery
          </button>
        ) : null}
      >
        {shadowSystems.length === 0 ? (
          <EmptyState
            title="No shadow AI systems"
            text="Run discovery to auto-populate the queue with unsanctioned AI detected across the estate."
          />
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {shadowSystems.map((system) => (
              <div
                key={system.ref || system.id || system.name}
                onMouseEnter={() => warm(systemDeepDive(system))}
                onClick={() => openDeepDive(systemDeepDive(system, { isAdmin, onReload }))}
                data-testid={`shadow-system-${system.ref || system.name}`}
                className="rounded-xl border border-crit/20 bg-crit/5 p-4 cursor-pointer hover:bg-crit/10 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-[10px] text-ai">{system.ref || system.id || "AI-SYSTEM"}</div>
                    <div className="font-head font-bold mt-1">{system.name || system.system || "Unnamed AI system"}</div>
                  </div>
                  <StatusPill value={system.status} />
                </div>
                <div className="text-xs text-muted-foreground mt-3 space-y-1">
                  {system.owner && <div>Owner: {system.owner}</div>}
                  {system.provider && <div>Provider: {system.provider}</div>}
                  {system.model && <div>Model: {system.model}</div>}
                  {system.risk_class && <div>Risk: {system.risk_class}</div>}
                </div>

                {isAdmin && system.ref && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onSanction(system); }}
                    disabled={busySystem === system.ref}
                    className="mt-4 w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-low/15 border border-low/25 text-low text-xs font-head font-bold disabled:opacity-50"
                  >
                    {busySystem === system.ref ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <ShieldCheck className="w-3.5 h-3.5" />
                    )}
                    Sanction governance record
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Sanctioned AI systems"
        subtitle="Existing governed AI system inventory."
        testid="agentic-sanctioned-ai"
      >
        {sanctioned.length === 0 ? (
          <div className="text-sm text-muted-foreground">No sanctioned AI systems are recorded.</div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
            {sanctioned.map((system) => (
              <div key={system.ref || system.id || system.name} className="rounded-lg border border-low/20 bg-low/5 p-3">
                <div className="font-head font-bold text-sm">{system.name || system.system || "AI System"}</div>
                <div className="text-[10px] font-mono text-muted-foreground mt-1">{system.ref || system.id || "—"}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}