// Extracted from SodCommandCenter for maintainability (no behavior change).
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Wrench } from "lucide-react";
import { Area } from "recharts";
import { Chip } from "@/components/sod/sodPrimitives";

export function SodConflictsTable(props) {
  const { area, data, openConflict, setArea, setControl, setMit, setMitStatus, setSev, setStatus, sev, status } = props;
  return (
      <div className="bg-card fact-border rounded-xl">
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
          <h2 className="font-head font-bold text-base flex-1">Detected Conflicts</h2>
          <Select value={sev} onValueChange={setSev}><SelectTrigger data-testid="sod-filter-sev" className="w-[130px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All severity</SelectItem><SelectItem value="Critical">Critical</SelectItem><SelectItem value="High">High</SelectItem><SelectItem value="Medium">Medium</SelectItem></SelectContent></Select>
          <Select value={area} onValueChange={setArea}><SelectTrigger data-testid="sod-filter-area" className="w-[150px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All areas</SelectItem>{data.areas.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent></Select>
          <Select value={status} onValueChange={setStatus}><SelectTrigger data-testid="sod-filter-status" className="w-[140px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All statuses</SelectItem><SelectItem value="Open">Open</SelectItem><SelectItem value="Mitigated">Mitigated</SelectItem><SelectItem value="Accepted">Accepted</SelectItem></SelectContent></Select>
        </div>
        <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
          <table className="w-full text-sm" data-testid="sod-table">
            <thead className="sticky top-0 bg-card"><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
              <th className="p-3">Severity</th><th className="p-3">Rule</th><th className="p-3">User</th><th className="p-3">System</th><th className="p-3">Area</th><th className="p-3">Status</th><th className="p-3 text-right">Action</th>
            </tr></thead>
            <tbody>
              {data.conflicts.map((c) => (
                <tr key={c.conflict_ref} className="border-b border-border/50 hover:bg-secondary/30" data-testid={`sod-row-${c.conflict_ref}`}>
                  <td className="p-3"><Chip v={c.severity} /></td>
                  <td className="p-3"><button onClick={() => openConflict(c)} className="text-left hover:text-primary font-medium" data-testid={`sod-open-${c.conflict_ref}`}>{c.rule_name}</button></td>
                  <td className="p-3 whitespace-nowrap">{c.person_name}</td>
                  <td className="p-3 font-mono text-xs">{c.system}</td>
                  <td className="p-3 text-xs">{c.area}</td>
                  <td className="p-3"><Chip v={c.status} map={{ Open: "0 84% 60%", Mitigated: "142 70% 45%", Accepted: "35 90% 55%" }} /></td>
                  <td className="p-3 text-right"><button data-testid={`sod-mitigate-${c.conflict_ref}`} onClick={() => { setMit(c); setControl(c.mitigating_control || ""); setMitStatus(c.status === "Open" ? "Mitigated" : c.status); }} className="inline-flex items-center gap-1 text-xs text-ai hover:underline"><Wrench className="w-3.5 h-3.5" /> Mitigate</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
  );
}
