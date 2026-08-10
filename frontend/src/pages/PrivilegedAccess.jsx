import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { AIInsight } from "@/components/AIInsight";
import { useDeepDive } from "@/context/DeepDiveContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { KeyRound, ShieldAlert, Users, MoonStar, Ban, Lock, ShieldCheck } from "lucide-react";

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "—");

const PRIV_META = {
  revoke_privileged: { label: "Revoke privileged", btn: "bg-crit hover:bg-crit/90", tone: "text-crit",
    desc: "Removes SAP_ALL and every privileged role from this account (non-privileged access is kept). Fires the automated ServiceNow → HR (ADP/IZ8) → SAP → AD/Entra workflow." },
  lock: { label: "Emergency lock", btn: "bg-crit hover:bg-crit/90", tone: "text-crit",
    desc: "Locks the SAP account, terminates sessions, deactivates the owner and disables directory sign-in. Fires the automated ServiceNow lock workflow." },
  recertify: { label: "Recertify", btn: "bg-ai hover:bg-ai/90", tone: "text-ai",
    desc: "Opens a privileged-access recertification task with entitlement and last-use evidence for the account owner to review." },
};

export default function PrivilegedAccess() {
  const { openDeepDive } = useDeepDive();
  const [d, setD] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { const { data } = await api.get("/sap/privileged"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;

  const askAction = (action, row) => { setReason(""); setConfirm({ action, row }); };
  const runAction = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/sap/privileged/${confirm.row.ref}/action`, { action: confirm.action, reason });
      toast.success(`${PRIV_META[confirm.action].label} — done`, { description: `ServiceNow ${data.ticket.number} opened & auto-closed` });
      setConfirm(null); window.dispatchEvent(new Event("sap-data-changed")); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const open = (r) => openDeepDive({
    accent: r.sap_all ? "0 84% 60%" : "35 90% 55%", refLabel: r.ref, title: `${r.sap_user} · ${r.person_name}`,
    rating: r.sap_all ? "Critical" : "High",
    facets: [
      { label: "System", value: r.system }, { label: "User type", value: r.user_type },
      { label: "SAP_ALL", value: r.sap_all ? "Yes" : "No" }, { label: "Dormant", value: r.dormant ? "Yes (>90d)" : "No" },
      { label: "Privileged roles", value: r.roles.join(", ") || "—" }, { label: "Last login", value: fmtDate(r.last_login) },
    ],
    recommendedActions: [
      r.sap_all ? "Replace SAP_ALL with a least-privilege composite role scoped to the actual job function." : "Confirm business need; time-box privileged access and route through firefighter/emergency access.",
      r.dormant ? "This privileged access is dormant >90 days — recommend immediate removal." : "Enrol in privileged-access certification and enable session logging.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-6", "ISO 27001 A.8.2"],
    explainTitle: `${r.sap_user} — privileged SAP access`, explainKind: "SAP privileged access least-privilege review",
    explainContext: { account: r },
  });

  return (
    <div className="space-y-6" data-testid="privileged-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="privileged-title">Privileged Access</h1>
        <p className="text-sm text-muted-foreground mt-1">SAP_ALL, security-admin and Basis-superuser access across the landscape, including shared and dormant privileged accounts.</p>
      </div>

      <AIInsight dashboard="Privileged Access" focus="SAP_ALL and privileged access least-privilege exposure" accent="266 85% 66%" auto slug="privileged-access" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Privileged accounts" value={d.total} accent="266 85% 66%" icon={KeyRound} testid="priv-total" />
        <StatCard label="Hold SAP_ALL" value={d.sap_all} accent="0 84% 60%" icon={ShieldAlert} testid="priv-sapall" />
        <StatCard label="Shared / technical" value={d.shared} accent="35 90% 55%" icon={Users} testid="priv-shared" />
        <StatCard label="Dormant privileged" value={d.dormant_privileged} sub="Unused >90d" accent="168 76% 46%" icon={MoonStar} testid="priv-dormant" />
      </div>
      <div className="bg-card fact-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm" data-testid="priv-table">
          <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <th className="p-3">SAP User</th><th className="p-3">Person</th><th className="p-3">System</th><th className="p-3">Type</th><th className="p-3">Privileged Roles</th><th className="p-3">Flags</th><th className="p-3">Last Login</th><th className="p-3 text-right">Actions</th>
          </tr></thead>
          <tbody>
            {d.privileged.map((r) => (
              <tr key={r.ref} onClick={() => open(r)} className="border-b border-border/50 hover:bg-secondary/40 cursor-pointer" data-testid={`priv-row-${r.ref}`}>
                <td className="p-3 font-mono text-xs">{r.sap_user}</td>
                <td className="p-3">{r.person_name}</td>
                <td className="p-3 font-mono text-xs">{r.system}</td>
                <td className="p-3 text-xs">{r.user_type}{r.technical ? " · technical" : ""}</td>
                <td className="p-3 text-xs">{r.roles.join(", ") || "—"}</td>
                <td className="p-3">
                  {r.sap_all && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-crit/15 text-crit mr-1">SAP_ALL</span>}
                  {r.dormant && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-teal/15 text-teal">DORMANT</span>}
                  {r.lock_state === "locked" && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">LOCKED</span>}
                </td>
                <td className="p-3 text-xs">{fmtDate(r.last_login)}</td>
                <td className="p-3 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                  <div className="inline-flex items-center gap-1 justify-end">
                    {(r.sap_all || r.roles.length > 0) && <button data-testid={`priv-revoke-${r.ref}`} title="Revoke privileged roles" onClick={() => askAction("revoke_privileged", r)} className="text-crit hover:bg-crit/10 rounded-md p-1.5"><Ban className="w-4 h-4" /></button>}
                    {r.lock_state !== "locked" && <button data-testid={`priv-lock-${r.ref}`} title="Emergency lock" onClick={() => askAction("lock", r)} className="text-crit hover:bg-crit/10 rounded-md p-1.5"><Lock className="w-4 h-4" /></button>}
                    <button data-testid={`priv-recertify-${r.ref}`} title="Recertify" onClick={() => askAction("recertify", r)} className="text-ai hover:bg-ai/10 rounded-md p-1.5"><ShieldCheck className="w-4 h-4" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent data-testid="priv-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">{confirm && PRIV_META[confirm.action].label} — {confirm?.row?.sap_user}</DialogTitle>
            <DialogDescription>{confirm && PRIV_META[confirm.action].desc}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea data-testid="priv-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ServiceNow work note / reason…" rows={2} />
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setConfirm(null)}>Cancel</Button><Button data-testid="priv-confirm-btn" disabled={busy} onClick={runAction} className={confirm ? PRIV_META[confirm.action].btn : ""}>{busy ? "Working…" : confirm && PRIV_META[confirm.action].label}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
