import { useMemo, useState, useEffect, useCallback } from "react";
import {
  KeyRound,
  ShieldOff,
  ShieldCheck,
  ShieldAlert,
  Bot,
  AlertOctagon,
  AlertTriangle,
  Megaphone,
  Radio,
  Mail,
  Share2,
  Presentation,
  Activity,
  HeartPulse,
  Workflow,
  Clock3,
  CheckCircle2,
  Download,
  Loader2,
  ClipboardList,
  Send,
  Plus,
  Trash2,
  Save,
  Timer,
  Target,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import { api } from "@/lib/api";
import {
  activeIncidents,
  actionSummary,
  controlFailureSummary,
  recoveryByCategory,
  recoveryOverall,
  toNumber,
  pirBlocks,
} from "@/lib/crisisCommanderModels";

// ---------------------------------------------------------------------------
// Shared local presentational helpers (mirror the CyberCrisisCommander page
// style so the vision dashboards are visually consistent while staying a
// self-contained module).
// ---------------------------------------------------------------------------
const CLASS_STYLE = {
  FACT: "bg-low/10 text-low border-low/25",
  MODELLED: "bg-med/10 text-med border-med/25",
  "AI RECOMMENDATION": "bg-ai/10 text-ai border-ai/25",
};

function DataClassBadge({ kind = "FACT" }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[9px] font-mono font-bold uppercase tracking-wider ${CLASS_STYLE[kind] || CLASS_STYLE.FACT}`}>
      {kind}
    </span>
  );
}

function StatusPill({ value }) {
  const text = String(value || "Unknown");
  const lower = text.toLowerCase();
  const style =
    lower.includes("critical") || lower.includes("failing") || lower.includes("failed") || lower.includes("down") || lower.includes("high") || lower.includes("breach")
      ? "bg-crit/10 text-crit border-crit/25"
      : lower.includes("drift") || lower.includes("investigating") || lower.includes("medium") || lower.includes("restoring") || lower.includes("at risk")
      ? "bg-high/10 text-high border-high/25"
      : lower.includes("stale") || lower.includes("monitor") || lower.includes("validated")
      ? "bg-med/10 text-med border-med/25"
      : lower.includes("passing") || lower.includes("resolved") || lower.includes("contained") || lower.includes("operational") || lower.includes("closed") || lower.includes("low") || lower.includes("met") || lower.includes("on track")
      ? "bg-low/10 text-low border-low/25"
      : "bg-secondary text-muted-foreground border-border";
  return <span className={`inline-flex px-2 py-0.5 rounded-full border text-[10px] font-mono font-bold ${style}`}>{text}</span>;
}

function Panel({ title, subtitle, actions, children, testid }) {
  return (
    <section data-testid={testid} className="bg-card fact-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="font-head font-black text-lg tracking-tight">{title}</h2>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function MetricCard({ label, value, sub, kind = "FACT", icon: Icon, accent = "0 84% 60%", testid }) {
  return (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-4" style={{ borderLeft: `3px solid hsl(${accent})` }}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          {Icon && <Icon className="w-3.5 h-3.5" />}
          {label}
        </div>
        <DataClassBadge kind={kind} />
      </div>
      <div className="font-head font-black text-2xl lg:text-3xl mt-2 break-words">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

function ProgressBar({ value = 0, accent = "142 70% 45%" }) {
  const width = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <div className="h-2 rounded-full bg-secondary/70 overflow-hidden">
      <div className="h-full rounded-full" style={{ width: `${width}%`, background: `hsl(${accent})` }} />
    </div>
  );
}

function EmptyState({ title, text }) {
  return (
    <div className="py-12 text-center">
      <AlertTriangle className="w-9 h-9 text-muted-foreground mx-auto" />
      <div className="font-head font-bold mt-3">{title}</div>
      <p className="text-sm text-muted-foreground max-w-xl mx-auto mt-2">{text}</p>
    </div>
  );
}

const CHART_TOOLTIP = { background: "#0A0E17", border: "1px solid rgba(255,255,255,.12)", borderRadius: 8, fontSize: 12 };

function hoursSince(iso) {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  return Number.isFinite(ms) ? ms / 3_600_000 : null;
}

function ageLabel(hours) {
  if (hours == null) return "—";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

function fmtMins(m) {
  if (m == null || m === "" || Number.isNaN(Number(m))) return "—";
  const n = Number(m);
  if (n < 60) return `${n}m`;
  if (n < 1440) return `${Math.round((n / 60) * 10) / 10}h`.replace(".0", "");
  return `${Math.round((n / 1440) * 10) / 10}d`.replace(".0", "");
}

// ---------------------------------------------------------------------------
// 1) Identity Crisis Intelligence
// ---------------------------------------------------------------------------
const IDENTITY_RE = /identit|iam|\baccess\b|privileg|credential|\bmfa\b|\bsso\b|entra|authenticat|password|sign-?in|login|token|azure ad|active directory/i;

export function IdentityCrisisIntelligence({ data = {}, caseDetail, selectedCase }) {
  const controls = data.controls || [];
  const incidents = data.incidents || [];
  const audit = data.audit || [];

  const idControls = controls.filter((c) => IDENTITY_RE.test(`${c.name || ""} ${c.category || ""} ${c.control_id || ""}`));
  const idControlFailures = idControls.filter((c) => c.status === "Failing" || c.status === "Drifting" || c.status === "Evidence Stale" || c.drift || c.stale);
  const idIncidents = activeIncidents(incidents).filter((i) => IDENTITY_RE.test(`${i.title || ""} ${i.system || ""}`));
  const containmentEvents = audit.filter((a) => /contain|identity|revoke|disable/i.test(`${a.action || ""} ${a.detail || ""}`));

  const posture = Math.max(0, 100 - (idControlFailures.length * 18 + idIncidents.length * 14));

  return (
    <div className="space-y-5" data-testid="crisis-identity-intelligence">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard testid="crisis-identity-kpi-incidents" label="Identity incidents" value={idIncidents.length} sub="Active, identity-linked" icon={KeyRound} />
        <MetricCard testid="crisis-identity-kpi-controls" label="Identity control failures" value={idControlFailures.length} sub={`${idControls.length} identity/IAM controls monitored`} icon={ShieldAlert} accent="35 90% 55%" />
        <MetricCard testid="crisis-identity-kpi-contained" label="Containment actions" value={containmentEvents.length} sub="Recorded in the audit stream" icon={ShieldOff} accent="266 85% 66%" />
        <MetricCard testid="crisis-identity-kpi-posture" label="Identity posture" value={`${posture}/100`} sub="Failures + active identity incidents" kind="MODELLED" icon={ShieldCheck} accent="142 70% 45%" />
      </div>

      <div className="grid xl:grid-cols-2 gap-5">
        <Panel testid="crisis-identity-control-failures" title="Identity & Access Control Failures" subtitle="Live control monitoring filtered to identity, access and credential domains.">
          {idControlFailures.length === 0 ? (
            <EmptyState title="No identity control failures" text="No identity, access or credential controls are currently failing, drifting or carrying stale evidence." />
          ) : (
            <div className="space-y-2">
              {idControlFailures.map((c) => (
                <div key={c.control_id} data-testid={`crisis-identity-control-${c.control_id}`} className="rounded-lg border border-border bg-secondary/20 p-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-mono text-[10px] text-ai">{c.control_id}</div>
                    <div className="font-head font-bold text-sm mt-0.5 truncate">{c.name}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{c.category} · {c.owner || "Unassigned"}</div>
                  </div>
                  <div className="text-right shrink-0">
                    <StatusPill value={c.status} />
                    <div className="text-[10px] text-muted-foreground mt-1">Eff {c.effectiveness ?? "-"}%</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel testid="crisis-identity-incidents" title="Identity-Linked Incidents" subtitle="Active incidents whose title or affected system implicates identity or credentials.">
          {idIncidents.length === 0 ? (
            <EmptyState title="No identity-linked incidents" text="No active incident currently implicates an account, credential or identity system." />
          ) : (
            <div className="space-y-2">
              {idIncidents.map((i) => (
                <div key={i.ref || i.title} data-testid={`crisis-identity-incident-${i.ref || "x"}`} className="rounded-lg border border-border bg-secondary/20 p-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-mono text-[10px] text-ai">{i.ref || "—"}</div>
                    <div className="font-head font-bold text-sm mt-0.5 truncate">{i.title}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{i.system || "Unknown system"} · opened {ageLabel(hoursSince(i.opened))} ago</div>
                  </div>
                  <StatusPill value={i.severity} />
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2) AI Incident Intelligence
// ---------------------------------------------------------------------------
const SEV_ORDER = ["Critical", "High", "Medium", "Low", "Info"];

export function AIIncidentIntelligence({ data = {} }) {
  const incidents = useMemo(() => data.incidents || [], [data.incidents]);
  const active = useMemo(() => activeIncidents(incidents), [incidents]);

  const sevData = useMemo(() => {
    const counts = {};
    for (const i of active) counts[i.severity || "Info"] = (counts[i.severity || "Info"] || 0) + 1;
    return SEV_ORDER.filter((s) => counts[s]).map((s) => ({ name: s, value: counts[s] }));
  }, [active]);

  const statusData = useMemo(() => {
    const counts = {};
    for (const i of incidents) counts[i.status || "Unknown"] = (counts[i.status || "Unknown"] || 0) + 1;
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [incidents]);

  const systems = useMemo(() => {
    const map = {};
    for (const i of active) {
      const key = i.system || "Unknown system";
      map[key] = map[key] || { system: key, count: 0 };
      map[key].count += 1;
    }
    return Object.values(map).sort((a, b) => b.count - a.count).slice(0, 8);
  }, [active]);

  const critHigh = active.filter((i) => ["Critical", "High"].includes(i.severity)).length;
  const ages = active.map((i) => hoursSince(i.opened)).filter((h) => h != null);
  const meanAge = ages.length ? ages.reduce((a, b) => a + b, 0) / ages.length : null;
  const resolved = incidents.filter((i) => ["Resolved", "Closed", "Remediated"].includes(i.status));
  const resolutionRate = incidents.length ? Math.round((resolved.length / incidents.length) * 100) : 0;

  const top = [...active].sort((a, b) => (SEV_ORDER.indexOf(a.severity || "Info")) - (SEV_ORDER.indexOf(b.severity || "Info")) || (hoursSince(b.opened) || 0) - (hoursSince(a.opened) || 0)).slice(0, 8);

  return (
    <div className="space-y-5" data-testid="crisis-ai-incident-intelligence">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard testid="crisis-aii-kpi-active" label="Active incidents" value={active.length} sub={`${incidents.length} tracked in total`} icon={Bot} />
        <MetricCard testid="crisis-aii-kpi-crithigh" label="Critical / High" value={critHigh} sub="Active, elevated severity" icon={AlertOctagon} accent="0 84% 60%" />
        <MetricCard testid="crisis-aii-kpi-mttr" label="Mean age (active)" value={meanAge == null ? "—" : ageLabel(meanAge)} sub="Time since detection" kind="MODELLED" icon={Clock3} accent="35 90% 55%" />
        <MetricCard testid="crisis-aii-kpi-resolution" label="Resolution rate" value={`${resolutionRate}%`} sub={`${resolved.length}/${incidents.length} resolved`} kind="MODELLED" icon={CheckCircle2} accent="142 70% 45%" />
      </div>

      <div className="grid xl:grid-cols-2 gap-5">
        <Panel testid="crisis-aii-severity" title="Active Incidents by Severity" subtitle="Live severity distribution across open AI incidents.">
          {sevData.length === 0 ? <EmptyState title="No active incidents" text="No open AI incidents are currently reported by the live feed." /> : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sevData} margin={{ left: 0, right: 8, top: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={30} />
                  <Tooltip contentStyle={CHART_TOOLTIP} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                  <Bar dataKey="value" radius={[5, 5, 0, 0]} fill="hsl(0 84% 60%)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel testid="crisis-aii-status" title="Incident Status Funnel" subtitle="Every tracked incident by current lifecycle status.">
          {statusData.length === 0 ? <EmptyState title="No incidents" text="No AI incidents are currently tracked." /> : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusData} margin={{ left: 0, right: 8, top: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={30} />
                  <Tooltip contentStyle={CHART_TOOLTIP} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                  <Bar dataKey="value" radius={[5, 5, 0, 0]} fill="hsl(266 85% 66%)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid xl:grid-cols-[1fr_1.3fr] gap-5">
        <Panel testid="crisis-aii-systems" title="Most-Affected Systems" subtitle="Active incidents grouped by the system under attack.">
          {systems.length === 0 ? <EmptyState title="No affected systems" text="No active incident names an affected system." /> : (
            <div className="space-y-3">
              {systems.map((s) => (
                <div key={s.system} data-testid={`crisis-aii-system-${s.system.replace(/\s+/g, "-").toLowerCase()}`}>
                  <div className="flex items-center justify-between text-xs mb-1"><span className="font-head font-bold truncate">{s.system}</span><span className="font-mono text-muted-foreground">{s.count}</span></div>
                  <ProgressBar value={Math.min(100, s.count * 25)} accent="0 84% 60%" />
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel testid="crisis-aii-top" title="Top Active Incidents" subtitle="Ordered by severity, then time open.">
          {top.length === 0 ? <EmptyState title="No active incidents" text="No open incidents to prioritise." /> : (
            <div className="space-y-2">
              {top.map((i) => (
                <div key={i.ref || i.title} data-testid={`crisis-aii-incident-${i.ref || "x"}`} className="rounded-lg border border-border bg-secondary/20 p-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-mono text-[10px] text-ai">{i.ref || "—"}</div>
                    <div className="font-head font-bold text-sm mt-0.5 truncate">{i.title}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{i.system || "Unknown"} · {ageLabel(hoursSince(i.opened))} open{i.confidence != null ? ` · confidence ${Math.round(toNumber(i.confidence) * 100)}%` : ""}</div>
                  </div>
                  <div className="text-right shrink-0"><StatusPill value={i.severity} /><div className="mt-1"><StatusPill value={i.status} /></div></div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3) Executive Communications Center
// ---------------------------------------------------------------------------
const COMMS_ACTIONS = {
  "crisis.comms.dispatch": { label: "Stakeholder communication", channel: "Stakeholder", Icon: Megaphone },
  "crisis.brief.email": { label: "Board brief emailed", channel: "Email", Icon: Mail },
  "crisis.auto_present": { label: "Auto board present emailed", channel: "Email", Icon: Presentation },
  "crisis.director_digest_now": { label: "Director digest sent", channel: "Email", Icon: Mail },
  "crisis.broadcast": { label: "War room broadcast", channel: "Teams / Slack", Icon: Radio },
  "crisis.sitrep_send_now": { label: "SITREP posted", channel: "Teams / Slack", Icon: Radio },
  "crisis.snapshot.create": { label: "Board snapshot link created", channel: "Snapshot", Icon: Share2 },
  "crisis.snapshot.revoke": { label: "Board snapshot revoked", channel: "Snapshot", Icon: Share2 },
  "crisis.present_board": { label: "Presented to board", channel: "Snapshot + PDF", Icon: Presentation },
};
const COMMS_FALLBACK_RE = /brief|broadcast|snapshot|present|sitrep|digest|notif|email|comms|dispatch/i;
const GROUP_LABEL = { regulator: "Regulator", customer: "Customer", employee: "Employee", board: "Board", media: "Media", partner: "Partner" };

export function ExecutiveCommsCenter({ data = {}, selectedCase, canOperate = false, reload, changed }) {
  const audit = useMemo(() => data.audit || [], [data.audit]);
  const ref = selectedCase?.ref || "";

  const [templates, setTemplates] = useState([]);
  const [coverage, setCoverage] = useState(null);
  const [group, setGroup] = useState("customer");
  const [templateId, setTemplateId] = useState("");
  const [message, setMessage] = useState("");
  const [broadcast, setBroadcast] = useState(false);
  const [busy, setBusy] = useState("");
  const [showManage, setShowManage] = useState(false);
  const [newTpl, setNewTpl] = useState({ group: "customer", label: "", text: "" });

  const events = useMemo(() => {
    return audit
      .filter((a) => COMMS_ACTIONS[a.action] || COMMS_FALLBACK_RE.test(a.action || ""))
      .map((a) => {
        const meta = COMMS_ACTIONS[a.action] || { label: a.action, channel: "Notification", Icon: Megaphone };
        return { ...a, ...meta };
      })
      .slice(0, 120);
  }, [audit]);

  const channelCounts = useMemo(() => {
    const map = {};
    for (const e of events) map[e.channel] = (map[e.channel] || 0) + 1;
    return Object.entries(map).map(([channel, count]) => ({ channel, count })).sort((a, b) => b.count - a.count);
  }, [events]);

  const briefs = events.filter((e) => e.action === "crisis.brief.email" || e.action === "crisis.auto_present").length;
  const sitreps = events.filter((e) => e.action === "crisis.sitrep_send_now").length;
  const broadcasts = events.filter((e) => e.action === "crisis.broadcast").length;
  const snapshots = events.filter((e) => e.action === "crisis.snapshot.create" || e.action === "crisis.present_board").length;

  const loadTemplates = useCallback(async () => {
    if (!canOperate) return;
    try {
      const r = await api.get("/crisis/comms/templates");
      setTemplates(r.data.templates || []);
    } catch { /* honest empty */ }
  }, [canOperate]);

  const loadCoverage = useCallback(async () => {
    if (!canOperate || !ref) { setCoverage(null); return; }
    try {
      const r = await api.get(`/crisis/cases/${ref}/comms/coverage`);
      setCoverage(r.data);
    } catch { setCoverage(null); }
  }, [canOperate, ref]);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);
  useEffect(() => { loadCoverage(); }, [loadCoverage]);

  const pickTemplate = (id) => {
    setTemplateId(id);
    const t = templates.find((x) => x.id === id);
    if (t) { setGroup(t.group); setMessage(t.text); }
  };

  const dispatch = async () => {
    if (!ref) { toast.error("Select a crisis case first."); return; }
    setBusy("dispatch");
    try {
      const label = templates.find((x) => x.id === templateId)?.label || `${GROUP_LABEL[group]} update`;
      const { data: res } = await api.post(`/crisis/cases/${ref}/comms/dispatch`, { group, label, message, broadcast });
      toast.success(`${GROUP_LABEL[group]} notified${res.posted ? " · broadcast to chat" : ""}.`);
      setMessage(""); setTemplateId("");
      await loadCoverage();
      await (changed ? changed(ref) : reload?.());
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to dispatch communication.");
    } finally { setBusy(""); }
  };

  const addTemplate = async () => {
    if (!newTpl.label.trim() || !newTpl.text.trim()) { toast.error("Label and message are required."); return; }
    setBusy("add-tpl");
    try {
      const { data: res } = await api.post("/crisis/comms/templates", { group: newTpl.group, label: newTpl.label, subject: "", text: newTpl.text });
      setTemplates(res.templates || []);
      setNewTpl({ group: "customer", label: "", text: "" });
      toast.success("Template saved.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to save template.");
    } finally { setBusy(""); }
  };

  const deleteTemplate = async (id) => {
    setBusy(`del-${id}`);
    try {
      const { data: res } = await api.delete(`/crisis/comms/templates/${id}`);
      setTemplates(res.templates || []);
      if (templateId === id) { setTemplateId(""); }
      toast.success("Template removed.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to remove template.");
    } finally { setBusy(""); }
  };

  const groupTemplates = templates.filter((t) => t.group === group);

  return (
    <div className="space-y-5" data-testid="crisis-comms-center">
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
        <MetricCard testid="crisis-comms-kpi-total" label="Communications dispatched" value={events.length} sub="Recorded stakeholder comms" icon={Megaphone} />
        <MetricCard testid="crisis-comms-kpi-briefs" label="Board briefs" value={briefs} sub="Emailed to directors" icon={Mail} accent="35 90% 55%" />
        <MetricCard testid="crisis-comms-kpi-sitreps" label="SITREPs posted" value={sitreps} sub="Teams / Slack" icon={Radio} accent="266 85% 66%" />
        <MetricCard testid="crisis-comms-kpi-broadcasts" label="War room broadcasts" value={broadcasts} sub="Teams / Slack" icon={Radio} accent="200 90% 55%" />
        <MetricCard testid="crisis-comms-kpi-snapshots" label="Board snapshots" value={snapshots} sub="Shareable links + present" icon={Share2} accent="142 70% 45%" />
      </div>

      {canOperate && (
        <div className="grid xl:grid-cols-2 gap-5">
          <Panel
            testid="crisis-comms-coverage"
            title="Notification Coverage"
            subtitle={coverage ? `${coverage.stale_count} of ${coverage.groups.length} stakeholder groups need an update (stale after ${coverage.threshold_hours}h).` : "Which stakeholder groups have been kept informed — a board trust signal."}
            actions={<button onClick={loadCoverage} data-testid="crisis-comms-coverage-refresh" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><Clock3 className="w-3.5 h-3.5" />Refresh</button>}
          >
            {!ref ? (
              <EmptyState title="No crisis case selected" text="Select a crisis case to track which stakeholder groups have been updated." />
            ) : !coverage ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading coverage…</div>
            ) : (
              <div className="space-y-2">
                {coverage.groups.map((g) => (
                  <div key={g.group} data-testid={`crisis-comms-coverage-${g.group}`} className={`rounded-lg border p-3 flex items-center justify-between gap-3 ${g.stale ? "border-crit/25 bg-crit/5" : "border-low/25 bg-low/5"}`}>
                    <div className="min-w-0">
                      <div className="font-head font-bold text-sm">{GROUP_LABEL[g.group] || g.group}</div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        {g.last_at ? `Last updated ${ageLabel(g.hours_since)} ago · ${g.count} update(s)` : "Not yet updated in this crisis"}
                      </div>
                    </div>
                    <span data-testid={`crisis-comms-coverage-flag-${g.group}`} className={`text-[9px] font-mono px-2 py-0.5 rounded-full shrink-0 ${g.stale ? "bg-crit/15 text-crit" : "bg-low/15 text-low"}`}>
                      {g.stale ? (g.last_at ? "STALE" : "NOT UPDATED") : "CURRENT"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel
            testid="crisis-comms-dispatch"
            title="One-Tap Stakeholder Dispatch"
            subtitle="Pick a template, choose the audience and send. Every dispatch is logged and feeds the coverage scorecard."
            actions={<button onClick={() => setShowManage((v) => !v)} data-testid="crisis-comms-manage-toggle" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><ClipboardList className="w-3.5 h-3.5" />Templates</button>}
          >
            {!ref ? (
              <EmptyState title="No crisis case selected" text="Select a crisis case before dispatching stakeholder communications." />
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[9px] font-mono uppercase text-muted-foreground">Audience</label>
                    <select value={group} onChange={(e) => { setGroup(e.target.value); setTemplateId(""); }} data-testid="crisis-comms-group" className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2 text-sm">
                      {Object.keys(GROUP_LABEL).map((g) => <option key={g} value={g}>{GROUP_LABEL[g]}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-[9px] font-mono uppercase text-muted-foreground">Template</label>
                    <select value={templateId} onChange={(e) => pickTemplate(e.target.value)} data-testid="crisis-comms-template" className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2 text-sm">
                      <option value="">— Choose a template —</option>
                      {groupTemplates.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                    </select>
                  </div>
                </div>
                <textarea rows={5} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Message to this stakeholder group…" data-testid="crisis-comms-message" className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <label className="inline-flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                    <input type="checkbox" checked={broadcast} onChange={(e) => setBroadcast(e.target.checked)} data-testid="crisis-comms-broadcast" className="accent-primary" />
                    Also broadcast to war-room chat (Teams / Slack)
                  </label>
                  <button onClick={dispatch} disabled={busy === "dispatch"} data-testid="crisis-comms-dispatch-btn" className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">
                    {busy === "dispatch" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}Dispatch
                  </button>
                </div>

                {showManage && (
                  <div className="rounded-lg border border-border bg-secondary/15 p-3 space-y-2" data-testid="crisis-comms-manage">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Reusable templates</div>
                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                      {templates.map((t) => (
                        <div key={t.id} data-testid={`crisis-comms-tpl-${t.id}`} className="flex items-center justify-between gap-2 rounded-md border border-border bg-card px-2.5 py-1.5">
                          <div className="min-w-0"><span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-secondary/70 text-muted-foreground uppercase mr-2">{t.group}</span><span className="text-xs font-head font-bold">{t.label}</span></div>
                          <button onClick={() => deleteTemplate(t.id)} disabled={busy === `del-${t.id}`} data-testid={`crisis-comms-tpl-del-${t.id}`} className="text-muted-foreground hover:text-crit shrink-0"><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-[1fr_1.4fr] gap-2 pt-1">
                      <select value={newTpl.group} onChange={(e) => setNewTpl({ ...newTpl, group: e.target.value })} data-testid="crisis-comms-newtpl-group" className="bg-secondary/60 rounded-md px-2 py-2 text-xs">{Object.keys(GROUP_LABEL).map((g) => <option key={g} value={g}>{GROUP_LABEL[g]}</option>)}</select>
                      <input value={newTpl.label} onChange={(e) => setNewTpl({ ...newTpl, label: e.target.value })} placeholder="Template label" data-testid="crisis-comms-newtpl-label" className="bg-secondary/60 rounded-md px-2 py-2 text-xs" />
                    </div>
                    <textarea rows={2} value={newTpl.text} onChange={(e) => setNewTpl({ ...newTpl, text: e.target.value })} placeholder="Template message…" data-testid="crisis-comms-newtpl-text" className="w-full bg-secondary/60 rounded-md px-2 py-2 text-xs" />
                    <button onClick={addTemplate} disabled={busy === "add-tpl"} data-testid="crisis-comms-newtpl-save" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{busy === "add-tpl" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}Save template</button>
                  </div>
                )}
              </div>
            )}
          </Panel>
        </div>
      )}

      <div className="grid xl:grid-cols-[1.5fr_1fr] gap-5">
        <Panel testid="crisis-comms-log" title="Communication Log" subtitle="Every stakeholder dispatch, board brief, SITREP, broadcast, digest and snapshot recorded in the audit stream.">
          {events.length === 0 ? (
            <EmptyState title="No communications yet" text="Stakeholder dispatches, board briefs, SITREPs, war-room broadcasts, director digests and board snapshots will appear here once sent." />
          ) : (
            <div className="space-y-2">
              {events.map((e, idx) => (
                <div key={`${e.ts}-${idx}`} data-testid={`crisis-comms-event-${idx}`} className="rounded-lg border border-border bg-secondary/20 p-3 flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5 min-w-0">
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-primary/10 text-primary shrink-0"><e.Icon className="w-3.5 h-3.5" /></span>
                    <div className="min-w-0">
                      <div className="font-head font-bold text-sm">{e.label}</div>
                      <div className="text-[10px] text-muted-foreground mt-0.5 truncate">{e.detail || "—"}</div>
                      <div className="text-[10px] font-mono text-muted-foreground mt-0.5">{e.actor || "system"} · {e.ts ? new Date(e.ts).toLocaleString() : "—"}</div>
                    </div>
                  </div>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-secondary/70 text-muted-foreground shrink-0">{e.channel}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel testid="crisis-comms-channels" title="Dispatch by Channel" subtitle="How stakeholders are being reached.">
          {channelCounts.length === 0 ? (
            <EmptyState title="No channels used" text="No communication channels have been used yet." />
          ) : (
            <div className="space-y-3">
              {channelCounts.map((c) => (
                <div key={c.channel} data-testid={`crisis-comms-channel-${c.channel.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`}>
                  <div className="flex items-center justify-between text-xs mb-1"><span className="font-head font-bold">{c.channel}</span><span className="font-mono text-muted-foreground">{c.count}</span></div>
                  <ProgressBar value={Math.min(100, (c.count / Math.max(1, events.length)) * 100)} accent="266 85% 66%" />
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4) Resilience Intelligence
// ---------------------------------------------------------------------------
function rtoStatus(item, elapsedMin) {
  if (item.status === "Operational") return { label: "Met", tone: "low" };
  const rto = item.rto_minutes;
  if (rto == null) return { label: "No target", tone: "muted" };
  if (elapsedMin == null) return { label: `Target ${fmtMins(rto)}`, tone: "muted" };
  if (elapsedMin > rto) return { label: `Breached +${fmtMins(Math.round(elapsedMin - rto))}`, tone: "crit" };
  if (elapsedMin > rto * 0.75) return { label: `At risk · ${fmtMins(Math.round(rto - elapsedMin))} left`, tone: "high" };
  return { label: `On track · ${fmtMins(Math.round(rto - elapsedMin))} left`, tone: "low" };
}

const TONE = { crit: "bg-crit/15 text-crit", high: "bg-high/15 text-high", low: "bg-low/15 text-low", muted: "bg-secondary/70 text-muted-foreground" };

function RtoRow({ item, caseRef, elapsedMin, onSaved }) {
  const [rto, setRto] = useState(item.rto_minutes ?? "");
  const [rpo, setRpo] = useState(item.rpo_minutes ?? "");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (rto === "" && rpo === "") { toast.error("Enter an RTO or RPO target (minutes)."); return; }
    setBusy(true);
    try {
      const body = {};
      if (rto !== "") body.rto_minutes = Number(rto);
      if (rpo !== "") body.rpo_minutes = Number(rpo);
      await api.patch(`/crisis/cases/${caseRef}/recovery/${item.recovery_id}`, body);
      toast.success(`Objectives saved for ${item.name}.`);
      await onSaved?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to save objectives.");
    } finally { setBusy(false); }
  };

  const st = rtoStatus(item, elapsedMin);
  return (
    <div data-testid={`crisis-rto-row-${item.recovery_id}`} className="rounded-lg border border-border bg-secondary/20 p-3 grid xl:grid-cols-[1.3fr_auto_auto_auto_auto] gap-3 items-center">
      <div className="min-w-0"><div className="font-head font-bold text-sm truncate">{item.name}</div><div className="text-[10px] text-muted-foreground mt-0.5">{item.category} · <StatusPill value={item.status} /></div></div>
      <div>
        <label className="text-[9px] font-mono uppercase text-muted-foreground">RTO (min)</label>
        <input type="number" min="0" value={rto} onChange={(e) => setRto(e.target.value)} data-testid={`crisis-rto-input-${item.recovery_id}`} className="mt-1 w-24 bg-secondary/60 rounded-md px-2 py-1.5 text-xs" />
      </div>
      <div>
        <label className="text-[9px] font-mono uppercase text-muted-foreground">RPO (min)</label>
        <input type="number" min="0" value={rpo} onChange={(e) => setRpo(e.target.value)} data-testid={`crisis-rpo-input-${item.recovery_id}`} className="mt-1 w-24 bg-secondary/60 rounded-md px-2 py-1.5 text-xs" />
      </div>
      <div className="text-center">
        <label className="text-[9px] font-mono uppercase text-muted-foreground block">RTO status</label>
        <span data-testid={`crisis-rto-status-${item.recovery_id}`} className={`inline-flex mt-1 text-[9px] font-mono px-2 py-0.5 rounded-full ${TONE[st.tone]}`}>{st.label}</span>
      </div>
      <button onClick={save} disabled={busy} data-testid={`crisis-rto-save-${item.recovery_id}`} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50 self-end">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}Save</button>
    </div>
  );
}

export function ResilienceIntelligence({ data = {}, caseDetail, selectedCase, changed }) {
  const recovery = caseDetail?.recovery || [];
  const overall = recoveryOverall(recovery);
  const byCat = recoveryByCategory(recovery);

  const controls = data.controls || [];
  const cf = controlFailureSummary(controls);
  const passing = controls.filter((c) => c.status === "Passing").length;
  const controlHealth = controls.length ? Math.round((passing / controls.length) * 100) : 0;

  const workflows = data.workflows || [];
  const activeWorkflows = workflows.filter((w) => {
    const s = String(w.status || w.state || "").toLowerCase();
    return s.includes("active") || s.includes("enabled") || s.includes("running") || Boolean(w.enabled) || Boolean(w.automated);
  }).length;
  const workflowReadiness = workflows.length ? Math.round((activeWorkflows / workflows.length) * 100) : 0;

  const openActions = actionSummary(caseDetail?.actions || []).open;
  const resilienceScore = Math.round(overall * 0.4 + controlHealth * 0.35 + workflowReadiness * 0.25 - Math.min(20, openActions * 3));
  const score = Math.max(0, Math.min(100, resilienceScore));

  const caseStart = selectedCase?.started_at || selectedCase?.created_at || null;
  const elapsedMin = caseStart ? Math.max(0, (Date.now() - new Date(caseStart).getTime()) / 60000) : null;
  const withTargets = recovery.filter((r) => r.rto_minutes != null);
  const breaches = recovery.filter((r) => r.status !== "Operational" && r.rto_minutes != null && elapsedMin != null && elapsedMin > r.rto_minutes).length;

  const reloadCase = () => (changed && selectedCase ? changed(selectedCase.ref) : undefined);

  return (
    <div className="space-y-5" data-testid="crisis-resilience-intelligence">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard testid="crisis-resilience-kpi-score" label="Resilience score" value={`${score}/100`} sub="Recovery, control health & automation" kind="MODELLED" icon={Activity} accent="142 70% 45%" />
        <MetricCard testid="crisis-resilience-kpi-recovery" label="Recovery readiness" value={`${overall}%`} sub={`${recovery.filter((i) => i.status === "Operational").length}/${recovery.length} operational`} kind="MODELLED" icon={HeartPulse} accent="35 90% 55%" />
        <MetricCard testid="crisis-resilience-kpi-controls" label="Control resilience" value={`${controlHealth}%`} sub={`${cf.failing} failing · ${cf.drifting} drifting`} icon={ShieldCheck} accent="266 85% 66%" />
        <MetricCard testid="crisis-resilience-kpi-rto" label="RTO breaches" value={breaches} sub={`${withTargets.length} item(s) carry a time objective`} kind="MODELLED" icon={Timer} accent="0 84% 60%" />
      </div>

      <Panel testid="crisis-resilience-rto" title="Recovery Time Objectives (RTO / RPO)" subtitle={caseStart ? `Elapsed since crisis start: ${fmtMins(Math.round(elapsedMin))}. RTO status compares elapsed time to each item's target — no times are invented.` : "Set a recovery-time (RTO) and recovery-point (RPO) objective per item to track readiness against real targets."}>
        {recovery.length === 0 ? (
          <EmptyState title="No recovery items tracked" text="Add recovery items under the Recovery tab, then set an RTO/RPO target for each here." />
        ) : (
          <div className="space-y-2">
            {recovery.map((item) => (
              <RtoRow key={item.recovery_id} item={item} caseRef={selectedCase?.ref} elapsedMin={elapsedMin} onSaved={reloadCase} />
            ))}
          </div>
        )}
      </Panel>

      <Panel testid="crisis-resilience-recovery" title="Recovery Readiness by Category" subtitle="Restoration posture across systems, applications and business services. Derived from the live crisis recovery record.">
        {byCat.length === 0 ? (
          <EmptyState title="No recovery items tracked" text="Add recovery items under Recovery to model restoration readiness and resilience by category." />
        ) : (
          <div className="space-y-3">
            {byCat.map((c) => (
              <div key={c.category} data-testid={`crisis-resilience-cat-${c.category.replace(/\s+/g, "-").toLowerCase()}`}>
                <div className="flex items-center justify-between text-xs mb-1"><span className="font-head font-bold">{c.category}</span><span className="font-mono text-muted-foreground">{c.pct}% · {c.operational}/{c.items} operational</span></div>
                <ProgressBar value={c.pct} accent={c.pct >= 80 ? "142 70% 45%" : c.pct >= 40 ? "35 90% 55%" : "0 84% 60%"} />
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid xl:grid-cols-2 gap-5">
        <Panel testid="crisis-resilience-controls" title="Control Resilience Posture" subtitle="Preventive and detective control health under crisis conditions.">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-low/5 border border-low/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Passing</div><div className="font-head font-black text-2xl mt-1 text-low">{passing}</div></div>
            <div className="rounded-lg bg-crit/5 border border-crit/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Failing</div><div className="font-head font-black text-2xl mt-1 text-crit">{cf.failing}</div></div>
            <div className="rounded-lg bg-high/5 border border-high/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Drifting</div><div className="font-head font-black text-2xl mt-1 text-high">{cf.drifting}</div></div>
            <div className="rounded-lg bg-med/5 border border-med/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Evidence stale</div><div className="font-head font-black text-2xl mt-1 text-med">{cf.stale}</div></div>
          </div>
          <div className="mt-4"><div className="flex items-center justify-between text-xs mb-1"><span className="font-head font-bold">Overall control health</span><span className="font-mono text-muted-foreground">{controlHealth}%</span></div><ProgressBar value={controlHealth} accent={controlHealth >= 80 ? "142 70% 45%" : controlHealth >= 50 ? "35 90% 55%" : "0 84% 60%"} /></div>
        </Panel>

        <Panel testid="crisis-resilience-workflows" title="Response Workflow Readiness" subtitle="Automated response and remediation workflows available to crisis leadership.">
          {workflows.length === 0 ? (
            <EmptyState title="No response workflows" text="No workflow engine data is currently available to assess automated response readiness." />
          ) : (
            <div className="space-y-2">
              {workflows.slice(0, 10).map((w, idx) => {
                const s = String(w.status || w.state || "").toLowerCase();
                const on = s.includes("active") || s.includes("enabled") || s.includes("running") || Boolean(w.enabled) || Boolean(w.automated);
                return (
                  <div key={w.ref || w.id || idx} data-testid={`crisis-resilience-workflow-${idx}`} className="rounded-lg border border-border bg-secondary/20 p-3 flex items-center justify-between gap-3">
                    <div className="min-w-0"><div className="font-head font-bold text-sm truncate">{w.name || w.title || w.ref || `Workflow ${idx + 1}`}</div>{w.trigger && <div className="text-[10px] text-muted-foreground mt-0.5 truncate">{w.trigger}</div>}</div>
                    <StatusPill value={on ? "Active" : (w.status || w.state || "Idle")} />
                  </div>
                );
              })}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 5) Post-Incident Review
// ---------------------------------------------------------------------------
export function PostIncidentReview({ data = {}, selectedCase, caseDetail, generatePIR, pirBusy }) {
  const blocks = useMemo(() => {
    if (!selectedCase) return [];
    try {
      return pirBlocks({ data, selectedCase, caseDetail });
    } catch {
      return [];
    }
  }, [data, selectedCase, caseDetail]);

  if (!selectedCase) {
    return (
      <div data-testid="crisis-pir-dashboard">
        <Panel title="Post-Incident Review" subtitle="Lessons learned, decisions, response and control outcomes for a resolved crisis.">
          <EmptyState title="No crisis case selected" text="Select or close a crisis case to compile its post-incident review." />
        </Panel>
      </div>
    );
  }

  const isClosed = selectedCase.status === "Closed";

  return (
    <div className="space-y-5" data-testid="crisis-pir-dashboard">
      {!isClosed && (
        <div className="rounded-xl border border-med/30 bg-med/5 p-4 flex items-start gap-3" data-testid="crisis-pir-open-note">
          <ClipboardList className="w-5 h-5 text-med shrink-0 mt-0.5" />
          <div className="text-xs text-muted-foreground"><span className="font-head font-bold text-foreground">Preview.</span> {selectedCase.ref} is still <span className="font-mono">{selectedCase.status}</span>. This review is compiled from the live record so far; close the case for the final post-incident review.</div>
        </div>
      )}

      <Panel
        testid="crisis-pir-panel"
        title={`Post-Incident Review — ${selectedCase.ref}`}
        subtitle="Compiled from the persistent, audit-logged crisis record. Timeline, decisions, actions, controls and recovery are source facts."
        actions={
          <button
            onClick={generatePIR}
            disabled={pirBusy}
            data-testid="crisis-pir-download"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
          >
            {pirBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            Download PDF
          </button>
        }
      >
        <div className="space-y-5">
          {blocks.map((block, bi) => (
            <div key={bi} data-testid={`crisis-pir-block-${bi}`} className="rounded-xl border border-border bg-secondary/15 p-4">
              <div className="font-head font-black text-sm tracking-tight">{block.heading}</div>
              <ul className="mt-2 space-y-1.5">
                {block.lines.map((line, li) => (
                  <li key={li} className="text-xs text-muted-foreground leading-relaxed flex items-start gap-2">
                    <span className="mt-1.5 w-1 h-1 rounded-full bg-primary/60 shrink-0" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
