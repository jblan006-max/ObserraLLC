import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { AIInsight } from "@/components/AIInsight";
import { useDeepDive } from "@/context/DeepDiveContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { MoonStar, Ghost, Cpu, Lock, Ban, ShieldCheck, Workflow, X } from "lucide-react";

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—");

const ACC_META = {
  lock: { label: "Emergency lock", btn: "bg-crit hover:bg-crit/90", tone: "text-crit",
    desc: "Locks the SAP account, terminates sessions and disables directory sign-in. Fires the automated ServiceNow → HR → SAP → AD/Entra workflow." },
  deactivate: { label: "De-provision", btn: "bg-crit hover:bg-crit/90", tone: "text-crit",
    desc: "Locks the account, revokes all roles and frees the license (deactivates the owner if linked). Fires the automated ServiceNow de-provisioning workflow." },
  recertify: { label: "Recertify", btn: "bg-ai hover:bg-ai/90", tone: "text-ai",
    desc: "Opens an access recertification task with entitlement and last-use evidence for the owner to review." },
};

const Table = ({ rows, cols, testid, empty, onRow, sel }) => {
  const allSel = rows.length > 0 && rows.every((r) => sel?.set.has(r.ref));
  return (
    <div className="bg-card fact-border rounded-xl overflow-x-auto" data-testid={testid}>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
          {sel && <th className="p-3 w-8"><input type="checkbox" data-testid={`${testid}-selectall`} checked={allSel} onChange={sel.toggleAll} className="accent-primary w-4 h-4 cursor-pointer" /></th>}
          {cols.map((c) => <th key={c.k} className={`p-3 ${c.k === "actions" ? "text-right" : ""}`}>{c.label}</th>)}
        </tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.ref || i} onClick={onRow ? () => onRow(r) : undefined} className={`border-b border-border/50 hover:bg-secondary/30 ${onRow ? "cursor-pointer" : ""} ${sel?.set.has(r.ref) ? "bg-primary/5" : ""}`}>
              {sel && <td className="p-3" onClick={(e) => e.stopPropagation()}><input type="checkbox" data-testid={`mon-select-${r.ref}`} checked={sel.set.has(r.ref)} onChange={() => sel.toggle(r.ref)} className="accent-primary w-4 h-4 cursor-pointer" /></td>}
              {cols.map((c) => <td key={c.k} className={`p-3 text-xs ${c.k === "actions" ? "text-right" : ""}`}>{c.render ? c.render(r) : r[c.k]}</td>)}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={cols.length + (sel ? 1 : 0)} className="p-6 text-center text-muted-foreground">{empty}</td></tr>}
        </tbody>
      </table>
    </div>
  );
};

export default function AccessMonitoring() {
  const { openDeepDive } = useDeepDive();
  const [d, setD] = useState(null);
  const [tab, setTab] = useState("dormant");
  const [confirm, setConfirm] = useState(null);
  const [bulk, setBulk] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { const { data } = await api.get("/sap/access-monitoring"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const h = () => load();
    window.addEventListener("sap-data-changed", h);
    return () => window.removeEventListener("sap-data-changed", h);
  }, [load]);
  useEffect(() => { setSelected(new Set()); }, [tab]);
  if (!d) return <Spinner />;

  const currentRows = tab === "dormant" ? d.dormant : tab === "orphan" ? d.orphan : d.service_accounts;
  const toggle = (ref) => setSelected((s) => { const n = new Set(s); n.has(ref) ? n.delete(ref) : n.add(ref); return n; });
  const toggleAll = () => setSelected((s) => { const all = currentRows.every((r) => s.has(r.ref)); const n = new Set(s); currentRows.forEach((r) => (all ? n.delete(r.ref) : n.add(r.ref))); return n; });
  const sel = { set: selected, toggle, toggleAll };

  const askAction = (action, row) => { setReason(""); setConfirm({ action, row }); };
  const runAction = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/sap/accounts/${confirm.row.ref}/action`, { action: confirm.action, reason });
      toast.success(`${ACC_META[confirm.action].label} — done`, { description: `ServiceNow ${data.ticket.number} opened & auto-closed` });
      setConfirm(null); window.dispatchEvent(new Event("sap-data-changed")); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const askBulk = (action) => { setReason(""); setBulk({ action }); };
  const runBulk = async () => {
    setBusy(true);
    try {
      const refs = [...selected];
      const { data } = await api.post("/sap/accounts/bulk-action", { refs, action: bulk.action, reason });
      toast.success(`${ACC_META[bulk.action].label} — ${data.changed} account(s)`, { description: `${data.tickets.length} ServiceNow workflow(s) opened & auto-closed` });
      setBulk(null); setSelected(new Set()); window.dispatchEvent(new Event("sap-data-changed")); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Bulk action failed"); }
    setBusy(false);
  };

  const openAcc = (r, kind) => openDeepDive({
    accent: r.privileged ? "266 85% 66%" : kind === "dormant" ? "168 76% 46%" : kind === "orphan" ? "38 92% 55%" : "266 85% 66%",
    refLabel: r.sap_user, title: r.person_name === "(no owner)" ? r.sap_user : r.person_name,
    rating: kind === "orphan" ? "High" : r.privileged ? "High" : "Medium",
    facets: [
      { label: "SAP user", value: `${r.sap_user} · ${r.system}` },
      { label: "Owner", value: r.owner || r.person_name },
      { label: "Account type", value: r.account_type || r.user_type },
      kind === "dormant"
        ? { label: "Days dormant", value: r.days_dormant != null ? `${r.days_dormant} days (last login ${fmtDate(r.last_login)})` : "Never logged in" }
        : { label: "Last login", value: fmtDate(r.last_login) },
      kind === "orphan" ? { label: "Orphan reason", value: r.reason } : null,
      { label: "Lock state", value: r.lock_state },
      { label: "Privileged", value: r.sap_all ? "SAP_ALL / full authorization" : r.privileged ? "Yes" : "No" },
      { label: "Roles", value: r.roles?.join(", ") || "None" },
    ].filter(Boolean),
    recommendedActions: [
      kind === "dormant" ? "Lock or de-provision this unused account to remove the standing attack surface." :
      kind === "orphan" ? "Assign an accountable owner or de-provision — ownerless access cannot be governed." :
      "Confirm the service/technical account is still required, has an owner, and rotate its credential.",
      "Open a recertification to capture reviewer evidence for the audit trail.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-2", "ISO 27001 A.5.16"],
    explainTitle: `${r.sap_user} — ${kind} account`, explainKind: `SAP ${kind} account access risk`,
    explainContext: { account: r, kind },
  });

  const flag = (r) => (
    <>
      {r.privileged && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple/15 text-purple mr-1">PRIV</span>}
      {r.lock_state === "locked" && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">LOCKED</span>}
    </>
  );
  const actions = (r) => (
    <div className="inline-flex items-center gap-1 justify-end" onClick={(e) => e.stopPropagation()}>
      {r.lock_state !== "locked" && <button data-testid={`mon-lock-${r.ref}`} title="Emergency lock" onClick={() => askAction("lock", r)} className="text-crit hover:bg-crit/10 rounded-md p-1.5"><Lock className="w-4 h-4" /></button>}
      <button data-testid={`mon-deactivate-${r.ref}`} title="De-provision (lock + revoke)" onClick={() => askAction("deactivate", r)} className="text-crit hover:bg-crit/10 rounded-md p-1.5"><Ban className="w-4 h-4" /></button>
      <button data-testid={`mon-recertify-${r.ref}`} title="Recertify" onClick={() => askAction("recertify", r)} className="text-ai hover:bg-ai/10 rounded-md p-1.5"><ShieldCheck className="w-4 h-4" /></button>
    </div>
  );
  const actionsCol = { k: "actions", label: "Actions", render: actions };

  const tabs = [
    { k: "dormant", label: `Dormant (${d.counts.dormant})`, icon: MoonStar },
    { k: "orphan", label: `Orphan (${d.counts.orphan})`, icon: Ghost },
    { k: "service", label: `Service / Technical (${d.counts.service})`, icon: Cpu },
  ];

  return (
    <div className="space-y-6" data-testid="monitoring-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="monitoring-title">Access Monitoring</h1>
        <p className="text-sm text-muted-foreground mt-1">Continuous detection of dormant, orphan and ownerless service/technical accounts — click any account for details, act individually, or multi-select to run a ServiceNow batch.</p>
      </div>

      <AIInsight dashboard="Access Monitoring" focus="dormant, orphan and ownerless service/technical accounts" accent="168 76% 46%" auto slug="access-monitoring" />
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Dormant accounts" value={d.counts.dormant} sub="Unused >90 days" accent="168 76% 46%" icon={MoonStar} testid="mon-dormant" />
        <StatCard label="Orphan accounts" value={d.counts.orphan} sub="No active owner" accent="38 92% 55%" icon={Ghost} testid="mon-orphan" />
        <StatCard label="Service / technical" value={d.counts.service} sub="RFC / batch / firefighter" accent="266 85% 66%" icon={Cpu} testid="mon-service" />
      </div>
      <div className="flex gap-2">
        {tabs.map((t) => (
          <button key={t.k} data-testid={`mon-tab-${t.k}`} onClick={() => setTab(t.k)} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${tab === t.k ? "bg-primary text-primary-foreground" : "bg-secondary/50 hover:bg-secondary"}`}><t.icon className="w-3.5 h-3.5" />{t.label}</button>
        ))}
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 p-3 rounded-xl bg-secondary/40 border border-border sticky top-2 z-10" data-testid="mon-bulk-bar">
          <Workflow className="w-4 h-4 text-ai" />
          <span className="text-sm font-medium" data-testid="mon-bulk-count">{selected.size} account{selected.size > 1 ? "s" : ""} selected</span>
          <div className="flex-1" />
          <Button size="sm" data-testid="mon-bulk-lock" className="h-8 gap-1.5 bg-crit hover:bg-crit/90" onClick={() => askBulk("lock")}><Lock className="w-3.5 h-3.5" /> Lock</Button>
          <Button size="sm" data-testid="mon-bulk-deactivate" className="h-8 gap-1.5 bg-crit hover:bg-crit/90" onClick={() => askBulk("deactivate")}><Ban className="w-3.5 h-3.5" /> De-provision</Button>
          <Button size="sm" data-testid="mon-bulk-recertify" className="h-8 gap-1.5 bg-ai hover:bg-ai/90" onClick={() => askBulk("recertify")}><ShieldCheck className="w-3.5 h-3.5" /> Recertify</Button>
          <Button size="sm" variant="ghost" data-testid="mon-bulk-clear" className="h-8 gap-1" onClick={() => setSelected(new Set())}><X className="w-3.5 h-3.5" /> Clear</Button>
        </div>
      )}

      {tab === "dormant" && <Table testid="mon-dormant-table" sel={sel} rows={d.dormant} empty="No dormant accounts." onRow={(r) => openAcc(r, "dormant")} cols={[
        { k: "sap_user", label: "SAP User" }, { k: "person_name", label: "Person" }, { k: "system", label: "System" },
        { k: "days_dormant", label: "Days Dormant", render: (r) => r.days_dormant != null ? `${r.days_dormant}d` : "never" },
        { k: "last_login", label: "Last Login", render: (r) => fmtDate(r.last_login) }, { k: "flags", label: "Flags", render: flag }, actionsCol,
      ]} />}
      {tab === "orphan" && <Table testid="mon-orphan-table" sel={sel} rows={d.orphan} empty="No orphan accounts." onRow={(r) => openAcc(r, "orphan")} cols={[
        { k: "sap_user", label: "SAP User" }, { k: "person_name", label: "Person" }, { k: "system", label: "System" },
        { k: "reason", label: "Reason" }, { k: "flags", label: "Flags", render: flag }, actionsCol,
      ]} />}
      {tab === "service" && <Table testid="mon-service-table" sel={sel} rows={d.service_accounts} empty="No service accounts." onRow={(r) => openAcc(r, "service")} cols={[
        { k: "sap_user", label: "SAP User" }, { k: "account_type", label: "Type" }, { k: "system", label: "System" },
        { k: "owner", label: "Owner", render: (r) => r.owner || <span className="text-crit">unassigned</span> },
        { k: "last_login", label: "Last Login", render: (r) => fmtDate(r.last_login) }, actionsCol,
      ]} />}

      <Dialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent data-testid="mon-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">{confirm && ACC_META[confirm.action].label} — {confirm?.row?.sap_user}</DialogTitle>
            <DialogDescription>{confirm && ACC_META[confirm.action].desc}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea data-testid="mon-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ServiceNow work note / reason…" rows={2} />
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setConfirm(null)}>Cancel</Button><Button data-testid="mon-confirm-btn" disabled={busy} onClick={runAction} className={confirm ? ACC_META[confirm.action].btn : ""}>{busy ? "Working…" : confirm && ACC_META[confirm.action].label}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!bulk} onOpenChange={(o) => !o && setBulk(null)}>
        <DialogContent data-testid="mon-bulk-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Workflow className="w-5 h-5 text-ai" />{bulk && ACC_META[bulk.action].label} — {selected.size} account{selected.size > 1 ? "s" : ""}</DialogTitle>
            <DialogDescription>{bulk && ACC_META[bulk.action].desc} One ServiceNow workflow is opened & auto-closed per account.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea data-testid="mon-bulk-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ServiceNow work note / reason applied to every ticket…" rows={2} />
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setBulk(null)}>Cancel</Button><Button data-testid="mon-bulk-confirm-btn" disabled={busy} onClick={runBulk} className={bulk ? ACC_META[bulk.action].btn : ""}>{busy ? "Working…" : bulk && `${ACC_META[bulk.action].label} ${selected.size}`}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
