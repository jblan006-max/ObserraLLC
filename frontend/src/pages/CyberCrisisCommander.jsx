import { useEffect, useMemo, useState, useRef, useCallback } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  Banknote,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  Gauge,
  Gavel,
  GitCommitVertical,
  Landmark,
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Wrench,
  Users,
  LifeBuoy,
  Scale,
  HeartPulse,
  Trash2,
  Play,
  Square,
  Timer,
  ClipboardList,
  UserPlus,
  Mail,
  CloudDownload,
  Send,
  Bell,
  ShieldOff,
  Share2,
  Copy,
  Pause,
  SkipForward,
  Rss,
  Link2,
  MoreVertical,
} from "lucide-react";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AIInsight } from "@/components/AIInsight";
import { AIExplain } from "@/components/AIExplain";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  actionSummary,
  activeIncidents,
  affectedRiskCount,
  controlFailureSummary,
  crisisScore,
  executiveBriefBlocks,
  mergeTimeline,
  money,
  portfolioExposure,
  recoveryByCategory,
  recoveryOverall,
  obligationCountdown,
  pirBlocks,
} from "@/lib/crisisCommanderModels";
import {
  fetchCrisisCase,
  useCrisisCommanderData,
} from "@/hooks/useCrisisCommanderData";
import { APP_VERSION_LABEL } from "@/version";
import { CrisisTour } from "@/components/crisis/CrisisTour";
import { NativeConnectors, WarRoomBroadcast, BoardCrisisDashboard, PresentToBoard } from "@/components/crisis/CrisisExtensions";

const TABS = [
  ["mission", "Mission Control", Gauge],
  ["command", "Incident Command", Siren],
  ["decisions", "Decision Room", Gavel],
  ["impact", "Business Impact", Banknote],
  ["response", "Containment & Recovery", Wrench],
  ["warroom", "War Room", Users],
  ["recovery", "Recovery", HeartPulse],
  ["regulatory", "Regulatory & Legal", Scale],
  ["controls", "Control Failures", ShieldAlert],
  ["timeline", "Timeline & Evidence", GitCommitVertical],
  ["briefing", "Executive Briefing", FileText],
  ["board", "Board View", Landmark],
  ["defensibility", "Defensibility", ShieldCheck],
];

const CLASS_STYLE = {
  FACT: "bg-low/10 text-low border-low/25",
  MODELLED: "bg-med/10 text-med border-med/25",
  "AI RECOMMENDATION": "bg-ai/10 text-ai border-ai/25",
};

function DataClassBadge({ kind = "FACT" }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[9px] font-mono font-bold uppercase tracking-wider ${
        CLASS_STYLE[kind] || CLASS_STYLE.FACT
      }`}
    >
      {kind}
    </span>
  );
}

function StatusPill({ value }) {
  const text = String(value || "Unknown");
  const lower = text.toLowerCase();
  const style =
    lower.includes("critical") || lower.includes("failed") || lower.includes("blocked")
      ? "bg-crit/10 text-crit border-crit/25"
      : lower.includes("high") || lower.includes("awaiting") || lower.includes("executing")
      ? "bg-high/10 text-high border-high/25"
      : lower.includes("medium") || lower.includes("recovering") || lower.includes("monitor")
      ? "bg-med/10 text-med border-med/25"
      : lower.includes("verified") || lower.includes("complete") || lower.includes("contained") || lower.includes("closed")
      ? "bg-low/10 text-low border-low/25"
      : "bg-secondary text-muted-foreground border-border";

  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full border text-[10px] font-mono font-bold ${style}`} data-testid="crisis-status-pill">
      {text}
    </span>
  );
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

function MetricCard({ label, value, sub, kind = "FACT", icon: Icon, accent = "0 84% 60%", onClick, testid }) {
  const Component = onClick ? "button" : "div";
  return (
    <Component
      type={onClick ? "button" : undefined}
      onClick={onClick}
      data-testid={testid}
      className={`w-full text-left bg-card fact-border rounded-xl p-4 ${onClick ? "hover:bg-secondary/30 transition-colors" : ""}`}
      style={{ borderLeft: `3px solid hsl(${accent})` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          {Icon && <Icon className="w-3.5 h-3.5" />}
          {label}
        </div>
        <DataClassBadge kind={kind} />
      </div>
      <div className="font-head font-black text-2xl lg:text-3xl mt-2 break-words">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </Component>
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

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function MissionControl({ data, selectedCase, caseDetail, openTab }) {
  const response = actionSummary(caseDetail?.actions || []);
  const incidents = activeIncidents(data.incidents || []);
  const controls = controlFailureSummary(data.controls || []);
  const exposure = portfolioExposure(data.risks || [], data.strategic || {});
  const risks = (data.risks || [])
    .filter((risk) => Number(risk.residual || 0) >= 10)
    .sort((a, b) => Number(b.residual_ale || 0) - Number(a.residual_ale || 0))
    .slice(0, 6);
  const chart = [
    { name: "Open", value: response.open },
    { name: "Awaiting", value: response.awaitingApproval },
    { name: "Executing", value: response.executing },
    { name: "Verified", value: response.verified },
  ];

  return (
    <div className="space-y-5" data-testid="crisis-mission-control">
      <div className="grid grid-cols-2 xl:grid-cols-6 gap-4">
        <MetricCard testid="crisis-kpi-severity" label="Crisis severity" value={selectedCase?.severity || data.severity || "None"} sub={selectedCase ? `${selectedCase.ref} · ${selectedCase.phase}` : "No crisis case selected"} icon={Siren} onClick={() => openTab("command")} />
        <MetricCard testid="crisis-kpi-score" label="Crisis score" value={`${data.crisisScore || 0}/100`} sub="Incident, risk, control and response posture" kind="MODELLED" icon={ShieldAlert} accent="15 80% 55%" />
        <MetricCard testid="crisis-kpi-incidents" label="Active incidents" value={incidents.length} sub={`${affectedRiskCount(data.risks || [])} high residual risks`} icon={AlertOctagon} />
        <MetricCard testid="crisis-kpi-exposure" label="Financial exposure" value={money(exposure)} sub="Current residual cyber ALE" icon={Banknote} accent="35 90% 55%" onClick={() => openTab("impact")} />
        <MetricCard testid="crisis-kpi-decisions" label="Decisions pending" value={response.awaitingApproval} sub={`${response.open} response actions open`} icon={Clock3} accent="266 85% 66%" onClick={() => openTab("decisions")} />
        <MetricCard testid="crisis-kpi-progress" label="Response progress" value={`${response.progress}%`} sub={`${response.verified}/${response.total} verified or complete`} kind="MODELLED" icon={CheckCircle2} accent="142 70% 45%" onClick={() => openTab("response")} />
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <Panel testid="crisis-active-command" title="Mission Control — Active Crisis Command" subtitle="Persistent crisis leadership and phase state.">
          {selectedCase ? (
            <div>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-mono text-[10px] text-ai">{selectedCase.ref}</div>
                  <div className="font-head font-black text-xl mt-1">{selectedCase.title}</div>
                </div>
                <StatusPill value={selectedCase.status} />
              </div>
              <p className="text-xs text-muted-foreground mt-3 leading-relaxed">{selectedCase.summary || "No command summary entered."}</p>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="rounded-lg bg-secondary/30 p-3">
                  <div className="text-[9px] font-mono uppercase text-muted-foreground">Incident Commander</div>
                  <div className="text-sm font-medium mt-1">{selectedCase.incident_commander || "Unassigned"}</div>
                </div>
                <div className="rounded-lg bg-secondary/30 p-3">
                  <div className="text-[9px] font-mono uppercase text-muted-foreground">Executive Sponsor</div>
                  <div className="text-sm font-medium mt-1">{selectedCase.executive_sponsor || "Unassigned"}</div>
                </div>
              </div>
              <button onClick={() => openTab("command")} data-testid="crisis-enter-command" className="mt-4 w-full px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-head font-bold">Enter Incident Command</button>
            </div>
          ) : (
            <EmptyState title="No active crisis case" text="Open Incident Command to create or select a persistent crisis case." />
          )}
        </Panel>

        <Panel testid="crisis-response-status" title="Response Action Status" subtitle="Persistent response, recovery, legal, communication and decision actions.">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart} margin={{ left: 0, right: 8, top: 10 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={30} />
                <Tooltip contentStyle={{ background: "#0A0E17", border: "1px solid rgba(255,255,255,.12)", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="value" fill="hsl(0 84% 60%)" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ProgressBar value={response.progress} />
        </Panel>

        <Panel testid="crisis-control-failure" title="Control Failure Intelligence" subtitle="Current control failures, drift and stale evidence.">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-crit/5 border border-crit/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Failing</div><div className="font-head font-black text-2xl mt-1 text-crit">{controls.failing}</div></div>
            <div className="rounded-lg bg-high/5 border border-high/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Drifting</div><div className="font-head font-black text-2xl mt-1 text-high">{controls.drifting}</div></div>
            <div className="rounded-lg bg-med/5 border border-med/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Evidence stale</div><div className="font-head font-black text-2xl mt-1 text-med">{controls.stale}</div></div>
            <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Unique attention</div><div className="font-head font-black text-2xl mt-1">{controls.totalAttention}</div></div>
          </div>
          <button onClick={() => openTab("controls")} data-testid="crisis-review-controls" className="mt-4 w-full px-3 py-2 rounded-md border border-border bg-secondary text-xs font-head font-bold">Review Control Failures</button>
        </Panel>
      </div>

      <Panel testid="crisis-top-risks" title="Highest Residual Enterprise Risks" subtitle="Current risk records that may amplify crisis impact.">
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {risks.map((risk) => (
            <button key={risk.ref} onClick={() => openTab("impact")} className="text-left rounded-xl border border-border bg-secondary/20 p-4 hover:bg-secondary/40">
              <div className="font-mono text-[10px] text-ai">{risk.ref}</div>
              <div className="font-head font-bold mt-1">{risk.title}</div>
              <div className="flex items-center justify-between gap-3 mt-3">
                <StatusPill value={risk.rating || `Residual ${risk.residual}`} />
                <span className="font-mono text-xs">{money(risk.residual_ale)}</span>
              </div>
            </button>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function WebhookFeed() {
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState("");
  const [reveal, setReveal] = useState(false);
  const base = process.env.REACT_APP_BACKEND_URL || "";
  const load = async () => {
    setBusy("load");
    try { const { data } = await api.get("/crisis/webhook/config"); setCfg(data); }
    catch (e) { toast.error(e.response?.data?.detail || "Unable to load webhook config."); }
    finally { setBusy(""); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const rotate = async () => {
    if (!window.confirm("Rotate the webhook secret? Tools using the old secret will stop posting until updated.")) return;
    setBusy("rotate");
    try { const { data } = await api.post("/crisis/webhook/rotate"); setCfg((c) => ({ ...c, secret: data.secret })); setReveal(true); toast.success("Webhook secret rotated."); }
    catch (e) { toast.error(e.response?.data?.detail || "Rotate failed."); }
    finally { setBusy(""); }
  };
  const url = `${base}${cfg?.path || "/api/crisis/ingest/webhook"}`;
  const copy = (text, label) => { navigator.clipboard?.writeText(text); toast.success(`${label} copied.`); };
  const [fmt, setFmt] = useState("crowdstrike");
  const [sample, setSample] = useState('{\n  "detection_name": "Ransomware Behavior Detected",\n  "SeverityName": "Critical",\n  "description": "Encryptor loader on host-42"\n}');
  const [mapped, setMapped] = useState(null);
  const [mapBusy, setMapBusy] = useState(false);
  const preview = async () => {
    setMapBusy(true); setMapped(null);
    try {
      const payload = JSON.parse(sample);
      const { data } = await api.post("/crisis/webhook/test-map", { format: fmt, payload });
      setMapped(data.mapped);
    } catch (e) {
      if (e instanceof SyntaxError) toast.error("Sample payload is not valid JSON.");
      else toast.error(e.response?.data?.detail || "Mapping preview failed.");
    } finally { setMapBusy(false); }
  };
  return (
    <Panel testid="crisis-webhook-feed" title="Live Incident Feed — inbound webhook" subtitle="Point any SIEM / EDR / SOAR / ServiceNow at this endpoint to stream incidents and containment steps straight onto the crisis timeline in real time." actions={<button onClick={load} disabled={busy === "load"} data-testid="crisis-webhook-refresh" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{busy === "load" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh</button>}>
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="bg-secondary/40 border border-border rounded-lg p-3">
            <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground mb-1">POST endpoint</div>
            <div className="flex items-center gap-2"><code data-testid="crisis-webhook-url" className="text-xs font-mono break-all flex-1">{url}</code><button onClick={() => copy(url, "URL")} data-testid="crisis-webhook-copy-url" className="shrink-0 p-1.5 rounded-md border border-border hover:bg-secondary"><Copy className="w-3.5 h-3.5" /></button></div>
          </div>
          <div className="bg-secondary/40 border border-border rounded-lg p-3">
            <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Secret (JSON field "secret")</div>
            <div className="flex items-center gap-2"><code data-testid="crisis-webhook-secret" className="text-xs font-mono break-all flex-1">{cfg?.secret ? (reveal ? cfg.secret : "•".repeat(18)) : "—"}</code><button onClick={() => setReveal((v) => !v)} className="shrink-0 px-2 py-1.5 rounded-md border border-border hover:bg-secondary text-[10px] font-mono">{reveal ? "Hide" : "Show"}</button><button onClick={() => copy(cfg?.secret || "", "Secret")} data-testid="crisis-webhook-copy-secret" className="shrink-0 p-1.5 rounded-md border border-border hover:bg-secondary"><Copy className="w-3.5 h-3.5" /></button><button onClick={rotate} disabled={busy === "rotate"} data-testid="crisis-webhook-rotate" className="shrink-0 px-2 py-1.5 rounded-md border border-crit/40 bg-crit/10 text-crit text-[10px] font-mono disabled:opacity-50">{busy === "rotate" ? <Loader2 className="w-3 h-3 animate-spin" /> : "Rotate"}</button></div>
          </div>
        </div>
        <div className="text-[11px] text-muted-foreground font-mono bg-secondary/30 border border-border rounded-lg p-3 overflow-x-auto">{`curl -X POST ${url} -H 'Content-Type: application/json' -d '{"secret":"<secret>","open_case":true,"events":[{"kind":"Detection","title":"EDR: ransomware behavior","source":"CrowdStrike","severity":"Critical"}]}'`}</div>
        <div className="bg-secondary/30 border border-border rounded-lg p-3 space-y-2" data-testid="crisis-webhook-mapper">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground">Field mapping — paste native JSON, no pre-formatting</div>
            <select value={fmt} onChange={(e) => setFmt(e.target.value)} data-testid="crisis-webhook-format" className="bg-background border border-border rounded-md px-2 py-1 text-xs font-mono">
              <option value="generic">Generic</option>
              <option value="crowdstrike">CrowdStrike</option>
              <option value="splunk">Splunk</option>
              <option value="sentinel">Microsoft Sentinel</option>
              <option value="servicenow">ServiceNow</option>
            </select>
          </div>
          <textarea value={sample} onChange={(e) => setSample(e.target.value)} data-testid="crisis-webhook-sample" rows={5} spellCheck={false} className="w-full bg-background border border-border rounded-md p-2 text-[11px] font-mono resize-y" />
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={preview} disabled={mapBusy} data-testid="crisis-webhook-preview" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{mapBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Rss className="w-3.5 h-3.5" />}Preview mapping</button>
            <span className="text-[10px] text-muted-foreground">{`Post native JSON as {secret, format, payload} — we map it onto the timeline.`}</span>
          </div>
          {mapped && (
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-1" data-testid="crisis-webhook-mapped">
              {[["kind", mapped.kind], ["severity", mapped.severity], ["source", mapped.source], ["title", mapped.title], ["detail", mapped.detail]].map(([k, v]) => (
                <div key={k}>
                  <div className="text-[8px] font-mono uppercase tracking-widest text-muted-foreground">{k}</div>
                  <div className="text-[11px] font-medium truncate" title={String(v || "")}>{String(v || "—")}</div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div>
          <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground mb-2">Recently received ({cfg?.count || 0})</div>
          {(cfg?.recent || []).length === 0 ? (
            <EmptyState title="No events received yet" text="Once your tool posts to this endpoint, incoming incidents and containment steps appear here and on the crisis timeline in real time." />
          ) : (
            <div className="space-y-1.5">{cfg.recent.map((e) => (
              <div key={e.event_id} data-testid={`crisis-webhook-event-${e.event_id}`} className="flex items-center justify-between gap-3 bg-secondary/40 border border-border rounded-md px-3 py-1.5">
                <div className="min-w-0"><div className="text-xs font-medium truncate">{e.title}</div><div className="text-[10px] font-mono text-muted-foreground">{e.kind} · {e.source} · {e.case_ref}</div></div>
                <span className="shrink-0 text-[9px] font-mono text-muted-foreground">{e.created_at ? new Date(e.created_at).toLocaleTimeString() : ""}</span>
              </div>
            ))}</div>
          )}
        </div>
      </div>
    </Panel>
  );
}

function IncidentCommand({ data, selectedCase, caseDetail, loadCase, changed, created }) {
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: "",
    severity: "High",
    summary: "",
    incident_commander: "",
    executive_sponsor: "",
  });

  const createCase = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await api.post("/crisis/cases", form);
      setShowCreate(false);
      setForm({ title: "", severity: "High", summary: "", incident_commander: "", executive_sponsor: "" });
      await created(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to create crisis case.");
    } finally {
      setBusy(false);
    }
  };

  const update = async (changes) => {
    if (!selectedCase) return;
    setBusy(true);
    try {
      await api.patch(`/crisis/cases/${selectedCase.ref}`, changes);
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to update crisis case.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid xl:grid-cols-[360px_1fr] gap-5" data-testid="crisis-incident-command">
      <Panel title="Crisis Cases" subtitle="Persistent organization-scoped crisis cases." actions={<button onClick={() => setShowCreate((value) => !value)} data-testid="crisis-new-case-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />New Crisis</button>}>
        {showCreate && (
          <form onSubmit={createCase} className="mb-4 rounded-lg border border-border bg-secondary/20 p-3 space-y-2">
            <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Crisis title" data-testid="crisis-form-title" className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm" />
            <select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} data-testid="crisis-form-severity" className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm"><option>Critical</option><option>High</option><option>Medium</option><option>Low</option></select>
            <input value={form.incident_commander} onChange={(e) => setForm({ ...form, incident_commander: e.target.value })} placeholder="Incident commander" data-testid="crisis-form-commander" className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm" />
            <input value={form.executive_sponsor} onChange={(e) => setForm({ ...form, executive_sponsor: e.target.value })} placeholder="Executive sponsor" data-testid="crisis-form-sponsor" className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm" />
            <textarea rows={3} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} placeholder="Initial crisis summary" data-testid="crisis-form-summary" className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm" />
            <button disabled={busy} data-testid="crisis-create-case-submit" className="w-full px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">{busy ? "Creating..." : "Open Crisis Case"}</button>
          </form>
        )}
        <div className="space-y-2">
          {(data.cases || []).map((item) => (
            <button key={item.ref} onClick={() => loadCase(item.ref)} data-testid={`crisis-case-${item.ref}`} className={`w-full text-left rounded-lg border p-3 ${selectedCase?.ref === item.ref ? "border-primary/40 bg-primary/10" : "border-border bg-secondary/20 hover:bg-secondary/40"}`}>
              <div className="flex items-start justify-between gap-2">
                <div><div className="font-mono text-[10px] text-ai">{item.ref}</div><div className="font-head font-bold text-sm mt-1">{item.title}</div></div>
                <StatusPill value={item.severity} />
              </div>
              <div className="text-[10px] text-muted-foreground mt-2">{item.phase} · {item.status}</div>
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Incident Command" subtitle="Leadership, phase, status and command summary.">
        {!selectedCase ? (
          <EmptyState title="Select or create a crisis case" text="Persistent incident command begins with a crisis case." />
        ) : (
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-mono text-[10px] text-ai">{selectedCase.ref}</div>
                <h2 className="font-head font-black text-2xl mt-1">{selectedCase.title}</h2>
                <div className="flex flex-wrap gap-1.5 mt-2"><StatusPill value={selectedCase.severity} /><StatusPill value={selectedCase.status} /><StatusPill value={selectedCase.phase} /></div>
              </div>
              <Siren className="w-8 h-8 text-crit" />
            </div>
            <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
              <label className="text-xs"><span className="text-muted-foreground">Phase</span><select value={selectedCase.phase} disabled={busy} onChange={(e) => update({ phase: e.target.value })} data-testid="crisis-phase-select" className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5">{["Detection","Triage","Containment","Eradication","Recovery","Post Incident"].map((v) => <option key={v}>{v}</option>)}</select></label>
              <label className="text-xs"><span className="text-muted-foreground">Status</span><select value={selectedCase.status} disabled={busy} onChange={(e) => update({ status: e.target.value })} data-testid="crisis-status-select" className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5">{["Open","Contained","Recovering","Monitoring","Closed"].map((v) => <option key={v}>{v}</option>)}</select></label>
              <label className="text-xs"><span className="text-muted-foreground">Incident Commander</span><input defaultValue={selectedCase.incident_commander || ""} onBlur={(e) => e.target.value !== selectedCase.incident_commander && update({ incident_commander: e.target.value })} className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5" /></label>
              <label className="text-xs"><span className="text-muted-foreground">Executive Sponsor</span><input defaultValue={selectedCase.executive_sponsor || ""} onBlur={(e) => e.target.value !== selectedCase.executive_sponsor && update({ executive_sponsor: e.target.value })} className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5" /></label>
            </div>
            <div className="rounded-xl border border-border bg-secondary/20 p-4"><div className="text-[10px] font-mono uppercase text-muted-foreground">Current command summary</div><p className="text-sm mt-2 leading-relaxed">{selectedCase.summary || "No current command summary."}</p></div>
            <div className="grid md:grid-cols-4 gap-3">
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Actions</div><div className="font-head font-black text-2xl mt-1">{caseDetail?.actions?.length || 0}</div></div>
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Timeline Events</div><div className="font-head font-black text-2xl mt-1">{caseDetail?.events?.length || 0}</div></div>
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Started</div><div className="text-sm font-medium mt-2">{selectedCase.started_at ? new Date(selectedCase.started_at).toLocaleString() : "-"}</div></div>
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Last Update</div><div className="text-sm font-medium mt-2">{selectedCase.updated_at ? new Date(selectedCase.updated_at).toLocaleString() : "-"}</div></div>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

function DecisionRoom({ selectedCase, caseDetail, recommendations, decisions, changed }) {
  const [busy, setBusy] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ title: "", owner: "", priority: "Critical", decision_owner: "", business_impact: "", technical_impact: "" });
  const pending = (caseDetail?.actions || []).filter((action) => action.decision_required || action.status === "Awaiting Approval" || action.action_type === "Decision");

  const add = async (event) => {
    event.preventDefault();
    if (!selectedCase) return;
    setBusy("add");
    try {
      await api.post(`/crisis/cases/${selectedCase.ref}/actions`, { ...form, action_type: "Decision", decision_required: true, status: "Awaiting Approval" });
      setShowAdd(false);
      setForm({ title: "", owner: "", priority: "Critical", decision_owner: "", business_impact: "", technical_impact: "" });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to create executive decision.");
    } finally {
      setBusy("");
    }
  };

  const approve = async (action) => {
    setBusy(action.action_id);
    try {
      await api.patch(`/crisis/cases/${selectedCase.ref}/actions/${action.action_id}`, { status: "Approved", approved_by: action.decision_owner || "Executive approval" });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to approve decision.");
    } finally {
      setBusy("");
    }
  };

  const scanSla = async () => {
    setBusy("sla");
    try {
      const { data } = await api.post("/crisis/decisions/sla-scan");
      toast.success(data.alerts_sent > 0 ? `${data.alerts_sent} SLA breach alert(s) sent to Teams/Slack.` : "No decisions have breached their approval SLA.");
      if (selectedCase) await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to scan decision SLAs.");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-5" data-testid="crisis-decision-room">
      <Panel title="Decision Room — Executive Approval Queue" subtitle="Persistent crisis decisions with business and technical impact context." actions={selectedCase ? (<div className="flex items-center gap-2"><button onClick={scanSla} disabled={busy === "sla"} data-testid="crisis-sla-scan-btn" title="Ping Teams/Slack for any decision that has blown its approval SLA" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-med/40 bg-med/10 text-med text-xs font-head font-bold disabled:opacity-50">{busy === "sla" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Timer className="w-3.5 h-3.5" />}Scan SLAs</button><button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-decision-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Decision</button></div>) : null}>
        {!selectedCase ? <EmptyState title="No crisis case selected" text="Select a crisis case before creating executive decision requirements." /> : (
          <>
            {showAdd && (
              <form onSubmit={add} className="rounded-lg border border-border bg-secondary/20 p-4 mb-4 grid md:grid-cols-2 gap-3">
                <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Decision required" data-testid="crisis-decision-title" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm md:col-span-2" />
                <input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} placeholder="Action owner" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <input value={form.decision_owner} onChange={(e) => setForm({ ...form, decision_owner: e.target.value })} placeholder="Executive approver" data-testid="crisis-decision-approver" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <textarea rows={3} value={form.business_impact} onChange={(e) => setForm({ ...form, business_impact: e.target.value })} placeholder="Business impact" data-testid="crisis-decision-impacts" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <textarea rows={3} value={form.technical_impact} onChange={(e) => setForm({ ...form, technical_impact: e.target.value })} placeholder="Technical impact" data-testid="crisis-decision-impact-technical" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <button disabled={busy === "add"} data-testid="crisis-decision-submit" className="md:col-span-2 px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Create Executive Decision</button>
              </form>
            )}
            <div className="space-y-3">
              {pending.map((action) => (
                <div key={action.action_id} data-testid={`crisis-decision-${action.action_id}`} className="rounded-xl border border-high/25 bg-high/5 p-4">
                  <div className="grid xl:grid-cols-[1.5fr_.7fr_auto] gap-4">
                    <div><div className="font-mono text-[10px] text-ai">{action.action_id}</div><div className="font-head font-bold text-lg mt-1">{action.title}</div><div className="grid md:grid-cols-2 gap-3 mt-3"><div className="rounded-lg bg-card/60 border border-border p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Business impact</div><div className="text-xs mt-1">{action.business_impact || "Not documented"}</div></div><div className="rounded-lg bg-card/60 border border-border p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Technical impact</div><div className="text-xs mt-1">{action.technical_impact || "Not documented"}</div></div></div></div>
                    <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Approval owner</div><div className="text-sm font-medium mt-1">{action.decision_owner || "Unassigned"}</div><div className="mt-3"><StatusPill value={action.status} /></div>{action.status === "Awaiting Approval" && action.decision_due_at && (() => { const cd = obligationCountdown(action.decision_due_at); return <div data-testid={`crisis-decision-sla-${action.action_id}`} className={`mt-2 inline-flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded-full ${cd.overdue ? "bg-crit/15 text-crit" : cd.urgent ? "bg-med/15 text-med" : "bg-secondary/60 text-muted-foreground"}`}><Timer className="w-3 h-3" />SLA {cd.label}</div>; })()}</div>
                    <div className="flex items-center">{action.status === "Awaiting Approval" ? <button onClick={() => approve(action)} disabled={busy === action.action_id} data-testid={`crisis-approve-${action.action_id}`} className="px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold inline-flex items-center gap-1.5 disabled:opacity-50">{busy === action.action_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}Approve</button> : <StatusPill value={action.status} />}</div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </Panel>
      <div className="grid xl:grid-cols-2 gap-5">
        <Panel title="Existing Obserra Recommendations" subtitle="Current recommendation inventory for crisis context."><div className="space-y-2">{(recommendations || []).slice(0, 10).map((item) => <div key={item.ref} className="rounded-lg border border-border p-3"><div className="flex items-start justify-between gap-3"><div><div className="font-mono text-[10px] text-ai">{item.ref}</div><div className="text-sm font-medium mt-1">{item.title}</div></div><StatusPill value={item.status} /></div></div>)}</div></Panel>
        <Panel title="Existing Executive Decisions" subtitle="Current decision register, preserved separately from crisis actions."><div className="space-y-2">{(decisions || []).slice(0, 10).map((item) => <div key={item.ref} className="rounded-lg border border-border p-3"><div className="font-mono text-[10px] text-ai">{item.ref}</div><div className="text-sm font-medium mt-1">{item.title}</div><div className="text-xs text-muted-foreground mt-2">Chosen: {item.chosen || "-"} · Approver: {item.approver || "-"}</div></div>)}</div></Panel>
      </div>
    </div>
  );
}

function BusinessImpact({ data, selectedCase }) {
  const exposure = portfolioExposure(data.risks || [], data.strategic || {});
  const risks = [...(data.risks || [])].sort((a, b) => Number(b.residual_ale || 0) - Number(a.residual_ale || 0)).slice(0, 12);
  const services = selectedCase?.business_services || [];
  const benchmark = data.strategic?.benchmark || {};

  return (
    <div className="space-y-5" data-testid="crisis-business-impact">
      <div className="grid md:grid-cols-4 gap-4">
        <MetricCard label="Residual exposure" value={money(exposure)} sub="Current portfolio residual ALE" icon={Banknote} accent="35 90% 55%" />
        <MetricCard label="High residual risks" value={affectedRiskCount(data.risks || [])} sub="Residual score 10 or above" icon={ShieldAlert} />
        <MetricCard label="Business services" value={services.length} sub="Explicitly linked to crisis case" icon={Gauge} accent="266 85% 66%" />
        <MetricCard label="Industry position" value={benchmark.position || "Not available"} sub={benchmark.industry || "No benchmark configured"} icon={FileText} accent="142 70% 45%" />
      </div>
      <Panel title="Financial Exposure by Enterprise Risk" subtitle="Existing residual ALE from the current risk engine. No crisis loss values are invented.">
        <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><tr><th className="text-left py-3 pr-3">Risk</th><th className="text-left py-3 px-3">Rating</th><th className="text-right py-3 px-3">Residual</th><th className="text-right py-3 px-3">Residual ALE</th><th className="text-left py-3 pl-3">Owner</th></tr></thead><tbody>{risks.map((risk) => <tr key={risk.ref} className="border-b border-border/60"><td className="py-3 pr-3"><div className="font-mono text-[10px] text-ai">{risk.ref}</div><div className="font-medium mt-1">{risk.title}</div></td><td className="py-3 px-3"><StatusPill value={risk.rating || "Risk"} /></td><td className="py-3 px-3 text-right font-mono">{risk.residual}</td><td className="py-3 px-3 text-right font-mono">{money(risk.residual_ale)}</td><td className="py-3 pl-3 text-muted-foreground">{risk.owner || "Unassigned"}</td></tr>)}</tbody></table></div>
      </Panel>
      <Panel title="Business Service Impact" subtitle="Only explicitly linked business services are shown as crisis affected.">{services.length ? <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">{services.map((service) => <div key={service} className="rounded-lg border border-border bg-secondary/20 p-3"><div className="font-head font-bold text-sm">{service}</div></div>)}</div> : <EmptyState title="No business services linked" text="Link business services to the crisis case to support enterprise impact analysis." />}</Panel>
    </div>
  );
}

function EntraContainment({ selectedCase, changed }) {
  const [q, setQ] = useState("");
  const [users, setUsers] = useState([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState("");
  const load = async (query = "") => {
    setBusy("load"); setStatus("");
    try {
      const r = await api.get(`/crisis/entra/users${query ? `?q=${encodeURIComponent(query)}` : ""}`);
      setUsers(r.data || []);
    } catch (e) {
      if (e.response?.status === 400) { setStatus("unconnected"); }
      else { setStatus("error"); toast.error(e.response?.data?.detail || "Unable to reach Microsoft Entra."); }
      setUsers([]);
    } finally { setBusy(""); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const contain = async (u) => {
    if (!selectedCase) { toast.error("Select a crisis case first."); return; }
    if (!window.confirm(`Disable ${u.displayName || u.userPrincipalName} and revoke all their sessions? This is a live Microsoft Entra action.`)) return;
    setBusy(u.id);
    try {
      const { data } = await api.post(`/crisis/cases/${selectedCase.ref}/contain-identity`, { user_id: u.id, upn: u.userPrincipalName || u.mail || "" });
      toast.success(`${u.displayName || u.userPrincipalName} contained — account disabled${data.sessions_revoked ? ", sessions revoked" : ""}.`);
      await load(q);
      await changed?.(selectedCase.ref);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Containment failed.");
    } finally { setBusy(""); }
  };
  const playbook = async (u) => {
    if (!selectedCase) { toast.error("Select a crisis case first."); return; }
    if (!window.confirm(`Run the containment playbook on ${u.displayName || u.userPrincipalName}? This disables the account, revokes all sessions and notifies the war room + Teams/Slack. Live Microsoft Entra action.`)) return;
    setBusy(`pb-${u.id}`);
    try {
      const { data } = await api.post(`/crisis/cases/${selectedCase.ref}/contain-playbook`, { user_id: u.id, upn: u.userPrincipalName || u.mail || "" });
      toast.success(`Playbook executed on ${u.displayName || u.userPrincipalName} — ${(data.steps || []).join(", ")}${data.notified ? " · war room notified" : ""}.`);
      await load(q);
      await changed?.(selectedCase.ref);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Playbook failed.");
    } finally { setBusy(""); }
  };
  return (
    <div data-testid="crisis-entra-containment">
      <Panel title="Identity Containment — Microsoft Entra" subtitle="Disable a compromised account and revoke its live sessions directly in Microsoft Entra (Graph).">
        {status === "unconnected" ? (
          <EmptyState title="Microsoft Entra not connected" text="Connect Microsoft Entra ID in Connector Health → Enterprise Connectors (Tenant ID, Client ID, Client secret) to enable live identity containment." />
        ) : (
          <div className="space-y-3">
            <form onSubmit={(e) => { e.preventDefault(); load(q); }} className="flex items-center gap-2">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search users by name or UPN…" data-testid="crisis-entra-search" className="flex-1 bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
              <button disabled={busy === "load"} data-testid="crisis-entra-search-btn" className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{busy === "load" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Search"}</button>
            </form>
            {users.length === 0 ? <EmptyState title="No Entra users" text="No users returned. Refine your search or verify the connection in Connector Health." /> : (
              <div className="space-y-2">
                {users.map((u) => (
                  <div key={u.id} data-testid={`crisis-entra-user-${u.id}`} className="flex items-center justify-between gap-3 bg-secondary/40 border border-border rounded-lg px-3 py-2">
                    <div className="min-w-0">
                      <div className="font-head font-bold text-sm truncate">{u.displayName || u.userPrincipalName}</div>
                      <div className="text-[11px] text-muted-foreground truncate">{u.userPrincipalName || u.mail}</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full ${u.accountEnabled === false ? "bg-crit/15 text-crit" : "bg-low/15 text-low"}`}>{u.accountEnabled === false ? "DISABLED" : "ENABLED"}</span>
                      <button disabled={busy === `pb-${u.id}` || u.accountEnabled === false} onClick={() => playbook(u)} data-testid={`crisis-entra-playbook-${u.id}`} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary/10 border border-primary/40 text-primary text-xs font-head font-bold disabled:opacity-40">{busy === `pb-${u.id}` ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}Playbook</button>
                      <button disabled={busy === u.id || u.accountEnabled === false} onClick={() => contain(u)} data-testid={`crisis-entra-contain-${u.id}`} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-crit/10 border border-crit/40 text-crit text-xs font-head font-bold disabled:opacity-40"><ShieldOff className="w-3.5 h-3.5" />Contain</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}

function ResponseActions({ selectedCase, caseDetail, changed }) {
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState({ title: "", owner: "", priority: "High", action_type: "Containment", business_impact: "", technical_impact: "" });
  const actions = caseDetail?.actions || [];
  const summary = actionSummary(actions);

  const add = async (event) => {
    event.preventDefault();
    if (!selectedCase) return;
    setBusy("add");
    try {
      await api.post(`/crisis/cases/${selectedCase.ref}/actions`, { ...form, status: "Open", decision_required: false, decision_owner: "" });
      setShowAdd(false);
      setForm({ title: "", owner: "", priority: "High", action_type: "Containment", business_impact: "", technical_impact: "" });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to create response action.");
    } finally {
      setBusy("");
    }
  };

  const setStatus = async (action, status) => {
    setBusy(action.action_id);
    try {
      await api.patch(`/crisis/cases/${selectedCase.ref}/actions/${action.action_id}`, { status });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to update response action.");
    } finally {
      setBusy("");
    }
  };

  return (
    <Panel testid="crisis-response-actions" title="Containment & Recovery Command" subtitle="Persistent response actions. External containment is not claimed until execution is verified by an integrated system." actions={selectedCase ? <button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-action-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Action</button> : null}>
      {!selectedCase ? <EmptyState title="No crisis case selected" text="Select a crisis case before coordinating containment and recovery." /> : (
        <>
          <div className="grid md:grid-cols-5 gap-3 mb-4">{[["Total",summary.total],["Open",summary.open],["Awaiting Approval",summary.awaitingApproval],["Executing",summary.executing],["Verified",summary.verified]].map(([label,value]) => <div key={label} className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">{label}</div><div className="font-head font-black text-2xl mt-1">{value}</div></div>)}</div>
          <ProgressBar value={summary.progress} />
          {showAdd && <form onSubmit={add} className="rounded-lg border border-border bg-secondary/20 p-4 my-4 grid md:grid-cols-2 gap-3"><input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Response action" data-testid="crisis-action-title" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm md:col-span-2" /><input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} placeholder="Owner" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" /><select value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm">{["Containment","Recovery","Communication","Legal","Investigation"].map((v) => <option key={v}>{v}</option>)}</select><textarea rows={3} value={form.business_impact} onChange={(e) => setForm({ ...form, business_impact: e.target.value })} placeholder="Business impact" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" /><textarea rows={3} value={form.technical_impact} onChange={(e) => setForm({ ...form, technical_impact: e.target.value })} placeholder="Technical impact" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" /><button disabled={busy === "add"} data-testid="crisis-action-submit" className="md:col-span-2 px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Create Response Action</button></form>}
          <div className="space-y-3 mt-5">{actions.map((action) => <div key={action.action_id} data-testid={`crisis-action-${action.action_id}`} className="rounded-xl border border-border bg-secondary/20 p-4"><div className="grid xl:grid-cols-[1.4fr_.6fr_.7fr_auto] gap-4 items-center"><div><div className="font-mono text-[10px] text-ai">{action.action_id}</div><div className="font-head font-bold mt-1">{action.title}</div><div className="text-xs text-muted-foreground mt-1">{action.action_type} · {action.owner || "Unassigned"}</div></div><div><div className="text-[9px] font-mono uppercase text-muted-foreground">Priority</div><div className="mt-2"><StatusPill value={action.priority} /></div></div><div><div className="text-[9px] font-mono uppercase text-muted-foreground">Status</div><div className="mt-2"><StatusPill value={action.status} /></div></div><div>{!["Verified","Complete"].includes(action.status) && <button onClick={() => setStatus(action, action.status === "Executing" ? "Verified" : "Executing")} disabled={busy === action.action_id} data-testid={`crisis-action-advance-${action.action_id}`} className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">{action.status === "Executing" ? "Verify" : "Execute"}</button>}</div></div></div>)}</div>
        </>
      )}
    </Panel>
  );
}

function ControlFailures({ data }) {
  const summary = controlFailureSummary(data.controls || []);
  const attention = (data.controls || []).filter((control) => control.status === "Failing" || control.status === "Drifting" || control.status === "Evidence Stale" || control.drift || control.stale);
  const frameworks = Array.isArray(data.compliance?.frameworks) ? data.compliance.frameworks : [];

  return (
    <div className="space-y-5" data-testid="crisis-control-failures">
      <div className="grid md:grid-cols-4 gap-4"><MetricCard label="Failing controls" value={summary.failing} icon={AlertTriangle} /><MetricCard label="Drifting controls" value={summary.drifting} icon={AlertTriangle} accent="35 90% 55%" /><MetricCard label="Stale evidence" value={summary.stale} icon={Clock3} accent="266 85% 66%" /><MetricCard label="Unique attention" value={summary.totalAttention} icon={ShieldCheck} accent="142 70% 45%" /></div>
      <Panel title="Control Failures Affecting Crisis Posture" subtitle="Existing control effectiveness, maturity, drift and evidence state."><div className="space-y-3">{attention.map((control) => <div key={control.control_id} className="rounded-xl border border-border bg-secondary/20 p-4"><div className="grid xl:grid-cols-[1.4fr_.6fr_.6fr_.7fr] gap-4"><div><div className="font-mono text-[10px] text-ai">{control.control_id}</div><div className="font-head font-bold mt-1">{control.name}</div><div className="text-xs text-muted-foreground mt-1">{control.category} · {control.owner || "Unassigned"}</div></div><div><div className="text-[9px] font-mono uppercase text-muted-foreground">Status</div><div className="mt-2"><StatusPill value={control.status} /></div></div><div><div className="text-[9px] font-mono uppercase text-muted-foreground">Effectiveness</div><div className="font-head font-black text-xl mt-1">{control.effectiveness}%</div></div><div><div className="text-[9px] font-mono uppercase text-muted-foreground">Evidence</div><div className="text-sm mt-1">{control.stale ? "Expired" : `${control.days_to_expiry ?? "-"} days to expiry`}</div></div></div></div>)}</div></Panel>
      <Panel title="Framework Readiness During Crisis" subtitle="Current control framework coverage for audit and response assurance."><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">{frameworks.map((framework) => <div key={framework.framework} className="rounded-lg border border-border p-3"><div className="font-head font-bold text-sm">{framework.framework}</div><div className="font-head font-black text-2xl mt-2">{framework.coverage}%</div><div className="text-xs text-muted-foreground mt-1">{framework.passing}/{framework.controls} controls passing</div></div>)}</div></Panel>
    </div>
  );
}

function TimelineEvidence({ selectedCase, caseDetail, data, changed }) {
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ kind: "Note", title: "", detail: "", source: "Manual", severity: "Info" });
  const rows = mergeTimeline({ caseEvents: caseDetail?.events || [], incidents: data.incidents || [], audit: data.audit || [] });

  const add = async (event) => {
    event.preventDefault();
    if (!selectedCase) return;
    setBusy(true);
    try {
      await api.post(`/crisis/cases/${selectedCase.ref}/events`, form);
      setShowAdd(false);
      setForm({ kind: "Note", title: "", detail: "", source: "Manual", severity: "Info" });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to add timeline event.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel testid="crisis-timeline" title="Crisis Timeline & Evidence" subtitle="Merged crisis events, incident timestamps and recent audit records." actions={selectedCase ? <button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-event-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Timeline Event</button> : null}>
      {showAdd && <form onSubmit={add} className="rounded-lg border border-border bg-secondary/20 p-4 mb-5 grid md:grid-cols-2 gap-3"><select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm">{["Detection","Threat","Containment","Decision","Communication","Recovery","Business Impact","Legal","Evidence","Note"].map((v) => <option key={v}>{v}</option>)}</select><select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm">{["Info","Low","Medium","High","Critical"].map((v) => <option key={v}>{v}</option>)}</select><input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Timeline event" data-testid="crisis-event-title" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm md:col-span-2" /><input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} placeholder="Source" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" /><textarea rows={3} value={form.detail} onChange={(e) => setForm({ ...form, detail: e.target.value })} placeholder="Detail" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" /><button disabled={busy} data-testid="crisis-event-submit" className="md:col-span-2 px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Add Timeline Event</button></form>}
      {rows.length === 0 ? <EmptyState title="No timeline evidence" text="No crisis events, incident timestamps or recent audit records are currently available." /> : <div className="relative"><div className="absolute left-[93px] top-0 bottom-0 w-px bg-border" /><div className="space-y-1">{rows.slice(0, 150).map((row) => <div key={`${row.id}:${row.ts}`} className="grid grid-cols-[80px_1fr] gap-7 py-3"><div className="text-right"><div className="font-mono text-[10px] text-muted-foreground">{row.ts ? new Date(row.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "-"}</div><div className="font-mono text-[9px] text-muted-foreground mt-1">{row.ts ? new Date(row.ts).toLocaleDateString() : ""}</div></div><div className="relative rounded-lg border border-border bg-secondary/20 p-3"><div className="absolute -left-[20px] top-4 w-2.5 h-2.5 rounded-full bg-primary border-2 border-background" /><div className="flex items-start justify-between gap-3"><div><div className="font-head font-bold text-sm">{row.title}</div><div className="text-[10px] text-muted-foreground mt-1">{row.kind} · {row.source}</div></div><StatusPill value={row.severity} /></div>{row.detail && <div className="text-xs text-muted-foreground mt-2">{row.detail}</div>}</div></div>)}</div></div>}
    </Panel>
  );
}

function ExecutiveBriefing({ data, selectedCase, caseDetail, reportBusy, generateReport }) {
  const response = actionSummary(caseDetail?.actions || []);
  const controls = controlFailureSummary(data.controls || []);
  const exposure = portfolioExposure(data.risks || [], data.strategic || {});
  const context = {
    crisis_case: selectedCase,
    active_incidents: activeIncidents(data.incidents || []).slice(0, 20),
    current_financial_exposure: exposure,
    crisis_score: data.crisisScore,
    response_actions: response,
    control_failures: controls,
    top_risks: (data.risks || []).slice(0, 10),
    current_decisions: (data.decisions || []).slice(0, 10),
  };

  return (
    <div className="space-y-5" data-testid="crisis-briefing">
      <div className="grid md:grid-cols-4 gap-4"><MetricCard label="Crisis" value={selectedCase?.severity || data.severity || "None"} sub={selectedCase?.title || "No case selected"} icon={Siren} /><MetricCard label="Exposure" value={money(exposure)} icon={Banknote} accent="35 90% 55%" /><MetricCard label="Response progress" value={`${response.progress}%`} kind="MODELLED" icon={CheckCircle2} accent="142 70% 45%" /><MetricCard label="Approvals pending" value={response.awaitingApproval} icon={Gavel} accent="266 85% 66%" /></div>
      <Panel title="Obserra Crisis Advisor" subtitle="Executive analysis grounded solely in the current crisis case, incidents, exposure and response status."><AIExplain title={selectedCase?.title || "Enterprise cyber crisis posture"} kind="cyber crisis executive decision business impact containment recovery" context={context} accent="0 84% 60%" groundOnly /></Panel>
      <Panel title="Board & Executive Reporting" subtitle="Uses the existing Obserra Studio PDF service."><button onClick={generateReport} disabled={reportBusy} data-testid="crisis-generate-brief" className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold disabled:opacity-50">{reportBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}Generate Cyber Crisis Executive Brief</button></Panel>
    </div>
  );
}

function Defensibility({ data, sourceStatus }) {
  const connectors = data.connectorHealth?.connectors || [];
  const labels = { risks: "Risk Register", incidents: "AI Incidents", recommendations: "Recommendations", decisions: "Decision Register", audit: "Audit", controls: "Control Monitoring", compliance: "Control Compliance", strategic: "Risk Engine Strategic", tactical: "Risk Engine Tactical", workflows: "Workflow Engine", connectorHealth: "Connector Health", cases: "Crisis Commander" };

  return (
    <div className="space-y-5" data-testid="crisis-defensibility">
      <div className="grid xl:grid-cols-3 gap-5">
        <Panel title="Data Source Status" subtitle="Unavailable source data is surfaced, never replaced."><div className="space-y-2">{Object.entries(sourceStatus || {}).map(([key, status]) => <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5"><div className="text-sm font-medium">{labels[key] || key}</div><span className={`text-[10px] font-mono ${status.ok ? "text-low" : "text-crit"}`}>{status.ok ? "LIVE" : "UNAVAILABLE"}</span></div>)}</div></Panel>
        <Panel title="Evidence Classification" subtitle="Source records, models and AI interpretation remain distinct."><div className="space-y-4"><div className="rounded-lg border border-border p-4"><DataClassBadge kind="FACT" /><p className="text-xs text-muted-foreground mt-2">Crisis cases, incidents, risks, controls, decisions, audit events, workflows, financial ALE and response actions.</p></div><div className="rounded-lg border border-border p-4"><DataClassBadge kind="MODELLED" /><p className="text-xs text-muted-foreground mt-2">Enterprise crisis score and response progress.</p></div><div className="rounded-lg border border-border p-4"><DataClassBadge kind="AI RECOMMENDATION" /><p className="text-xs text-muted-foreground mt-2">Obserra Crisis Advisor summaries and recommendations.</p></div></div></Panel>
        <Panel title="Execution Boundary" subtitle="Crisis orchestration records are not confused with external defensive execution."><div className="space-y-3 text-sm"><div>External isolation, token revocation, SAP suspension or cloud containment is not claimed unless a connected execution system verifies the action.</div><div>Crisis case updates and action changes are written into the existing audit stream.</div><div>"Executing" means the response team marked execution in Obserra, not that an external system has been independently verified.</div></div></Panel>
      </div>
      <Panel title="Connector Health Context" subtitle="Existing enterprise connector telemetry available to crisis leadership.">{connectors.length ? <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">{connectors.map((connector) => <div key={`${connector.id}:${connector.name}`} className="rounded-lg border border-border p-3"><div className="font-head font-bold text-sm">{connector.name}</div><div className="text-[10px] text-muted-foreground mt-1">{connector.category}</div><div className="text-[10px] font-mono mt-2">{connector.health || connector.state || "unknown"}</div></div>)}</div> : <EmptyState title="No connector health data" text="No connector health records are currently returned." />}</Panel>
    </div>
  );
}

function WarRoomChat({ selectedCase, caseDetail, user, live, changed }) {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const ref = selectedCase?.ref;
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const canOperate = ["admin", "executive", "owner"].includes(user?.role);
  const roles = [...new Set((caseDetail?.participants || []).map((p) => p.role).filter(Boolean))];

  const load = useCallback(async () => {
    if (!ref) { setMsgs([]); return; }
    try { const r = await api.get(`/crisis/cases/${ref}/messages`); setMsgs(r.data || []); } catch { /* keep existing */ }
  }, [ref]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!ref || !live) return undefined;
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, [ref, live, load]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs.length]);

  const insertMention = (role) => {
    setText((t) => `${t}${t && !t.endsWith(" ") ? " " : ""}@${role} `);
    inputRef.current?.focus();
  };

  const send = async (e) => {
    e.preventDefault();
    const value = text.trim();
    if (!value || !ref) return;
    setBusy(true);
    try {
      await api.post(`/crisis/cases/${ref}/messages`, { text: value });
      setText("");
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to send message.");
    } finally {
      setBusy(false);
    }
  };

  const convert = async (m) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/crisis/cases/${ref}/messages/${m.message_id}/to-action`);
      toast.success(`Tracked as decision ${data.action_id} — awaiting approval in the Decision Room.`);
      await load();
      await changed?.(ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to convert message.");
    } finally {
      setBusy(false);
    }
  };

  const renderText = (t) => (t || "").split(/(@\S+)/g).map((part, i) =>
    part.startsWith("@") ? <span key={i} className="text-ai font-bold">{part}</span> : <span key={i}>{part}</span>);

  return (
    <div data-testid="crisis-war-room-chat">
      <Panel title="War Room Chat" subtitle="Shared responder thread — @mention a role to ping them on Teams/Slack, and turn any message into a tracked decision.">
        {!ref ? <EmptyState title="No crisis case selected" text="Select a crisis case to open the war room thread." /> : (
          <div className="flex flex-col h-[460px]">
            <div className="flex-1 overflow-y-auto space-y-3 pr-1" data-testid="crisis-chat-thread">
              {msgs.length === 0 ? <EmptyState title="No messages yet" text="Start the war room conversation below." /> : msgs.map((m) => {
                const mine = m.author === (user?.name || user?.email);
                return (
                  <div key={m.message_id} data-testid={`crisis-chat-msg-${m.message_id}`} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[80%] rounded-xl px-3 py-2 ${mine ? "bg-primary/15 border border-primary/30" : "bg-secondary/40 border border-border"}`}>
                      <div className="flex items-center gap-2"><span className="font-head font-bold text-xs">{m.author}</span><span className="text-[9px] font-mono uppercase text-muted-foreground">{m.role}</span></div>
                      <div className="text-sm mt-1 whitespace-pre-wrap break-words">{renderText(m.text)}</div>
                      {Array.isArray(m.mentions) && m.mentions.length > 0 && (
                        <div className="text-[9px] font-mono text-ai mt-1 flex items-center gap-1"><Bell className="w-3 h-3" />pinged {m.mentions.map((x) => x.role).join(", ")}</div>
                      )}
                      <div className="flex items-center justify-between gap-3 mt-1">
                        <span className="text-[9px] text-muted-foreground">{m.created_at ? new Date(m.created_at).toLocaleTimeString() : ""}</span>
                        {canOperate && (m.converted_action_id ? (
                          <span data-testid={`crisis-chat-tracked-${m.message_id}`} className="text-[9px] font-mono text-low inline-flex items-center gap-1"><Gavel className="w-3 h-3" />{m.converted_action_id}</span>
                        ) : (
                          <button onClick={() => convert(m)} disabled={busy} data-testid={`crisis-chat-to-action-${m.message_id}`} className="text-[9px] font-mono text-primary hover:underline inline-flex items-center gap-1 disabled:opacity-50"><Gavel className="w-3 h-3" />Turn into decision</button>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={endRef} />
            </div>
            {roles.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3" data-testid="crisis-chat-mentions">
                {roles.map((r) => (
                  <button key={r} type="button" onClick={() => insertMention(r)} data-testid={`crisis-chat-mention-${r.replace(/[^a-zA-Z0-9]/g, "-")}`} className="text-[10px] px-2 py-1 rounded-full bg-ai/10 border border-ai/30 text-ai hover:bg-ai/20">@{r}</button>
                ))}
              </div>
            )}
            <form onSubmit={send} className="mt-2 flex items-center gap-2">
              <input ref={inputRef} value={text} onChange={(e) => setText(e.target.value)} placeholder="Message the war room… use @Role to ping" data-testid="crisis-chat-input" className="flex-1 bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
              <button disabled={busy || !text.trim()} data-testid="crisis-chat-send" className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}Send</button>
            </form>
          </div>
        )}
      </Panel>
    </div>
  );
}

function RiskyUsers({ selectedCase, changed }) {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState("");
  const load = async () => {
    setBusy("load"); setStatus("");
    try {
      const r = await api.get("/crisis/entra/risky-users");
      setRows(r.data || []);
    } catch (e) {
      if (e.response?.status === 400) { setStatus("unconnected"); }
      else { setStatus("error"); toast.error(e.response?.data?.detail || "Unable to load risky users."); }
      setRows([]);
    } finally { setBusy(""); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const contain = async (u) => {
    if (!selectedCase) { toast.error("Select a crisis case first."); return; }
    if (!window.confirm(`Run the containment playbook on ${u.displayName || u.userPrincipalName}? This disables the account, revokes all sessions and notifies the war room. Live Microsoft Entra action.`)) return;
    setBusy(u.id);
    try {
      const { data } = await api.post(`/crisis/cases/${selectedCase.ref}/contain-playbook`, { user_id: u.id, upn: u.userPrincipalName || "" });
      toast.success(`${u.displayName || u.userPrincipalName} contained — ${(data.steps || []).join(", ")}${data.notified ? " · war room notified" : ""}.`);
      await load();
      await changed?.(selectedCase.ref);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Containment failed.");
    } finally { setBusy(""); }
  };
  const riskColor = (lvl) => {
    const l = String(lvl || "").toLowerCase();
    return l === "high" ? "bg-crit/15 text-crit" : l === "medium" ? "bg-high/15 text-high" : l === "low" ? "bg-med/15 text-med" : "bg-secondary/60 text-muted-foreground";
  };
  return (
    <Panel testid="crisis-risky-users" title="Identity Protection — Risky Users (live Microsoft Entra)" subtitle="Users flagged by Microsoft Entra ID Protection. Contain a compromised account in one click." actions={<button onClick={load} disabled={busy === "load"} data-testid="crisis-risky-refresh" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{busy === "load" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh</button>}>
      {status === "unconnected" ? (
        <EmptyState title="Microsoft Entra not connected" text="Connect Microsoft Entra ID in Connector Health → Enterprise Connectors to surface live risky-user signals. Identity Protection requires Entra ID P2." />
      ) : rows.length === 0 ? (
        <EmptyState title="No risky users" text="Microsoft Entra ID Protection reports no active at-risk users." />
      ) : (
        <div className="space-y-2">{rows.map((u) => (
          <div key={u.id} data-testid={`crisis-risky-user-${u.id}`} className="flex items-center justify-between gap-3 bg-secondary/40 border border-border rounded-lg px-3 py-2">
            <div className="min-w-0">
              <div className="font-head font-bold text-sm truncate">{u.displayName || u.userPrincipalName}</div>
              <div className="text-[11px] text-muted-foreground truncate">{u.userPrincipalName}{u.riskDetail ? ` · ${u.riskDetail}` : ""}{u.lastUpdated ? ` · ${new Date(u.lastUpdated).toLocaleString()}` : ""}</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full uppercase ${riskColor(u.riskLevel)}`}>{u.riskLevel || "unknown"} risk</span>
              <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-secondary/60 text-muted-foreground uppercase">{u.riskState || "-"}</span>
              <button disabled={busy === u.id} onClick={() => contain(u)} data-testid={`crisis-risky-contain-${u.id}`} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-crit/10 border border-crit/40 text-crit text-xs font-head font-bold disabled:opacity-40">{busy === u.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldOff className="w-3.5 h-3.5" />}Contain</button>
            </div>
          </div>
        ))}</div>
      )}
    </Panel>
  );
}

function WarRoom({ selectedCase, caseDetail, changed, user, live }) {
  const [busy, setBusy] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ role: "", name: "", contact: "", responsibility: "", status: "Engaged" });
  const participants = caseDetail?.participants || [];
  const pending = (caseDetail?.actions || []).filter((a) => a.decision_required || a.status === "Awaiting Approval");

  const add = async (event) => {
    event.preventDefault();
    if (!selectedCase) return;
    setBusy("add");
    try {
      await api.post(`/crisis/cases/${selectedCase.ref}/participants`, form);
      setShowAdd(false);
      setForm({ role: "", name: "", contact: "", responsibility: "", status: "Engaged" });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to add participant.");
    } finally {
      setBusy("");
    }
  };

  const join = async () => {
    if (!selectedCase || !user) return;
    setBusy("join");
    try {
      await api.post(`/crisis/cases/${selectedCase.ref}/participants`, {
        role: user.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : "Responder",
        name: user.name || user.email || "Responder",
        contact: user.email || "",
        responsibility: "Joined the war room",
        status: "Engaged",
      });
      toast.success("You joined the war room.");
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to join the war room.");
    } finally {
      setBusy("");
    }
  };

  const remove = async (pid) => {
    setBusy(pid);
    try {
      await api.delete(`/crisis/cases/${selectedCase.ref}/participants/${pid}`);
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to remove participant.");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-5" data-testid="crisis-war-room">
      <div className="grid xl:grid-cols-[1.3fr_1fr] gap-5">
      <Panel title="War Room Roster" subtitle="Leadership and responders coordinating this crisis, by role." actions={selectedCase ? (
        <div className="flex items-center gap-2">
          {live && <span data-testid="crisis-warroom-live" className="inline-flex items-center gap-1 text-[10px] font-mono text-low"><span className="w-1.5 h-1.5 rounded-full bg-low animate-pulse" />LIVE · 8s</span>}
          <button onClick={join} disabled={busy === "join"} data-testid="crisis-join-warroom-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 bg-ai/10 text-ai text-xs font-head font-bold disabled:opacity-50"><UserPlus className="w-3.5 h-3.5" />Join War Room</button>
          <button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-participant-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Participant</button>
        </div>
      ) : null}>
        {!selectedCase ? <EmptyState title="No crisis case selected" text="Select a crisis case to convene the war room." /> : (
          <>
            {showAdd && (
              <form onSubmit={add} className="rounded-lg border border-border bg-secondary/20 p-4 mb-4 grid md:grid-cols-2 gap-3">
                <input required value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} placeholder="Role (e.g. Legal)" data-testid="crisis-participant-role" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" data-testid="crisis-participant-name" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <input value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} placeholder="Contact" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm">{["Engaged", "Standby", "Stood Down"].map((v) => <option key={v}>{v}</option>)}</select>
                <input value={form.responsibility} onChange={(e) => setForm({ ...form, responsibility: e.target.value })} placeholder="Responsibility" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm md:col-span-2" />
                <button disabled={busy === "add"} data-testid="crisis-participant-submit" className="md:col-span-2 px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Add to War Room</button>
              </form>
            )}
            {participants.length === 0 ? <EmptyState title="No participants yet" text="Add responders by role to build the war room roster." /> : (
              <div className="space-y-2">{participants.map((p) => (
                <div key={p.participant_id} data-testid={`crisis-participant-${p.participant_id}`} className="rounded-lg border border-border bg-secondary/20 p-3 flex items-center justify-between gap-3">
                  <div className="min-w-0"><div className="flex items-center gap-2"><Users className="w-3.5 h-3.5 text-ai" /><span className="font-head font-bold text-sm">{p.role}</span><StatusPill value={p.status} /></div><div className="text-xs text-muted-foreground mt-1">{p.name || "Unassigned"}{p.responsibility ? ` · ${p.responsibility}` : ""}{p.contact ? ` · ${p.contact}` : ""}</div></div>
                  <button onClick={() => remove(p.participant_id)} disabled={busy === p.participant_id} data-testid={`crisis-participant-remove-${p.participant_id}`} className="shrink-0 text-muted-foreground hover:text-crit"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}</div>
            )}
          </>
        )}
      </Panel>
      <Panel title="Pending Executive Decisions" subtitle="Decisions awaiting an owner's approval, mirrored from the Decision Room.">
        {pending.length === 0 ? <EmptyState title="No decisions pending" text="No response actions are currently awaiting executive approval." /> : (
          <div className="space-y-2">{pending.map((a) => (
            <div key={a.action_id} className="rounded-lg border border-high/25 bg-high/5 p-3">
              <div className="font-mono text-[10px] text-ai">{a.action_id}</div>
              <div className="font-head font-bold text-sm mt-1">{a.title}</div>
              <div className="flex items-center justify-between gap-3 mt-2"><span className="text-xs text-muted-foreground">Owner: {a.decision_owner || "Unassigned"}</span><div className="flex items-center gap-2">{a.status === "Awaiting Approval" && a.decision_due_at && (() => { const cd = obligationCountdown(a.decision_due_at); return <span data-testid={`crisis-warroom-sla-${a.action_id}`} className={`inline-flex items-center gap-1 text-[9px] font-mono px-2 py-0.5 rounded-full ${cd.overdue ? "bg-crit/15 text-crit" : cd.urgent ? "bg-med/15 text-med" : "bg-secondary/60 text-muted-foreground"}`}><Timer className="w-3 h-3" />{cd.label}</span>; })()}<StatusPill value={a.status} /></div></div>
            </div>
          ))}</div>
        )}
      </Panel>
      </div>
      <WarRoomChat selectedCase={selectedCase} caseDetail={caseDetail} user={user} live={live} changed={changed} />
      <RiskyUsers selectedCase={selectedCase} changed={changed} />
    </div>
  );
}

function RecoveryCommand({ selectedCase, caseDetail, changed }) {
  const [busy, setBusy] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", category: "System", owner: "" });
  const items = caseDetail?.recovery || [];
  const overall = recoveryOverall(items);
  const byCat = recoveryByCategory(items);
  const NEXT = { Down: "Restoring", Restoring: "Validated", Validated: "Operational", Operational: "Operational" };

  const add = async (event) => {
    event.preventDefault();
    if (!selectedCase) return;
    setBusy("add");
    try {
      await api.post(`/crisis/cases/${selectedCase.ref}/recovery`, { ...form, status: "Down", note: "" });
      setShowAdd(false);
      setForm({ name: "", category: "System", owner: "" });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to add recovery item.");
    } finally {
      setBusy("");
    }
  };

  const advance = async (item) => {
    setBusy(item.recovery_id);
    try {
      await api.patch(`/crisis/cases/${selectedCase.ref}/recovery/${item.recovery_id}`, { status: NEXT[item.status] });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to update recovery item.");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-5" data-testid="crisis-recovery">
      <div className="grid md:grid-cols-4 gap-4">
        <MetricCard label="Overall recovery" value={`${overall}%`} kind="MODELLED" icon={HeartPulse} accent="142 70% 45%" />
        <MetricCard label="Items tracked" value={items.length} icon={LifeBuoy} />
        <MetricCard label="Operational" value={items.filter((i) => i.status === "Operational").length} icon={CheckCircle2} accent="142 70% 45%" />
        <MetricCard label="Still down" value={items.filter((i) => i.status === "Down").length} icon={AlertOctagon} accent="0 84% 60%" />
      </div>
      <Panel title="Recovery by Category" subtitle="Restoration percentage across systems, applications and business services.">
        {byCat.length === 0 ? <EmptyState title="No recovery items" text="Add recovery items to track restoration by category." /> : (
          <div className="space-y-3">{byCat.map((c) => (
            <div key={c.category}>
              <div className="flex items-center justify-between text-xs mb-1"><span className="font-head font-bold">{c.category}</span><span className="font-mono text-muted-foreground">{c.pct}% · {c.operational}/{c.items} operational</span></div>
              <ProgressBar value={c.pct} accent={c.pct >= 80 ? "142 70% 45%" : c.pct >= 40 ? "35 90% 55%" : "0 84% 60%"} />
            </div>
          ))}</div>
        )}
      </Panel>
      <Panel title="Recovery Items" subtitle="Advance each item Down to Restoring to Validated to Operational." actions={selectedCase ? <button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-recovery-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Item</button> : null}>
        {!selectedCase ? <EmptyState title="No crisis case selected" text="Select a crisis case to coordinate recovery." /> : (
          <>
            {showAdd && (
              <form onSubmit={add} className="rounded-lg border border-border bg-secondary/20 p-4 mb-4 grid md:grid-cols-3 gap-3">
                <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="System / application / service" data-testid="crisis-recovery-name" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm md:col-span-2" />
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} data-testid="crisis-recovery-category" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm">{["System", "Application", "Business Service", "Region", "Business Unit"].map((v) => <option key={v}>{v}</option>)}</select>
                <button disabled={busy === "add"} data-testid="crisis-recovery-submit" className="md:col-span-3 px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Add Recovery Item</button>
              </form>
            )}
            <div className="space-y-2">{items.map((item) => (
              <div key={item.recovery_id} data-testid={`crisis-recovery-${item.recovery_id}`} className="rounded-lg border border-border bg-secondary/20 p-3 grid xl:grid-cols-[1.4fr_.6fr_.8fr_auto] gap-3 items-center">
                <div><div className="font-head font-bold text-sm">{item.name}</div><div className="text-[10px] text-muted-foreground mt-1">{item.category}</div></div>
                <StatusPill value={item.status} />
                <div className="w-full"><ProgressBar value={item.pct} accent={item.pct >= 80 ? "142 70% 45%" : item.pct >= 40 ? "35 90% 55%" : "0 84% 60%"} /></div>
                <div>{item.status !== "Operational" && <button onClick={() => advance(item)} disabled={busy === item.recovery_id} data-testid={`crisis-recovery-advance-${item.recovery_id}`} className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Advance</button>}</div>
              </div>
            ))}</div>
          </>
        )}
      </Panel>
    </div>
  );
}

function RegulatoryLegal({ selectedCase, caseDetail, changed }) {
  const [busy, setBusy] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ jurisdiction: "", regulation: "", trigger: "", deadline_at: "", responsible: "", evidence_required: "" });
  const obligations = caseDetail?.obligations || [];

  const add = async (event) => {
    event.preventDefault();
    if (!selectedCase) return;
    if (!form.deadline_at) { toast.error("A deadline is required."); return; }
    setBusy("add");
    try {
      await api.post(`/crisis/cases/${selectedCase.ref}/obligations`, { ...form, deadline_at: new Date(form.deadline_at).toISOString() });
      setShowAdd(false);
      setForm({ jurisdiction: "", regulation: "", trigger: "", deadline_at: "", responsible: "", evidence_required: "" });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to add obligation.");
    } finally {
      setBusy("");
    }
  };

  const setStatus = async (o, status) => {
    setBusy(o.obligation_id);
    try {
      await api.patch(`/crisis/cases/${selectedCase.ref}/obligations/${o.obligation_id}`, { status });
      await changed(selectedCase.ref);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to update obligation.");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-5" data-testid="crisis-regulatory">
      <div className="rounded-xl border border-med/30 bg-med/5 p-4 flex items-start gap-3">
        <Scale className="w-5 h-5 text-med shrink-0 mt-0.5" />
        <div className="text-xs text-muted-foreground"><span className="font-head font-bold text-foreground">Evidence-only.</span> Obserra surfaces potential applicability, required evidence and deadlines. It never determines legal obligation as fact — authorized legal counsel confirms whether notification is required.</div>
      </div>
      <Panel title="Regulatory & Legal Command" subtitle="Potential notification obligations with countdown deadlines." actions={selectedCase ? <button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-obligation-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Obligation</button> : null}>
        {!selectedCase ? <EmptyState title="No crisis case selected" text="Select a crisis case to track regulatory obligations." /> : (
          <>
            {showAdd && (
              <form onSubmit={add} className="rounded-lg border border-border bg-secondary/20 p-4 mb-4 grid md:grid-cols-2 gap-3">
                <input required value={form.jurisdiction} onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })} placeholder="Jurisdiction (e.g. EU)" data-testid="crisis-obligation-jurisdiction" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <input required value={form.regulation} onChange={(e) => setForm({ ...form, regulation: e.target.value })} placeholder="Regulation" data-testid="crisis-obligation-regulation" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                <input value={form.trigger} onChange={(e) => setForm({ ...form, trigger: e.target.value })} placeholder="Trigger" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm md:col-span-2" />
                <label className="text-xs text-muted-foreground">Deadline<input required type="datetime-local" value={form.deadline_at} onChange={(e) => setForm({ ...form, deadline_at: e.target.value })} data-testid="crisis-obligation-deadline" className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm" /></label>
                <input value={form.responsible} onChange={(e) => setForm({ ...form, responsible: e.target.value })} placeholder="Responsible attorney" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm self-end" />
                <input value={form.evidence_required} onChange={(e) => setForm({ ...form, evidence_required: e.target.value })} placeholder="Evidence required" className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm md:col-span-2" />
                <button disabled={busy === "add"} data-testid="crisis-obligation-submit" className="md:col-span-2 px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Add Obligation</button>
              </form>
            )}
            {obligations.length === 0 ? <EmptyState title="No obligations tracked" text="Add potential notification obligations to start the countdown clocks." /> : (
              <div className="space-y-3">{obligations.map((o) => {
                const cd = obligationCountdown(o.deadline_at);
                return (
                  <div key={o.obligation_id} data-testid={`crisis-obligation-${o.obligation_id}`} className={`rounded-xl border p-4 ${cd.overdue ? "border-crit/30 bg-crit/5" : cd.urgent ? "border-high/30 bg-high/5" : "border-border bg-secondary/20"}`}>
                    <div className="grid xl:grid-cols-[1.6fr_.7fr_auto] gap-4">
                      <div>
                        <div className="flex items-center gap-2"><Landmark className="w-3.5 h-3.5 text-ai" /><span className="font-head font-bold text-sm">{o.jurisdiction}</span></div>
                        <div className="text-sm mt-1">{o.regulation}</div>
                        <div className="text-xs text-muted-foreground mt-1">{o.trigger || "No trigger documented"}</div>
                        <div className="text-[11px] text-muted-foreground mt-2">Attorney: {o.responsible || "Unassigned"}{o.evidence_required ? ` · Evidence: ${o.evidence_required}` : ""}</div>
                      </div>
                      <div>
                        <div className="text-[9px] font-mono uppercase text-muted-foreground flex items-center gap-1"><Timer className="w-3 h-3" />Deadline</div>
                        <div className={`font-head font-black text-lg mt-1 ${cd.overdue ? "text-crit" : cd.urgent ? "text-high" : ""}`} data-testid={`crisis-obligation-countdown-${o.obligation_id}`}>{cd.label}</div>
                        <div className="text-[10px] text-muted-foreground mt-1">{o.deadline_at ? new Date(o.deadline_at).toLocaleString() : "-"}</div>
                        <div className="mt-2"><StatusPill value={o.status} /></div>
                        <div className="mt-2">
                          <label className="text-[9px] font-mono uppercase text-muted-foreground flex items-center gap-1"><Timer className="w-3 h-3" />Alert threshold</label>
                          <select value={o.notify_within_hours ?? 24} onChange={(e) => setThreshold(o, e.target.value)} disabled={busy === `${o.obligation_id}-thr`} data-testid={`crisis-obligation-threshold-${o.obligation_id}`} className="mt-1 w-full bg-secondary/60 rounded-md px-2 py-1.5 text-xs">
                            {[6, 12, 24, 48, 72].map((h) => <option key={h} value={h}>{`${h}h before deadline`}</option>)}
                          </select>
                        </div>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        {["Notification Required", "Notified", "Not Applicable"].map((s) => (
                          <button key={s} onClick={() => setStatus(o, s)} disabled={busy === o.obligation_id || o.status === s} data-testid={`crisis-obligation-${s.replace(/\s+/g, "-").toLowerCase()}-${o.obligation_id}`} className="px-2.5 py-1.5 rounded-md border border-border text-[10px] font-head font-bold disabled:opacity-40 hover:bg-secondary">{s}</button>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}</div>
            )}
          </>
        )}
      </Panel>
    </div>
  );
}

export default function CyberCrisisCommander() {
  const { mode, user } = useAuth();
  const { data, loading, refreshing, error, sourceStatus, reload } = useCrisisCommanderData();
  const [activeTab, setActiveTab] = useState(() => localStorage.getItem("cyber-crisis-commander-tab") || "mission");
  const [selectedCaseRef, setSelectedCaseRef] = useState(() => localStorage.getItem("cyber-crisis-case-ref") || "");
  const [caseDetail, setCaseDetail] = useState(null);
  const [caseBusy, setCaseBusy] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [demoActive, setDemoActive] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [pirBusy, setPirBusy] = useState(false);
  const [ingestBusy, setIngestBusy] = useState(false);
  const [emailBusy, setEmailBusy] = useState(false);
  const [packBusy, setPackBusy] = useState(false);
  const [unreadMentions, setUnreadMentions] = useState(0);
  const [scenario, setScenario] = useState({ active: false, step: 0, total: 0, done: false, ref: "" });
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [scenarioPlaying, setScenarioPlaying] = useState(false);
  const [scenarioLib, setScenarioLib] = useState([]);
  const [scenarioMenu, setScenarioMenu] = useState(false);
  const [moreMenu, setMoreMenu] = useState(false);
  const [snapshotLink, setSnapshotLink] = useState(null);
  const [snapshotBusy, setSnapshotBusy] = useState(false);
  const canOperate = ["admin", "owner", "executive"].includes(String(user?.role || "").toLowerCase());

  const selectedCase = useMemo(() => {
    if (caseDetail?.case) return caseDetail.case;
    return (data?.cases || []).find((item) => item.ref === selectedCaseRef) || null;
  }, [caseDetail, data, selectedCaseRef]);

  const effectiveData = useMemo(() => {
    if (!data) return data;
    return {
      ...data,
      crisisScore: crisisScore({
        incidents: data.incidents || [],
        risks: data.risks || [],
        controls: data.controls || [],
        actions: caseDetail?.actions || [],
      }),
    };
  }, [data, caseDetail]);

  const openTab = (tab) => {
    setActiveTab(tab);
    localStorage.setItem("cyber-crisis-commander-tab", tab);
  };

  const loadCase = async (ref) => {
    if (!ref) {
      setCaseDetail(null);
      return;
    }
    setCaseBusy(true);
    try {
      const detail = await fetchCrisisCase(ref);
      setCaseDetail(detail);
      setSelectedCaseRef(ref);
      localStorage.setItem("cyber-crisis-case-ref", ref);
    } catch (caseError) {
      toast.error(caseError.response?.data?.detail || "Unable to load crisis case.");
      setCaseDetail(null);
    } finally {
      setCaseBusy(false);
    }
  };

  useEffect(() => {
    if (!data) return;
    let ref = selectedCaseRef;
    if (!ref && data.cases?.length) {
      ref = data.cases.find((item) => item.status !== "Closed")?.ref || data.cases[0]?.ref || "";
    }
    if (ref) loadCase(ref);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.cases?.length]);

  const changed = async (ref) => {
    await Promise.all([reload(), loadCase(ref)]);
  };

  const openScenarioMenu = async () => {
    setScenarioMenu((v) => !v);
    if (scenarioLib.length === 0) {
      try { const { data } = await api.get("/crisis/scenario/library"); setScenarioLib(data.scenarios || []); }
      catch (_) { /* ignore */ }
    }
  };
  const startScenario = async (key = "ransomware") => {
    setScenarioMenu(false);
    setScenarioBusy(true);
    try {
      const { data: res } = await api.post("/crisis/scenario/start", { key });
      setScenario({ active: true, step: res.step, total: res.total, done: false, ref: res.ref });
      setDemoActive(true);
      window.dispatchEvent(new Event("ci-demo-changed"));
      setScenarioPlaying(true);
      await changed(res.ref);
      openTab("timeline");
      toast.success(`${res.label || "Sample breach"} started — playing live.`);
    } catch (e) { toast.error(e.response?.data?.detail || "Unable to start sample breach."); }
    finally { setScenarioBusy(false); }
  };
  const advanceScenario = async () => {
    try {
      const { data: res } = await api.post("/crisis/scenario/advance");
      setScenario((s) => ({ ...s, step: res.step, total: res.total, done: res.done }));
      if (res.done) { setScenarioPlaying(false); toast.success("Sample breach complete — incident resolved."); }
      await changed(scenario.ref);
    } catch (e) { setScenarioPlaying(false); toast.error(e.response?.data?.detail || "Unable to advance scenario."); }
  };
  const stopScenario = async () => {
    setScenarioBusy(true); setScenarioPlaying(false);
    try {
      await api.post("/crisis/scenario/stop");
      setScenario({ active: false, step: 0, total: 0, done: false, ref: "" });
      setDemoActive(false);
      window.dispatchEvent(new Event("ci-demo-changed"));
      await reload();
      toast.success("Sample breach cleared.");
    } catch (e) { toast.error(e.response?.data?.detail || "Unable to stop scenario."); }
    finally { setScenarioBusy(false); }
  };
  const shareSnapshot = async () => {
    if (!selectedCase) { toast.error("Select a crisis case first."); return; }
    setSnapshotBusy(true);
    try {
      const { data: res } = await api.post(`/crisis/cases/${selectedCase.ref}/snapshot`, { expires_days: 7 });
      const url = `${window.location.origin}${res.path}`;
      setSnapshotLink({ url, expires_at: res.expires_at });
      try { await navigator.clipboard?.writeText(url); } catch (_) { /* clipboard blocked */ }
      toast.success("Board snapshot link created & copied — expires in 7 days.");
    } catch (e) { toast.error(e.response?.data?.detail || "Unable to create snapshot link."); }
    finally { setSnapshotBusy(false); }
  };
  const revokeSnapshot = async () => {
    if (!selectedCase) return;
    try { await api.post(`/crisis/cases/${selectedCase.ref}/snapshot/revoke`); setSnapshotLink(null); toast.success("Snapshot link revoked."); }
    catch (e) { toast.error(e.response?.data?.detail || "Unable to revoke snapshot."); }
  };

  useEffect(() => {
    api.get("/crisis/scenario/status").then((r) => {
      if (r.data?.active) setScenario({ active: true, step: r.data.step, total: r.data.total, done: r.data.done, ref: r.data.ref });
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!scenarioPlaying || !scenario.active || scenario.done) return;
    const id = setTimeout(() => { advanceScenario(); }, 4000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarioPlaying, scenario.active, scenario.done, scenario.step]);

  const created = async (createdCase) => {
    await reload();
    await loadCase(createdCase.ref);
    openTab("command");
    toast.success(`${createdCase.ref} crisis case opened.`);
  };

  const generateReport = async () => {
    if (!effectiveData) return;
    setReportBusy(true);
    try {
      const response = await api.post(
        "/studio/report/pdf",
        {
          title: "Cyber Crisis Executive Brief",
          ai_narrative:
            `This brief is grounded in the selected Obserra crisis case, current incidents, risk exposure, control posture, response actions, decision state and audit evidence. Crisis score and response progress are modeled decision-support metrics. External containment is not claimed unless a connected execution system verifies it. Generated by Obserra Cyber Crisis Commander ${APP_VERSION_LABEL}.`,
          blocks: executiveBriefBlocks({ data: effectiveData, selectedCase, caseDetail }),
        },
        { responseType: "blob" }
      );
      downloadBlob(response.data, "obserra-cyber-crisis-executive-brief.pdf");
      toast.success("Cyber Crisis Executive Brief generated.");
    } catch (reportError) {
      toast.error(reportError.response?.data?.detail || "Unable to generate crisis executive brief.");
    } finally {
      setReportBusy(false);
    }
  };

  useEffect(() => {
    api.get("/crisis/demo/status").then((r) => setDemoActive(!!r.data.active)).catch(() => {});
  }, []);

  const toggleDemo = async () => {
    setDemoBusy(true);
    try {
      if (demoActive) {
        await api.post("/crisis/demo/clear");
        toast.success("Crisis demo scenario cleared.");
        setCaseDetail(null);
        setSelectedCaseRef("");
        localStorage.removeItem("cyber-crisis-case-ref");
      } else {
        const r = await api.post("/crisis/demo/seed");
        toast.success("Staged ransomware demo scenario loaded.");
        if (r.data.ref) {
          setSelectedCaseRef(r.data.ref);
          localStorage.setItem("cyber-crisis-case-ref", r.data.ref);
        }
      }
      await reload();
      const s = await api.get("/crisis/demo/status");
      setDemoActive(!!s.data.active);
      window.dispatchEvent(new Event("ci-demo-changed"));
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to toggle demo mode.");
    } finally {
      setDemoBusy(false);
    }
  };

  const generatePIR = async () => {
    if (!effectiveData || !selectedCase) return;
    setPirBusy(true);
    try {
      const response = await api.post(
        "/studio/report/pdf",
        {
          title: `Post-Incident Review — ${selectedCase.ref}`,
          ai_narrative: `Post-incident review for ${selectedCase.title}, compiled from the persistent, audit-logged crisis record. Generated by Obserra Cyber Crisis Commander ${APP_VERSION_LABEL}.`,
          blocks: pirBlocks({ data: effectiveData, selectedCase, caseDetail }),
        },
        { responseType: "blob" }
      );
      downloadBlob(response.data, `obserra-post-incident-review-${selectedCase.ref}.pdf`);
      toast.success("Post-Incident Review generated.");
    } catch (pirError) {
      toast.error(pirError.response?.data?.detail || "Unable to generate post-incident review.");
    } finally {
      setPirBusy(false);
    }
  };

  const generateReportPack = async () => {
    if (!selectedCase) return;
    setPackBusy(true);
    try {
      const response = await api.get(`/crisis/cases/${selectedCase.ref}/report-pack.pdf`, { responseType: "blob" });
      downloadBlob(response.data, `obserra-crisis-report-pack-${selectedCase.ref}.pdf`);
      toast.success("Post-crisis report pack generated.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to generate report pack.");
    } finally {
      setPackBusy(false);
    }
  };

  const ingestServiceNow = async () => {
    setIngestBusy(true);
    try {
      const { data: res } = await api.post("/crisis/ingest/servicenow");
      toast.success(`ServiceNow: ${res.ingested} new case(s) opened, ${res.skipped} already tracked.`);
      await reload();
      if (res.refs?.[0]) loadCase(res.refs[0]);
    } catch (e) {
      toast.error(e.response?.data?.detail || "ServiceNow ingestion failed.");
    } finally {
      setIngestBusy(false);
    }
  };

  const emailBrief = async () => {
    if (!selectedCase) { toast.error("Select a crisis case first."); return; }
    setEmailBusy(true);
    try {
      const { data: res } = await api.post(`/crisis/cases/${selectedCase.ref}/email-brief`);
      toast.success(`Board brief emailed to ${res.sent} recipient(s).`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to email the board brief.");
    } finally {
      setEmailBusy(false);
    }
  };

  const setBriefCadence = async (hours) => {
    if (!selectedCase) return;
    try {
      await api.patch(`/crisis/cases/${selectedCase.ref}`, { brief_schedule_hours: Number(hours) });
      toast.success(Number(hours) > 0 ? `Auto-brief every ${hours}h enabled.` : "Auto-brief disabled.");
      await changed(selectedCase.ref);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to update auto-brief cadence.");
    }
  };

  const setSitrepCadence = async (hours) => {
    if (!selectedCase) return;
    try {
      await api.patch(`/crisis/cases/${selectedCase.ref}`, { sitrep_schedule_hours: Number(hours) });
      toast.success(Number(hours) > 0 ? `Auto-SITREP every ${hours}h enabled.` : "Auto-SITREP disabled.");
      await changed(selectedCase.ref);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to update auto-SITREP cadence.");
    }
  };

  // War Room Live Sync — poll the case detail while the War Room tab is open so
  // the roster and pending decisions update without a manual refresh.
  useEffect(() => {
    if (activeTab !== "warroom" || !selectedCaseRef) return undefined;
    const id = setInterval(() => { loadCase(selectedCaseRef); }, 8000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedCaseRef]);

  // Unread war-room @mentions badge — count messages that mention me since I last
  // opened the War Room tab; clears while I'm viewing it.
  useEffect(() => {
    if (!selectedCaseRef) { setUnreadMentions(0); return undefined; }
    let active = true;
    const mine = [user?.name, user?.email].filter(Boolean);
    const myRole = String(user?.role || "").toLowerCase();
    const seenKey = `crisis-warroom-seen-${selectedCaseRef}`;
    const mentionsMe = (m) => Array.isArray(m.mentions) && m.mentions.some((x) => (x.name && mine.includes(x.name)) || (x.role && myRole && x.role.toLowerCase().includes(myRole)));
    const compute = async () => {
      if (activeTab === "warroom") { localStorage.setItem(seenKey, String(Date.now())); setUnreadMentions(0); return; }
      try {
        const r = await api.get(`/crisis/cases/${selectedCaseRef}/messages`);
        if (!active) return;
        const seen = Number(localStorage.getItem(seenKey) || 0);
        const count = (r.data || []).filter((m) => mentionsMe(m) && m.author && !mine.includes(m.author) && new Date(m.created_at).getTime() > seen).length;
        setUnreadMentions(count);
      } catch { /* ignore */ }
    };
    compute();
    const id = setInterval(compute, 15000);
    return () => { active = false; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCaseRef, activeTab, user]);

  if (loading && !data) {
    return (
      <div className="min-h-[55vh] flex items-center justify-center">
        <div className="text-center"><Loader2 className="w-7 h-7 animate-spin text-primary mx-auto" /><div className="text-sm text-muted-foreground mt-3">Loading crisis command intelligence</div></div>
      </div>
    );
  }

  return (
    <div className="rise space-y-6" data-testid="cyber-crisis-commander-page">
      <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap"><Siren className="w-7 h-7 text-crit" /><h1 className="font-head font-black text-3xl tracking-tight">Cyber Crisis Commander</h1><span className="px-2 py-1 rounded-full border border-crit/25 bg-crit/10 text-crit text-[10px] font-mono">EXECUTIVE INCIDENT COMMAND</span><span data-testid="crisis-version-badge" className="px-2 py-1 rounded-full border border-border bg-secondary/40 text-muted-foreground text-[10px] font-mono">{APP_VERSION_LABEL}</span></div>
          <p className="text-sm text-muted-foreground mt-2 max-w-4xl">{mode === "executive" ? "Command enterprise cyber crises through business impact, financial exposure, executive decisions, containment, recovery, control failures, timeline evidence and board-ready intelligence." : "Coordinate persistent crisis cases, response actions, approvals, control failures, incident evidence, audit records and recovery using the existing Obserra platform services."}</p>
          <div className="text-[10px] font-mono text-muted-foreground mt-2">Current case: {selectedCase?.ref || "none"} · Data refresh {effectiveData?.generatedAt ? new Date(effectiveData.generatedAt).toLocaleString() : "unavailable"}{caseBusy ? " · refreshing case" : ""}</div>
        </div>
        <div className="flex flex-wrap gap-2">{canOperate && <button onClick={toggleDemo} disabled={demoBusy} data-testid="crisis-demo-toggle" className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-md border text-xs font-head font-bold disabled:opacity-50 ${demoActive ? "border-ai/40 bg-ai/15 text-ai" : "border-border bg-secondary/40"}`}>{demoBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : demoActive ? <Square className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}{demoActive ? "Exit Demo" : "Demo Mode"}</button>}{canOperate && (scenario.active ? (
          <div className="inline-flex items-center gap-1 rounded-md border border-ai/40 bg-ai/10 px-1.5 py-1" data-testid="crisis-scenario-controls">
            <button onClick={() => setScenarioPlaying((v) => !v)} disabled={scenario.done} data-testid="crisis-scenario-play" title={scenarioPlaying ? "Pause" : "Play"} className="p-1.5 rounded text-ai hover:bg-ai/15 disabled:opacity-40">{scenarioPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}</button>
            <button onClick={advanceScenario} disabled={scenario.done} data-testid="crisis-scenario-step" title="Next step" className="p-1.5 rounded text-ai hover:bg-ai/15 disabled:opacity-40"><SkipForward className="w-3.5 h-3.5" /></button>
            <span data-testid="crisis-scenario-progress" className="px-1.5 text-[10px] font-mono text-ai">{scenario.done ? "Resolved" : `Step ${scenario.step}/${scenario.total}`}</span>
            <button onClick={stopScenario} disabled={scenarioBusy} data-testid="crisis-scenario-stop" title="Stop & clear" className="p-1.5 rounded text-crit hover:bg-crit/15 disabled:opacity-40"><Square className="w-3.5 h-3.5" /></button>
          </div>
        ) : (
          <div className="relative" data-testid="crisis-scenario-menu-wrap">
            <button onClick={openScenarioMenu} disabled={scenarioBusy} data-testid="crisis-scenario-start" title="Play a scripted sample breach — pick a storyline" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 bg-ai/10 text-ai text-xs font-head font-bold disabled:opacity-50">{scenarioBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Rss className="w-3.5 h-3.5" />}Sample Breach</button>
            {scenarioMenu && (
              <div className="absolute right-0 mt-2 w-72 z-50 rounded-lg border border-border bg-popover shadow-xl p-1.5" data-testid="crisis-scenario-list">
                <div className="px-2 py-1.5 text-[9px] font-mono uppercase tracking-widest text-muted-foreground">Pick a storyline</div>
                {(scenarioLib.length ? scenarioLib : [{ key: "ransomware", label: "Ransomware — Order Fulfillment", description: "Loading storylines…", steps: 9 }]).map((s) => (
                  <button key={s.key} onClick={() => startScenario(s.key)} data-testid={`crisis-scenario-pick-${s.key}`} className="w-full text-left px-2.5 py-2 rounded-md hover:bg-secondary transition-colors">
                    <div className="text-xs font-head font-bold">{s.label}</div>
                    <div className="text-[10px] text-muted-foreground leading-snug">{s.description}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}<button onClick={reload} disabled={refreshing} data-testid="crisis-refresh-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{refreshing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh</button><button onClick={() => openTab("briefing")} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Download className="w-3.5 h-3.5" />Executive Brief</button><div className="relative" data-testid="crisis-more-wrap"><button onClick={() => setMoreMenu((v) => !v)} data-testid="crisis-more-btn" title="More actions" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><MoreVertical className="w-3.5 h-3.5" />More</button>{moreMenu && (<div className="absolute right-0 mt-2 w-64 z-50 rounded-lg border border-border bg-popover shadow-xl p-1.5 flex flex-col gap-1" data-testid="crisis-more-menu">{canOperate && selectedCase && <button onClick={shareSnapshot} disabled={snapshotBusy} data-testid="crisis-share-snapshot-btn" title="Create a public, mobile-friendly board snapshot link" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{snapshotBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Share2 className="w-3.5 h-3.5" />}Share Snapshot</button>}{selectedCase?.status === "Closed" && <button onClick={generatePIR} disabled={pirBusy} data-testid="crisis-pir-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{pirBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ClipboardList className="w-3.5 h-3.5" />}Post-Incident Review</button>}{selectedCase?.status === "Closed" && <button onClick={generateReportPack} disabled={packBusy} data-testid="crisis-report-pack-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{packBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}Report Pack</button>}{canOperate && <button onClick={ingestServiceNow} disabled={ingestBusy} data-testid="crisis-ingest-servicenow-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{ingestBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CloudDownload className="w-3.5 h-3.5" />}Ingest ServiceNow</button>}{canOperate && selectedCase && <button onClick={emailBrief} disabled={emailBusy} data-testid="crisis-email-brief-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{emailBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}Email Board Brief</button>}{canOperate && selectedCase && <select value={selectedCase.brief_schedule_hours || 0} onChange={(e) => setBriefCadence(e.target.value)} data-testid="crisis-brief-cadence" title="Auto-email the board brief on a cadence while the crisis is active" className="px-2 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">{[[0, "Auto-brief: Off"], [4, "Auto-brief: 4h"], [12, "Auto-brief: 12h"], [24, "Auto-brief: 24h"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>}{canOperate && selectedCase && <select value={selectedCase.sitrep_schedule_hours || 0} onChange={(e) => setSitrepCadence(e.target.value)} data-testid="crisis-sitrep-cadence" title="Auto-post a containment SITREP to Teams/Slack while the crisis is active" className="px-2 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">{[[0, "Auto-SITREP: Off"], [4, "Auto-SITREP: 4h"], [12, "Auto-SITREP: 12h"], [24, "Auto-SITREP: 24h"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>}<button onClick={() => setTourOpen(true)} data-testid="crisis-walkthrough-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-crit/30 bg-crit/10 text-crit text-xs font-head font-bold"><Siren className="w-3.5 h-3.5" />Walkthrough</button></div>)}</div></div>
      </div>

      {snapshotLink && (
        <div className="rounded-xl border border-ai/30 bg-ai/5 p-3 flex flex-wrap items-center gap-3" data-testid="crisis-snapshot-bar">
          <Link2 className="w-4 h-4 text-ai shrink-0" />
          <span className="text-xs font-head font-bold shrink-0">Board snapshot link</span>
          <input readOnly value={snapshotLink.url} data-testid="crisis-snapshot-url" onFocus={(e) => e.target.select()} className="flex-1 min-w-[200px] bg-secondary/60 rounded-md px-3 py-1.5 text-xs font-mono" />
          <button onClick={() => { navigator.clipboard?.writeText(snapshotLink.url); toast.success("Link copied."); }} data-testid="crisis-snapshot-copy" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><Copy className="w-3.5 h-3.5" />Copy</button>
          <a href={snapshotLink.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">Open</a>
          <button onClick={revokeSnapshot} data-testid="crisis-snapshot-revoke" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-crit/40 bg-crit/10 text-crit text-xs font-head font-bold">Revoke</button>
          <span className="text-[10px] font-mono text-muted-foreground">expires {snapshotLink.expires_at ? new Date(snapshotLink.expires_at).toLocaleDateString() : "—"}</span>
        </div>
      )}

      {scenario.done && selectedCase && canOperate && <PresentToBoard selectedCase={selectedCase} variant="banner" />}

      {error && <div className="rounded-xl border border-crit/30 bg-crit/5 p-4 flex items-start gap-3" data-testid="crisis-error"><AlertTriangle className="w-5 h-5 text-crit shrink-0 mt-0.5" /><div><div className="font-head font-bold text-sm">Crisis intelligence incomplete</div><div className="text-xs text-muted-foreground mt-1">{error}</div></div></div>}

      <AIInsight dashboard="Cyber Crisis Commander" endpoint={selectedCase ? `/crisis/insight?ref=${selectedCase.ref}` : "/crisis/insight"} groundingLabel="the live crisis case, decisions, recovery & regulatory clocks" accent="0 84% 60%" auto slug="cyber-crisis-commander" />

      <div className="overflow-x-auto"><div className="inline-flex min-w-max rounded-xl border border-border bg-card p-1">{TABS.map(([id, label, Icon]) => <button key={id} onClick={() => openTab(id)} data-testid={`crisis-tab-${id}`} className={`relative inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-head font-bold transition-colors ${activeTab === id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"}`}><Icon className="w-3.5 h-3.5" />{label}{id === "warroom" && unreadMentions > 0 && <span data-testid="crisis-warroom-unread" className="ml-1 min-w-[16px] h-4 px-1 rounded-full bg-crit text-white text-[9px] font-mono inline-flex items-center justify-center">{unreadMentions}</span>}</button>)}</div></div>

      {activeTab === "mission" && <MissionControl data={effectiveData} selectedCase={selectedCase} caseDetail={caseDetail} openTab={openTab} />}
      {activeTab === "command" && <div className="space-y-5"><IncidentCommand data={effectiveData} selectedCase={selectedCase} caseDetail={caseDetail} loadCase={loadCase} changed={changed} created={created} />{canOperate && <WebhookFeed />}{canOperate && <NativeConnectors />}</div>}
      {activeTab === "decisions" && <DecisionRoom selectedCase={selectedCase} caseDetail={caseDetail} recommendations={effectiveData?.recommendations || []} decisions={effectiveData?.decisions || []} changed={changed} />}
      {activeTab === "impact" && <BusinessImpact data={effectiveData} selectedCase={selectedCase} />}
      {activeTab === "response" && <div className="space-y-5"><ResponseActions selectedCase={selectedCase} caseDetail={caseDetail} changed={changed} /><EntraContainment selectedCase={selectedCase} changed={changed} /></div>}
      {activeTab === "warroom" && <div className="space-y-5">{canOperate && <WarRoomBroadcast selectedCase={selectedCase} changed={changed} />}<WarRoom selectedCase={selectedCase} caseDetail={caseDetail} changed={changed} user={user} live={activeTab === "warroom"} /></div>}
      {activeTab === "recovery" && <RecoveryCommand selectedCase={selectedCase} caseDetail={caseDetail} changed={changed} />}
      {activeTab === "regulatory" && <RegulatoryLegal selectedCase={selectedCase} caseDetail={caseDetail} changed={changed} />}
      {activeTab === "controls" && <ControlFailures data={effectiveData} />}
      {activeTab === "timeline" && <TimelineEvidence selectedCase={selectedCase} caseDetail={caseDetail} data={effectiveData} changed={changed} />}
      {activeTab === "briefing" && <ExecutiveBriefing data={effectiveData} selectedCase={selectedCase} caseDetail={caseDetail} reportBusy={reportBusy} generateReport={generateReport} />}
      {activeTab === "board" && <BoardCrisisDashboard selectedCase={selectedCase} />}
      {activeTab === "defensibility" && <Defensibility data={effectiveData} sourceStatus={sourceStatus} />}

      <CrisisTour open={tourOpen} onClose={() => setTourOpen(false)} openTab={openTab} />
    </div>
  );
}
