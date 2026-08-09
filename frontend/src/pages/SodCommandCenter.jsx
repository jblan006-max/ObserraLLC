import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { useDeepDive } from "@/context/DeepDiveContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { GitCompare, ShieldAlert, ShieldCheck, FlaskConical, ScrollText, Wrench, Bot, Mail, CalendarClock, Send, Eye, Download, TrendingUp, FileText, BellRing, FileWarning, Sparkles } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const SEV = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "190 90% 50%", Low: "142 70% 45%" };
const Chip = ({ v, map = SEV }) => <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${map[v] || "220 10% 55%"} / 0.15)`, color: `hsl(${map[v] || "220 10% 55%"})` }}>{v}</span>;
const ScoreTile = ({ label, v, suffix = "", accent = "199 89% 48%", testid }) => (
  <div className="rounded-lg bg-secondary/30 p-3" data-testid={testid}>
    <div className="font-head font-black text-2xl" style={{ color: `hsl(${accent})` }}>{v}<span className="text-xs font-normal text-muted-foreground">{suffix}</span></div>
    <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">{label}</div>
  </div>
);
const ACTION_LABEL = { recertify: "Open recertification", revoke_all: "Revoke all roles", deactivate: "De-provision account", lock: "Emergency lock" };
const TrendTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const p = payload[0]?.payload || {};
  return (
    <div className="rounded-lg border border-border bg-card p-2.5 text-xs shadow-lg" style={{ maxWidth: 240 }} data-testid="scorecard-trend-tip">
      <div className="font-bold mb-1">{label} · Gov {p.governance_score}/100</div>
      <div className="text-muted-foreground">Open SoD {p.open_sod} · Auto-rem {p.autoremediated} · Movers {p.movers ?? 0} · Residual {p.residual}</div>
      {p.note && <div className="mt-1.5 pt-1.5 border-t border-border text-[11px]">{p.note}</div>}
    </div>
  );
};

export default function SodCommandCenter() {
  const { openDeepDive } = useDeepDive();
  const [data, setData] = useState(null);
  const [rules, setRules] = useState([]);
  const [people, setPeople] = useState([]);
  const [roles, setRoles] = useState([]);
  const [sev, setSev] = useState("all");
  const [area, setArea] = useState("all");
  const [status, setStatus] = useState("all");
  const [mit, setMit] = useState(null);
  const [control, setControl] = useState("");
  const [mitStatus, setMitStatus] = useState("Mitigated");
  const [busy, setBusy] = useState(false);
  // simulator
  const [simPerson, setSimPerson] = useState("");
  const [simRole, setSimRole] = useState("");
  const [simRoles, setSimRoles] = useState([]);
  const [simResult, setSimResult] = useState(null);
  // auto-remediation engine
  const [arem, setArem] = useState(null);
  const [aremBusy, setAremBusy] = useState(false);
  const [digestBusy, setDigestBusy] = useState(false);
  const [dcfg, setDcfg] = useState(null);
  const [dcfgLocal, setDcfgLocal] = useState(null);
  const [dcfgBusy, setDcfgBusy] = useState(false);
  const [scorecard, setScorecard] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [scoreBusy, setScoreBusy] = useState(false);
  const [evidBusy, setEvidBusy] = useState(false);
  const [scoreAlerts, setScoreAlerts] = useState([]);
  const [scoreMute, setScoreMute] = useState({ muted: false });
  const [muteBusy, setMuteBusy] = useState(false);
  const [approveBusy, setApproveBusy] = useState(false);
  const [why, setWhy] = useState(null);
  const [whyBusy, setWhyBusy] = useState(false);
  const [evidPreview, setEvidPreview] = useState(null);
  const [evidPreviewBusy, setEvidPreviewBusy] = useState(false);
  const [nowTs, setNowTs] = useState(Date.now());

  const loadConflicts = useCallback(async () => {
    const p = new URLSearchParams();
    if (sev !== "all") p.set("severity", sev);
    if (area !== "all") p.set("area", area);
    if (status !== "all") p.set("status", status);
    const { data } = await api.get(`/sap/sod/conflicts?${p.toString()}`);
    setData(data);
  }, [sev, area, status]);
  const loadArem = useCallback(async () => { const { data } = await api.get("/sap/autoremediation"); setArem(data); }, []);
  const loadDcfg = useCallback(async () => { const { data } = await api.get("/sap/digest/config"); setDcfg(data); setDcfgLocal({ ...data.config, recipients: (data.config.recipients || []).join(", "), evidence_recipients: (data.config.evidence_recipients || []).join(", "), auditor_scopes: (data.config.auditor_scopes || []).map((s) => ({ email: s.email, areas: (s.areas || []).join(", "), systems: (s.systems || []).join(", ") })) }); }, []);
  const loadScorecard = useCallback(async () => { const { data } = await api.get("/sap/scorecard"); setScorecard(data); }, []);
  const loadAlerts = useCallback(async () => { try { const { data } = await api.get("/sap/scorecard/alerts"); setScoreAlerts(data.log || []); setScoreMute({ muted: data.muted, mute_until: data.mute_until, mute_reason: data.mute_reason }); } catch { /* noop */ } }, []);
  const loadWhy = useCallback(async () => { setWhyBusy(true); try { const { data } = await api.get("/sap/scorecard/why"); setWhy(data); } catch { /* noop */ } setWhyBusy(false); }, []);
  useEffect(() => { loadConflicts(); }, [loadConflicts]);
  useEffect(() => { loadArem(); }, [loadArem]);
  useEffect(() => { loadDcfg(); }, [loadDcfg]);
  useEffect(() => { loadScorecard(); }, [loadScorecard]);
  useEffect(() => { loadAlerts(); }, [loadAlerts]);
  useEffect(() => { loadWhy(); }, [loadWhy]);
  useEffect(() => { const id = setInterval(() => setNowTs(Date.now()), 1000); return () => clearInterval(id); }, []);
  useEffect(() => {
    api.get("/sap/sod/rules").then((r) => setRules(r.data.rules));
    api.get("/sap/identities").then((r) => setPeople(r.data.identities));
    api.get("/sap/roles").then((r) => setRoles(r.data.roles));
  }, []);

  if (!data) return <Spinner />;
  const cooldownRemain = dcfg?.last_at ? Math.max(0, Math.ceil((new Date(dcfg.last_at).getTime() + 60000 - nowTs) / 1000)) : 0;

  const saveArem = async (patch) => {
    if (!arem) return;
    setAremBusy(true);
    try {
      const { data: res } = await api.put("/sap/autoremediation", { ...arem.config, ...patch });
      if (res.remediated) toast.success(`Auto-remediation engine — ${res.remediated} workflow(s) opened`, { description: "ServiceNow tickets opened & auto-closed" });
      else toast.success("Auto-remediation rule updated");
      await loadArem(); await loadConflicts();
    } catch (e) { toast.error("Could not update rule"); }
    setAremBusy(false);
  };
  const runArem = async () => {
    setAremBusy(true);
    try { const { data: res } = await api.post("/sap/autoremediation/run"); toast.success(`${res.remediated} auto-remediation workflow(s) opened`); await loadArem(); await loadConflicts(); }
    catch { toast.error("Run failed"); }
    setAremBusy(false);
  };
  const sendDigest = async () => {
    setDigestBusy(true);
    try {
      const { data: res } = await api.post("/sap/governance-digest/send");
      if (res.throttled) toast.info(res.message || "Digest was just sent — try again shortly");
      else toast.success(`SAP Governance Digest emailed to ${res.sent} recipient(s)`, { description: (res.recipients || []).join(", ") });
    }
    catch (e) { toast.error(e?.response?.data?.detail || "Could not send digest"); }
    await loadDcfg();
    setDigestBusy(false);
  };
  const saveDcfg = async () => {
    setDcfgBusy(true);
    try {
      const recips = (dcfgLocal.recipients || "").split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
      const evid = (dcfgLocal.evidence_recipients || "").split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
      const scopes = (dcfgLocal.auditor_scopes || []).map((s) => ({ email: (s.email || "").trim(), areas: (s.areas || "").split(/[,\n]/).map((x) => x.trim()).filter(Boolean), systems: (s.systems || "").split(/[,\n]/).map((x) => x.trim()).filter(Boolean) })).filter((s) => s.email);
      await api.put("/sap/digest/config", { ...dcfgLocal, recipients: recips, evidence_recipients: evid, score_threshold: Number(dcfgLocal.score_threshold) || 60, auditor_scopes: scopes });
      toast.success("Governance digest schedule saved");
      await loadDcfg();
    } catch (e) { toast.error(e?.response?.data?.detail || (e?.response?.status === 403 ? "Admin access required" : "Could not save schedule")); }
    setDcfgBusy(false);
  };
  const testChat = async () => {
    try {
      const { data: res } = await api.post("/sap/digest/test-chat");
      if (res.posted) toast.success("Test alert posted to Teams / Slack");
      else toast.info("No chat webhook configured — add a dedicated SAP webhook or configure org alerts");
    } catch (e) { toast.error(e?.response?.data?.detail || "Test failed (admin only)"); }
  };
  const openPreview = async () => {
    setPreviewBusy(true);
    try { const { data } = await api.get("/sap/digest/preview"); setPreview(data.html); }
    catch { toast.error("Could not load preview"); }
    setPreviewBusy(false);
  };
  const openEvidPreview = async () => {
    setEvidPreviewBusy(true);
    try { const { data } = await api.get("/sap/sod-evidence/preview"); setEvidPreview(data); }
    catch { toast.error("Could not load preview"); }
    setEvidPreviewBusy(false);
  };
  const exportScorecard = async (fmt = "csv") => {
    try {
      const res = await api.get(`/sap/scorecard/export?format=${fmt}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `sap-governance-scorecard.${fmt}`; a.click();
      URL.revokeObjectURL(url);
      toast.success(`Governance scorecard exported (${fmt.toUpperCase()})`);
    } catch { toast.error("Export failed"); }
  };
  const checkScoreAlert = async () => {
    setScoreBusy(true);
    try {
      const { data } = await api.post("/sap/scorecard/alert-check");
      const rs = (data.reasons || []).join(" · ");
      if (data.muted) toast.info(`Alerts muted — would flag score ${data.score}/100`, { description: rs || "No breach right now" });
      else if (data.below) toast[data.posted ? "success" : "info"](`Threshold breached — score ${data.score}/100`, { description: (data.posted ? "Alert posted to Slack / Teams. " : "No chat webhook configured. ") + rs });
      else toast.success(`All thresholds healthy — score ${data.score}/100`, { description: "No alert needed" });
      await loadAlerts();
    } catch (e) { toast.error(e?.response?.data?.detail || "Check failed (admin only)"); }
    setScoreBusy(false);
  };
  const sendEvidence = async () => {
    setEvidBusy(true);
    try {
      const { data } = await api.post("/sap/sod-evidence/send", { prepared_by: dcfgLocal?.evidence_prepared_by || "" });
      const scoped = (data.detail || []).some((d) => d.scoped);
      toast.success(`SoD evidence pack emailed to ${data.sent} recipient(s)`, { description: `Prepared by ${data.prepared_by}${data.approved_by ? ` · approved by ${data.approved_by}` : " · pending approval"}${scoped ? " · scoped per auditor" : ""}` });
    } catch (e) { toast.error(e?.response?.data?.detail || "Send failed (admin only)"); }
    setEvidBusy(false);
  };
  const exportEvidence = async (fmt) => {
    try {
      const sb = fmt === "pdf" && dcfgLocal?.evidence_prepared_by ? `&prepared_by=${encodeURIComponent(dcfgLocal.evidence_prepared_by)}` : "";
      const res = await api.get(`/sap/sod-evidence/export?format=${fmt}${sb}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `sap-sod-evidence.${fmt}`; a.click();
      URL.revokeObjectURL(url);
      toast.success(`SoD evidence pack exported (${fmt.toUpperCase()})`);
    } catch { toast.error("Export failed"); }
  };
  const muteAlert = async (hours) => {
    setMuteBusy(true);
    try {
      const reason = window.prompt("Reason for snoozing alerts (optional):", "Known dip — remediation in progress") || "";
      const { data } = await api.post("/sap/scorecard/alert-mute", { hours, reason });
      toast.success(`Alerts muted for ${hours >= 168 ? "7 days" : hours + "h"}`, { description: data.mute_reason || "" });
      await loadAlerts();
    } catch (e) { toast.error(e?.response?.data?.detail || "Mute failed (admin only)"); }
    setMuteBusy(false);
  };
  const unmuteAlert = async () => {
    setMuteBusy(true);
    try { await api.post("/sap/scorecard/alert-unmute"); toast.success("Alerts un-muted"); await loadAlerts(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Unmute failed (admin only)"); }
    setMuteBusy(false);
  };
  const approveEvidence = async () => {
    const approver = window.prompt("Approver name / title:", dcfg?.config?.evidence_approved_by || "");
    if (approver === null) return;
    setApproveBusy(true);
    try {
      const { data } = await api.post("/sap/sod-evidence/approve", { approved_by: approver });
      toast.success("Evidence pack approved", { description: `Approved by ${data.approved_by}` });
      await loadDcfg();
    } catch (e) { toast.error(e?.response?.data?.detail || "Approve failed (set & save 'Prepared by' first)"); }
    setApproveBusy(false);
  };
  const unapproveEvidence = async () => {
    setApproveBusy(true);
    try { await api.post("/sap/sod-evidence/unapprove"); toast.success("Approval revoked"); await loadDcfg(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed (admin only)"); }
    setApproveBusy(false);
  };
  const addScope = () => setDcfgLocal({ ...dcfgLocal, auditor_scopes: [...(dcfgLocal.auditor_scopes || []), { email: "", areas: "", systems: "" }] });
  const setScope = (i, k, v) => setDcfgLocal({ ...dcfgLocal, auditor_scopes: (dcfgLocal.auditor_scopes || []).map((s, j) => (j === i ? { ...s, [k]: v } : s)) });
  const removeScope = (i) => setDcfgLocal({ ...dcfgLocal, auditor_scopes: (dcfgLocal.auditor_scopes || []).filter((_, j) => j !== i) });
  const toggleSev = (s) => { const cur = arem.config.severities; const next = cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]; saveArem({ severities: next.length ? next : ["Critical"] }); };

  const openRule = async (r) => {
    try {
      const { data } = await api.get(`/sap/sod/rules/${r.ref}`);
      const ru = data.rule;
      openDeepDive({
        accent: SEV[ru.severity], refLabel: ru.ref, title: ru.name, rating: ru.severity,
        facets: [
          { label: "Risk area", value: ru.area },
          { label: "Business risk", value: ru.business_risk },
          { label: "Violations", value: `${data.counts.total} total · ${data.counts.open} open · ${data.counts.mitigated} mitigated` },
          { label: data.function_a.label, value: `T-codes: ${data.function_a.tcodes.join(", ") || "—"}` },
          { label: data.function_b.label, value: `T-codes: ${data.function_b.tcodes.join(", ") || "—"}` },
          { label: "Current holders", value: data.holders.slice(0, 8).map((h) => h.person_name).join(", ") || "None currently" },
        ],
        recommendedActions: [
          `Prevent any single identity from holding both “${data.function_a.label}” and “${data.function_b.label}”.`,
          data.counts.open > 0 ? `Remediate ${data.counts.open} open violation(s): remove one conflicting role or attach a mitigating control with evidence.` : "No open violations — keep this rule under continuous monitoring.",
        ],
        complianceRefs: ["SOX ITGC", "NIST AC-5", "ISO 27001 A.5.3"],
        explainTitle: `${ru.name} — SoD rule`, explainKind: "SAP segregation of duties rule and its toxic function combination",
        explainContext: { rule: data },
      });
    } catch (e) { toast.error("Could not load rule detail"); }
  };

  const openConflict = (c) => openDeepDive({
    accent: SEV[c.severity], refLabel: c.conflict_ref, title: c.rule_name, rating: c.severity,
    facets: [
      { label: "User", value: c.person_name }, { label: "System", value: c.system },
      { label: "Risk area", value: c.area }, { label: "Status", value: c.status },
      { label: c.function_a, value: `via ${c.a_via_roles.join(", ")}` },
      { label: c.function_b, value: `via ${c.b_via_roles.join(", ")}` },
    ],
    recommendedActions: [
      `Remove one conflicting role (${c.a_via_roles[0]} or ${c.b_via_roles[0]}) to break the toxic combination.`,
      "If the access is required, attach a mitigating control with evidence and an expiry date.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-5", "ISO 27001 A.5.3"],
    explainTitle: `${c.rule_name} — SoD conflict`, explainKind: "SAP segregation of duties conflict remediation",
    explainContext: { conflict: c },
  });

  const runMitigate = async () => {
    setBusy(true);
    try {
      await api.post("/sap/sod/conflicts/mitigate", { conflict_ref: mit.conflict_ref, control, status: mitStatus });
      toast.success(`Conflict ${mitStatus.toLowerCase()}`); setMit(null); setControl(""); await loadConflicts();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const addSimRole = () => { if (simRole && !simRoles.includes(simRole)) setSimRoles([...simRoles, simRole]); setSimRole(""); };
  const runSim = async () => {
    if (!simPerson || simRoles.length === 0) { toast.error("Pick an identity and at least one role"); return; }
    try {
      const { data } = await api.post("/sap/sod/simulate", { person_ref: simPerson, add_roles: simRoles });
      setSimResult(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Simulation failed"); }
  };

  return (
    <div className="space-y-6" data-testid="sod-command-center">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="sod-title">SoD Command Center</h1>
        <p className="text-sm text-muted-foreground mt-1">Live Segregation-of-Duties detection across users and roles, mitigating controls, pre-assignment risk simulation, and hands-free auto-remediation.</p>
      </div>

      <SapInsight dashboard="SoD Command Center" focus="segregation-of-duties toxic combinations and mitigation" accent="0 84% 60%" auto slug="sod-command" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Critical conflicts" value={data.summary.Critical} accent="0 84% 60%" icon={ShieldAlert} testid="sod-critical" />
        <StatCard label="High conflicts" value={data.summary.High} accent="35 90% 55%" icon={ShieldAlert} testid="sod-high" />
        <StatCard label="Medium conflicts" value={data.summary.Medium} accent="190 90% 50%" icon={GitCompare} testid="sod-medium" />
        <StatCard label="Total rows" value={data.total} sub={`${rules.length} rules in library`} accent="142 70% 45%" icon={ShieldCheck} testid="sod-total" />
      </div>

      {scorecard && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sod-scorecard">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <div className="flex items-center gap-2"><TrendingUp className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-base">Access Governance Scorecard</h2></div>
            <span data-testid="scorecard-source" className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">{scorecard.trend_source === "real" ? "LIVE TREND" : "DERIVED TREND"}</span>
            <div className="flex-1" />
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="scorecard-export" onClick={() => exportScorecard("csv")}><Download className="w-3.5 h-3.5" /> CSV</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="scorecard-export-pdf" onClick={() => exportScorecard("pdf")}><FileText className="w-3.5 h-3.5" /> PDF</Button>
          </div>
          <p className="text-[11px] text-muted-foreground mb-3">A leadership- and auditor-ready snapshot of SAP access posture, trended over the last 8 weeks. {scorecard.trend_source === "derived" ? "Trajectory derived from current posture until weekly snapshots accrue." : "Trend built from recorded weekly snapshots."}</p>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-4">
            <ScoreTile testid="score-governance" label="Governance score" v={scorecard.current.governance_score} suffix="/100" accent="142 70% 45%" />
            <ScoreTile testid="score-open-sod" label="Open SoD" v={scorecard.current.open_sod} accent="0 84% 60%" />
            <ScoreTile testid="score-autorem" label="Auto-remediated" v={scorecard.current.autorem_total} accent="190 90% 50%" />
            <ScoreTile testid="score-movers" label="Movers cleaned" v={scorecard.current.movers_stripped} accent="260 85% 66%" />
            <ScoreTile testid="score-residual" label="Residual leavers" v={scorecard.current.residual} accent="35 90% 55%" />
            <ScoreTile testid="score-risk" label="Avg SAP risk" v={scorecard.current.avg_risk} suffix="/100" accent="199 89% 48%" />
          </div>
          <div className="mb-3 rounded-lg border border-primary/25 bg-primary/[0.04] px-3 py-2.5 flex items-start gap-2.5" data-testid="scorecard-why">
            <Sparkles className="w-4 h-4 text-primary mt-0.5 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Why did the score move?</span>
                <button data-testid="scorecard-why-refresh" onClick={loadWhy} disabled={whyBusy} className="text-[10px] text-primary hover:underline disabled:opacity-50">{whyBusy ? "…" : "refresh"}</button>
                {why?.model && <span className="text-[9px] font-mono text-muted-foreground">· {why.model}</span>}
                <div className="flex-1" />
                {scorecard.forecast && (
                  <span data-testid="scorecard-forecast" title={scorecard.forecast.basis} className="text-[10px] font-mono px-2 py-0.5 rounded-full shrink-0" style={{ background: scorecard.forecast.delta >= 0 ? "hsl(142 70% 45% / 0.14)" : "hsl(0 84% 60% / 0.14)", color: scorecard.forecast.delta >= 0 ? "hsl(142 70% 36%)" : "hsl(0 84% 52%)" }}>
                    Forecast next wk {scorecard.forecast.next_week_score}/100 ({scorecard.forecast.delta >= 0 ? "+" : ""}{scorecard.forecast.delta})
                  </span>
                )}
              </div>
              <div className="text-sm text-foreground/90 mt-0.5" data-testid="scorecard-why-text">{whyBusy && !why ? "Analyzing the 8-week trend…" : (why?.summary || "—")}</div>
            </div>
          </div>
          <div className="h-[200px]" data-testid="scorecard-trend">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={scorecard.trend} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="scOpen" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="hsl(0 84% 60%)" stopOpacity={0.35} /><stop offset="100%" stopColor="hsl(0 84% 60%)" stopOpacity={0.02} /></linearGradient>
                  <linearGradient id="scAuto" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="hsl(142 70% 45%)" stopOpacity={0.3} /><stop offset="100%" stopColor="hsl(142 70% 45%)" stopOpacity={0.02} /></linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} width={36} />
                <Tooltip content={<TrendTip />} />
                <Area type="monotone" dataKey="open_sod" stroke="hsl(0 84% 60%)" strokeWidth={2} fill="url(#scOpen)" name="Open SoD" />
                <Area type="monotone" dataKey="autoremediated" stroke="hsl(142 70% 45%)" strokeWidth={2} fill="url(#scAuto)" name="Auto-remediated" />
                <Area type="monotone" dataKey="residual" stroke="hsl(35 90% 55%)" strokeWidth={2} fill="transparent" name="Residual leavers" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          {scorecard.trend?.some((t) => (t.changes || []).length) && (
            <div className="mt-3 border-t border-border pt-3" data-testid="scorecard-annotations">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">What changed week-over-week</div>
              <div className="space-y-1.5 max-h-[150px] overflow-y-auto pr-1">
                {[...scorecard.trend].slice(1).reverse().map((t) => (
                  <div key={t.week} data-testid={`scorecard-annotation-${t.week}`} className="flex items-start gap-2 text-[11px]">
                    <span className="font-mono text-muted-foreground w-12 shrink-0">{t.label}</span>
                    <div className="flex flex-wrap gap-1">
                      {(t.changes || []).length ? (t.changes || []).map((c, j) => (
                        <span key={j} className="px-1.5 py-0.5 rounded font-mono text-[10px]" style={{ background: c.tone === "up" ? "hsl(142 70% 45% / 0.12)" : "hsl(0 84% 60% / 0.12)", color: c.tone === "up" ? "hsl(142 70% 40%)" : "hsl(0 84% 55%)" }}>{c.label}</span>
                      )) : <span className="text-muted-foreground">No material change</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* SoD → ServiceNow Auto-Remediation Rule Engine */}
      {arem && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sod-autorem">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2"><Bot className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-base">SoD → ServiceNow Auto-Remediation</h2></div>
            <span data-testid="autorem-state" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${arem.config.enabled ? "bg-low/15 text-low" : "bg-secondary text-muted-foreground"}`}>{arem.config.enabled ? "ACTIVE" : "OFF"}</span>
            <div className="flex-1" />
            <div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">Enable engine</span><Switch data-testid="autorem-toggle" checked={arem.config.enabled} disabled={aremBusy} onCheckedChange={(v) => saveArem({ enabled: v })} /></div>
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">When enabled, the platform automatically opens a ServiceNow workflow for every account carrying an open SoD conflict of a watched severity — closing risk without a human click. A daily scheduled sweep (folded into the platform cron, 08:00 UTC) runs it unattended and emails the SAP Access Governance Digest.</p>
          <div className="flex flex-wrap items-center gap-3 mt-2">
            {arem.config.last_cron_at && (
              <span className="text-[10px] font-mono text-muted-foreground" data-testid="autorem-last-cron">Last scheduled sweep {new Date(arem.config.last_cron_at).toLocaleString()} · {arem.config.last_cron_count ?? 0} opened</span>
            )}
            <div className="flex-1" />
            <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="autorem-digest" onClick={sendDigest} disabled={digestBusy}><Mail className="w-3.5 h-3.5" />{digestBusy ? "Sending…" : "Email governance digest"}</Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Trigger severities</div>
              <div className="flex gap-1.5">{["Critical", "High", "Medium"].map((s) => {
                const on = arem.config.severities.includes(s);
                return <button key={s} data-testid={`autorem-sev-${s}`} onClick={() => toggleSev(s)} disabled={aremBusy} className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-full border transition-opacity" style={{ borderColor: `hsl(${SEV[s]} / ${on ? 0.6 : 0.25})`, background: `hsl(${SEV[s]} / ${on ? 0.15 : 0})`, color: `hsl(${SEV[s]})`, opacity: on ? 1 : 0.45 }}>{s}</button>;
              })}</div>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Remediation action</div>
              <Select value={arem.config.action} onValueChange={(v) => saveArem({ action: v })}><SelectTrigger data-testid="autorem-action" className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>{Object.entries(ACTION_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Pending candidates</div>
              <div className="flex items-center gap-3">
                <span className="font-head font-black text-2xl" style={{ color: `hsl(${arem.candidates > 0 ? "0 84% 60%" : "142 70% 45%"})` }} data-testid="autorem-candidates">{arem.candidates}</span>
                <Button size="sm" className="h-8" data-testid="autorem-run" onClick={runArem} disabled={aremBusy || arem.candidates === 0}>{aremBusy ? "Running…" : "Run now"}</Button>
              </div>
            </div>
          </div>
          {arem.log.length > 0 && (
            <div className="mt-4 border-t border-border pt-3">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Recent auto-remediations · {arem.remediated_total}</div>
              <div className="space-y-1 max-h-[160px] overflow-y-auto pr-1" data-testid="autorem-log">
                {arem.log.slice(0, 12).map((l, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <Chip v={l.severity} />
                    <span className="font-mono text-muted-foreground">{l.ticket_number}</span>
                    <span className="font-medium whitespace-nowrap">{l.sap_user}</span>
                    <span className="text-muted-foreground truncate">{l.rules.join(", ")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Governance Digest schedule */}
      {dcfgLocal && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sod-digest-schedule">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2"><CalendarClock className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-base">Governance Digest Schedule</h2></div>
            <span data-testid="digest-state" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${dcfgLocal.enabled ? "bg-low/15 text-low" : "bg-secondary text-muted-foreground"}`}>{dcfgLocal.enabled ? "SCHEDULED" : "PAUSED"}</span>
            <div className="flex-1" />
            <div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">Daily scheduled digest</span><Switch data-testid="digest-enable" checked={dcfgLocal.enabled} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, enabled: v })} /></div>
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">Dispatched by the platform scheduler at <span className="font-mono">{dcfg?.next_window || "08:00 UTC"}</span>. Configure who receives it, on which days, and optionally post a summary to Teams/Slack. {dcfg?.last_at && <>Last sent <span className="font-mono">{new Date(dcfg.last_at).toLocaleString()}</span>.</>}</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Send on</div>
              <Select value={dcfgLocal.days} onValueChange={(v) => setDcfgLocal({ ...dcfgLocal, days: v })}><SelectTrigger data-testid="digest-days" className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="everyday">Every day</SelectItem><SelectItem value="weekdays">Weekdays only (Mon–Fri)</SelectItem></SelectContent></Select>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Recipients (comma-separated · blank = all admins/execs)</div>
              <Textarea data-testid="digest-recipients" rows={2} value={dcfgLocal.recipients} onChange={(e) => setDcfgLocal({ ...dcfgLocal, recipients: e.target.value })} placeholder={(dcfg?.default_recipients || []).join(", ") || "admin@company.com"} />
            </div>
          </div>

          <div className="mt-4 border-t border-border pt-3">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <Switch data-testid="digest-chat-toggle" checked={dcfgLocal.chat_alert} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, chat_alert: v })} />
              <span className="text-xs">Also post a summary to Slack / Microsoft Teams</span>
              <span className="text-[10px] font-mono text-muted-foreground">{dcfg?.fallback_chat_configured ? "· org webhook available as fallback" : "· no org webhook — add a dedicated one below"}</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Dedicated SAP Teams webhook (optional)</div><Input data-testid="digest-teams-url" value={dcfgLocal.teams_url} onChange={(e) => setDcfgLocal({ ...dcfgLocal, teams_url: e.target.value })} placeholder="https://outlook.office.com/webhook/…" /></div>
              <div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Dedicated SAP Slack webhook (optional)</div><Input data-testid="digest-slack-url" value={dcfgLocal.slack_url} onChange={(e) => setDcfgLocal({ ...dcfgLocal, slack_url: e.target.value })} placeholder="https://hooks.slack.com/services/…" /></div>
            </div>
          </div>

          {/* Score-drop alert */}
          <div className="mt-4 border-t border-border pt-3" data-testid="score-alert-config">
            <div className="flex flex-wrap items-center gap-2">
              <BellRing className="w-4 h-4 text-amber" />
              <span className="text-sm font-medium">Governance score-drop alert</span>
              <div className="flex-1" />
              <span className="text-xs text-muted-foreground">Alert Slack/Teams when the score drops below</span>
              <Input type="number" min={0} max={100} data-testid="score-threshold" value={dcfgLocal.score_threshold ?? 60} onChange={(e) => setDcfgLocal({ ...dcfgLocal, score_threshold: e.target.value })} className="w-20 h-8" />
              <Switch data-testid="score-alert-toggle" checked={!!dcfgLocal.score_alert} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, score_alert: v })} />
            </div>
            <div className="flex flex-wrap items-center gap-3 mt-2" data-testid="sev-thresholds">
              <span className="text-xs text-muted-foreground">Also alert when open conflicts exceed —</span>
              <div className="flex items-center gap-1.5"><span className="text-[11px] font-mono text-crit">Critical</span><Input type="number" min={0} data-testid="sev-threshold-Critical" value={dcfgLocal.sev_thresholds?.Critical ?? ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, sev_thresholds: { ...(dcfgLocal.sev_thresholds || {}), Critical: e.target.value } })} className="w-16 h-8" /></div>
              <div className="flex items-center gap-1.5"><span className="text-[11px] font-mono text-amber">High</span><Input type="number" min={0} data-testid="sev-threshold-High" value={dcfgLocal.sev_thresholds?.High ?? ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, sev_thresholds: { ...(dcfgLocal.sev_thresholds || {}), High: e.target.value } })} className="w-16 h-8" /></div>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <span className="text-[11px] text-muted-foreground">Current governance score <b>{scorecard?.current?.governance_score ?? "—"}/100</b>. The daily sweep posts a one-time alert per week while any threshold stays breached.</span>
              <div className="flex-1" />
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="score-alert-check" onClick={checkScoreAlert} disabled={scoreBusy}><BellRing className="w-3.5 h-3.5" />{scoreBusy ? "Checking…" : "Check & alert now"}</Button>
            </div>
            {scoreAlerts.length > 0 && (
              <div className="mt-3 border-t border-border pt-3" data-testid="score-alert-history">
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Recent alerts · {scoreAlerts.length}</div>
                <div className="space-y-1.5 max-h-[150px] overflow-y-auto pr-1">
                  {scoreAlerts.slice(0, 12).map((a, i) => (
                    <div key={i} data-testid={`score-alert-${i}`} className="flex items-start gap-2 text-[11px]">
                      <span className="font-mono text-muted-foreground w-32 shrink-0">{new Date(a.at).toLocaleString()}</span>
                      <span className="font-head font-bold shrink-0" style={{ color: "hsl(0 84% 60%)" }}>{a.score}/100</span>
                      <span className="text-muted-foreground">{(a.reasons || []).join(" · ")}{a.posted ? "" : " (not posted)"}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Weekly SoD evidence pack */}
          <div className="mt-4 border-t border-border pt-3" data-testid="evidence-export-config">
            <div className="flex flex-wrap items-center gap-2">
              <FileWarning className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">Weekly SoD evidence pack (auditors)</span>
              <div className="flex-1" />
              <Switch data-testid="evidence-export-toggle" checked={!!dcfgLocal.evidence_export} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, evidence_export: v })} />
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">Auto-email a branded SOX-grade SoD evidence pack PDF — every conflict with its toxic function combination and remediation state — to your auditors on a set weekday.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Send on</div>
                <Select value={dcfgLocal.evidence_day || "mon"} onValueChange={(v) => setDcfgLocal({ ...dcfgLocal, evidence_day: v })}><SelectTrigger data-testid="evidence-day" className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>{[["mon", "Monday"], ["tue", "Tuesday"], ["wed", "Wednesday"], ["thu", "Thursday"], ["fri", "Friday"], ["sat", "Saturday"], ["sun", "Sunday"]].map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
              </div>
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Auditor recipients (comma-separated · blank = admins/execs)</div>
                <Input data-testid="evidence-recipients" value={dcfgLocal.evidence_recipients || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, evidence_recipients: e.target.value })} placeholder="auditor@company.com, soc@company.com" />
              </div>
            </div>
            <div className="mt-3 rounded-md border border-border p-2.5" data-testid="evidence-signoff">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Two-step signoff (stamped on the PDF)</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1">1 · Prepared by</div>
                  <Input data-testid="evidence-prepared-by" value={dcfgLocal.evidence_prepared_by || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, evidence_prepared_by: e.target.value })} placeholder="e.g. Sam Prep, GRC Analyst" className="h-8" />
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1">2 · Approval</div>
                  {dcfg?.config?.evidence_approved_by ? (
                    <div className="flex items-center gap-2 h-8">
                      <span data-testid="evidence-approval-status" className="text-[11px] px-2 py-0.5 rounded-full font-mono" style={{ background: "hsl(142 70% 45% / 0.14)", color: "hsl(142 70% 34%)" }}>✓ {dcfg.config.evidence_approved_by} · {(dcfg.config.evidence_approved_at || "").slice(0, 10)}</span>
                      <Button size="sm" variant="ghost" className="h-7 text-[11px]" data-testid="evidence-unapprove" onClick={unapproveEvidence} disabled={approveBusy}>Revoke</Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 h-8">
                      <span data-testid="evidence-approval-status" className="text-[11px] px-2 py-0.5 rounded-full font-mono" style={{ background: "hsl(35 90% 55% / 0.14)", color: "hsl(35 90% 40%)" }}>Pending approval</span>
                      <Button size="sm" variant="outline" className="h-7 text-[11px]" data-testid="evidence-approve" onClick={approveEvidence} disabled={approveBusy}>Approve pack</Button>
                    </div>
                  )}
                </div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-1.5">Save the schedule after editing "Prepared by" (changing it clears any prior approval), then approve. The PDF carries both names + the approval date.</p>
            </div>
            <div className="mt-3" data-testid="auditor-scopes">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">Per-auditor scopes — each recipient gets a pack filtered to their areas/systems (blank = full pack)</div>
                <div className="flex-1" />
                <Button size="sm" variant="outline" className="h-7 text-[11px]" data-testid="auditor-scope-add" onClick={addScope}>+ Add scope</Button>
              </div>
              <div className="space-y-2">
                {(dcfgLocal.auditor_scopes || []).map((s, i) => (
                  <div key={i} className="grid grid-cols-1 md:grid-cols-[1.4fr_1fr_1fr_auto] gap-2 items-center" data-testid={`auditor-scope-${i}`}>
                    <Input data-testid={`auditor-scope-email-${i}`} value={s.email} onChange={(e) => setScope(i, "email", e.target.value)} placeholder="auditor@company.com" className="h-8" />
                    <Input data-testid={`auditor-scope-areas-${i}`} value={s.areas} onChange={(e) => setScope(i, "areas", e.target.value)} placeholder="Finance, Treasury" className="h-8" />
                    <Input data-testid={`auditor-scope-systems-${i}`} value={s.systems} onChange={(e) => setScope(i, "systems", e.target.value)} placeholder="S4P, ECP" className="h-8" />
                    <Button size="sm" variant="ghost" className="h-8 text-crit" data-testid={`auditor-scope-remove-${i}`} onClick={() => removeScope(i)}>Remove</Button>
                  </div>
                ))}
                {(!dcfgLocal.auditor_scopes || dcfgLocal.auditor_scopes.length === 0) && <div className="text-[11px] text-muted-foreground">No scopes — every recipient gets the full evidence pack.</div>}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="evidence-send-now" onClick={sendEvidence} disabled={evidBusy}><Mail className="w-3.5 h-3.5" />{evidBusy ? "Sending…" : "Send evidence pack now"}</Button>
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="evidence-preview" onClick={openEvidPreview} disabled={evidPreviewBusy}><Eye className="w-3.5 h-3.5" />{evidPreviewBusy ? "Loading…" : "Preview pack"}</Button>
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="evidence-export-pdf" onClick={() => exportEvidence("pdf")}><FileText className="w-3.5 h-3.5" /> Download PDF</Button>
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="evidence-export-csv" onClick={() => exportEvidence("csv")}><Download className="w-3.5 h-3.5" /> Download CSV</Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-4">
            <Button size="sm" data-testid="digest-save" onClick={saveDcfg} disabled={dcfgBusy}>{dcfgBusy ? "Saving…" : "Save schedule"}</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-preview" onClick={openPreview} disabled={previewBusy}><Eye className="w-3.5 h-3.5" />{previewBusy ? "Loading…" : "Preview email"}</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-test-chat" onClick={testChat}><Send className="w-3.5 h-3.5" /> Test chat alert</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-send-now" onClick={sendDigest} disabled={digestBusy || cooldownRemain > 0}><Mail className="w-3.5 h-3.5" />{digestBusy ? "Sending…" : cooldownRemain > 0 ? `Send again in ${cooldownRemain}s` : "Send digest now"}</Button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Simulator */}
        <div className="lg:col-span-5 bg-card fact-border rounded-xl p-5" data-testid="sod-simulator">
          <div className="flex items-center gap-2 mb-1"><FlaskConical className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-base">Pre-Assignment Risk Simulation</h2></div>
          <p className="text-[11px] text-muted-foreground mb-3">Check which SoD conflicts a role assignment would introduce before approving it.</p>
          <div className="space-y-2">
            <Select value={simPerson} onValueChange={setSimPerson}><SelectTrigger data-testid="sim-person" className="h-9"><SelectValue placeholder="Select identity…" /></SelectTrigger>
              <SelectContent>{people.slice(0, 60).map((p) => <SelectItem key={p.ref} value={p.ref}>{p.name} · {p.department}</SelectItem>)}</SelectContent></Select>
            <div className="flex gap-2">
              <Select value={simRole} onValueChange={setSimRole}><SelectTrigger data-testid="sim-role" className="h-9 flex-1"><SelectValue placeholder="Add role…" /></SelectTrigger>
                <SelectContent>{roles.map((r) => <SelectItem key={r.ref} value={r.ref}>{r.name}</SelectItem>)}</SelectContent></Select>
              <Button data-testid="sim-add-role" variant="outline" className="h-9" onClick={addSimRole}>Add</Button>
            </div>
            {simRoles.length > 0 && <div className="flex flex-wrap gap-1.5">{simRoles.map((r) => <span key={r} className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary">{r}</span>)}</div>}
            <Button data-testid="sim-run" className="w-full" onClick={runSim}>Simulate</Button>
          </div>
          {simResult && (
            <div className="mt-4 border-t border-border pt-3" data-testid="sim-result">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs">Decision:</span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full" style={{ background: `hsl(${simResult.decision === "BLOCK" ? "0 84% 60%" : simResult.decision === "REVIEW" ? "35 90% 55%" : "142 70% 45%"} / 0.15)`, color: `hsl(${simResult.decision === "BLOCK" ? "0 84% 60%" : simResult.decision === "REVIEW" ? "35 90% 55%" : "142 70% 45%"})` }}>{simResult.decision}</span>
              </div>
              {simResult.introduced_conflicts.length === 0 ? <p className="text-xs text-low">No new conflicts introduced.</p> : (
                <div className="space-y-1.5">{simResult.introduced_conflicts.map((c) => (
                  <div key={c.conflict_ref} className="text-xs flex items-center gap-2"><Chip v={c.severity} /> {c.rule_name}</div>
                ))}</div>
              )}
            </div>
          )}
        </div>

        {/* Rule library */}
        <div className="lg:col-span-7 bg-card fact-border rounded-xl p-5" data-testid="sod-rules">
          <div className="flex items-center gap-2 mb-3"><ScrollText className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-base">SoD Rule Library</h2></div>
          <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
            {rules.map((r) => (
              <button key={r.ref} onClick={() => openRule(r)} data-testid={`sod-rule-${r.ref}`} className="w-full text-left flex items-start gap-3 p-2.5 rounded-lg bg-secondary/30 hover:bg-secondary/60 transition-colors">
                <Chip v={r.severity} />
                <div className="min-w-0">
                  <div className="text-sm font-medium">{r.name} <span className="text-[10px] font-mono text-muted-foreground">· {r.ref} · {r.area}</span></div>
                  <div className="text-[11px] text-muted-foreground">{r.function_a_label} ✕ {r.function_b_label}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Conflicts table */}
      <div className="bg-card fact-border rounded-xl">
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
          <h2 className="font-head font-bold text-base flex-1">Detected Conflicts</h2>
          <Select value={sev} onValueChange={setSev}><SelectTrigger data-testid="sod-filter-sev" className="w-[130px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All severity</SelectItem><SelectItem value="Critical">Critical</SelectItem><SelectItem value="High">High</SelectItem><SelectItem value="Medium">Medium</SelectItem></SelectContent></Select>
          <Select value={area} onValueChange={setArea}><SelectTrigger data-testid="sod-filter-area" className="w-[150px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All areas</SelectItem>{data.areas.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent></Select>
          <Select value={status} onValueChange={setStatus}><SelectTrigger data-testid="sod-filter-status" className="w-[140px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All statuses</SelectItem><SelectItem value="Open">Open</SelectItem><SelectItem value="Mitigated">Mitigated</SelectItem><SelectItem value="Accepted">Accepted</SelectItem></SelectContent></Select>
        </div>
        <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
          <table className="w-full text-sm" data-testid="sod-table">
            <thead className="sticky top-0 bg-card"><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
              <th className="p-3">Severity</th><th className="p-3">Rule</th><th className="p-3">User</th><th className="p-3">System</th><th className="p-3">Area</th><th className="p-3">Status</th><th className="p-3 text-right">Action</th>
            </tr></thead>
            <tbody>
              {data.conflicts.map((c) => (
                <tr key={c.conflict_ref} className="border-b border-border/50 hover:bg-secondary/30" data-testid={`sod-row-${c.conflict_ref}`}>
                  <td className="p-3"><Chip v={c.severity} /></td>
                  <td className="p-3"><button onClick={() => openConflict(c)} className="text-left hover:text-primary font-medium" data-testid={`sod-open-${c.conflict_ref}`}>{c.rule_name}</button></td>
                  <td className="p-3 whitespace-nowrap">{c.person_name}</td>
                  <td className="p-3 font-mono text-xs">{c.system}</td>
                  <td className="p-3 text-xs">{c.area}</td>
                  <td className="p-3"><Chip v={c.status} map={{ Open: "0 84% 60%", Mitigated: "142 70% 45%", Accepted: "35 90% 55%" }} /></td>
                  <td className="p-3 text-right"><button data-testid={`sod-mitigate-${c.conflict_ref}`} onClick={() => { setMit(c); setControl(c.mitigating_control || ""); setMitStatus(c.status === "Open" ? "Mitigated" : c.status); }} className="inline-flex items-center gap-1 text-xs text-ai hover:underline"><Wrench className="w-3.5 h-3.5" /> Mitigate</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={!!mit} onOpenChange={(o) => !o && setMit(null)}>
        <DialogContent data-testid="sod-mitigate-dialog">
          <DialogHeader><DialogTitle>Mitigate — {mit?.rule_name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">{mit?.business_risk}</p>
            <Textarea data-testid="mit-control" value={control} onChange={(e) => setControl(e.target.value)} placeholder="Describe the mitigating control (e.g. monthly detective review of payment runs by Controller)…" rows={3} />
            <Select value={mitStatus} onValueChange={setMitStatus}><SelectTrigger data-testid="mit-status" className="h-9"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="Mitigated">Mitigated (control in place)</SelectItem><SelectItem value="Accepted">Risk Accepted</SelectItem><SelectItem value="Open">Re-open (remove control)</SelectItem></SelectContent></Select>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setMit(null)}>Cancel</Button><Button data-testid="mit-save" disabled={busy} onClick={runMitigate}>{busy ? "Saving…" : "Save"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-2xl" data-testid="digest-preview-dialog">
          <DialogHeader><DialogTitle>Governance digest — email preview</DialogTitle></DialogHeader>
          <div className="max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-white" data-testid="digest-preview-body" dangerouslySetInnerHTML={{ __html: preview || "" }} />
        </DialogContent>
      </Dialog>

      <Dialog open={!!evidPreview} onOpenChange={(o) => !o && setEvidPreview(null)}>
        <DialogContent className="max-w-3xl" data-testid="evidence-preview-dialog">
          <DialogHeader><DialogTitle>Weekly SoD evidence pack — preview</DialogTitle></DialogHeader>
          {evidPreview && (
            <div className="max-h-[72vh] overflow-y-auto space-y-4">
              <div className="text-[11px] font-mono text-muted-foreground" data-testid="evidence-preview-meta">
                {evidPreview.enabled ? "Scheduled" : "Not scheduled"} · sends every <b className="text-foreground">{({ mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday" })[evidPreview.evidence_day] || evidPreview.evidence_day}</b> · Prepared by <b className="text-foreground">{evidPreview.prepared_by || "—"}</b> · {evidPreview.approved_by ? <span style={{ color: "hsl(142 70% 38%)" }}>Approved by {evidPreview.approved_by}</span> : <span style={{ color: "hsl(35 90% 45%)" }}>Pending approval</span>}
              </div>
              {(evidPreview.recipients_detail || []).length > 0 && (
                <div className="rounded-lg border border-border p-2.5" data-testid="evidence-preview-recipients">
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Per-recipient delivery</div>
                  <div className="space-y-1">
                    {evidPreview.recipients_detail.map((r, i) => (
                      <div key={i} className="flex flex-wrap items-center gap-2 text-[11px]" data-testid={`evidence-preview-recipient-${i}`}>
                        <span className="font-mono">{r.email}</span>
                        <span className="px-1.5 py-0.5 rounded-full bg-secondary text-muted-foreground">{r.conflicts} conflict(s)</span>
                        {r.scoped ? <span className="px-1.5 py-0.5 rounded-full font-mono" style={{ background: "hsl(199 89% 48% / 0.12)", color: "hsl(199 89% 42%)" }}>scoped: {[...(r.areas || []), ...(r.systems || [])].join(", ")}</span> : <span className="text-muted-foreground">full pack</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="rounded-lg border border-border bg-white" dangerouslySetInnerHTML={{ __html: evidPreview.html || "" }} />
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Attached PDF preview — first {evidPreview.rows?.length || 0} of {evidPreview.summary?.total || 0} conflict(s)</div>
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-xs" data-testid="evidence-preview-table">
                    <thead className="bg-secondary/60 text-left text-[10px] font-mono uppercase text-muted-foreground"><tr>
                      <th className="p-2">Ref</th><th className="p-2">Sev</th><th className="p-2">Status</th><th className="p-2">Rule</th><th className="p-2">User (Dept)</th>
                    </tr></thead>
                    <tbody>
                      {(evidPreview.rows || []).map((r, i) => (
                        <tr key={i} className="border-t border-border/50">
                          <td className="p-2 font-mono">{r.rule_ref}</td>
                          <td className="p-2"><Chip v={r.severity} /></td>
                          <td className="p-2">{r.status}</td>
                          <td className="p-2">{r.rule_name}</td>
                          <td className="p-2 whitespace-nowrap">{r.person_name} <span className="text-muted-foreground">({r.department})</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
