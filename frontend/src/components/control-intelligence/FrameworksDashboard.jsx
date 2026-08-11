import { useState } from "react";
import { Layers } from "lucide-react";
import { EmptyState, PALETTE, Panel, ProgressBar, StatusPill } from "@/components/control-intelligence/shared";
import {
  convergenceLeaders,
  frameworkNames,
} from "@/lib/controlIntelligenceModels";
import FrameworkDetailModal from "@/components/control-intelligence/FrameworkDetailModal";

const pal = (i) => PALETTE[i % PALETTE.length];

function mappingValue(row, framework) {
  const candidates = [
    row.frameworks,
    row.mapping,
    row.mappings,
    row.framework_map,
    row.framework_refs,
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (typeof candidate !== "object") continue;
    const value = candidate[framework];
    if (Array.isArray(value)) return value.join(", ");
    if (value) return String(value);
  }

  const direct = row[framework];
  if (Array.isArray(direct)) return direct.join(", ");
  return direct ? String(direct) : "";
}

export default function FrameworksDashboard({ compliance, crosswalk, controls = [] }) {
  const [selected, setSelected] = useState(null);
  const frameworks = Array.isArray(compliance?.frameworks) ? compliance.frameworks : [];
  const names = frameworkNames(crosswalk, compliance);
  const rows = Array.isArray(crosswalk?.rows) ? crosswalk.rows : [];
  const leaders = convergenceLeaders(crosswalk, compliance);

  return (
    <div className="space-y-5">
      <Panel
        title="Framework readiness"
        subtitle="Existing framework coverage from the shared controls compliance service — click a framework for details, risk, scoring, mapped controls and AI fixes."
        testid="control-intel-framework-cards"
      >
        {frameworks.length === 0 ? (
          <EmptyState
            title="No framework readiness data"
            text="The existing controls compliance endpoint returned no framework records."
          />
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {frameworks.map((framework, i) => (
              <button
                key={framework.framework}
                onClick={() => setSelected(framework)}
                data-testid={`control-intel-framework-card-${i}`}
                className="text-left rounded-xl border border-border bg-secondary/20 p-4 hover:bg-secondary/40 transition-colors"
                style={{ borderLeft: `3px solid hsl(${pal(i)})` }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="font-head font-bold flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: `hsl(${pal(i)})` }} />
                    {framework.framework}
                  </div>
                  <StatusPill
                    value={framework.coverage >= 75 ? "Strong" : framework.coverage >= 55 ? "Watch" : "High gap"}
                  />
                </div>
                <div className="font-head font-black text-3xl mt-3" style={{ color: `hsl(${pal(i)})` }}>{framework.coverage}%</div>
                <div className="mt-3">
                  <ProgressBar value={framework.coverage} accent={pal(i)} />
                </div>
                <div className="text-xs text-muted-foreground mt-3">
                  {framework.passing}/{framework.controls} controls passing · {Math.max(0, (framework.controls || 0) - (framework.passing || 0))} gap(s)
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Cross-framework convergence leaders"
        subtitle="MODELLED ranking of controls mapped across the greatest number of current frameworks."
        testid="control-intel-convergence"
      >
        {leaders.length === 0 ? (
          <div className="text-sm text-muted-foreground">No crosswalk rows are currently available.</div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-5 gap-3">
            {leaders.map((row, index) => (
              <div key={row.control_id || row.id || index} className="rounded-lg border border-border p-3" style={{ borderTop: `2px solid hsl(${pal(index)})` }}>
                <div className="flex items-center justify-between gap-2">
                  <Layers className="w-4 h-4" style={{ color: `hsl(${pal(index)})` }} />
                  <span className="font-head font-black text-xl">{row.convergence_count}</span>
                </div>
                <div className="font-mono text-[10px] text-ai mt-2">
                  {row.control_id || row.id || "CONTROL"}
                </div>
                <div className="text-sm font-medium mt-1">
                  {row.name || row.control_name || "Mapped control"}
                </div>
                <div className="text-[10px] text-muted-foreground mt-1">framework mappings</div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Control crosswalk matrix"
        subtitle="Exact mappings returned by the existing /controls/crosswalk API."
        testid="control-intel-crosswalk"
      >
        {rows.length === 0 ? (
          <EmptyState
            title="Crosswalk unavailable"
            text="No control crosswalk rows were returned by the current backend."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1300px] text-xs">
              <thead className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
                <tr>
                  <th className="text-left py-3 pr-3">Obserra control</th>
                  <th className="text-left py-3 px-3">Verdict</th>
                  {names.map((framework, i) => (
                    <th key={framework} className="text-left py-3 px-3"><span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 rounded-full" style={{ background: `hsl(${pal(i)})` }} />{framework}</span></th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 200).map((row, index) => (
                  <tr key={row.control_id || row.id || index} className="border-b border-border/60">
                    <td className="py-3 pr-3 max-w-[280px]">
                      <div className="font-mono text-[10px] text-ai">
                        {row.control_id || row.id || "CONTROL"}
                      </div>
                      <div className="font-medium mt-1">
                        {row.name || row.control_name || "Control"}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <StatusPill
                        value={
                          row.compliant === true
                            ? "Passing"
                            : row.compliant === false
                            ? "Gap"
                            : row.status || "Mapped"
                        }
                      />
                    </td>
                    {names.map((framework) => {
                      const value = mappingValue(row, framework);
                      return (
                        <td key={framework} className="py-3 px-3 max-w-[240px]">
                          {value ? (
                            <span className="font-mono text-[10px]">{value}</span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {selected && (
        <FrameworkDetailModal framework={selected} controls={controls} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
