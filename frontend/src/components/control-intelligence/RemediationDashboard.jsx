import { useState } from "react";
import { AlertTriangle, Bell, Loader2, TrendingDown } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { EmptyState, Panel, StatusPill } from "@/components/control-intelligence/shared";

export default function RemediationDashboard({ controls, gaps, onSelectControl, isAdmin }) {
  const [nudging, setNudging] = useState(false);
  const sendNudges = async () => {
    setNudging(true);
    try {
      const r = await api.post("/control-intelligence/owner-nudges");
      if (r.data.at_risk === 0) toast.success("No at-risk controls — nothing to remind.");
      else toast.success(`Reminder sent for ${r.data.at_risk} control(s) to ${r.data.emailed.length} recipient(s).`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to send owner reminders.");
    } finally {
      setNudging(false);
    }
  };

  const priority = (controls || []).filter(
    (control) =>
      control.status !== "Passing" ||
      control.evidence_state !== "Fresh" ||
      control.drift
  );

  return (
    <div className="space-y-5">
      <Panel
        title="Control remediation priority"
        subtitle="MODELLED priority is derived client-side from existing status, effectiveness, maturity, drift and evidence freshness."
        testid="control-intel-remediation"
        actions={isAdmin ? (
          <button data-testid="ci-send-owner-nudges" onClick={sendNudges} disabled={nudging}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">
            {nudging ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Bell className="w-3.5 h-3.5" />} Send owner reminders
          </button>
        ) : null}
      >
        {priority.length === 0 ? (
          <EmptyState
            title="No control remediation queue"
            text="All current controls are passing with sufficiently fresh evidence."
          />
        ) : (
          <div className="space-y-3">
            {priority.map((control) => (
              <button
                key={control.control_id}
                onClick={() => onSelectControl(control)}
                data-testid={`control-intel-remediation-row-${control.control_id}`}
                className="w-full text-left rounded-xl border border-border bg-secondary/20 p-4 hover:bg-secondary/40"
              >
                <div className="grid xl:grid-cols-[1.4fr_.6fr_.6fr_.6fr] gap-4">
                  <div>
                    <div className="font-mono text-[10px] text-ai">{control.control_id}</div>
                    <div className="font-head font-bold mt-1">{control.name}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {control.owner || "Unassigned"} · {control.category}
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      <StatusPill value={control.status} />
                      <StatusPill value={control.evidence_state} />
                      {control.drift && <StatusPill value="Drift detected" />}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Priority</div>
                    <div className="font-head font-black text-2xl mt-1">{control.priority_score}</div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Effectiveness</div>
                    <div className="font-head font-black text-2xl mt-1">{control.effectiveness}%</div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Maturity</div>
                    <div className="font-head font-black text-2xl mt-1">{control.maturity || 0}/5</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Framework gap feed"
        subtitle="Gap records returned by the existing controls compliance service."
        testid="control-intel-framework-gaps"
      >
        {(gaps || []).length === 0 ? (
          <div className="text-sm text-muted-foreground">No framework gap records were returned.</div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {(gaps || []).slice(0, 18).map((gap, index) => (
              <div key={gap.control_id || gap.id || index} className="rounded-lg border border-border p-3">
                <div className="flex items-start justify-between gap-2">
                  <AlertTriangle className="w-4 h-4 text-high" />
                  <StatusPill value={gap.status || "Gap"} />
                </div>
                <div className="font-mono text-[10px] text-ai mt-2">
                  {gap.control_id || gap.id || "CONTROL"}
                </div>
                <div className="font-head font-bold text-sm mt-1">
                  {gap.name || gap.control_name || "Control gap"}
                </div>
                <div className="flex items-center gap-1 text-[10px] text-muted-foreground mt-2">
                  <TrendingDown className="w-3 h-3" />
                  Effectiveness {gap.effectiveness ?? "—"}%
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
