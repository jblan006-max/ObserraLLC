import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import {
  EmptyState,
  Panel,
  ProgressBar,
  StatusPill,
} from "@/components/control-intelligence/shared";

export default function EffectivenessDashboard({ controls, onSelectControl }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (controls || []).filter((control) => {
      if (status !== "all" && control.status !== status) return false;
      if (!q) return true;
      return `${control.control_id} ${control.name} ${control.category} ${control.owner || ""}`
        .toLowerCase()
        .includes(q);
    });
  }, [controls, query, status]);

  return (
    <Panel
      title="Control effectiveness intelligence"
      subtitle="Current effectiveness, maturity, drift, evidence freshness and modeled priority in one operational view."
      testid="control-intel-effectiveness"
    >
      <div className="flex flex-col md:flex-row gap-2 mb-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search control, owner or category"
            className="w-full bg-secondary/60 rounded-md pl-9 pr-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary"
            data-testid="control-intel-effectiveness-search"
          />
        </div>
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
          data-testid="control-intel-effectiveness-status"
        >
          <option value="all">All statuses</option>
          <option value="Passing">Passing</option>
          <option value="Drifting">Drifting</option>
          <option value="Failing">Failing</option>
          <option value="Evidence Stale">Evidence Stale</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="No matching controls"
          text="Adjust the current filters or populate the existing control catalog."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] text-sm">
            <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
              <tr>
                <th className="text-left py-3 pr-3">Control</th>
                <th className="text-left py-3 px-3">Status</th>
                <th className="text-left py-3 px-3">Effectiveness</th>
                <th className="text-left py-3 px-3">Maturity</th>
                <th className="text-left py-3 px-3">Evidence</th>
                <th className="text-left py-3 px-3">Frameworks</th>
                <th className="text-left py-3 pl-3">Priority</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((control) => (
                <tr
                  key={control.control_id}
                  onClick={() => onSelectControl(control)}
                  className="border-b border-border/60 hover:bg-secondary/35 cursor-pointer"
                  data-testid={`control-intel-effectiveness-row-${control.control_id}`}
                >
                  <td className="py-3 pr-3 max-w-[380px]">
                    <div className="font-mono text-[10px] text-ai">{control.control_id}</div>
                    <div className="font-medium">{control.name}</div>
                    <div className="text-[10px] text-muted-foreground mt-1">
                      {control.category} · {control.owner || "Unassigned"}
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <StatusPill value={control.status} />
                  </td>
                  <td className="py-3 px-3 min-w-[180px]">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span>{control.effectiveness}%</span>
                    </div>
                    <ProgressBar
                      value={control.effectiveness}
                      accent={
                        control.effectiveness >= 75
                          ? "142 70% 45%"
                          : control.effectiveness >= 55
                          ? "35 90% 55%"
                          : "0 84% 60%"
                      }
                    />
                  </td>
                  <td className="py-3 px-3 font-mono">{control.maturity || 0}/5</td>
                  <td className="py-3 px-3">
                    <StatusPill value={control.evidence_state} />
                    <div className="text-[10px] text-muted-foreground mt-1">
                      {control.days_to_expiry != null
                        ? `${control.days_to_expiry} days`
                        : "No expiry returned"}
                    </div>
                  </td>
                  <td className="py-3 px-3 font-mono">{control.framework_count}</td>
                  <td className="py-3 pl-3">
                    <span className="font-head font-black text-lg">{control.priority_score}</span>
                    <span className="text-[10px] text-muted-foreground">/100</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
