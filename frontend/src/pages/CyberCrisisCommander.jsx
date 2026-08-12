import { useEffect, useMemo, useState } from "react";
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
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Wrench,
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
} from "@/lib/crisisCommanderModels";
import {
  fetchCrisisCase,
  useCrisisCommanderData,
} from "@/hooks/useCrisisCommanderData";
import { APP_VERSION_LABEL } from "@/version";
import { CrisisTour } from "@/components/crisis/CrisisTour";

const TABS = [
  ["mission", "Mission Control", Gauge],
  ["command", "Incident Command", Siren],
  ["decisions", "Decision Room", Gavel],
  ["impact", "Business Impact", Banknote],
  ["response", "Containment & Recovery", Wrench],
  ["controls", "Control Failures", ShieldAlert],
  ["timeline", "Timeline & Evidence", GitCommitVertical],
  ["briefing", "Executive Briefing", FileText],
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
        <Panel testid="crisis-active-command" title="Active crisis command" subtitle="Persistent crisis leadership and phase state.">
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

        <Panel testid="crisis-response-status" title="Response action status" subtitle="Persistent response, recovery, legal, communication and decision actions.">
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

        <Panel testid="crisis-control-failure" title="Control failure intelligence" subtitle="Current control failures, drift and stale evidence.">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-crit/5 border border-crit/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Failing</div><div className="font-head font-black text-2xl mt-1 text-crit">{controls.failing}</div></div>
            <div className="rounded-lg bg-high/5 border border-high/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Drifting</div><div className="font-head font-black text-2xl mt-1 text-high">{controls.drifting}</div></div>
            <div className="rounded-lg bg-med/5 border border-med/20 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Evidence stale</div><div className="font-head font-black text-2xl mt-1 text-med">{controls.stale}</div></div>
            <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Unique attention</div><div className="font-head font-black text-2xl mt-1">{controls.totalAttention}</div></div>
          </div>
          <button onClick={() => openTab("controls")} data-testid="crisis-review-controls" className="mt-4 w-full px-3 py-2 rounded-md border border-border bg-secondary text-xs font-head font-bold">Review Control Failures</button>
        </Panel>
      </div>

      <Panel testid="crisis-top-risks" title="Highest residual enterprise risks" subtitle="Current risk records that may amplify crisis impact.">
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
      <Panel title="Crisis cases" subtitle="Persistent organization-scoped crisis cases." actions={<button onClick={() => setShowCreate((value) => !value)} data-testid="crisis-new-case-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />New Crisis</button>}>
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

      <Panel title="Incident command" subtitle="Leadership, phase, status and command summary.">
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

  return (
    <div className="space-y-5" data-testid="crisis-decision-room">
      <Panel title="Executive approval queue" subtitle="Persistent crisis decisions with business and technical impact context." actions={selectedCase ? <button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-decision-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Decision</button> : null}>
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
                    <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Approval owner</div><div className="text-sm font-medium mt-1">{action.decision_owner || "Unassigned"}</div><div className="mt-3"><StatusPill value={action.status} /></div></div>
                    <div className="flex items-center">{action.status === "Awaiting Approval" ? <button onClick={() => approve(action)} disabled={busy === action.action_id} data-testid={`crisis-approve-${action.action_id}`} className="px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold inline-flex items-center gap-1.5 disabled:opacity-50">{busy === action.action_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}Approve</button> : <StatusPill value={action.status} />}</div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </Panel>
      <div className="grid xl:grid-cols-2 gap-5">
        <Panel title="Existing Obserra recommendations" subtitle="Current recommendation inventory for crisis context."><div className="space-y-2">{(recommendations || []).slice(0, 10).map((item) => <div key={item.ref} className="rounded-lg border border-border p-3"><div className="flex items-start justify-between gap-3"><div><div className="font-mono text-[10px] text-ai">{item.ref}</div><div className="text-sm font-medium mt-1">{item.title}</div></div><StatusPill value={item.status} /></div></div>)}</div></Panel>
        <Panel title="Existing executive decisions" subtitle="Current decision register, preserved separately from crisis actions."><div className="space-y-2">{(decisions || []).slice(0, 10).map((item) => <div key={item.ref} className="rounded-lg border border-border p-3"><div className="font-mono text-[10px] text-ai">{item.ref}</div><div className="text-sm font-medium mt-1">{item.title}</div><div className="text-xs text-muted-foreground mt-2">Chosen: {item.chosen || "-"} · Approver: {item.approver || "-"}</div></div>)}</div></Panel>
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
      <Panel title="Financial exposure by enterprise risk" subtitle="Existing residual ALE from the current risk engine. No crisis loss values are invented.">
        <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><tr><th className="text-left py-3 pr-3">Risk</th><th className="text-left py-3 px-3">Rating</th><th className="text-right py-3 px-3">Residual</th><th className="text-right py-3 px-3">Residual ALE</th><th className="text-left py-3 pl-3">Owner</th></tr></thead><tbody>{risks.map((risk) => <tr key={risk.ref} className="border-b border-border/60"><td className="py-3 pr-3"><div className="font-mono text-[10px] text-ai">{risk.ref}</div><div className="font-medium mt-1">{risk.title}</div></td><td className="py-3 px-3"><StatusPill value={risk.rating || "Risk"} /></td><td className="py-3 px-3 text-right font-mono">{risk.residual}</td><td className="py-3 px-3 text-right font-mono">{money(risk.residual_ale)}</td><td className="py-3 pl-3 text-muted-foreground">{risk.owner || "Unassigned"}</td></tr>)}</tbody></table></div>
      </Panel>
      <Panel title="Business service impact" subtitle="Only explicitly linked business services are shown as crisis affected.">{services.length ? <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">{services.map((service) => <div key={service} className="rounded-lg border border-border bg-secondary/20 p-3"><div className="font-head font-bold text-sm">{service}</div></div>)}</div> : <EmptyState title="No business services linked" text="Link business services to the crisis case to support enterprise impact analysis." />}</Panel>
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
    <Panel testid="crisis-response-actions" title="Containment and recovery command" subtitle="Persistent response actions. External containment is not claimed until execution is verified by an integrated system." actions={selectedCase ? <button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-action-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Action</button> : null}>
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
      <Panel title="Control failures affecting crisis posture" subtitle="Existing control effectiveness, maturity, drift and evidence state."><div className="space-y-3">{attention.map((control) => <div key={control.control_id} className="rounded-xl border border-border bg-secondary/20 p-4"><div className="grid xl:grid-cols-[1.4fr_.6fr_.6fr_.7fr] gap-4"><div><div className="font-mono text-[10px] text-ai">{control.control_id}</div><div className="font-head font-bold mt-1">{control.name}</div><div className="text-xs text-muted-foreground mt-1">{control.category} · {control.owner || "Unassigned"}</div></div><div><div className="text-[9px] font-mono uppercase text-muted-foreground">Status</div><div className="mt-2"><StatusPill value={control.status} /></div></div><div><div className="text-[9px] font-mono uppercase text-muted-foreground">Effectiveness</div><div className="font-head font-black text-xl mt-1">{control.effectiveness}%</div></div><div><div className="text-[9px] font-mono uppercase text-muted-foreground">Evidence</div><div className="text-sm mt-1">{control.stale ? "Expired" : `${control.days_to_expiry ?? "-"} days to expiry`}</div></div></div></div>)}</div></Panel>
      <Panel title="Framework readiness during crisis" subtitle="Current control framework coverage for audit and response assurance."><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">{frameworks.map((framework) => <div key={framework.framework} className="rounded-lg border border-border p-3"><div className="font-head font-bold text-sm">{framework.framework}</div><div className="font-head font-black text-2xl mt-2">{framework.coverage}%</div><div className="text-xs text-muted-foreground mt-1">{framework.passing}/{framework.controls} controls passing</div></div>)}</div></Panel>
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
    <Panel testid="crisis-timeline" title="Crisis timeline and evidence" subtitle="Merged crisis events, incident timestamps and recent audit records." actions={selectedCase ? <button onClick={() => setShowAdd((v) => !v)} data-testid="crisis-add-event-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Plus className="w-3.5 h-3.5" />Add Timeline Event</button> : null}>
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
      <Panel title="Obserra Crisis Advisor" subtitle="Executive analysis grounded in current crisis case, incidents, risks, controls and response status."><AIExplain title={selectedCase?.title || "Enterprise cyber crisis posture"} kind="cyber crisis executive decision business impact containment recovery" context={context} accent="0 84% 60%" /></Panel>
      <Panel title="Board and executive reporting" subtitle="Uses the existing Obserra Studio PDF service."><button onClick={generateReport} disabled={reportBusy} data-testid="crisis-generate-brief" className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold disabled:opacity-50">{reportBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}Generate Cyber Crisis Executive Brief</button></Panel>
    </div>
  );
}

function Defensibility({ data, sourceStatus }) {
  const connectors = data.connectorHealth?.connectors || [];
  const labels = { risks: "Risk Register", incidents: "AI Incidents", recommendations: "Recommendations", decisions: "Decision Register", audit: "Audit", controls: "Control Monitoring", compliance: "Control Compliance", strategic: "Risk Engine Strategic", tactical: "Risk Engine Tactical", workflows: "Workflow Engine", connectorHealth: "Connector Health", cases: "Crisis Commander" };

  return (
    <div className="space-y-5" data-testid="crisis-defensibility">
      <div className="grid xl:grid-cols-3 gap-5">
        <Panel title="Data source status" subtitle="Unavailable source data is surfaced, never replaced."><div className="space-y-2">{Object.entries(sourceStatus || {}).map(([key, status]) => <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5"><div className="text-sm font-medium">{labels[key] || key}</div><span className={`text-[10px] font-mono ${status.ok ? "text-low" : "text-crit"}`}>{status.ok ? "LIVE" : "UNAVAILABLE"}</span></div>)}</div></Panel>
        <Panel title="Evidence classification" subtitle="Source records, models and AI interpretation remain distinct."><div className="space-y-4"><div className="rounded-lg border border-border p-4"><DataClassBadge kind="FACT" /><p className="text-xs text-muted-foreground mt-2">Crisis cases, incidents, risks, controls, decisions, audit events, workflows, financial ALE and response actions.</p></div><div className="rounded-lg border border-border p-4"><DataClassBadge kind="MODELLED" /><p className="text-xs text-muted-foreground mt-2">Enterprise crisis score and response progress.</p></div><div className="rounded-lg border border-border p-4"><DataClassBadge kind="AI RECOMMENDATION" /><p className="text-xs text-muted-foreground mt-2">Obserra Crisis Advisor summaries and recommendations.</p></div></div></Panel>
        <Panel title="Execution boundary" subtitle="Crisis orchestration records are not confused with external defensive execution."><div className="space-y-3 text-sm"><div>External isolation, token revocation, SAP suspension or cloud containment is not claimed unless a connected execution system verifies the action.</div><div>Crisis case updates and action changes are written into the existing audit stream.</div><div>"Executing" means the response team marked execution in Obserra, not that an external system has been independently verified.</div></div></Panel>
      </div>
      <Panel title="Connector health context" subtitle="Existing enterprise connector telemetry available to crisis leadership.">{connectors.length ? <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">{connectors.map((connector) => <div key={`${connector.id}:${connector.name}`} className="rounded-lg border border-border p-3"><div className="font-head font-bold text-sm">{connector.name}</div><div className="text-[10px] text-muted-foreground mt-1">{connector.category}</div><div className="text-[10px] font-mono mt-2">{connector.health || connector.state || "unknown"}</div></div>)}</div> : <EmptyState title="No connector health data" text="No connector health records are currently returned." />}</Panel>
    </div>
  );
}

export default function CyberCrisisCommander() {
  const { mode } = useAuth();
  const { data, loading, refreshing, error, sourceStatus, reload } = useCrisisCommanderData();
  const [activeTab, setActiveTab] = useState(() => localStorage.getItem("cyber-crisis-commander-tab") || "mission");
  const [selectedCaseRef, setSelectedCaseRef] = useState(() => localStorage.getItem("cyber-crisis-case-ref") || "");
  const [caseDetail, setCaseDetail] = useState(null);
  const [caseBusy, setCaseBusy] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);

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
        <div className="flex gap-2"><button onClick={() => setTourOpen(true)} data-testid="crisis-walkthrough-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-crit/30 bg-crit/10 text-crit text-xs font-head font-bold"><Siren className="w-3.5 h-3.5" />Walkthrough</button><button onClick={reload} disabled={refreshing} data-testid="crisis-refresh-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{refreshing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh</button><button onClick={() => openTab("briefing")} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"><Download className="w-3.5 h-3.5" />Executive Brief</button></div>
      </div>

      {error && <div className="rounded-xl border border-crit/30 bg-crit/5 p-4 flex items-start gap-3" data-testid="crisis-error"><AlertTriangle className="w-5 h-5 text-crit shrink-0 mt-0.5" /><div><div className="font-head font-bold text-sm">Crisis intelligence incomplete</div><div className="text-xs text-muted-foreground mt-1">{error}</div></div></div>}

      <AIInsight dashboard="Cyber Crisis Commander" accent="0 84% 60%" auto slug="cyber-crisis-commander" />

      <div className="overflow-x-auto"><div className="inline-flex min-w-max rounded-xl border border-border bg-card p-1">{TABS.map(([id, label, Icon]) => <button key={id} onClick={() => openTab(id)} data-testid={`crisis-tab-${id}`} className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-head font-bold transition-colors ${activeTab === id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"}`}><Icon className="w-3.5 h-3.5" />{label}</button>)}</div></div>

      {activeTab === "mission" && <MissionControl data={effectiveData} selectedCase={selectedCase} caseDetail={caseDetail} openTab={openTab} />}
      {activeTab === "command" && <IncidentCommand data={effectiveData} selectedCase={selectedCase} caseDetail={caseDetail} loadCase={loadCase} changed={changed} created={created} />}
      {activeTab === "decisions" && <DecisionRoom selectedCase={selectedCase} caseDetail={caseDetail} recommendations={effectiveData?.recommendations || []} decisions={effectiveData?.decisions || []} changed={changed} />}
      {activeTab === "impact" && <BusinessImpact data={effectiveData} selectedCase={selectedCase} />}
      {activeTab === "response" && <ResponseActions selectedCase={selectedCase} caseDetail={caseDetail} changed={changed} />}
      {activeTab === "controls" && <ControlFailures data={effectiveData} />}
      {activeTab === "timeline" && <TimelineEvidence selectedCase={selectedCase} caseDetail={caseDetail} data={effectiveData} changed={changed} />}
      {activeTab === "briefing" && <ExecutiveBriefing data={effectiveData} selectedCase={selectedCase} caseDetail={caseDetail} reportBusy={reportBusy} generateReport={generateReport} />}
      {activeTab === "defensibility" && <Defensibility data={effectiveData} sourceStatus={sourceStatus} />}

      <CrisisTour open={tourOpen} onClose={() => setTourOpen(false)} openTab={openTab} />
    </div>
  );
}
