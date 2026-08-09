import { useEffect, useState, useCallback, useRef } from "react";
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
import { GitCompare, ShieldAlert, ShieldCheck, FlaskConical, ScrollText, Wrench, Bot, Mail, CalendarClock, Send, Eye, Download, TrendingUp, FileText, BellRing, FileWarning, Sparkles, MessagesSquare, Share2, Volume2, History, Slack, Copy } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { SodScorecardCard } from "@/components/sod/SodScorecardCard";
import { SodAutoRemCard } from "@/components/sod/SodAutoRemCard";
import { SodToolsRow } from "@/components/sod/SodToolsRow";
import { SodConflictsTable } from "@/components/sod/SodConflictsTable";

import { SodWatchlist } from "@/components/SodWatchlist";
import { GovernanceDigestCard } from "@/components/sod/GovernanceDigestCard";
import { SEV, Chip, ScoreTile, ACTION_LABEL, TrendTip } from "@/components/sod/sodPrimitives";

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
  const [askOpen, setAskOpen] = useState(false);
  const [askSession, setAskSession] = useState("");
  const [askMsgs, setAskMsgs] = useState([]);
  const [askInput, setAskInput] = useState("");
  const [askBusy, setAskBusy] = useState(false);
  const [askSuggestions, setAskSuggestions] = useState([]);
  const [askExportBusy, setAskExportBusy] = useState(false);
  const [askEmailBusy, setAskEmailBusy] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceUrl, setVoiceUrl] = useState("");
  const [shareBusy, setShareBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [askHistory, setAskHistory] = useState([]);
  const [shares, setShares] = useState(null);
  const [briefingBusy, setBriefingBusy] = useState(false);
  const [recapOpen, setRecapOpen] = useState(false);
  const [recapData, setRecapData] = useState(null);
  const [recapBusy, setRecapBusy] = useState(false);
  const previewAudioRef = useRef(null);

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
  const slackAskUrl = `${process.env.REACT_APP_BACKEND_URL || ""}/api/sap/slack/ask`;
  const teamsAskUrl = `${process.env.REACT_APP_BACKEND_URL || ""}/api/sap/teams/ask`;
  const [slackTest, setSlackTest] = useState(null);
  const [slackTestBusy, setSlackTestBusy] = useState(false);
  const [teamsTest, setTeamsTest] = useState(null);
  const [teamsTestBusy, setTeamsTestBusy] = useState(false);
  const loadScorecard = useCallback(async () => { const { data } = await api.get("/sap/scorecard"); setScorecard(data); }, []);
  const loadAlerts = useCallback(async () => { try { const { data } = await api.get("/sap/scorecard/alerts"); setScoreAlerts(data.log || []); setScoreMute({ muted: data.muted, mute_until: data.mute_until, mute_reason: data.mute_reason }); } catch { /* noop */ } }, []);
  const loadWhy = useCallback(async () => { setWhyBusy(true); try { const { data } = await api.get("/sap/scorecard/why"); setWhy(data); } catch { /* noop */ } setWhyBusy(false); }, []);
  const loadShares = useCallback(async () => { try { const { data } = await api.get("/sap/digest/shares"); setShares(data); } catch { /* noop */ } }, []);
  useEffect(() => { loadConflicts(); }, [loadConflicts]);
  useEffect(() => { loadArem(); }, [loadArem]);
  useEffect(() => { loadShares(); }, [loadShares]);
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
  const askHasThread = askMsgs.some((m) => m.role === "user");

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
  const runSlackTest = async () => {
    setSlackTestBusy(true); setSlackTest(null);
    try {
      const { data } = await api.post("/sap/slack/test", { question: "top risks" });
      setSlackTest(data);
      if (!data.signing_secret_set) toast.warning("Answer generated — but save a signing secret so inbound Slack verifies.");
      else if (data.webhook_posted) toast.success("Test answer posted to your Slack webhook");
      else toast.success("Slack Ask is working — sample answer generated");
    } catch (e) { toast.error(e?.response?.data?.detail || (e?.response?.status === 403 ? "Admin access required" : "Test failed")); }
    setSlackTestBusy(false);
  };
  const runTeamsTest = async () => {
    setTeamsTestBusy(true); setTeamsTest(null);
    try {
      const { data } = await api.post("/sap/teams/test", { question: "top risks" });
      setTeamsTest(data);
      if (!data.secret_set) toast.warning("Answer generated — but save an HMAC secret so inbound Teams verifies.");
      else if (data.webhook_posted) toast.success("Test answer posted to your Teams webhook");
      else toast.success("Teams Ask is working — sample answer generated");
    } catch (e) { toast.error(e?.response?.data?.detail || (e?.response?.status === 403 ? "Admin access required" : "Test failed")); }
    setTeamsTestBusy(false);
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
  const openAsk = async () => {
    const sid = (typeof crypto !== "undefined" && crypto.randomUUID) ? crypto.randomUUID() : `s-${Date.now()}`;
    setAskSession(sid); setAskMsgs([]); setAskInput(""); setAskSuggestions([]); setHistoryOpen(false); setAskOpen(true);
    loadAskHistory();
    try {
      const { data } = await api.get("/sap/digest/ask/intro");
      setAskMsgs([{ role: "assistant", text: data.greeting }]);
      setAskSuggestions(data.suggestions || []);
    } catch { setAskMsgs([{ role: "assistant", text: "Ask me anything about this governance digest." }]); }
  };
  const sendAsk = async (q) => {
    const question = (q ?? askInput).trim();
    if (!question || askBusy) return;
    setAskMsgs((m) => [...m, { role: "user", text: question }]);
    setAskInput(""); setAskBusy(true);
    try {
      const { data } = await api.post("/sap/digest/ask", { session_id: askSession, question });
      if (data.session_id) setAskSession(data.session_id);
      setAskMsgs((m) => [...m, { role: "assistant", text: data.answer, model: data.model }]);
      if (data.suggestions) setAskSuggestions(data.suggestions);
    } catch {
      setAskMsgs((m) => [...m, { role: "assistant", text: "Sorry — I couldn't analyze that just now. Please try again." }]);
    }
    setAskBusy(false);
  };
  const exportAsk = async () => {
    if (!askSession) return;
    setAskExportBusy(true);
    try {
      const res = await api.get(`/sap/digest/ask/export?session_id=${encodeURIComponent(askSession)}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = "sap-digest-ai-qa.pdf"; a.click();
      URL.revokeObjectURL(url);
      toast.success("AI Q&A note downloaded (PDF)");
    } catch (e) { toast.error(e?.response?.data?.detail || "Export failed"); }
    setAskExportBusy(false);
  };
  const emailAsk = async () => {
    if (!askSession) return;
    const def = (dcfgLocal?.recipients || "").split(/[,\n]/).map((s) => s.trim()).filter(Boolean).join(", ");
    const raw = window.prompt("Email the AI Q&A note to (comma-separated):", def || "");
    if (raw === null) return;
    const recipients = raw.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
    setAskEmailBusy(true);
    try {
      const { data } = await api.post("/sap/digest/ask/email", { session_id: askSession, recipients });
      toast.success(`AI Q&A note emailed to ${data.sent} recipient(s)`, { description: (data.recipients || []).join(", ") });
    } catch (e) { toast.error(e?.response?.data?.detail || "Email failed"); }
    setAskEmailBusy(false);
  };
  const createShare = async () => {
    setShareBusy(true);
    try {
      const { data } = await api.post("/sap/digest/share");
      try { await navigator.clipboard.writeText(data.url); } catch { /* clipboard blocked */ }
      toast.success("Read-only share link copied", { description: data.url });
      loadShares();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not create share link"); }
    setShareBusy(false);
  };
  const playVoice = async () => {
    setVoiceBusy(true);
    try {
      const res = await api.get(`/sap/digest/voice?voice=${encodeURIComponent(dcfgLocal?.voice_name || "onyx")}&speed=${dcfgLocal?.voice_speed || 1}`, { responseType: "blob" });
      if (voiceUrl) URL.revokeObjectURL(voiceUrl);
      const url = URL.createObjectURL(res.data);
      setVoiceUrl(url);
      toast.success("Voice briefing ready");
    } catch (e) { toast.error(e?.response?.data?.detail || "Voice generation unavailable right now"); }
    setVoiceBusy(false);
  };
  const loadAskHistory = async () => {
    try { const { data } = await api.get("/sap/digest/ask/history"); setAskHistory(data.threads || []); }
    catch { setAskHistory([]); }
  };
  const openThread = async (sid) => {
    try {
      const { data } = await api.get(`/sap/digest/ask/thread?session_id=${encodeURIComponent(sid)}`);
      setAskSession(data.session_id); setAskMsgs(data.messages || []); setAskSuggestions([]); setHistoryOpen(false);
    } catch { toast.error("Could not load that thread"); }
  };
  const previewVoice = async (v) => {
    try {
      const res = await api.get(`/sap/digest/voice/sample?voice=${encodeURIComponent(v)}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      if (previewAudioRef.current) { try { previewAudioRef.current.pause(); } catch { /* noop */ } }
      const a = new Audio(url); previewAudioRef.current = a;
      a.play().catch(() => {});
    } catch { /* preview optional */ }
  };
  const shareBriefing = async () => {
    const def = (dcfgLocal?.recipients || "").split(/[,\n]/).map((s) => s.trim()).filter(Boolean).join(", ");
    const raw = window.prompt("Email the audio briefing + live snapshot link to (comma-separated):", def || "");
    if (raw === null) return;
    const recipients = raw.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
    setBriefingBusy(true);
    try {
      const { data } = await api.post("/sap/digest/share-briefing", { recipients });
      toast.success(`Briefing emailed to ${data.sent} recipient(s)`, { description: `${data.has_audio ? "Audio .mp3 attached · " : ""}live snapshot link included` });
      loadShares();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not send briefing"); }
    setBriefingBusy(false);
  };
  const renameThread = async (sid, cur) => {
    const title = window.prompt("Rename this Q&A thread:", cur || "");
    if (title === null) return;
    try {
      await api.post("/sap/digest/ask/rename", { session_id: sid, title });
      toast.success("Thread renamed");
      loadAskHistory();
    } catch { toast.error("Rename failed"); }
  };
  const previewRecap = async () => {
    setRecapBusy(true); setRecapOpen(true); setRecapData(null);
    try { const { data } = await api.get("/sap/digest/recap/preview"); setRecapData(data); }
    catch { setRecapData({ total: 0, unique: 0, top: [] }); }
    setRecapBusy(false);
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

      <SodWatchlist />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Critical conflicts" value={data.summary.Critical} accent="0 84% 60%" icon={ShieldAlert} testid="sod-critical" />
        <StatCard label="High conflicts" value={data.summary.High} accent="35 90% 55%" icon={ShieldAlert} testid="sod-high" />
        <StatCard label="Medium conflicts" value={data.summary.Medium} accent="190 90% 50%" icon={GitCompare} testid="sod-medium" />
        <StatCard label="Total rows" value={data.total} sub={`${rules.length} rules in library`} accent="142 70% 45%" icon={ShieldCheck} testid="sod-total" />
      </div>

      {scorecard && <SodScorecardCard {...{ data, exportScorecard, loadWhy, scorecard, why, whyBusy }} />}

      {/* SoD → ServiceNow Auto-Remediation Rule Engine */}
      {arem && <SodAutoRemCard {...{ arem, aremBusy, data, digestBusy, rules, runArem, saveArem, sendDigest, sev, toggleSev }} />}

      {/* Governance Digest schedule */}
      {dcfgLocal && <GovernanceDigestCard {...{ addScope, approveBusy, approveEvidence, briefingBusy, checkScoreAlert, cooldownRemain, createShare, data, dcfg, dcfgBusy, dcfgLocal, digestBusy, evidBusy, evidPreviewBusy, exportEvidence, muteAlert, muteBusy, openAsk, openEvidPreview, openPreview, playVoice, preview, previewBusy, previewRecap, previewVoice, removeScope, runSlackTest, runTeamsTest, saveDcfg, scoreAlerts, scoreBusy, scoreMute, scorecard, sendDigest, sendEvidence, setDcfgLocal, setScope, sev, shareBriefing, shareBusy, shares, slackAskUrl, slackTest, slackTestBusy, status, teamsAskUrl, teamsTest, teamsTestBusy, testChat, unapproveEvidence, unmuteAlert, voiceBusy, voiceUrl }} />}

      <SodToolsRow {...{ addSimRole, area, data, openRule, people, roles, rules, runSim, setSimPerson, setSimRole, simPerson, simResult, simRole, simRoles }} />

      <SodConflictsTable {...{ area, data, openConflict, setArea, setControl, setMit, setMitStatus, setSev, setStatus, sev, status }} />

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

      <Dialog open={askOpen} onOpenChange={setAskOpen}>
        <DialogContent className="max-w-lg" data-testid="digest-ask-dialog">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <DialogTitle className="flex items-center gap-2"><MessagesSquare className="w-4 h-4 text-primary" /> Ask AI about this digest</DialogTitle>
              <div className="flex-1" />
              <Button size="sm" variant="ghost" className="h-7 text-[11px] gap-1" data-testid="digest-ask-history-toggle" onClick={() => { const n = !historyOpen; setHistoryOpen(n); if (n) loadAskHistory(); }}><History className="w-3.5 h-3.5" /> History</Button>
            </div>
          </DialogHeader>
          {historyOpen && (
            <div className="rounded-lg border border-border bg-secondary/30 p-2 max-h-[180px] overflow-y-auto -mt-1" data-testid="digest-ask-history">
              {(askHistory || []).length === 0 ? (
                <div className="text-[11px] text-muted-foreground px-1 py-2" data-testid="digest-ask-history-empty">No past threads yet.</div>
              ) : (askHistory || []).map((t, i) => (
                <div key={t.session_id} className="flex items-center gap-1 rounded hover:bg-secondary/70 transition-colors">
                  <button data-testid={`digest-ask-history-${i}`} onClick={() => openThread(t.session_id)} className="flex-1 text-left px-2 py-1.5 min-w-0">
                    <div className="text-[12px] truncate">{t.title}</div>
                    <div className="text-[10px] text-muted-foreground">{t.questions} question(s){t.updated_at ? ` · ${new Date(t.updated_at).toLocaleString()}` : ""}</div>
                  </button>
                  <button data-testid={`digest-ask-rename-${i}`} onClick={() => renameThread(t.session_id, t.title)} title="Rename thread" className="px-2 py-1 text-muted-foreground hover:text-primary shrink-0"><FileText className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
          )}
          <p className="text-[11px] text-muted-foreground -mt-2">Grounded in your live SAP access snapshot — open conflicts, score trend, residual leavers, auto-remediation. Follow-ups keep context.</p>
          <div className="space-y-3">
            <div className="max-h-[46vh] min-h-[160px] overflow-y-auto space-y-3 pr-1" data-testid="digest-ask-messages">
              {askMsgs.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`} data-testid={`digest-ask-msg-${i}`}>
                  <div className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${m.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary/60 text-foreground"}`}>
                    {m.text}
                    {m.model === "deterministic-fallback" && <div className="text-[9px] font-mono opacity-60 mt-1">offline summary</div>}
                  </div>
                </div>
              ))}
              {askBusy && <div className="flex justify-start"><div className="rounded-2xl px-3.5 py-2 text-sm bg-secondary/60 text-muted-foreground" data-testid="digest-ask-typing">Analyzing the live snapshot…</div></div>}
            </div>
            {askSuggestions.length > 0 && !askBusy && (
              <div className="flex flex-wrap gap-1.5" data-testid="digest-ask-suggestions">
                {askSuggestions.map((s, i) => (
                  <button key={i} data-testid={`digest-ask-suggestion-${i}`} onClick={() => sendAsk(s)} className="text-[11px] px-2.5 py-1 rounded-full border border-border hover:border-primary/50 hover:bg-primary/[0.05] transition-colors text-muted-foreground">{s}</button>
                ))}
              </div>
            )}
            <div className="flex items-center gap-2">
              <Input data-testid="digest-ask-input" value={askInput} onChange={(e) => setAskInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") sendAsk(); }} placeholder="e.g. Which area needs attention first?" />
              <Button size="sm" data-testid="digest-ask-send" onClick={() => sendAsk()} disabled={askBusy || !askInput.trim()}><Send className="w-3.5 h-3.5" /></Button>
            </div>
            {askHasThread && (
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border/60" data-testid="digest-ask-actions">
                <span className="text-[10px] font-mono uppercase text-muted-foreground">Save thread</span>
                <div className="flex-1" />
                <Button size="sm" variant="outline" className="h-7 text-[11px] gap-1" data-testid="digest-ask-export" onClick={exportAsk} disabled={askExportBusy}><FileText className="w-3 h-3" />{askExportBusy ? "…" : "Download PDF"}</Button>
                <Button size="sm" variant="outline" className="h-7 text-[11px] gap-1" data-testid="digest-ask-email" onClick={emailAsk} disabled={askEmailBusy}><Mail className="w-3 h-3" />{askEmailBusy ? "…" : "Email thread"}</Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={recapOpen} onOpenChange={setRecapOpen}>
        <DialogContent className="max-w-md" data-testid="recap-preview-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><History className="w-4 h-4 text-primary" /> Weekly AI Q&amp;A recap — preview</DialogTitle></DialogHeader>
          {recapBusy ? (
            <div className="text-sm text-muted-foreground py-6 text-center" data-testid="recap-preview-loading">Gathering this week's questions…</div>
          ) : !recapData || recapData.total === 0 ? (
            <div className="text-sm text-muted-foreground py-6 text-center" data-testid="recap-preview-empty">No AI questions asked in the last 7 days yet.</div>
          ) : (
            <div className="space-y-1" data-testid="recap-preview-list">
              <div className="text-[11px] text-muted-foreground mb-1">{recapData.total} question(s) · {recapData.unique} distinct — top asked:</div>
              {recapData.top.map((it, i) => (
                <div key={i} data-testid={`recap-preview-item-${i}`} className="flex items-center gap-2 text-sm py-1 border-b border-border/50">
                  <span className="font-bold text-primary w-5">{i + 1}</span>
                  <span className="flex-1">{it.q}</span>
                  <span className="font-mono text-xs text-muted-foreground">{it.count}×</span>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
