// Extracted from SodCommandCenter for maintainability (no behavior change).
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FlaskConical, ScrollText } from "lucide-react";
import { Chip } from "@/components/sod/sodPrimitives";

export function SodToolsRow(props) {
  const { addSimRole, area, data, openRule, people, roles, rules, runSim, setSimPerson, setSimRole, simPerson, simResult, simRole, simRoles } = props;
  return (
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Simulator */}
        <div className="lg:col-span-5 bg-card fact-border rounded-xl p-5" data-testid="sod-simulator">
          <div className="flex items-center gap-2 mb-1"><FlaskConical className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-base">Pre-Assignment Risk Simulation</h2></div>
          <p className="text-[11px] text-muted-foreground mb-3">Check which SoD conflicts a role assignment would introduce before approving it.</p>
          <div className="space-y-2">
            <Select value={simPerson} onValueChange={setSimPerson}><SelectTrigger data-testid="sim-person" className="h-9"><SelectValue placeholder="Select identity…" /></SelectTrigger>
              <SelectContent>{people.slice(0, 60).map((p) => <SelectItem key={p.ref} value={p.ref}>{p.name} · {p.department}</SelectItem>)}</SelectContent></Select>
            <div className="flex gap-2">
              <Select value={simRole} onValueChange={setSimRole}><SelectTrigger data-testid="sim-role" className="h-9 flex-1"><SelectValue placeholder="Add role…" /></SelectTrigger>
                <SelectContent>{roles.map((r) => <SelectItem key={r.ref} value={r.ref}>{r.name}</SelectItem>)}</SelectContent></Select>
              <Button data-testid="sim-add-role" variant="outline" className="h-9" onClick={addSimRole}>Add</Button>
            </div>
            {simRoles.length > 0 && <div className="flex flex-wrap gap-1.5">{simRoles.map((r) => <span key={r} className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary">{r}</span>)}</div>}
            <Button data-testid="sim-run" className="w-full" onClick={runSim}>Simulate</Button>
          </div>
          {simResult && (
            <div className="mt-4 border-t border-border pt-3" data-testid="sim-result">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs">Decision:</span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full" style={{ background: `hsl(${simResult.decision === "BLOCK" ? "0 84% 60%" : simResult.decision === "REVIEW" ? "35 90% 55%" : "142 70% 45%"} / 0.15)`, color: `hsl(${simResult.decision === "BLOCK" ? "0 84% 60%" : simResult.decision === "REVIEW" ? "35 90% 55%" : "142 70% 45%"})` }}>{simResult.decision}</span>
              </div>
              {simResult.introduced_conflicts.length === 0 ? <p className="text-xs text-low">No new conflicts introduced.</p> : (
                <div className="space-y-1.5">{simResult.introduced_conflicts.map((c) => (
                  <div key={c.conflict_ref} className="text-xs flex items-center gap-2"><Chip v={c.severity} /> {c.rule_name}</div>
                ))}</div>
              )}
            </div>
          )}
        </div>

        {/* Rule library */}
        <div className="lg:col-span-7 bg-card fact-border rounded-xl p-5" data-testid="sod-rules">
          <div className="flex items-center gap-2 mb-3"><ScrollText className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-base">SoD Rule Library</h2></div>
          <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
            {rules.map((r) => (
              <button key={r.ref} onClick={() => openRule(r)} data-testid={`sod-rule-${r.ref}`} className="w-full text-left flex items-start gap-3 p-2.5 rounded-lg bg-secondary/30 hover:bg-secondary/60 transition-colors">
                <Chip v={r.severity} />
                <div className="min-w-0">
                  <div className="text-sm font-medium">{r.name} <span className="text-[10px] font-mono text-muted-foreground">· {r.ref} · {r.area}</span></div>
                  <div className="text-[11px] text-muted-foreground">{r.function_a_label} ✕ {r.function_b_label}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
  );
}
