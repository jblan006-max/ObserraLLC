import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Building, GitCompare, ShieldAlert, CheckCircle2 } from "lucide-react";

const STATE = { NORMAL: "142 70% 45%", STALE: "35 90% 55%", CONFLICT: "35 90% 55%", "SECURITY HOLD": "0 84% 60%", RECONCILED: "190 90% 50%" };

export default function HrReconciliation() {
  const [d, setD] = useState(null);
  const [rec, setRec] = useState(null); // {person, conflict}
  const [val, setVal] = useState("");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { const { data } = await api.get("/sap/hr/reconciliation"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;

  const openRec = (person, conflict) => { setRec({ person, conflict }); setVal(conflict.authoritative_value ?? String(conflict.adp_value)); setRationale(""); };
  const runRec = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/sap/hr/reconcile", { person_ref: rec.person.person_ref, field: rec.conflict.field, resolved_value: String(val), rationale });
      const num = data?.ticket?.number;
      const deact = data?.deactivation?.changed ? " · access auto-deactivated" : "";
      toast.success("Conflict reconciled", { description: (num ? `ServiceNow ${num} opened & auto-closed` : "HR master updated") + deact });
      setRec(null); window.dispatchEvent(new Event("sap-data-changed")); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const S = d.states;
  return (
    <div className="space-y-6" data-testid="hr-reconciliation-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="hr-title">HR Reconciliation</h1>
        <p className="text-sm text-muted-foreground mt-1">Dual-authority workforce truth across ADP & IZ8 HR with a conflict state machine and security-hold safeguards on termination-critical fields.</p>
      </div>

      <SapInsight dashboard="HR Reconciliation" focus="ADP vs IZ8 HR conflicts and termination security holds" accent="330 82% 60%" auto slug="hr-reconciliation" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="ADP population" value={d.coverage.ADP} sub="US-authoritative" accent="190 90% 50%" icon={Building} testid="hr-adp" />
        <StatCard label="IZ8 population" value={d.coverage.IZ8} sub="EMEA/APAC-authoritative" accent="266 85% 66%" icon={Building} testid="hr-iz8" />
        <StatCard label="Security holds" value={S["SECURITY HOLD"] || 0} sub="Termination-critical conflicts" accent="0 84% 60%" icon={ShieldAlert} testid="hr-holds" />
        <StatCard label="Open conflicts" value={(S.CONFLICT || 0) + (S["SECURITY HOLD"] || 0)} sub={`${S.RECONCILED || 0} reconciled`} accent="35 90% 55%" icon={GitCompare} testid="hr-conflicts" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-5 bg-card fact-border rounded-xl p-5" data-testid="hr-authority">
          <h2 className="font-head font-bold text-base mb-3">HR Field Authority Matrix</h2>
          <div className="space-y-2">
            {d.authority_matrix.map((m) => (
              <div key={m.field} className="text-xs p-2.5 rounded-lg bg-secondary/30">
                <div className="flex justify-between"><span className="font-medium">{m.field}</span><span className="font-mono text-ai">{m.authority}</span></div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{m.note}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-7 bg-card fact-border rounded-xl p-5" data-testid="hr-queue">
          <h2 className="font-head font-bold text-base mb-3">Reconciliation Queue</h2>
          <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
            {d.queue.map((p) => (
              <div key={p.person_ref} className="rounded-lg bg-secondary/30 p-3" data-testid={`hr-item-${p.person_ref}`}>
                <div className="flex items-center justify-between mb-2">
                  <div><span className="font-medium text-sm">{p.name}</span> <span className="text-[10px] font-mono text-muted-foreground">· {p.legal_entity} · {p.hr_authority}</span></div>
                  <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${STATE[p.state]} / 0.15)`, color: `hsl(${STATE[p.state]})` }}>{p.state}</span>
                </div>
                {p.conflicts.map((c, i) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1 border-t border-border/40">
                    <div><span className="font-medium">{c.field}</span> · ADP=<span className="font-mono">{String(c.adp_value)}</span> vs IZ8=<span className="font-mono">{String(c.iz8_value)}</span></div>
                    {c.state === "RECONCILED" ? <span className="text-[10px] text-ai flex items-center gap-1"><CheckCircle2 className="w-3 h-3" />{String(c.resolved_value)}</span>
                      : <Button data-testid={`hr-reconcile-${p.person_ref}-${c.field}`} size="sm" variant="outline" className="h-7 px-2.5 text-ai border-ai/40 hover:bg-ai/10" onClick={() => openRec(p, c)}>Reconcile</Button>}
                  </div>
                ))}
              </div>
            ))}
            {d.queue.length === 0 && <p className="text-sm text-low py-3">No HR conflicts. ✓</p>}
          </div>
        </div>
      </div>

      <Dialog open={!!rec} onOpenChange={(o) => !o && setRec(null)}>
        <DialogContent data-testid="hr-reconcile-dialog">
          <DialogHeader><DialogTitle>Reconcile — {rec?.person.name} · {rec?.conflict.field}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">Authority for this field: <span className="font-mono text-ai">{rec?.conflict.authority}</span>. Choose the authoritative value; the decision is recorded with immutable provenance.</p>
            <Select value={val} onValueChange={setVal}><SelectTrigger data-testid="hr-value" className="h-9"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={String(rec?.conflict.adp_value)}>ADP: {String(rec?.conflict.adp_value)}</SelectItem>
                <SelectItem value={String(rec?.conflict.iz8_value)}>IZ8: {String(rec?.conflict.iz8_value)}</SelectItem>
              </SelectContent></Select>
            <Textarea data-testid="hr-rationale" value={rationale} onChange={(e) => setRationale(e.target.value)} placeholder="Rationale / evidence…" rows={2} />
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setRec(null)}>Cancel</Button><Button data-testid="hr-save" disabled={busy} onClick={runRec}>{busy ? "Saving…" : "Reconcile"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
