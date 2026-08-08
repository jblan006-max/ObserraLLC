import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  PieChart, Pie, Cell, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from "recharts";
import {
  UserCheck, UserX, RefreshCw, Search, Ticket, Ban, ToggleRight, Users, Gauge, TriangleAlert, CheckCircle2, Mail, Workflow, Power, UserPlus, Zap, PauseCircle, PlayCircle, Sparkles, KeyRound, ShieldAlert,
} from "lucide-react";

const CHART_TT = { background: "hsl(215 38% 10%)", border: "1px solid hsl(215 30% 18%)", borderRadius: 8, fontSize: 12 };
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—");
const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");

const VERB = { activate: "activated", deactivate: "deactivated", suspend: "suspended", resume: "resumed" };
const ACTION_META = {
  activate: { label: "Activate", Icon: UserCheck, btn: "bg-low hover:bg-low/90", tone: "text-low",
    desc: "Restores login access and re-provisions the account (consuming a license). A ServiceNow provisioning request is opened and auto-closed across HR (ADP/IZ8) → AD/Entra → SAP." },
  deactivate: { label: "Deactivate", Icon: Ban, btn: "bg-crit hover:bg-crit/90", tone: "text-crit",
    desc: "The user can no longer log in and their license is freed (private content retained). A ServiceNow deactivation workflow is opened and auto-closed across HR (ADP/IZ8) → SAP → AD/Entra." },
  suspend: { label: "Suspend", Icon: PauseCircle, btn: "bg-amber hover:bg-amber/90", tone: "text-amber",
    desc: "Temporary hold (leave of absence): sign-in is disabled but the license and private content are retained. A ServiceNow suspension workflow is opened and auto-closed." },
  resume: { label: "Resume", Icon: PlayCircle, btn: "bg-low hover:bg-low/90", tone: "text-low",
    desc: "Restores access for a suspended user (re-enables sign-in). A ServiceNow resume workflow is opened and auto-closed across HR (ADP/IZ8) → AD/Entra → SAP." },
};
const DETAIL_ACTIONS = { Activated: ["suspend", "deactivate"], Suspended: ["resume", "deactivate"], Deactivated: ["activate"] };
const RATE = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "190 90% 50%", Low: "142 70% 45%" };

export default function UserActivation() {
  const [d, setD] = useState(null);
  const [tickets, setTickets] = useState(null);
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("all");
  const [status, setStatus] = useState("all");
  const [license, setLicense] = useState("all");
  const [sel, setSel] = useState(new Set());
  const [confirm, setConfirm] = useState(null); // { action, refs, names }
  const [reason, setReason] = useState("");
  const [notify, setNotify] = useState(true);
  const [busy, setBusy] = useState(false);
  const [ticketView, setTicketView] = useState(null);
  const [bulk, setBulk] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [suggesting, setSuggesting] = useState(false);
  const [roleList, setRoleList] = useState([]);
  const [cf, setCf] = useState({ first_name: "", last_name: "", email: "", department: "Finance", legal_entity: "US01", role: "", roles: [] });

  const load = useCallback(async () => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (dept !== "all") p.set("department", dept);
    if (status !== "all") p.set("status", status);
    const [a, t] = await Promise.all([
      api.get(`/sap/activation?${p.toString()}`),
      api.get("/sap/activation/tickets"),
    ]);
    setD(a.data); setTickets(t.data);
  }, [q, dept, status]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const h = () => load();
    window.addEventListener("sap-data-changed", h);
    return () => window.removeEventListener("sap-data-changed", h);
  }, [load]);
  useEffect(() => { api.get("/sap/roles").then((r) => setRoleList(r.data.roles)).catch(() => {}); }, []);

  if (!d) return <Spinner />;

  const users = license === "all" ? d.users : d.users.filter((u) => u.license_type === license);
  const toggle = (id) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allSelected = users.length > 0 && users.every((u) => sel.has(u.user_id));
  const toggleAll = () => setSel(allSelected ? new Set() : new Set(users.map((u) => u.user_id)));

  const askAction = (action, refs, names) => { setReason(""); setNotify(true); setConfirm({ action, refs, names }); };
  const runAction = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/sap/activation/set", { person_refs: confirm.refs, action: confirm.action, reason, work_note: reason, notify });
      const nums = (data.tickets || []).map((t) => t.number).join(", ");
      toast.success(`${data.changed} user(s) ${VERB[confirm.action] || "updated"}`, {
        description: nums ? `ServiceNow ${nums} opened & auto-closed` : undefined,
      });
      setConfirm(null); setSel(new Set()); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Action failed"); }
    setBusy(false);
  };

  const runBulk = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/sap/activation/bulk", { action: bulk.action, scope: "all", reason, work_note: reason, notify });
      toast.success(`${data.changed} user(s) ${VERB[bulk.action] || "updated"}`, { description: `${data.ticket_count} ServiceNow ticket(s) opened & auto-closed` });
      setBulk(null); setSel(new Set()); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Bulk action failed"); }
    setBusy(false);
  };
  const addCf = () => { if (cf.role && !cf.roles.includes(cf.role)) setCf({ ...cf, roles: [...cf.roles, cf.role], role: "" }); };
  const aiFill = async () => {
    setSuggesting(true);
    try {
      const { data } = await api.post("/sap/activation/create/suggest", { department: cf.department });
      setCf({ first_name: data.first_name, last_name: data.last_name, email: data.email, department: data.department, legal_entity: data.legal_entity, role: "", roles: data.roles || [] });
      setReason(data.work_note || "");
      toast.success("AI drafted a new-hire profile", { description: `${data.first_name} ${data.last_name} · ${data.department} · ${(data.role_names || []).join(", ") || "birthright roles"}` });
    } catch (e) { toast.error("AI auto-fill failed"); }
    setSuggesting(false);
  };
  const runCreate = async () => {
    if (!cf.first_name.trim() || !cf.last_name.trim() || !cf.email.trim()) { toast.error("First, last name and email required"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/sap/activation/create", { first_name: cf.first_name, last_name: cf.last_name, email: cf.email, department: cf.department, legal_entity: cf.legal_entity, roles: cf.roles, work_note: reason, notify });
      toast.success(`Created ${data.name}`, { description: `${data.ticket.number} provisioning workflow auto-closed` });
      setCreateOpen(false); setCf({ first_name: "", last_name: "", email: "", department: "Finance", legal_entity: "US01", role: "", roles: [] }); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Create failed"); }
    setBusy(false);
  };

  const openUser = async (u) => {
    setDetail({ loading: true, u });
    try { const { data } = await api.get(`/sap/identities/${u.user_id}`); setDetail({ ...data, u }); }
    catch { setDetail(null); toast.error("Could not load user detail"); }
  };

  const S = d.summary;
  const PIE = ["#42c98e", "#e0574a"];
  const maxLic = Math.max(1, ...d.license_breakdown.map((l) => l.value));

  return (
    <div className="space-y-6" data-testid="user-activation">
      {/* SAP-style header */}
      <div className="rounded-xl overflow-hidden fact-border">
        <div className="bg-[#0f1e3d] px-5 py-4 flex items-center gap-3">
          <ToggleRight className="w-5 h-5 text-[#4fc3f7]" />
          <div className="flex-1 min-w-0">
            <h1 className="font-head font-black text-lg lg:text-xl text-white truncate" data-testid="ua-title">User Account Activation / Deactivation</h1>
            <p className="text-[11px] text-white/60">SAP license governance · deactivated users can't log in, license is freed, private content is retained</p>
          </div>
          <button data-testid="ua-refresh" onClick={load} className="text-white/70 hover:text-white p-2 rounded-lg hover:bg-white/10"><RefreshCw className="w-4 h-4" /></button>
        </div>
      </div>

      {/* AI summary (Obserra standard) */}
      <SapInsight dashboard="User Access Activation" accent="35 90% 55%" auto slug="user-activation" />

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        <StatCard label="Total users" value={S.total} accent="190 90% 50%" icon={Users} testid="ua-total" />
        <StatCard label="Activated" value={S.activated} sub="Consuming a license" accent="142 70% 45%" icon={UserCheck} testid="ua-activated" />
        <StatCard label="Suspended" value={S.suspended} sub="On hold · license kept" accent="35 90% 55%" icon={PauseCircle} testid="ua-suspended" />
        <StatCard label="Deactivated" value={S.deactivated} sub="License freed · content kept" accent="0 84% 60%" icon={UserX} testid="ua-deactivated" />
        <StatCard label="License usage" value={`${S.license_usage_pct}%`} sub="Consumed of total" accent="266 85% 66%" icon={Gauge} testid="ua-usage" />
        <StatCard label="Underutilized" value={S.underutilized_licenses} sub="Prof. license · inactive >30d" accent="168 76% 46%" icon={TriangleAlert} testid="ua-underutilized" />
      </div>

      {/* Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-3 bg-card fact-border rounded-xl p-5" data-testid="ua-pie">
          <h2 className="font-head font-bold text-base mb-1">Activated vs Deactivated</h2>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={d.pie} dataKey="value" nameKey="name" innerRadius={46} outerRadius={70} paddingAngle={3} stroke="none">
                {d.pie.map((e, i) => <Cell key={e.name} fill={PIE[i]} />)}
              </Pie>
              <Tooltip contentStyle={CHART_TT} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex gap-3 justify-center">
            {d.pie.map((c, i) => <span key={c.name} className="text-[10px] text-muted-foreground flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: PIE[i] }} />{c.name} {c.value}</span>)}
          </div>
        </div>
        <div className="lg:col-span-5 bg-card fact-border rounded-xl p-5" data-testid="ua-trend">
          <h2 className="font-head font-bold text-base mb-1">Activation / Deactivation Trend</h2>
          <p className="text-[11px] text-muted-foreground mb-2">Last 6 months (from hire/termination + admin actions).</p>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={d.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 30% 18%)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis width={24} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip contentStyle={CHART_TT} />
              <Line type="monotone" dataKey="activated" stroke="#42c98e" strokeWidth={2.5} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="deactivated" stroke="#e0574a" strokeWidth={2.5} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="lg:col-span-4 bg-card fact-border rounded-xl p-5" data-testid="ua-heatmap">
          <h2 className="font-head font-bold text-base mb-1">Inactivity by Department</h2>
          <p className="text-[11px] text-muted-foreground mb-3">% of activated users inactive &gt; 30 days.</p>
          <div className="space-y-2 max-h-[150px] overflow-y-auto pr-1">
            {d.heatmap.map((h) => (
              <div key={h.department} className="flex items-center gap-2">
                <span className="text-[11px] w-24 truncate shrink-0">{h.department}</span>
                <div className="flex-1 h-3 rounded bg-secondary/60 overflow-hidden">
                  <div className="h-full rounded" style={{ width: `${Math.max(4, h.inactive_pct)}%`, background: `hsl(${h.inactive_pct >= 40 ? "0 84% 60%" : h.inactive_pct >= 15 ? "35 90% 55%" : "142 70% 45%"})` }} />
                </div>
                <span className="text-[10px] font-mono text-muted-foreground w-8 text-right">{h.inactive_pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ServiceNow automation */}
      <div className="bg-card fact-border rounded-xl p-5" data-testid="ua-automation">
        <div className="flex items-center gap-2 mb-1"><Zap className="w-4 h-4 text-amber" /><h2 className="font-head font-bold text-lg">ServiceNow Automation</h2></div>
        <p className="text-[11px] text-muted-foreground mb-3">One-click, work-note-enabled ServiceNow workflows that kick off and complete automatically — create, deactivate all, or reactivate all accounts.</p>
        <div className="flex flex-wrap gap-2">
          <Button data-testid="ua-create-user" onClick={() => { setReason(""); setNotify(true); setCreateOpen(true); }} className="gap-1.5"><UserPlus className="w-4 h-4" /> Create User</Button>
          <Button data-testid="ua-suspend-all" variant="outline" className="gap-1.5 text-amber border-amber/30" onClick={() => { setReason(""); setNotify(true); setBulk({ action: "suspend" }); }}><PauseCircle className="w-4 h-4" /> Suspend All Active ({S.activated})</Button>
          <Button data-testid="ua-deactivate-all" variant="outline" className="gap-1.5 text-crit border-crit/30" onClick={() => { setReason(""); setNotify(true); setBulk({ action: "deactivate" }); }}><Power className="w-4 h-4" /> Deactivate All ({S.activated + S.suspended})</Button>
          <Button data-testid="ua-reactivate-all" variant="outline" className="gap-1.5 text-low border-low/30" onClick={() => { setReason(""); setNotify(true); setBulk({ action: "activate" }); }}><UserCheck className="w-4 h-4" /> Reactivate All ({S.deactivated + S.suspended})</Button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="bg-card fact-border rounded-xl">
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background/50 px-2.5 h-9 flex-1 min-w-[180px]">
            <Search className="w-3.5 h-3.5 text-muted-foreground" />
            <input data-testid="ua-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name or email…" className="bg-transparent text-sm outline-none w-full" />
          </div>
          <Select value={license} onValueChange={setLicense}><SelectTrigger data-testid="ua-filter-license" className="w-[170px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All license types</SelectItem>{d.license_types.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}</SelectContent></Select>
          <Select value={dept} onValueChange={setDept}><SelectTrigger data-testid="ua-filter-dept" className="w-[150px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All departments</SelectItem>{d.departments.map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent></Select>
          <Select value={status} onValueChange={setStatus}><SelectTrigger data-testid="ua-filter-status" className="w-[140px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All statuses</SelectItem><SelectItem value="Activated">Activated</SelectItem><SelectItem value="Suspended">Suspended</SelectItem><SelectItem value="Deactivated">Deactivated</SelectItem></SelectContent></Select>
        </div>

        {sel.size > 0 && (
          <div className="flex items-center gap-3 px-4 py-2.5 bg-primary/10 border-b border-border" data-testid="ua-bulk-bar">
            <span className="text-xs font-medium">{sel.size} selected</span>
            <Button data-testid="ua-bulk-activate" size="sm" variant="outline" className="h-8 gap-1.5" onClick={() => askAction("activate", [...sel], `${sel.size} users`)}><UserCheck className="w-3.5 h-3.5" /> Activate</Button>
            <Button data-testid="ua-bulk-suspend" size="sm" variant="outline" className="h-8 gap-1.5 text-amber border-amber/30" onClick={() => askAction("suspend", [...sel], `${sel.size} users`)}><PauseCircle className="w-3.5 h-3.5" /> Suspend</Button>
            <Button data-testid="ua-bulk-deactivate" size="sm" className="h-8 gap-1.5 bg-crit hover:bg-crit/90" onClick={() => askAction("deactivate", [...sel], `${sel.size} users`)}><Ban className="w-3.5 h-3.5" /> Deactivate</Button>
          </div>
        )}

        {/* SAP-style users table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="ua-table">
            <thead>
              <tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
                <th className="p-3 w-8"><Checkbox checked={allSelected} onCheckedChange={toggleAll} data-testid="ua-select-all" /></th>
                <th className="p-3">User Name</th><th className="p-3">Name</th><th className="p-3">Display Name</th><th className="p-3">Email</th>
                <th className="p-3">Roles</th><th className="p-3">SAML Mapping</th><th className="p-3">License</th>
                <th className="p-3">Last Login</th><th className="p-3">Status</th><th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="border-b border-border/50 hover:bg-secondary/30" data-testid={`ua-row-${u.user_id}`}>
                  <td className="p-3"><Checkbox checked={sel.has(u.user_id)} onCheckedChange={() => toggle(u.user_id)} data-testid={`ua-check-${u.user_id}`} /></td>
                  <td className="p-3 font-mono text-xs">{u.user_name}</td>
                  <td className="p-3 font-medium whitespace-nowrap">
                    <button data-testid={`ua-open-${u.user_id}`} onClick={() => openUser(u)} className="inline-flex items-center gap-1.5 text-left hover:text-primary transition-colors">
                      {u.status === "Deactivated" && <Ban className="w-3.5 h-3.5 text-crit shrink-0" title="Deactivated" />}
                      {u.status === "Suspended" && <PauseCircle className="w-3.5 h-3.5 text-amber shrink-0" title="Suspended" />}
                      {u.name}
                    </button>
                  </td>
                  <td className="p-3 text-xs">{u.display_name}</td>
                  <td className="p-3 text-muted-foreground text-xs">{u.email}</td>
                  <td className="p-3 text-xs" title={u.roles.join(", ")}>{u.role_count}{u.roles[0] ? ` · ${u.roles[0].replace(/^Z_|^SAP_/, "")}` : ""}</td>
                  <td className="p-3 text-xs text-muted-foreground">{u.saml_user_mapping}</td>
                  <td className="p-3 text-xs whitespace-nowrap">{u.license_type}</td>
                  <td className="p-3 text-xs whitespace-nowrap">
                    {fmtDate(u.last_login)}
                    {u.inactivity_flag && <span className="ml-1 text-[9px] text-amber font-mono">{u.inactive_days}d</span>}
                  </td>
                  <td className="p-3">
                    <span data-testid={`ua-status-${u.user_id}`} className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded ${u.status === "Deactivated" ? "bg-crit/15 text-crit" : u.status === "Suspended" ? "bg-amber/15 text-amber" : "bg-low/15 text-low"}`}>{u.status}</span>
                  </td>
                  <td className="p-3 text-right whitespace-nowrap">
                    <div className="inline-flex items-center gap-1 justify-end">
                      {u.status === "Activated" && (
                        <button data-testid={`ua-suspend-${u.user_id}`} onClick={() => askAction("suspend", [u.user_id], u.name)} className="text-amber hover:bg-amber/10 rounded-md p-1.5" title="Suspend user (temporary hold)"><PauseCircle className="w-4 h-4" /></button>
                      )}
                      {u.status === "Suspended" && (
                        <button data-testid={`ua-resume-${u.user_id}`} onClick={() => askAction("resume", [u.user_id], u.name)} className="text-low hover:bg-low/10 rounded-md p-1.5" title="Resume user"><PlayCircle className="w-4 h-4" /></button>
                      )}
                      {u.status === "Activated" || u.status === "Suspended" ? (
                        <button data-testid={`ua-deactivate-${u.user_id}`} onClick={() => askAction("deactivate", [u.user_id], u.name)} className="text-crit hover:bg-crit/10 rounded-md p-1.5" title="Deactivate user"><Ban className="w-4 h-4" /></button>
                      ) : (
                        <button data-testid={`ua-activate-${u.user_id}`} onClick={() => askAction("activate", [u.user_id], u.name)} className="text-low hover:bg-low/10 rounded-md p-1.5" title="Activate user"><UserCheck className="w-4 h-4" /></button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {users.length === 0 && <tr><td colSpan={11} className="p-8 text-center text-sm text-muted-foreground">No users match these filters.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {/* ServiceNow workflow tickets */}
      <div className="bg-card fact-border rounded-xl p-5" data-testid="ua-tickets">
        <div className="flex items-center gap-2 mb-1">
          <Workflow className="w-4 h-4 text-ai" />
          <h2 className="font-head font-bold text-lg">ServiceNow Workflow</h2>
          <span className="text-[10px] font-mono text-muted-foreground ml-2">{tickets?.closed || 0} auto-closed · {tickets?.open || 0} open</span>
        </div>
        <p className="text-[11px] text-muted-foreground mb-3">Every activation/deactivation opens a ServiceNow ticket workflow that provisions/revokes access and closes automatically. Syncs to ServiceNow when the CON-SNOW connector is live.</p>
        <div className="space-y-2">
          {(tickets?.tickets || []).slice(0, 8).map((t) => (
            <button key={t.number} data-testid={`ua-ticket-${t.number}`} onClick={() => setTicketView(t)} className="w-full text-left flex items-center gap-3 p-3 rounded-lg bg-secondary/30 hover:bg-secondary/60 transition-colors">
              <Ticket className="w-4 h-4 text-ai shrink-0" />
              <span className="font-mono text-xs w-24 shrink-0">{t.number}</span>
              <div className="flex-1 min-w-0"><div className="text-sm truncate">{t.type} · {t.person_name}</div><div className="text-[10px] text-muted-foreground">{fmtDT(t.opened_at)} · resolved in {t.duration_sec}s</div></div>
              <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-low/15 text-low shrink-0 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" />{t.state}</span>
            </button>
          ))}
          {(!tickets?.tickets || tickets.tickets.length === 0) && <p className="text-sm text-muted-foreground py-4 text-center">No workflow tickets yet — activate or deactivate a user to kick one off.</p>}
        </div>
      </div>

      {/* Confirm dialog */}
      <Dialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent data-testid="ua-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {confirm && (() => { const M = ACTION_META[confirm.action]; const I = M.Icon; return <I className={`w-5 h-5 ${M.tone}`} />; })()}
              {confirm && ACTION_META[confirm.action].label} — {confirm?.names}
            </DialogTitle>
            <DialogDescription>
              {confirm && ACTION_META[confirm.action].desc}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea data-testid="ua-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (e.g. paternity leave, license recovery)…" rows={2} />
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <Checkbox checked={notify} onCheckedChange={(v) => setNotify(!!v)} data-testid="ua-notify" />
              <Mail className="w-3.5 h-3.5 text-muted-foreground" /> Email the user about this change
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirm(null)}>Cancel</Button>
            <Button data-testid="ua-confirm-btn" disabled={busy} onClick={runAction} className={confirm ? ACTION_META[confirm.action].btn : ""}>
              {busy ? "Working…" : confirm && ACTION_META[confirm.action].label}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Ticket timeline dialog */}
      <Dialog open={!!ticketView} onOpenChange={(o) => !o && setTicketView(null)}>
        <DialogContent data-testid="ua-ticket-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Ticket className="w-5 h-5 text-ai" /> {ticketView?.number}</DialogTitle>
            <DialogDescription>{ticketView?.type} · {ticketView?.person_name} · {ticketView?.email}</DialogDescription>
          </DialogHeader>
          <div className="space-y-0">
            {ticketView?.stages?.map((s, i) => (
              <div key={i} className="flex gap-3 pb-4 relative">
                <div className="flex flex-col items-center">
                  <span className={`w-3 h-3 rounded-full ${s.state === "Closed" ? "bg-low" : "bg-ai"} z-10`} />
                  {i < ticketView.stages.length - 1 && <span className="w-px flex-1 bg-border" />}
                </div>
                <div className="pb-1 -mt-0.5">
                  <div className="text-sm font-medium">{s.state}</div>
                  <div className="text-[11px] text-muted-foreground">{s.note}</div>
                  <div className="text-[10px] font-mono text-muted-foreground/70">{fmtDT(s.at)}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="text-[11px] text-muted-foreground border-t border-border pt-3">
            Auto-closed after {ticketView?.duration_sec}s · {ticketView?.synced_to_servicenow ? "synced to ServiceNow" : "pending ServiceNow sync (connector not yet live)"}
          </div>
        </DialogContent>
      </Dialog>

      {/* Bulk automation dialog */}
      <Dialog open={!!bulk} onOpenChange={(o) => !o && setBulk(null)}>
        <DialogContent data-testid="ua-bulk-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">{bulk && (() => { const M = ACTION_META[bulk.action]; const I = M.Icon; return <I className={`w-5 h-5 ${M.tone}`} />; })()}{bulk?.action === "deactivate" ? `Deactivate all ${S.activated + S.suspended} active / suspended users` : bulk?.action === "suspend" ? `Suspend all ${S.activated} active users` : `Reactivate all ${S.deactivated + S.suspended} deactivated / suspended users`}</DialogTitle>
            <DialogDescription>{bulk?.action === "deactivate" ? "Turns off every active/suspended account, freeing all licenses (content retained). A ServiceNow workflow is opened & auto-closed per user." : bulk?.action === "suspend" ? "Places every active account on temporary hold (sign-in disabled; licenses & content retained). A ServiceNow suspension workflow is opened & auto-closed per user." : "Restores login for every deactivated/suspended user (consuming licenses). A ServiceNow provisioning request is opened & auto-closed per user."}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea data-testid="ua-bulk-note" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ServiceNow work note (added to every ticket)…" rows={2} />
            <label className="flex items-center gap-2 text-sm cursor-pointer"><Checkbox checked={notify} onCheckedChange={(v) => setNotify(!!v)} /> <Mail className="w-3.5 h-3.5 text-muted-foreground" /> Email affected users</label>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setBulk(null)}>Cancel</Button><Button data-testid="ua-bulk-confirm" disabled={busy} onClick={runBulk} className={bulk ? ACTION_META[bulk.action].btn : ""}>{busy ? "Running…" : bulk?.action === "deactivate" ? "Deactivate All" : bulk?.action === "suspend" ? "Suspend All" : "Reactivate All"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create user dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent data-testid="ua-create-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><UserPlus className="w-5 h-5 text-primary" /> Create SAP User</DialogTitle><DialogDescription>Provisions a new SAP account via an auto-processing ServiceNow request.</DialogDescription></DialogHeader>
          <div className="space-y-2">
            <Button type="button" variant="outline" data-testid="cf-ai-fill" disabled={suggesting} onClick={aiFill} className="w-full gap-1.5 border-ai/40 text-ai hover:bg-ai/10">
              {suggesting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              {suggesting ? "Drafting with AI…" : "AI Auto-fill all fields"}
            </Button>
            <div className="grid grid-cols-2 gap-2">
              <Input data-testid="cf-first" value={cf.first_name} onChange={(e) => setCf({ ...cf, first_name: e.target.value })} placeholder="First name" />
              <Input data-testid="cf-last" value={cf.last_name} onChange={(e) => setCf({ ...cf, last_name: e.target.value })} placeholder="Last name" />
            </div>
            <Input data-testid="cf-email" value={cf.email} onChange={(e) => setCf({ ...cf, email: e.target.value })} placeholder="Email" />
            <div className="grid grid-cols-2 gap-2">
              <Select value={cf.department} onValueChange={(v) => setCf({ ...cf, department: v })}><SelectTrigger data-testid="cf-dept" className="h-9"><SelectValue /></SelectTrigger><SelectContent>{["Finance", "Procurement", "Treasury", "Sales", "HR", "IT Basis", "Master Data"].map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent></Select>
              <Select value={cf.legal_entity} onValueChange={(v) => setCf({ ...cf, legal_entity: v })}><SelectTrigger data-testid="cf-le" className="h-9"><SelectValue /></SelectTrigger><SelectContent>{["US01", "DE01", "UK01", "IN01"].map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent></Select>
            </div>
            <div className="flex gap-2">
              <Select value={cf.role} onValueChange={(v) => setCf({ ...cf, role: v })}><SelectTrigger data-testid="cf-role" className="h-9 flex-1"><SelectValue placeholder="Add role…" /></SelectTrigger><SelectContent>{roleList.map((r) => <SelectItem key={r.ref} value={r.ref}>{r.name}</SelectItem>)}</SelectContent></Select>
              <Button variant="outline" className="h-9" data-testid="cf-add-role" onClick={addCf}>Add</Button>
            </div>
            {cf.roles.length > 0 && <div className="flex flex-wrap gap-1.5">{cf.roles.map((r) => <span key={r} className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary">{r}</span>)}</div>}
            <Textarea data-testid="cf-note" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ServiceNow work note…" rows={2} />
            <label className="flex items-center gap-2 text-sm cursor-pointer"><Checkbox checked={notify} onCheckedChange={(v) => setNotify(!!v)} /> <Mail className="w-3.5 h-3.5 text-muted-foreground" /> Email welcome to the user</label>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button><Button data-testid="cf-submit" disabled={busy} onClick={runCreate}>{busy ? "Provisioning…" : "Create & Provision"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Per-user detail (Obserra standard: clickable identity detail + live workflow actions) */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="ua-detail-dialog">
          {detail?.loading ? <div className="py-16"><Spinner /></div> : detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  <span className="font-head font-black text-2xl" style={{ color: `hsl(${RATE[detail.risk.rating]})` }}>{detail.risk.score}</span>
                  {detail.person.name}
                  <span data-testid="ua-detail-status" className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded ${detail.activation_status === "Deactivated" ? "bg-crit/15 text-crit" : detail.activation_status === "Suspended" ? "bg-amber/15 text-amber" : "bg-low/15 text-low"}`}>{detail.activation_status}</span>
                </DialogTitle>
                <DialogDescription>{detail.person.job_title} · {detail.person.department} · {detail.u.license_type} license</DialogDescription>
              </DialogHeader>
              <div className="flex flex-wrap items-center gap-2 mb-3 p-3 rounded-lg bg-secondary/30 border border-border" data-testid="ua-detail-actions">
                <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground inline-flex items-center gap-1.5 mr-1"><Workflow className="w-3.5 h-3.5 text-ai" /> ServiceNow workflow</span>
                {(DETAIL_ACTIONS[detail.activation_status] || []).map((a) => { const M = ACTION_META[a]; const I = M.Icon; return (
                  <Button key={a} size="sm" data-testid={`ua-detail-${a}`} className={`h-8 gap-1.5 ${M.btn}`} onClick={() => { const u = detail.u; setDetail(null); askAction(a, [u.user_id], u.name); }}><I className="w-3.5 h-3.5" /> {M.label}</Button>
                ); })}
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm mb-3">
                <div><span className="text-muted-foreground text-xs">Manager</span><div>{detail.u.manager || "—"} · HR {detail.person.hr_authority}</div></div>
                <div><span className="text-muted-foreground text-xs">Legal entity</span><div>{detail.person.legal_entity_name} ({detail.person.country})</div></div>
                <div><span className="text-muted-foreground text-xs">Last login</span><div>{fmtDate(detail.u.last_login)}{detail.u.inactivity_flag ? ` · inactive ${detail.u.inactive_days}d` : ""}</div></div>
                <div><span className="text-muted-foreground text-xs">Worker type</span><div>{detail.person.worker_type}</div></div>
              </div>
              <div className="border-t border-border pt-3 mb-3">
                <div className="flex items-center gap-2 mb-2"><KeyRound className="w-4 h-4 text-primary" /><h3 className="font-head font-bold text-sm">SAP Accounts ({detail.accounts.length})</h3></div>
                {detail.accounts.map((a) => (
                  <div key={a.ref} className="p-2.5 rounded-lg bg-secondary/30 mb-2">
                    <div className="font-mono text-sm">{a.sap_user} <span className="text-muted-foreground">· {a.system}/{a.client} · {a.lock_state}</span></div>
                    <div className="flex flex-wrap gap-1 mt-1.5">{a.roles.map((r) => <span key={r.ref} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary" title={r.functions.join(", ")}>{r.name}</span>)}</div>
                  </div>
                ))}
                {detail.accounts.length === 0 && <p className="text-xs text-muted-foreground">No SAP accounts linked.</p>}
              </div>
              {detail.sod_conflicts.length > 0 && (
                <div className="border-t border-border pt-3">
                  <div className="flex items-center gap-2 mb-2"><ShieldAlert className="w-4 h-4 text-crit" /><h3 className="font-head font-bold text-sm">SoD Conflicts ({detail.sod_conflicts.length})</h3></div>
                  {detail.sod_conflicts.map((c) => (
                    <div key={c.conflict_ref} className="flex items-center gap-2 text-sm mb-1">
                      <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${RATE[c.severity]} / 0.15)`, color: `hsl(${RATE[c.severity]})` }}>{c.severity}</span>
                      {c.rule_name}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
