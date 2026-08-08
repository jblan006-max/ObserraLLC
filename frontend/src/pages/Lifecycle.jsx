import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { useDeepDive } from "@/context/DeepDiveContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { UserPlus, UserX, GitBranch, Ban, PauseCircle, PlayCircle, Power } from "lucide-react";

const VERB = { activate: "reactivated", deactivate: "deactivated", suspend: "suspended" };
const ACTION_META = {
  deactivate: { label: "Deactivate", Icon: Ban, btn: "bg-crit hover:bg-crit/90", tone: "text-crit",
    desc: "Locks all residual SAP accounts, revokes roles and frees the license. Fires the automated ServiceNow → HR (ADP/IZ8) → SAP → AD/Entra deactivation workflow." },
  suspend: { label: "Suspend", Icon: PauseCircle, btn: "bg-amber hover:bg-amber/90", tone: "text-amber",
    desc: "Temporarily locks SAP sign-in (license retained). Fires the automated ServiceNow suspension workflow." },
  activate: { label: "Reactivate", Icon: PlayCircle, btn: "bg-low hover:bg-low/90", tone: "text-low",
    desc: "Restores SAP access (consuming a license). Fires the automated ServiceNow reactivation workflow." },
};

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—");

export default function Lifecycle() {
  const { openDeepDive } = useDeepDive();
  const [d, setD] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [bulk, setBulk] = useState(null);
  const [reason, setReason] = useState("");
  const [notify, setNotify] = useState(true);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { const { data } = await api.get("/sap/jml"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;

  const askAction = (action, refs, names) => { setReason(""); setNotify(true); setConfirm({ action, refs, names }); };
  const runAction = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/sap/activation/set", { person_refs: confirm.refs, action: confirm.action, reason, work_note: reason, notify });
      const nums = (data.tickets || []).map((t) => t.number).join(", ");
      toast.success(`${data.changed} worker(s) ${VERB[confirm.action] || "updated"}`, { description: nums ? `ServiceNow ${nums} opened & auto-closed` : undefined });
      setConfirm(null); window.dispatchEvent(new Event("sap-data-changed")); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const runBulk = async () => {
    setBusy(true);
    try {
      const refs = d.leavers.map((l) => l.ref);
      const { data } = await api.post("/sap/activation/set", { person_refs: refs, action: bulk.action, reason: reason || "Bulk leaver de-provisioning", work_note: reason, notify });
      toast.success(`${data.changed} terminated worker(s) ${VERB[bulk.action] || "updated"}`, { description: `${(data.tickets || []).length} ServiceNow ticket(s) opened & auto-closed` });
      setBulk(null); window.dispatchEvent(new Event("sap-data-changed")); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const openLeaver = (l) => openDeepDive({
    accent: "0 84% 60%", refLabel: l.ref, title: `${l.name} — residual access`, rating: "Critical", score: l.score,
    facets: [
      { label: "Department", value: l.department }, { label: "Terminated", value: fmtDate(l.termination_date) },
      { label: "Residual SAP accounts", value: l.residual_accounts }, { label: "AD/Entra enabled", value: l.ad_enabled ? "Yes" : "No" },
    ],
    recommendedActions: [
      "Immediately lock all residual SAP accounts and revoke roles for this terminated worker.",
      "Disable the linked AD/Entra identity and open a ServiceNow leaver ticket to verify closure.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-2", "ISO 27001 A.5.11"],
    explainTitle: `${l.name} — terminated worker residual SAP access`, explainKind: "SAP leaver residual access remediation",
    explainContext: { leaver: l },
  });

  return (
    <div className="space-y-6" data-testid="lifecycle-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="lifecycle-title">Joiner / Mover / Leaver</h1>
        <p className="text-sm text-muted-foreground mt-1">Workforce lifecycle correlated with SAP access — recent joiners, transfers and terminated workers still holding access.</p>
      </div>

      <SapInsight dashboard="Joiner / Mover / Leaver" focus="leaver residual access and joiner provisioning gaps" accent="142 70% 45%" auto slug="lifecycle" />
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Joiners (21d)" value={d.counts.joiners} accent="142 70% 45%" icon={UserPlus} testid="jml-joiners" />
        <StatCard label="Movers" value={d.counts.movers} accent="260 85% 66%" icon={GitBranch} testid="jml-movers" />
        <StatCard label="Leavers w/ residual access" value={d.counts.leavers} accent="0 84% 60%" icon={UserX} testid="jml-leavers" />
      </div>

      <div className="bg-card fact-border rounded-xl p-5" data-testid="jml-leavers-panel">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2"><UserX className="w-4 h-4 text-crit" /><h2 className="font-head font-bold text-lg">Terminated — Residual Access (Critical)</h2></div>
          {d.leavers.length > 0 && (
            <Button data-testid="jml-deactivate-all" size="sm" className="gap-1.5 bg-crit hover:bg-crit/90" onClick={() => { setReason(""); setNotify(true); setBulk({ action: "deactivate" }); }}>
              <Power className="w-3.5 h-3.5" /> Deactivate All Residual ({d.leavers.length})
            </Button>
          )}
        </div>
        <div className="space-y-2">
          {d.leavers.map((l) => (
            <div key={l.ref} data-testid={`jml-leaver-${l.ref}`} className="flex items-center gap-3 p-3 rounded-lg bg-crit/5 border border-crit/20">
              <button onClick={() => openLeaver(l)} data-testid={`jml-leaver-open-${l.ref}`} className="flex items-center gap-3 flex-1 min-w-0 text-left hover:opacity-80 transition-opacity">
                <span className="font-head font-black text-xl text-crit w-10">{l.score}</span>
                <div className="flex-1 min-w-0"><div className="text-sm font-medium">{l.name}</div><div className="text-[11px] text-muted-foreground">{l.department} · terminated {fmtDate(l.termination_date)} · {l.residual_accounts} active account(s){l.ad_enabled ? " · AD still enabled" : ""}</div></div>
              </button>
              <div className="flex items-center gap-1 shrink-0">
                <button data-testid={`jml-deactivate-${l.ref}`} onClick={() => askAction("deactivate", [l.ref], l.name)} title="Deactivate (lock residual access)" className="text-crit hover:bg-crit/10 rounded-md p-1.5"><Ban className="w-4 h-4" /></button>
                <button data-testid={`jml-suspend-${l.ref}`} onClick={() => askAction("suspend", [l.ref], l.name)} title="Suspend (temporary hold)" className="text-amber hover:bg-amber/10 rounded-md p-1.5"><PauseCircle className="w-4 h-4" /></button>
                <button data-testid={`jml-reactivate-${l.ref}`} onClick={() => askAction("activate", [l.ref], l.name)} title="Reactivate access" className="text-low hover:bg-low/10 rounded-md p-1.5"><PlayCircle className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
          {d.leavers.length === 0 && <p className="text-sm text-low py-3">No terminated workers with residual SAP access. ✓</p>}
        </div>
      </div>

      <div className="bg-card fact-border rounded-xl p-5" data-testid="jml-joiners-panel">
        <div className="flex items-center gap-2 mb-3"><UserPlus className="w-4 h-4 text-low" /><h2 className="font-head font-bold text-lg">Recent Joiners</h2></div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-2">Name</th><th className="p-2">Dept</th><th className="p-2">Hire Date</th><th className="p-2">HR Source</th><th className="p-2">Provisioned</th></tr></thead>
            <tbody>
              {d.joiners.map((j) => (
                <tr key={j.ref} className="border-b border-border/50"><td className="p-2 font-medium">{j.name}</td><td className="p-2 text-xs">{j.department}</td><td className="p-2 text-xs">{fmtDate(j.hire_date)}</td><td className="p-2 text-xs font-mono">{j.hr_authority}</td><td className="p-2 text-xs">{j.provisioned ? <span className="text-low">✓ {j.accounts} account(s)</span> : <span className="text-amber">Pending</span>}</td></tr>
              ))}
              {d.joiners.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-muted-foreground">No recent joiners.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent data-testid="jml-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">{confirm && (() => { const M = ACTION_META[confirm.action]; const I = M.Icon; return <I className={`w-5 h-5 ${M.tone}`} />; })()}{confirm && ACTION_META[confirm.action].label} — {confirm?.names}</DialogTitle>
            <DialogDescription>{confirm && ACTION_META[confirm.action].desc}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea data-testid="jml-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ServiceNow work note / reason…" rows={2} />
            <label className="flex items-center gap-2 text-sm cursor-pointer"><Checkbox checked={notify} onCheckedChange={(v) => setNotify(!!v)} /> Notify stakeholders</label>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setConfirm(null)}>Cancel</Button><Button data-testid="jml-confirm-btn" disabled={busy} onClick={runAction} className={confirm ? ACTION_META[confirm.action].btn : ""}>{busy ? "Working…" : confirm && ACTION_META[confirm.action].label}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!bulk} onOpenChange={(o) => !o && setBulk(null)}>
        <DialogContent data-testid="jml-bulk-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Power className="w-5 h-5 text-crit" /> Deactivate all {d.leavers.length} terminated workers</DialogTitle>
            <DialogDescription>Locks every residual SAP account, revokes roles and frees licenses. A ServiceNow → HR (ADP/IZ8) → SAP → AD/Entra workflow is opened &amp; auto-closed per worker.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea data-testid="jml-bulk-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ServiceNow work note / reason…" rows={2} />
            <label className="flex items-center gap-2 text-sm cursor-pointer"><Checkbox checked={notify} onCheckedChange={(v) => setNotify(!!v)} /> Notify stakeholders</label>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setBulk(null)}>Cancel</Button><Button data-testid="jml-bulk-confirm" disabled={busy} onClick={runBulk} className="bg-crit hover:bg-crit/90">{busy ? "Running…" : "Deactivate All"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
