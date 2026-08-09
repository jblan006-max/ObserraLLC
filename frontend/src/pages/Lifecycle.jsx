import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { useDeepDive } from "@/context/DeepDiveContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { UserPlus, UserX, GitBranch, Ban, PauseCircle, PlayCircle, Power, ArrowLeftRight, Scissors, Zap } from "lucide-react";

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
  const [moverReview, setMoverReview] = useState(null);
  const [stripBusy, setStripBusy] = useState(false);
  const [moverRule, setMoverRule] = useState(null);
  const [ruleBusy, setRuleBusy] = useState(false);
  const load = useCallback(async () => { const { data } = await api.get("/sap/jml"); setD(data); }, []);
  const loadRule = useCallback(async () => { try { const { data } = await api.get("/sap/mover-rule"); setMoverRule(data); } catch { /* ignore */ } }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadRule(); }, [loadRule]);
  useEffect(() => {
    const h = () => { load(); loadRule(); };
    window.addEventListener("sap-data-changed", h);
    return () => window.removeEventListener("sap-data-changed", h);
  }, [load, loadRule]);
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

  const stripMover = async (m) => {
    setStripBusy(true);
    try {
      const { data } = await api.post(`/sap/jml/${m.ref}/strip-carried-over`, { reason: "Mover access-accumulation cleanup" });
      toast.success(`Stripped ${data.stripped_count} carried-over role(s) from ${m.name}`, { description: `ServiceNow ${data.ticket.number} opened & auto-closed` });
      setMoverReview(null); window.dispatchEvent(new Event("sap-data-changed")); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Strip failed"); }
    setStripBusy(false);
  };

  const toggleRule = async (v) => {
    setRuleBusy(true);
    try {
      const { data } = await api.put("/sap/mover-rule", { enabled: v });
      if (v && data.stripped) toast.success(`Auto-strip enabled — cleaned ${data.stripped} mover(s)`, { description: "ServiceNow cleanup workflows opened & auto-closed" });
      else toast.success(v ? "Mover auto-strip rule enabled" : "Mover auto-strip rule disabled");
      await loadRule(); window.dispatchEvent(new Event("sap-data-changed"));
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not update rule (admin only)"); }
    setRuleBusy(false);
  };

  const rowActions = (ref, name) => (
    <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
      <button data-testid={`jml-deactivate-${ref}`} onClick={() => askAction("deactivate", [ref], name)} title="Deactivate (lock access)" className="text-crit hover:bg-crit/10 rounded-md p-1.5"><Ban className="w-4 h-4" /></button>
      <button data-testid={`jml-suspend-${ref}`} onClick={() => askAction("suspend", [ref], name)} title="Suspend (temporary hold)" className="text-amber hover:bg-amber/10 rounded-md p-1.5"><PauseCircle className="w-4 h-4" /></button>
      <button data-testid={`jml-reactivate-${ref}`} onClick={() => askAction("activate", [ref], name)} title="Reactivate access" className="text-low hover:bg-low/10 rounded-md p-1.5"><PlayCircle className="w-4 h-4" /></button>
    </div>
  );

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
  const openMover = (m) => openDeepDive({
    accent: "260 85% 66%", refLabel: m.ref, title: `${m.name} — in-flight transfer`, rating: m.rating, score: m.score,
    facets: [
      { label: "Current department", value: m.department },
      ...m.changes.map((c) => ({ label: `Change · ${c.field}`, value: `${c.from ?? "—"} → ${c.to ?? "—"}` })),
      { label: "SAP access", value: `${m.accounts} account(s) · ${m.roles} role(s)` },
      { label: "HR authority", value: m.hr_authority },
    ],
    recommendedActions: [
      "Re-evaluate this mover's SAP roles against their new position and strip access carried over from the previous role (avoid access accumulation).",
      "Run an SoD pre-check and recertify remaining access after the transfer completes.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-6", "ISO 27001 A.5.18"],
    explainTitle: `${m.name} — mover / transfer access review`, explainKind: "SAP mover transfer access accumulation risk",
    explainContext: { mover: m },
  });
  const openJoiner = (j) => openDeepDive({
    accent: "142 70% 45%", refLabel: j.ref, title: `${j.name} — new joiner`, rating: j.provisioned ? "Low" : "Medium",
    facets: [
      { label: "Department", value: j.department }, { label: "Hire date", value: fmtDate(j.hire_date) },
      { label: "HR authority", value: j.hr_authority }, { label: "SAP provisioning", value: j.provisioned ? `${j.accounts} account(s) provisioned` : "Not yet provisioned" },
    ],
    recommendedActions: [
      j.provisioned ? "Confirm birthright roles match the joiner's job and run an SoD pre-check before granting extra access." : "Provision the joiner's SAP account with birthright roles via the automated ServiceNow workflow.",
      "Recertify the joiner's access at day 30 to confirm least-privilege.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-2", "ISO 27001 A.5.16"],
    explainTitle: `${j.name} — new joiner provisioning`, explainKind: "SAP joiner provisioning and birthright access",
    explainContext: { joiner: j },
  });

  return (
    <div className="space-y-6" data-testid="lifecycle-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="lifecycle-title">Joiner / Mover / Leaver</h1>
        <p className="text-sm text-muted-foreground mt-1">Workforce lifecycle correlated with SAP access — click any worker for details and kick off a live ServiceNow access workflow.</p>
      </div>

      <SapInsight dashboard="Joiner / Mover / Leaver" focus="leaver residual access, mover access accumulation and joiner provisioning gaps" accent="142 70% 45%" auto slug="lifecycle" />
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Joiners (21d)" value={d.counts.joiners} accent="142 70% 45%" icon={UserPlus} testid="jml-joiners" />
        <StatCard label="Movers (in-flight transfers)" value={d.counts.movers} accent="260 85% 66%" icon={ArrowLeftRight} testid="jml-movers" />
        <StatCard label="Leavers w/ residual access" value={d.counts.leavers} accent="0 84% 60%" icon={UserX} testid="jml-leavers" />
      </div>

      {/* Leavers */}
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
              {rowActions(l.ref, l.name)}
            </div>
          ))}
          {d.leavers.length === 0 && <p className="text-sm text-low py-3">No terminated workers with residual SAP access. ✓</p>}
        </div>
      </div>

      {/* Movers */}
      <div className="bg-card fact-border rounded-xl p-5" data-testid="jml-movers-panel">
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <div className="flex items-center gap-2"><ArrowLeftRight className="w-4 h-4 text-purple" /><h2 className="font-head font-bold text-lg">Movers — In-Flight Transfers</h2></div>
          {moverRule && <span data-testid="mover-rule-state" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${moverRule.config.enabled ? "bg-low/15 text-low" : "bg-secondary text-muted-foreground"}`}>{moverRule.config.enabled ? "AUTO-STRIP ON" : "AUTO-STRIP OFF"}</span>}
          <div className="flex-1" />
          {moverRule && (
            <div className="flex items-center gap-2" title="When on, carried-over access is auto-stripped for every mover — zero-click least privilege.">
              <Zap className="w-3.5 h-3.5 text-amber" />
              <span className="text-xs text-muted-foreground">Auto-strip carried-over access</span>
              <Switch data-testid="mover-rule-toggle" checked={moverRule.config.enabled} disabled={ruleBusy} onCheckedChange={toggleRule} />
            </div>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground mb-3">Workers whose ADP and IZ8 HR records disagree on org attributes (legal entity, manager, job title) — a transfer in progress. Review for access carried over from the previous role.{moverRule?.config?.enabled && <span className="text-low"> Auto-strip rule active — carried-over roles are removed automatically via ServiceNow.</span>}{moverRule?.config?.last_cron_at && <span className="font-mono"> Last scheduled sweep {new Date(moverRule.config.last_cron_at).toLocaleDateString()} · {moverRule.config.last_cron_count ?? 0} cleaned.</span>}</p>
        <div className="space-y-2">
          {d.movers.map((m) => (
            <div key={m.ref} data-testid={`jml-mover-${m.ref}`} className="flex items-center gap-3 p-3 rounded-lg bg-purple/5 border border-purple/20">
              <button onClick={() => setMoverReview(m)} data-testid={`jml-mover-open-${m.ref}`} className="flex items-center gap-3 flex-1 min-w-0 text-left hover:opacity-80 transition-opacity">
                <span className="font-head font-black text-xl text-purple w-10">{m.score}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{m.name}{m.carried_over_count > 0 && <span className="ml-2 text-[9px] font-mono px-1.5 py-0.5 rounded bg-crit/15 text-crit align-middle">{m.carried_over_count} carried over</span>}</div>
                  <div className="text-[11px] text-muted-foreground">{m.department} · {m.accounts} account(s) · {m.roles} role(s) · {m.changes.map((c) => c.field).join(", ")} changed</div>
                </div>
                <div className="hidden md:flex flex-wrap gap-1 justify-end max-w-[280px]">{m.changes.slice(0, 3).map((c, i) => <span key={i} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">{c.field}: {c.from ?? "—"}→{c.to ?? "—"}</span>)}</div>
              </button>
              {rowActions(m.ref, m.name)}
            </div>
          ))}
          {d.movers.length === 0 && <p className="text-sm text-muted-foreground py-3">No in-flight transfers detected — ADP and IZ8 records are aligned. ✓</p>}
        </div>
      </div>

      {moverRule && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="mover-rule-report">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Scissors className="w-4 h-4 text-amber" /><h2 className="font-head font-bold text-lg">Auto-Strip Activity Log</h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-secondary text-muted-foreground" data-testid="mover-rule-total">{moverRule.stripped_total} mover(s) cleaned total</span>
          </div>
          {moverRule.log?.length ? (
            <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
              {moverRule.log.map((l, i) => (
                <div key={i} data-testid={`mover-log-${i}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 p-2.5 rounded-lg bg-secondary/30 text-xs">
                  <span className="font-mono text-primary shrink-0">{l.ticket_number}</span>
                  <span className="font-medium">{l.name}</span>
                  <span className="text-muted-foreground">{l.department}</span>
                  <span className="flex-1 min-w-0 truncate text-crit">− {(l.stripped_names || []).join(", ")}</span>
                  <span className="font-mono text-muted-foreground shrink-0">{new Date(l.at).toLocaleString()}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground py-2" data-testid="mover-rule-empty">No auto-strip activity yet. Enable the auto-strip rule above to automatically remove carried-over access from movers — every cleanup is logged here with its ServiceNow ticket.</p>
          )}
        </div>
      )}

      {/* Joiners */}
      <div className="bg-card fact-border rounded-xl p-5" data-testid="jml-joiners-panel">
        <div className="flex items-center gap-2 mb-3"><UserPlus className="w-4 h-4 text-low" /><h2 className="font-head font-bold text-lg">Recent Joiners</h2></div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-2">Name</th><th className="p-2">Dept</th><th className="p-2">Hire Date</th><th className="p-2">HR Source</th><th className="p-2">Provisioned</th><th className="p-2 text-right">Actions</th></tr></thead>
            <tbody>
              {d.joiners.map((j) => (
                <tr key={j.ref} className="border-b border-border/50 hover:bg-secondary/30 cursor-pointer" data-testid={`jml-joiner-${j.ref}`} onClick={() => openJoiner(j)}>
                  <td className="p-2 font-medium"><button data-testid={`jml-joiner-open-${j.ref}`} className="hover:text-primary text-left">{j.name}</button></td>
                  <td className="p-2 text-xs">{j.department}</td>
                  <td className="p-2 text-xs">{fmtDate(j.hire_date)}</td>
                  <td className="p-2 text-xs font-mono">{j.hr_authority}</td>
                  <td className="p-2 text-xs">{j.provisioned ? <span className="text-low">✓ {j.accounts} account(s)</span> : <span className="text-amber">Pending</span>}</td>
                  <td className="p-2 text-right">{rowActions(j.ref, j.name)}</td>
                </tr>
              ))}
              {d.joiners.length === 0 && <tr><td colSpan={6} className="p-4 text-center text-muted-foreground">No recent joiners.</td></tr>}
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

      <Dialog open={!!moverReview} onOpenChange={(o) => !o && setMoverReview(null)}>
        <DialogContent className="max-w-2xl" data-testid="jml-mover-dialog">
          {moverReview && (() => {
            const m = moverReview;
            const heldRefs = new Set((m.current_roles || []).map((r) => r.ref));
            const carriedRefs = new Set((m.carried_over || []).map((r) => r.ref));
            return (
              <>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2"><ArrowLeftRight className="w-5 h-5 text-purple" /> {m.name} — mover role review</DialogTitle>
                  <DialogDescription>In-flight transfer detected from disagreeing ADP / IZ8 HR records. Compare the roles held now against the current department's birthright set, then strip access carried over from the previous role (least privilege).</DialogDescription>
                </DialogHeader>
                <div className="flex flex-wrap gap-1.5 mb-3" data-testid="mover-changes">
                  {m.changes.map((c, i) => <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary text-muted-foreground">{c.field}: {c.from ?? "—"} → {c.to ?? "—"}</span>)}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div data-testid="mover-role-current">
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Roles held now ({m.current_roles.length})</div>
                    <div className="space-y-1.5">
                      {m.current_roles.map((r) => {
                        const carried = carriedRefs.has(r.ref);
                        return (
                          <div key={r.ref} data-testid={`mover-current-${r.ref}`} className={`flex items-center justify-between gap-2 text-xs p-2 rounded-lg border ${carried ? "bg-crit/5 border-crit/30" : "bg-secondary/30 border-border"}`}>
                            <span className="truncate"><span className="font-mono">{r.ref}</span> · {r.name}</span>
                            {carried ? <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-crit/15 text-crit shrink-0">CARRIED OVER</span> : <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-low/15 text-low shrink-0">BIRTHRIGHT</span>}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div data-testid="mover-role-birthright">
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">{m.department} birthright ({m.birthright_roles.length})</div>
                    <div className="space-y-1.5">
                      {m.birthright_roles.map((r) => {
                        const held = heldRefs.has(r.ref);
                        return (
                          <div key={r.ref} className={`flex items-center justify-between gap-2 text-xs p-2 rounded-lg border ${held ? "bg-low/5 border-low/30" : "bg-secondary/20 border-dashed border-border"}`}>
                            <span className={`truncate ${held ? "" : "text-muted-foreground"}`}><span className="font-mono">{r.ref}</span> · {r.name}</span>
                            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded shrink-0 ${held ? "bg-low/15 text-low" : "bg-secondary text-muted-foreground"}`}>{held ? "HELD" : "NOT PROVISIONED"}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <DialogFooter className="mt-4 gap-2 sm:justify-between">
                  <Button variant="outline" size="sm" data-testid="mover-ai-review" onClick={() => { const mm = m; setMoverReview(null); openMover(mm); }}>AI deep-dive</Button>
                  <div className="flex gap-2">
                    <Button variant="outline" onClick={() => setMoverReview(null)}>Close</Button>
                    <Button data-testid="jml-mover-strip-btn" disabled={stripBusy || m.carried_over_count === 0} onClick={() => stripMover(m)} className="gap-1.5 bg-crit hover:bg-crit/90"><Scissors className="w-3.5 h-3.5" />{stripBusy ? "Stripping…" : m.carried_over_count > 0 ? `Strip carried-over (${m.carried_over_count})` : "No carried-over access"}</Button>
                  </div>
                </DialogFooter>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>
    </div>
  );
}
