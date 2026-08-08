import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ShieldCheck, Plus, CheckCircle2, XCircle } from "lucide-react";

const RISK = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "190 90% 50%", Low: "142 70% 45%" };

export default function Certifications() {
  const [d, setD] = useState(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("User Access");
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => { const { data } = await api.get("/sap/certifications"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;

  const create = async () => {
    if (!name.trim()) { toast.error("Name required"); return; }
    setBusy(true);
    try { const { data } = await api.post("/sap/certifications", { name, type, scope: "all" }); toast.success(`${data.ref} created · ${data.items} items`); setCreating(false); setName(""); await load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const openDetail = async (ref) => { setDetail({ loading: true }); const { data } = await api.get(`/sap/certifications/${ref}`); setDetail(data); };
  const decide = async (ref, itemRef, decision) => { await api.post(`/sap/certifications/${ref}/decide`, { item_ref: itemRef, decision }); await openDetail(ref); await load(); };

  return (
    <div className="space-y-6" data-testid="certifications-page">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="cert-title">Access Certifications</h1>
          <p className="text-sm text-muted-foreground mt-1">Periodic recertification campaigns for user access, privileged access, roles and SoD — reviewers certify or revoke each item.</p>
        </div>
        <Button data-testid="cert-new" onClick={() => setCreating(true)} className="gap-1.5"><Plus className="w-4 h-4" /> New Campaign</Button>
      </div>

      <SapInsight dashboard="Access Certifications" focus="recertification campaign progress and revocation risk" accent="142 70% 45%" auto slug="certifications" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {d.campaigns.map((c) => (
          <button key={c.ref} data-testid={`cert-card-${c.ref}`} onClick={() => openDetail(c.ref)} className="text-left bg-card fact-border rounded-xl p-5 hover:border-primary/40 transition-colors">
            <div className="flex items-center justify-between mb-1">
              <span className="font-head font-bold">{c.name}</span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${c.status === "Completed" ? "bg-low/15 text-low" : "bg-amber/15 text-amber"}`}>{c.status}</span>
            </div>
            <div className="text-[11px] text-muted-foreground mb-3">{c.ref} · {c.type} · {c.total} items · {c.revoked} revoked</div>
            <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className="h-full rounded-full bg-primary" style={{ width: `${c.progress}%` }} /></div>
            <div className="text-[10px] text-muted-foreground mt-1">{c.progress}% reviewed ({c.decided}/{c.total})</div>
          </button>
        ))}
        {d.campaigns.length === 0 && <div className="lg:col-span-2 bg-card fact-border rounded-xl p-8 text-center text-muted-foreground">No campaigns yet — create one to start recertification.</div>}
      </div>

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent data-testid="cert-dialog">
          <DialogHeader><DialogTitle>New Certification Campaign</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input data-testid="cert-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Campaign name (e.g. Q2 SAP User Access Review)" />
            <Select value={type} onValueChange={setType}><SelectTrigger data-testid="cert-type" className="h-9"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="User Access">User Access</SelectItem><SelectItem value="Privileged Access">Privileged Access</SelectItem><SelectItem value="Role">Role</SelectItem><SelectItem value="SoD">SoD</SelectItem></SelectContent></Select>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setCreating(false)}>Cancel</Button><Button data-testid="cert-create" disabled={busy} onClick={create}>{busy ? "Building…" : "Create"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-3xl max-h-[86vh] overflow-y-auto" data-testid="cert-detail">
          {detail?.loading ? <div className="py-16"><Spinner /></div> : detail && (
            <>
              <DialogHeader><DialogTitle className="flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-primary" />{detail.name}</DialogTitle></DialogHeader>
              <div className="text-xs text-muted-foreground mb-3">{detail.ref} · {detail.type} · {detail.progress}% reviewed · {detail.revoked} revoked</div>
              <div className="space-y-1.5 max-h-[60vh] overflow-y-auto">
                {detail.items.map((it) => (
                  <div key={it.item_ref} className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-secondary/30" data-testid={`cert-item-${it.item_ref}`}>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{it.subject_name} <span className="text-[10px] font-mono px-1.5 py-0.5 rounded ml-1" style={{ background: `hsl(${RISK[it.risk] || "220 10% 55%"} / 0.15)`, color: `hsl(${RISK[it.risk] || "220 10% 55%"})` }}>{it.risk}</span></div>
                      <div className="text-[11px] text-muted-foreground">{it.detail} · reviewer {it.reviewer}</div>
                    </div>
                    {it.decision === "Pending" ? (
                      <div className="flex gap-1.5 shrink-0">
                        <button data-testid={`cert-certify-${it.item_ref}`} onClick={() => decide(detail.ref, it.item_ref, "Certify")} className="inline-flex items-center gap-1 text-xs text-low hover:bg-low/10 rounded px-2 py-1"><CheckCircle2 className="w-3.5 h-3.5" />Certify</button>
                        <button data-testid={`cert-revoke-${it.item_ref}`} onClick={() => decide(detail.ref, it.item_ref, "Revoke")} className="inline-flex items-center gap-1 text-xs text-crit hover:bg-crit/10 rounded px-2 py-1"><XCircle className="w-3.5 h-3.5" />Revoke</button>
                      </div>
                    ) : <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full shrink-0 ${it.decision === "Certify" ? "bg-low/15 text-low" : "bg-crit/15 text-crit"}`}>{it.decision}</span>}
                  </div>
                ))}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
