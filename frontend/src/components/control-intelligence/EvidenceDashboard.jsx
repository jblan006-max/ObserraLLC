import { Clock, FileDown, Loader2, ShieldCheck } from "lucide-react";
import { EmptyState, Panel, StatusPill } from "@/components/control-intelligence/shared";

export default function EvidenceDashboard({
  controls,
  busyId,
  onSelectControl,
  onEvidencePack,
  onExportLog,
}) {
  const ordered = [...(controls || [])].sort((a, b) => {
    const ad = Number(a.days_to_expiry ?? 9999);
    const bd = Number(b.days_to_expiry ?? 9999);
    return ad - bd;
  });

  return (
    <div className="space-y-5">
      <Panel
        title="Evidence assurance queue"
        subtitle="Prioritized by evidence expiry. Uses the existing evidence pack and control log report endpoints."
        testid="control-intel-evidence"
      >
        {ordered.length === 0 ? (
          <EmptyState
            title="No controls available"
            text="Evidence assurance requires controls from the existing control catalog."
          />
        ) : (
          <div className="space-y-3">
            {ordered.map((control) => (
              <div key={control.control_id} className="rounded-xl border border-border bg-secondary/20 p-4">
                <div className="grid xl:grid-cols-[1.3fr_.7fr_.7fr_auto] gap-4 items-center">
                  <button onClick={() => onSelectControl(control)} className="text-left">
                    <div className="font-mono text-[10px] text-ai">{control.control_id}</div>
                    <div className="font-head font-bold mt-1">{control.name}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {control.owner || "Unassigned"} · {control.category}
                    </div>
                  </button>

                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Evidence state</div>
                    <div className="mt-2"><StatusPill value={control.evidence_state} /></div>
                  </div>

                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3 h-3" /> Time to expiry
                    </div>
                    <div className="font-head font-black text-xl mt-1">
                      {control.days_to_expiry != null ? `${control.days_to_expiry}d` : "—"}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => onEvidencePack(control)}
                      disabled={busyId === control.control_id}
                      data-testid={`control-intel-evidence-pack-${control.control_id}`}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
                    >
                      {busyId === control.control_id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <ShieldCheck className="w-3.5 h-3.5" />
                      )}
                      Evidence Pack
                    </button>
                    <button
                      onClick={() => onExportLog(control)}
                      disabled={busyId === control.control_id}
                      data-testid={`control-intel-evidence-log-${control.control_id}`}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary text-xs font-head font-bold disabled:opacity-50"
                    >
                      <FileDown className="w-3.5 h-3.5" />
                      Control Log
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
