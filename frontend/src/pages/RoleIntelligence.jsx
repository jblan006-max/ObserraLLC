import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { SapAIFix } from "@/components/SapAIFix";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Search, Layers, ShieldAlert, KeyRound, ShieldCheck, Wrench, Ban } from "lucide-react";

const SEV = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "190 90% 50%" };
const Chip = ({ v }) => <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${SEV[v] || "220 10% 55%"} / 0.15)`, color: `hsl(${SEV[v] || "220 10% 55%"})` }}>{v}</span>;

export default function RoleIntelligence() {
  const [d, setD] = useState(null);
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState(null);
  const [acting, setActing] = useState(false);
  const load = useCallback(async () => { const { data } = await api.get(`/sap/roles${q ? `?q=${encodeURIComponent(q)}` : ""}`); setD(data); }, [q]);
  useEffect(() => { load(); }, [load]);

  const open = async (ref) => { setDetail({ loading: true }); try { const { data } = await api.get(`/sap/roles/${ref}`); setDetail(data); } catch { setDetail(null); } };
  const roleAction = async (action, account_ref) => {
    if (!detail?.role) return;
    setActing(true);
    try {
      const { data } = await api.post(`/sap/roles/${detail.role.ref}/action`, { action, account_ref: account_ref || "" });
      const label = action === "revoke_holder" ? "Role revoked from holder" : action === "recertify" ? "Recertification opened" : "Remediation opened";
      toast.success(label, { description: `ServiceNow ${data.ticket.number} opened & auto-closed` });
      window.dispatchEvent(new Event("sap-data-changed"));
      if (action === "revoke_holder") await open(detail.role.ref);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setActing(false);
  };
  if (!d) return <Spinner />;
  const privileged = d.roles.filter((r) => r.privileged).length;
  const toxic = d.roles.filter((r) => r.internal_sod.length > 0).length;

  return (
    <div className="space-y-6" data-testid="roles-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="roles-title">Role Intelligence</h1>
        <p className="text-sm text-muted-foreground mt-1">SAP role catalog with composition, assignment usage, privilege severity and single-role toxic combinations.</p>
      </div>

      <SapInsight dashboard="Role Intelligence" focus="toxic composite roles and over-privileged role design" accent="35 90% 55%" auto slug="role-intelligence" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Roles in catalog" value={d.total} accent="280 80% 66%" icon={Layers} testid="role-total" />
        <StatCard label="Privileged roles" value={privileged} accent="0 84% 60%" icon={KeyRound} testid="role-priv" />
        <StatCard label="Toxic composite roles" value={toxic} sub="Internal SoD conflict" accent="35 90% 55%" icon={ShieldAlert} testid="role-toxic" />
        <StatCard label="Most assigned" value={d.roles[0]?.users || 0} sub={d.roles[0]?.name} accent="190 90% 50%" icon={Layers} testid="role-top" />
      </div>

      <div className="bg-card fact-border rounded-xl">
        <div className="flex items-center gap-2 p-3 border-b border-border">
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background/50 px-2.5 h-9 flex-1">
            <Search className="w-3.5 h-3.5 text-muted-foreground" />
            <input data-testid="role-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search role…" className="bg-transparent text-sm outline-none w-full" />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="role-table">
            <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
              <th className="p-3">Role</th><th className="p-3">Type</th><th className="p-3">Owner</th><th className="p-3">Users</th><th className="p-3">Functions</th><th className="p-3">T-codes</th><th className="p-3">Flags</th>
            </tr></thead>
            <tbody>
              {d.roles.map((r) => (
                <tr key={r.ref} onClick={() => open(r.ref)} className="border-b border-border/50 hover:bg-secondary/40 cursor-pointer" data-testid={`role-row-${r.ref}`}>
                  <td className="p-3"><div className="font-medium">{r.name}</div><div className="text-[10px] font-mono text-muted-foreground">{r.ref}</div></td>
                  <td className="p-3 text-xs">{r.type}</td>
                  <td className="p-3 text-xs">{r.owner}</td>
                  <td className="p-3 text-xs font-mono">{r.users}</td>
                  <td className="p-3 text-xs">{r.function_count}</td>
                  <td className="p-3 text-xs">{r.tcode_count}</td>
                  <td className="p-3">
                    {r.sap_all && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-crit/15 text-crit mr-1">SAP_ALL</span>}
                    {r.privileged && !r.sap_all && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple/15 text-purple mr-1">PRIV</span>}
                    {r.internal_sod.length > 0 && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber/15 text-amber">SoD×{r.internal_sod.length}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-2xl max-h-[86vh] overflow-y-auto" data-testid="role-detail">
          {detail?.loading ? <div className="py-16"><Spinner /></div> : detail && (
            <>
              <DialogHeader><DialogTitle className="flex items-center gap-2">{detail.role.name} {detail.role.sap_all && <Chip v="Critical" />}</DialogTitle></DialogHeader>
              <div className="text-xs text-muted-foreground mb-3 font-mono">{detail.role.ref} · {detail.role.type} · owner {detail.role.owner}{detail.role.parent ? ` · derived from ${detail.role.parent}` : ""}</div>
              <div className="flex flex-wrap gap-2 mb-3">
                <Button size="sm" variant="outline" data-testid="role-recertify" disabled={acting} onClick={() => roleAction("recertify")} className="h-8 gap-1.5"><ShieldCheck className="w-3.5 h-3.5" /> Recertify role</Button>
                {detail.internal_sod.length > 0 && <Button size="sm" data-testid="role-remediate" disabled={acting} onClick={() => roleAction("remediate")} className="h-8 gap-1.5 bg-amber hover:bg-amber/90 text-[#050810]"><Wrench className="w-3.5 h-3.5" /> Remediate toxic role</Button>}
              </div>
              <div className="mb-3"><SapAIFix entity="role" refId={detail.role.ref} accent="35 90% 55%" onApplied={() => { open(detail.role.ref); load(); }} /></div>
              {detail.internal_sod.length > 0 && (
                <div className="mb-3"><h3 className="font-head font-bold text-sm mb-1">Internal SoD Conflicts</h3>{detail.internal_sod.map((s) => <div key={s.ref} className="text-sm flex items-center gap-2 mb-1"><Chip v={s.severity} />{s.name}</div>)}</div>
              )}
              <div className="mb-3"><h3 className="font-head font-bold text-sm mb-1">Business Functions ({detail.functions.length})</h3>
                {detail.functions.map((f) => <div key={f.id} className="text-xs py-0.5"><span className="font-medium">{f.label}</span> <span className="text-muted-foreground">· {f.process}</span></div>)}
                {detail.functions.length === 0 && <p className="text-xs text-muted-foreground">Display-only (no sensitive functions).</p>}
              </div>
              <div className="grid grid-cols-2 gap-4 mb-3">
                <div><h3 className="font-head font-bold text-sm mb-1">T-codes</h3><div className="flex flex-wrap gap-1">{detail.tcodes.map((t) => <span key={t} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary">{t}</span>)}</div></div>
                <div><h3 className="font-head font-bold text-sm mb-1">Auth Objects</h3><div className="flex flex-wrap gap-1">{detail.auth_objects.map((t) => <span key={t} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary">{t}</span>)}</div></div>
              </div>
              <div><h3 className="font-head font-bold text-sm mb-1">Holders ({detail.holders.length})</h3>
                <div className="max-h-40 overflow-y-auto">{detail.holders.map((h) => <div key={h.account_ref} className="text-xs flex justify-between items-center gap-2 py-0.5 border-b border-border/40"><span className="min-w-0 truncate">{h.person_name} <span className="font-mono text-muted-foreground">· {h.sap_user}</span></span><span className="flex items-center gap-2 shrink-0"><span className="text-muted-foreground">{h.system} · {h.status}</span><button data-testid={`role-revoke-${h.account_ref}`} disabled={acting} onClick={() => roleAction("revoke_holder", h.account_ref)} title="Revoke this role from the holder" className="text-crit hover:bg-crit/10 rounded p-1"><Ban className="w-3.5 h-3.5" /></button></span></div>)}</div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
