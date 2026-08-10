import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { AIInsight } from "@/components/AIInsight";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ListChecks, Plus, CheckCircle2, XCircle, Rocket, Info, X } from "lucide-react";

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
  const [detail, setDetail] = useState(null);
  const [editRoles, setEditRoles] = useState([]);
  const [editRole, setEditRole] = useState("");

  const load = useCallback(async () => { const { data } = await api.get("/sap/access-requests"); setD(data); return data; }, []);
  useEffect(() => { load(); api.get("/sap/identities").then((r) => setPeople(r.data.identities)); api.get("/sap/roles").then((r) => setRoles(r.data.roles)); }, [load]);
  const refreshDetail = (nd, ref) => setDetail(nd?.requests?.find((x) => x.ref === ref) || null);
  const openDetail = (r) => { setDetail(r); setEditRoles(r.roles.map((x) => x.ref)); setEditRole(""); };
  const saveRoles = async () => {
    if (!detail || editRoles.length === 0) { toast.error("Pick at least one role"); return; }
    try {
      const { data } = await api.post(`/sap/access-requests/${detail.ref}/roles`, { roles: editRoles });
      toast.success("Roles updated", { description: `SoD simulation: ${data.risk_simulation.decision}` });
      const nd = await load(); refreshDetail(nd, detail.ref);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
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
  const decide = async (ref, decision) => { try { const { data } = await api.post(`/sap/access-requests/${ref}/decide`, { decision }); toast.success(`Request ${decision}d`, { description: data.ticket ? `ServiceNow ${data.ticket.number} opened & auto-closed` : undefined }); const nd = await load(); if (detail?.ref === ref) refreshDetail(nd, ref); } catch (e) { toast.error("Failed"); } };
  const provision = async (ref) => { try { const { data } = await api.post(`/sap/access-requests/${ref}/provision`); toast.success("Provisioned to SAP", { description: data.ticket ? `ServiceNow ${data.ticket.number} opened & auto-closed` : undefined }); const nd = await load(); if (detail?.ref === ref) refreshDetail(nd, ref); } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } };

  return (
    <div className="space-y-6" data-testid="access-requests-page">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="ar-title">Access Requests</h1>
          <p className="text-sm text-muted-foreground mt-1">Governed role provisioning with pre-approval SoD risk simulation and multi-stage approval.</p>
        </div>
        <Button data-testid="ar-new" onClick={() => setCreating(true)} className="gap-1.5"><Plus className="w-4 h-4" /> New Request</Button>
      </div>

      <AIInsight dashboard="Access Requests" focus="pending access-request risk and SoD-blocking approvals" accent="199 89% 48%" auto slug="access-requests" />

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
                <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid={`ar-details-${r.ref}`} onClick={() => openDetail(r)}><Info className="w-3.5 h-3.5" /> Details</Button>
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

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-lg" data-testid="ar-detail-dialog">
          {detail && (
            <>
              <DialogHeader><DialogTitle className="flex items-center gap-2">{detail.ref} · {detail.person_name} <span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${ST[detail.status]} / 0.15)`, color: `hsl(${ST[detail.status]})` }}>{detail.status}</span></DialogTitle></DialogHeader>
              <div className="space-y-3 text-sm">
                <div><span className="text-muted-foreground text-xs">Justification</span><div>{detail.justification}</div></div>
                <div className="flex items-center gap-2"><span className="text-muted-foreground text-xs">SoD decision:</span><span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${DEC[detail.risk_simulation.decision]} / 0.15)`, color: `hsl(${DEC[detail.risk_simulation.decision]})` }}>{detail.risk_simulation.decision}</span></div>
                {detail.risk_simulation.introduced?.length > 0 && <div className="flex flex-wrap gap-1.5">{detail.risk_simulation.introduced.map((c) => <span key={c.conflict_ref} className="text-[10px] font-mono px-2 py-0.5 rounded bg-crit/10 text-crit">{c.rule_name}</span>)}</div>}
                <div>
                  <span className="text-muted-foreground text-xs">Requested roles</span>
                  {detail.status === "Pending" ? (
                    <div className="mt-1 space-y-2" data-testid="ar-edit-roles">
                      <div className="flex flex-wrap gap-1.5">{editRoles.map((rf) => <span key={rf} className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary inline-flex items-center gap-1">{roles.find((x) => x.ref === rf)?.name || rf}<button onClick={() => setEditRoles(editRoles.filter((x) => x !== rf))}><X className="w-3 h-3" /></button></span>)}</div>
                      <div className="flex gap-2">
                        <Select value={editRole} onValueChange={setEditRole}><SelectTrigger data-testid="ar-edit-role" className="h-8 flex-1"><SelectValue placeholder="Add role…" /></SelectTrigger><SelectContent>{roles.map((r) => <SelectItem key={r.ref} value={r.ref}>{r.name}</SelectItem>)}</SelectContent></Select>
                        <Button size="sm" variant="outline" className="h-8" onClick={() => { if (editRole && !editRoles.includes(editRole)) setEditRoles([...editRoles, editRole]); setEditRole(""); }}>Add</Button>
                        <Button size="sm" className="h-8" data-testid="ar-save-roles" onClick={saveRoles}>Save &amp; re-simulate</Button>
                      </div>
                    </div>
                  ) : (
                    <div>{detail.roles.map((x) => x.name).join(", ")}</div>
                  )}
                </div>
                <div>
                  <span className="text-muted-foreground text-xs">Approval chain</span>
                  <div className="mt-1 space-y-1">{(detail.stages || []).map((s, i) => <div key={i} className="flex justify-between text-xs"><span>{s.stage} · {s.approver}</span><span className="font-mono" style={{ color: `hsl(${ST[s.status] || "220 10% 55%"})` }}>{s.status}</span></div>)}</div>
                </div>
                {(detail.approval_ticket || detail.provision_ticket) && <div className="text-xs font-mono text-muted-foreground">ServiceNow: {[detail.approval_ticket, detail.provision_ticket].filter(Boolean).join(" · ")}</div>}
              </div>
              <DialogFooter>
                {detail.status === "Pending" && <><Button variant="outline" className="text-crit" data-testid="ar-detail-reject" onClick={() => decide(detail.ref, "reject")}>Reject</Button><Button data-testid="ar-detail-approve" onClick={() => decide(detail.ref, "approve")}>Approve</Button></>}
                {detail.status === "Approved" && <Button className="bg-low hover:bg-low/90" data-testid="ar-detail-provision" onClick={() => provision(detail.ref)}>Provision</Button>}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
