import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ListChecks, Plus, CheckCircle2, XCircle, Rocket } from "lucide-react";

const DEC = { BLOCK: "0 84% 60%", REVIEW: "35 90% 55%", APPROVE: "142 70% 45%" };
const ST = { Pending: "35 90% 55%", Approved: "190 90% 50%", Provisioned: "142 70% 45%", Rejected: "0 84% 60%" };

export default function AccessRequests() {
  const [d, setD] = useState(null);
  const [people, setPeople] = useState([]);
  const [roles, setRoles] = useState([]);
  const [creating, setCreating] = useState(false);
  const [person, setPerson] = useState("");
  const [role, setRole] = useState("");
  const [pickedRoles, setPickedRoles] = useState([]);
  const [justification, setJustification] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => { const { data } = await api.get("/sap/access-requests"); setD(data); }, []);
  useEffect(() => { load(); api.get("/sap/identities").then((r) => setPeople(r.data.identities)); api.get("/sap/roles").then((r) => setRoles(r.data.roles)); }, [load]);
  if (!d) return <Spinner />;

  const addRole = () => { if (role && !pickedRoles.includes(role)) setPickedRoles([...pickedRoles, role]); setRole(""); };
  const create = async () => {
    if (!person || pickedRoles.length === 0 || !justification.trim()) { toast.error("Pick identity, role(s) and justification"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/sap/access-requests", { person_ref: person, roles: pickedRoles, justification });
      toast.success(`Request ${data.ref} created`, { description: `SoD simulation: ${data.risk_simulation.decision}` });
      setCreating(false); setPerson(""); setPickedRoles([]); setJustification(""); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const decide = async (ref, decision) => { try { await api.post(`/sap/access-requests/${ref}/decide`, { decision }); toast.success(`Request ${decision}d`); await load(); } catch (e) { toast.error("Failed"); } };
  const provision = async (ref) => { try { await api.post(`/sap/access-requests/${ref}/provision`); toast.success("Provisioned to access model"); await load(); } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } };

  return (
    <div className="space-y-6" data-testid="access-requests-page">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="ar-title">Access Requests</h1>
          <p className="text-sm text-muted-foreground mt-1">Governed role provisioning with pre-approval SoD risk simulation and multi-stage approval.</p>
        </div>
        <Button data-testid="ar-new" onClick={() => setCreating(true)} className="gap-1.5"><Plus className="w-4 h-4" /> New Request</Button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Pending" value={d.counts.pending} accent="35 90% 55%" icon={ListChecks} testid="ar-pending" />
        <StatCard label="Approved" value={d.counts.approved} accent="190 90% 50%" icon={CheckCircle2} testid="ar-approved" />
        <StatCard label="Provisioned" value={d.counts.provisioned} accent="142 70% 45%" icon={Rocket} testid="ar-provisioned" />
        <StatCard label="Rejected" value={d.counts.rejected} accent="0 84% 60%" icon={XCircle} testid="ar-rejected" />
      </div>

      <div className="space-y-3">
        {d.requests.map((r) => (
          <div key={r.ref} className="bg-card fact-border rounded-xl p-4" data-testid={`ar-row-${r.ref}`}>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="min-w-0">
                <div className="font-medium">{r.ref} · {r.person_name} <span className="text-[10px] font-mono px-2 py-0.5 rounded-full ml-1" style={{ background: `hsl(${ST[r.status]} / 0.15)`, color: `hsl(${ST[r.status]})` }}>{r.status}</span></div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{r.roles.map((x) => x.name).join(", ")} · {r.justification}</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${DEC[r.risk_simulation.decision]} / 0.15)`, color: `hsl(${DEC[r.risk_simulation.decision]})` }}>SoD: {r.risk_simulation.decision}</span>
                {r.status === "Pending" && <><Button size="sm" variant="outline" className="h-8" data-testid={`ar-approve-${r.ref}`} onClick={() => decide(r.ref, "approve")}>Approve</Button><Button size="sm" variant="outline" className="h-8 text-crit" data-testid={`ar-reject-${r.ref}`} onClick={() => decide(r.ref, "reject")}>Reject</Button></>}
                {r.status === "Approved" && <Button size="sm" className="h-8 bg-low hover:bg-low/90" data-testid={`ar-provision-${r.ref}`} onClick={() => provision(r.ref)}>Provision</Button>}
              </div>
            </div>
            {r.risk_simulation.introduced?.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">{r.risk_simulation.introduced.map((c) => <span key={c.conflict_ref} className="text-[10px] font-mono px-2 py-0.5 rounded bg-crit/10 text-crit">{c.rule_name}</span>)}</div>
            )}
          </div>
        ))}
        {d.requests.length === 0 && <div className="bg-card fact-border rounded-xl p-8 text-center text-muted-foreground">No access requests yet.</div>}
      </div>

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent data-testid="ar-dialog">
          <DialogHeader><DialogTitle>New Access Request</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Select value={person} onValueChange={setPerson}><SelectTrigger data-testid="ar-person" className="h-9"><SelectValue placeholder="Select identity…" /></SelectTrigger>
              <SelectContent>{people.slice(0, 60).map((p) => <SelectItem key={p.ref} value={p.ref}>{p.name} · {p.department}</SelectItem>)}</SelectContent></Select>
            <div className="flex gap-2">
              <Select value={role} onValueChange={setRole}><SelectTrigger data-testid="ar-role" className="h-9 flex-1"><SelectValue placeholder="Add role…" /></SelectTrigger>
                <SelectContent>{roles.map((r) => <SelectItem key={r.ref} value={r.ref}>{r.name}</SelectItem>)}</SelectContent></Select>
              <Button variant="outline" className="h-9" data-testid="ar-add-role" onClick={addRole}>Add</Button>
            </div>
            {pickedRoles.length > 0 && <div className="flex flex-wrap gap-1.5">{pickedRoles.map((r) => <span key={r} className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary">{r}</span>)}</div>}
            <Textarea data-testid="ar-justification" value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="Business justification…" rows={2} />
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setCreating(false)}>Cancel</Button><Button data-testid="ar-submit" disabled={busy} onClick={create}>{busy ? "Simulating…" : "Submit (runs SoD simulation)"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
