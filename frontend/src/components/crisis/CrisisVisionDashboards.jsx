import { useMemo } from "react";
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
  Gauge,
  Clock3,
  CheckCircle2,
  Users,
  Download,
  Loader2,
  ClipboardList,
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
import {
  money,
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
    lower.includes("critical") || lower.includes("failing") || lower.includes("failed") || lower.includes("down") || lower.includes("high")
      ? "bg-crit/10 text-crit border-crit/25"
      : lower.includes("drift") || lower.includes("investigating") || lower.includes("medium") || lower.includes("restoring")
      ? "bg-high/10 text-high border-high/25"
      : lower.includes("stale") || lower.includes("monitor") || lower.includes("validated")
      ? "bg-med/10 text-med border-med/25"
      : lower.includes("passing") || lower.includes("resolved") || lower.includes("contained") || lower.includes("operational") || lower.includes("closed") || lower.includes("low")
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
const SEV_COLOR = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 60% 45%", Info: "210 12% 60%" };

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
      map[key] = map[key] || { system: key, count: 0, worst: 0 };
      map[key].count += 1;
      map[key].worst = Math.max(map[key].worst, SEV_ORDER.length - SEV_ORDER.indexOf(i.severity || "Info"));
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
  "crisis.brief.email": { label: "Board brief emailed", channel: "Email", Icon: Mail },
  "crisis.auto_present": { label: "Auto board present emailed", channel: "Email", Icon: Presentation },
  "crisis.director_digest_now": { label: "Director digest sent", channel: "Email", Icon: Mail },
  "crisis.broadcast": { label: "War room broadcast", channel: "Teams / Slack", Icon: Radio },
  "crisis.sitrep_send_now": { label: "SITREP posted", channel: "Teams / Slack", Icon: Radio },
  "crisis.snapshot.create": { label: "Board snapshot link created", channel: "Snapshot", Icon: Share2 },
  "crisis.snapshot.revoke": { label: "Board snapshot revoked", channel: "Snapshot", Icon: Share2 },
  "crisis.present_board": { label: "Presented to board", channel: "Snapshot + PDF", Icon: Presentation },
};
const COMMS_FALLBACK_RE = /brief|broadcast|snapshot|present|sitrep|digest|notif|email/i;

export function ExecutiveCommsCenter({ data = {}, selectedCase }) {
  const audit = useMemo(() => data.audit || [], [data.audit]);
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

  return (
    <div className="space-y-5" data-testid="crisis-comms-center">
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
        <MetricCard testid="crisis-comms-kpi-total" label="Communications dispatched" value={events.length} sub="Recorded stakeholder comms" icon={Megaphone} />
        <MetricCard testid="crisis-comms-kpi-briefs" label="Board briefs" value={briefs} sub="Emailed to directors" icon={Mail} accent="35 90% 55%" />
        <MetricCard testid="crisis-comms-kpi-sitreps" label="SITREPs posted" value={sitreps} sub="Teams / Slack" icon={Radio} accent="266 85% 66%" />
        <MetricCard testid="crisis-comms-kpi-broadcasts" label="War room broadcasts" value={broadcasts} sub="Teams / Slack" icon={Radio} accent="200 90% 55%" />
        <MetricCard testid="crisis-comms-kpi-snapshots" label="Board snapshots" value={snapshots} sub="Shareable links + present" icon={Share2} accent="142 70% 45%" />
      </div>

      <div className="grid xl:grid-cols-[1.5fr_1fr] gap-5">
        <Panel testid="crisis-comms-log" title="Communication Log" subtitle="Every board brief, SITREP, broadcast, digest and snapshot recorded in the audit stream.">
          {events.length === 0 ? (
            <EmptyState title="No communications yet" text="Board briefs, SITREPs, war-room broadcasts, director digests and board snapshots will appear here once dispatched from the crisis workspace." />
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
              <div className="rounded-lg border border-border bg-secondary/10 p-3 text-[11px] text-muted-foreground">
                {selectedCase ? `Comms for ${selectedCase.ref} and the wider crisis audit stream are consolidated here.` : "Select a crisis case to focus dispatch tracking on a single incident."}
              </div>
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
export function ResilienceIntelligence({ data = {}, caseDetail }) {
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
  const resilienceScore = Math.round(
    overall * 0.4 + controlHealth * 0.35 + workflowReadiness * 0.25 - Math.min(20, openActions * 3)
  );
  const score = Math.max(0, Math.min(100, resilienceScore));

  return (
    <div className="space-y-5" data-testid="crisis-resilience-intelligence">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard testid="crisis-resilience-kpi-score" label="Resilience score" value={`${score}/100`} sub="Recovery, control health & automation" kind="MODELLED" icon={Activity} accent="142 70% 45%" />
        <MetricCard testid="crisis-resilience-kpi-recovery" label="Recovery readiness" value={`${overall}%`} sub={`${recovery.filter((i) => i.status === "Operational").length}/${recovery.length} operational`} kind="MODELLED" icon={HeartPulse} accent="35 90% 55%" />
        <MetricCard testid="crisis-resilience-kpi-controls" label="Control resilience" value={`${controlHealth}%`} sub={`${cf.failing} failing · ${cf.drifting} drifting`} icon={ShieldCheck} accent="266 85% 66%" />
        <MetricCard testid="crisis-resilience-kpi-workflows" label="Automation readiness" value={workflows.length ? `${workflowReadiness}%` : "—"} sub={`${activeWorkflows}/${workflows.length} response workflows active`} icon={Workflow} accent="200 90% 55%" />
      </div>

      <Panel testid="crisis-resilience-recovery" title="Recovery Readiness by Category" subtitle="Restoration posture across systems, applications and business services. Derived from the live crisis recovery record — no recovery-time targets are invented.">
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
