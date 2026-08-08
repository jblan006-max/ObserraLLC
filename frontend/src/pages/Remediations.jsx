import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { StatCard, CardShell, EmptyState, Spinner } from "@/components/dash";
import { AIInsight } from "@/components/AIInsight";
import { AIExplain } from "@/components/AIExplain";
import { RiskDetailModal } from "@/components/RiskDetailModal";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import {
  Target, Wrench, Boxes, ShieldCheck, AlertTriangle, Loader2, Building2, Sparkles,
  ShieldX, ChevronDown, Gauge, DollarSign, Bug, User, FileWarning, Clock, MapPin, Zap,
  Radar, TrendingUp, Network, ScrollText, PlugZap, CheckCircle2, XCircle, Download,
} from "lucide-react";

const ACCENT = "255 85% 66%";
const RATE = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
const SEVR = { critical: "Critical", high: "High", medium: "Medium", low: "Low", info: "Low" };
const money = (n) => n == null ? "—" : n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}k` : `$${Math.round(n || 0)}`;
const col = (v) => v >= 75 ? "142 70% 45%" : v >= 55 ? "35 90% 55%" : "0 84% 60%";
const worstRating = (list) => ["Critical", "High", "Medium", "Low"].find((r) => list.includes(r)) || "Low";

function Pill({ label, tone }) {
  return <span className="text-[9px] font-mono font-bold px-2 py-0.5 rounded-full whitespace-nowrap" style={{ background: `hsl(${tone} / 0.15)`, color: `hsl(${tone})` }}>{label}</span>;
}

// One immutable Defensibility Ledger record — every REAL remediation / verification attempt
// with its raw provider response, shown as board-defensible evidence.
function LedgerRow({ e }) {
  const [open, setOpen] = useState(false);
  const verified = e.verified === true;
  const inProg = e.status === "In Progress";
  const isVerify = !!e.results;
  const tone = isVerify ? ACCENT : verified ? "142 70% 45%" : inProg ? "35 90% 55%" : "0 84% 60%";
  const evidence = e.external || e.results || e.trace;
  const label = isVerify ? "VERIFY-CONNECTORS" : `${(e.action || "action").toUpperCase()} · ${e.task_id || "—"}`;
  const when = e.finished_at || e.at || e.started_at;
  return (
    <div data-testid={`ledger-row-${e.id}`} className="rounded-lg bg-secondary/30 p-2.5 text-xs">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono truncate min-w-0">{label}</span>
        <span className="shrink-0 font-mono text-[9px] px-2 py-0.5 rounded-full" style={{ background: `hsl(${tone} / 0.15)`, color: `hsl(${tone})` }}>{isVerify ? "VERIFY" : (e.status || "—")}</span>
      </div>
      {e.message && <div className="text-[11px] text-muted-foreground mt-1 leading-snug">{e.message}</div>}
      <div className="flex items-center gap-2 mt-1 text-[9px] font-mono text-muted-foreground flex-wrap">
        {e.provider && <span>{e.provider}</span>}
        {e.by && <span>· {e.by}</span>}
        {when && <span>· {new Date(when).toLocaleString()}</span>}
        {(e.risk_reduced || 0) > 0 && <span style={{ color: "hsl(142 70% 45%)" }}>· ALE ↓ {money(e.risk_reduced)}</span>}
        {evidence && <button data-testid={`ledger-raw-${e.id}`} onClick={() => setOpen((o) => !o)} className="ml-auto underline hover:text-foreground">{open ? "Hide raw evidence" : "Raw evidence"}</button>}
      </div>
      {open && evidence && <pre className="text-[10px] font-mono bg-[#0a0e17] border border-border rounded-lg p-2 mt-1.5 overflow-x-auto max-h-52 overflow-y-auto">{JSON.stringify(evidence, null, 2)}</pre>}
    </div>
  );
}

function LensCard({ icon: Icon, title, subtitle, rating, compliancePct, metrics, frameworks, children, explainTitle, explainKind, explainContext, testid, remedy }) {
  const [open, setOpen] = useState(false);
  return (
    <CardShell testid={testid} title={title} icon={Icon} accent={ACCENT}
      right={<div className="flex items-center gap-1.5">
        {rating && <Pill label={`${rating} RISK`} tone={RATE[rating] || ACCENT} />}
        {compliancePct != null && <Pill label={`${compliancePct}% compliant`} tone={col(compliancePct)} />}
      </div>}>
      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">{subtitle}</p>
        <div className="grid grid-cols-3 gap-2" data-testid={`${testid}-metrics`}>
          {metrics.map((m) => (
            <div key={m.label} className="rounded-lg bg-secondary/40 p-2.5">
              <div className="text-[9px] font-mono uppercase text-muted-foreground leading-tight">{m.label}</div>
              <div className="font-head font-black text-lg tracking-tight" style={m.accent ? { color: `hsl(${m.accent})` } : {}}>{m.value}</div>
            </div>
          ))}
        </div>
        {children}
        {frameworks?.length > 0 && (
          <div>
            <div className="text-[9px] font-mono uppercase text-muted-foreground mb-1">Framework alignment</div>
            <div className="flex flex-wrap gap-1">
              {frameworks.map((f) => <span key={f.framework} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm" style={{ background: `hsl(${col(f.coverage)} / 0.12)`, color: `hsl(${col(f.coverage)})` }}>{f.framework} {f.coverage}%</span>)}
            </div>
          </div>
        )}
        {remedy}
        <button data-testid={`${testid}-why`} onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1.5 text-[11px] font-head font-bold px-3 py-1.5 rounded-full transition-transform active:scale-95"
          style={{ background: `hsl(${ACCENT} / 0.12)`, color: `hsl(${ACCENT})` }}>
          <Sparkles className="w-3 h-3" /> {open ? "Hide AI reasoning" : "Analyze — why this matters"} <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        {open && <AIExplain title={explainTitle} kind={explainKind} context={explainContext} accent={ACCENT} />}
      </div>
    </CardShell>
  );
}

const Row = ({ children, onClick, testid }) => (
  <div data-testid={testid} onClick={onClick} className="flex items-center justify-between gap-2 text-xs bg-secondary/30 hover:bg-secondary/60 rounded-md px-2.5 py-1.5 cursor-pointer transition-colors">
    {children}
  </div>
);

export default function Remediations() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [strat, setStrat] = useState(null);
  const [tac, setTac] = useState(null);
  const [exp, setExp] = useState(null);
  const [comp, setComp] = useState(null);
  const [fw, setFw] = useState([]);
  const [busy, setBusy] = useState("");
  const [detail, setDetail] = useState(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [actionResult, setActionResult] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [verify, setVerify] = useState(null);
  const [verifyBusy, setVerifyBusy] = useState(false);

  const loadLedger = () => api.get("/risk-engine/ledger").then((r) => setLedger(r.data.entries || [])).catch(() => setLedger([]));
  const load = () => {
    api.get("/risk-engine/strategic").then((r) => setStrat(r.data)).catch(() => setStrat(null));
    api.get("/risk-engine/tactical").then((r) => setTac(r.data)).catch(() => setTac(null));
    api.get("/risk-engine/exposure").then((r) => setExp(r.data)).catch(() => setExp(null));
    api.get("/risk-engine/compliance").then((r) => setComp(r.data)).catch(() => setComp(null));
    api.get("/controls/compliance").then((r) => setFw((r.data.frameworks || []).map((f) => ({ framework: f.framework, coverage: f.coverage })))).catch(() => setFw([]));
    loadLedger();
  };
  useEffect(() => { load(); }, []);
  useEffect(() => { setActionResult(null); }, [detail?.taskId]);

  const doVerify = async () => {
    setVerifyBusy(true);
    try { const { data } = await api.post("/risk-engine/verify-connectors"); setVerify(data); toast.success("Live connector verification complete — evidence logged"); loadLedger(); }
    catch (e) { toast.error(e.response?.data?.detail || "Verification failed"); }
    setVerifyBusy(false);
  };

  const runAction = async (kind) => {
    setBusy(kind);
    try {
      if (kind === "fix") { const { data } = await api.post("/self-scan/autofix"); toast.success(data.message || "AI Autofix launched"); }
      else { const { data } = await api.post("/self-scan/containment/scan"); toast.success(`Containment evaluated — ${data.active} active response(s)`); }
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Action failed"); }
    setBusy("");
  };

  if (!strat || !tac || !exp || !comp) return <Spinner />;

  const p = strat.portfolio || {};
  const b = strat.benchmark || {};
  const drift = strat.drift || {};
  const dist = p.ratings_dist || {};
  const overall = strat.compliance?.overall_pct ?? 0;
  const tasks = tac.tasks || [];
  const assets = exp.assets || [];
  const emap = exp.exposure_map || [];
  const items = comp.items || [];
  const areas = strat.areas || [];
  const topFw = [...fw].sort((a, c) => a.coverage - c.coverage).slice(0, 4);
  const benchTone = b.position === "above" ? "0 84% 60%" : b.position === "below" ? "35 90% 55%" : "142 70% 45%";
  const assetsWithVulns = assets.filter((a) => a.vuln_count > 0).length;
  const kevAssets = assets.filter((a) => a.kev).length;
  const weakestArea = (strat.compliance?.by_area || [])[0];
  const taskFor = (ref) => tasks.find((t) => t.asset_ref === ref);

  const doAction = async (kind) => {
    if (!detail?.taskId) return;
    setDetailBusy(true);
    try {
      let data;
      if (kind === "remediate" || kind === "isolate") ({ data } = await api.post(`/risk-engine/task/${detail.taskId}/action`, { action: kind }));
      else ({ data } = await api.post(`/risk-engine/task/${detail.taskId}/status`, { status: kind === "soc" ? "In Progress" : "Accepted" }));
      const rr = data.risk_reduced || 0;
      const after = data.portfolio_after?.residual_ale;
      // Honest outcome — reflect the REAL backend verification, never a fake success.
      if (kind === "remediate" || kind === "isolate") {
        const verified = data.verified === true;
        const inProgress = data.status === "In Progress";
        const msg = data.message || (verified ? "Verified remediation applied" : "Action complete");
        if (verified) toast.success(`Verified — ${msg}${rr ? ` · ALE ↓ ${money(rr)}` : ""}`);
        else if (inProgress) toast(`Sandbox-verifying — ${msg}`);
        else toast.error(`Not applied — ${msg}`);
        setActionResult({ ...data, kind, taskId: detail.taskId });
      } else {
        const label = kind === "soc" ? "Assigned to SOC" : "Risk accepted";
        toast.success(`${label}${after != null ? ` — ALE now ${money(after)}` : ""}${rr ? ` (↓ ${money(rr)} risk reduced)` : ""}`);
        setDetail(null);
      }
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Action failed"); }
    setDetailBusy(false);
  };
  const quickStatus = async (taskId, status) => {
    try { const { data } = await api.post(`/risk-engine/task/${taskId}/status`, { status }); toast.success(`${status} — ALE ${money(data.portfolio_after.residual_ale)}`); load(); }
    catch { toast.error("Status update failed"); }
  };

  const openTask = (t) => setDetail({
    refLabel: (t.cve_ids || []).join(", ") || t.id, title: t.title, rating: SEVR[t.severity], score: t.exploitability?.score,
    ale: t.ale_at_stake, taskId: t.id, fixScript: t.fix_script, recommendedActions: t.fix_path,
    facets: [
      { icon: User, label: "Who (owner)", value: t.owner || "Platform" },
      { icon: FileWarning, label: "What", value: `${t.title}${t.kev ? " · KEV (actively exploited)" : ""}` },
      { icon: Clock, label: "When (SLA)", value: `${t.sla_days} days` },
      { icon: MapPin, label: "Where (asset)", value: t.asset_name },
      { icon: Zap, label: "Why (exploitability)", value: `${t.exploitability?.label} — ${t.exploitability?.basis}` },
      { icon: DollarSign, label: "ROI", value: `${money(t.remediation_roi?.ale_reduced)} reduced · ${t.remediation_roi?.roi}× per $` },
    ],
    explainTitle: t.title, explainKind: "tactical remediation cyber roi", explainContext: { task: t },
  });
  const openMap = (m) => setDetail({
    refLabel: (m.cve_ids || []).join(", ") || m.id, title: m.finding, rating: SEVR[m.severity], score: m.exploitability?.score,
    ale: m.residual_ale, taskId: m.id, recommendedActions: [m.remediation].filter(Boolean),
    facets: [
      { icon: MapPin, label: "Direct linkage (asset)", value: `${m.asset_name}${m.internet_facing ? " · internet-facing" : ""}` },
      { icon: FileWarning, label: "What (finding)", value: `${m.finding} ${(m.cve_ids || []).join(", ")}` },
      { icon: Zap, label: "Exploitability", value: `${m.exploitability?.label} (${m.exploitability?.score}/100) — ${m.exploitability?.basis}` },
      { icon: Network, label: "Blast radius", value: m.blast_radius?.count ? `${m.blast_radius.count} reachable: ${m.blast_radius.reachable.map((x) => x.name).join(", ")}` : "No lateral reach detected" },
    ],
    explainTitle: m.finding, explainKind: "exposure correlation evidence exploitability blast-radius", explainContext: { exposure: m },
  });
  const openRisk = (r) => setDetail({
    refLabel: r.ref, title: r.title, rating: r.rating, score: r.score, ale: r.residual_ale, exceedsAppetite: r.exceeds_appetite,
    taskId: taskFor(r.asset_ref)?.id, recommendedActions: [`Reduce residual to ${r.remediation_roi?.target_residual}/25 — retires ${money(r.remediation_roi?.ale_reduced)} at ${r.remediation_roi?.roi}× ROI.`],
    facets: [
      { icon: User, label: "Who (owner)", value: r.owner || "unassigned" },
      { icon: FileWarning, label: "What (risk)", value: r.title },
      { icon: MapPin, label: "Where (asset)", value: r.asset_ref || "portfolio" },
      { icon: Zap, label: "Why (peer position)", value: `${r.compliance_pct}% area compliance · ${r.peer?.position} peers (${r.peer?.ratio ?? "—"}×)` },
    ],
    explainTitle: r.title, explainKind: "strategic financial benchmark fair", explainContext: { risk: r, benchmark: b },
  });
  const openAsset = (a) => setDetail({
    refLabel: a.ref, title: a.name, rating: a.rating, score: a.exploitability?.score, ale: a.residual_ale,
    taskId: taskFor(a.ref)?.id,
    facets: [
      { icon: MapPin, label: "Where", value: `${a.name}${a.internet_facing ? " · internet-facing" : ""}` },
      { icon: FileWarning, label: "What", value: `${a.vuln_count} vuln(s) · worst ${a.worst_severity || "none"}` },
      { icon: Boxes, label: "Effective criticality", value: `${a.effective_criticality}${a.escalated ? " (escalated by vuln correlation)" : ""}` },
      { icon: Network, label: "Blast radius", value: a.blast_radius?.count ? `${a.blast_radius.count} reachable` : "No lateral reach" },
    ],
    explainTitle: a.name, explainKind: "exposure asset correlation exploitability", explainContext: { asset: a },
  });
  const openComp = (i) => setDetail({
    refLabel: i.ref, title: i.title, rating: i.rating, score: i.score, ale: i.residual_ale, taskId: taskFor(i.asset_ref)?.id,
    facets: [
      { icon: ShieldCheck, label: "Area", value: `${i.area} · ${i.compliance_pct}% compliant` },
      { icon: Gauge, label: "Probability × Impact", value: `${i.probability} × ${i.impact}` },
      { icon: DollarSign, label: "ALE", value: money(i.residual_ale) },
    ],
    explainTitle: i.title, explainKind: "compliance framework rating probability impact", explainContext: { item: i },
  });

  return (
    <div className="rise space-y-5" data-testid="remediations-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2" style={{ color: `hsl(${ACCENT})` }}><Wrench className="w-7 h-7" strokeWidth={1.5} /> Remediations — Unified Command</h1>
        <p className="text-sm text-muted-foreground mt-1">Full-lifecycle command center across all four areas — Strategic, Tactical, Exposure and Compliance — driven by the Unified Risk Correlation Engine (assets ↔ vulnerabilities ↔ controls). Click any row for a deep-dive with the FAIR rating, AI brief, fix script and one-click actions.</p>
      </div>

      {(drift.direction === "up" || drift.trending_critical) && (
        <div data-testid="rem-drift-banner" className="rounded-xl border p-3 flex items-start gap-2.5" style={{ borderColor: `hsl(${drift.trending_critical ? "0 84% 60%" : "35 90% 55%"} / 0.4)`, background: `hsl(${drift.trending_critical ? "0 84% 60%" : "35 90% 55%"} / 0.06)` }}>
          <TrendingUp className="w-4 h-4 mt-0.5 shrink-0" style={{ color: `hsl(${drift.trending_critical ? "0 84% 60%" : "35 90% 55%"})` }} />
          <div><div className="font-head font-bold text-sm">Predictive risk drift</div><p className="text-xs text-muted-foreground mt-0.5">{drift.note}</p></div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard testid="rem-kpi-ale" label="$ Residual exposure" value={money(p.residual_ale)} accent="15 80% 55%" sub={`↓ ${p.reduction_pct ?? 0}% vs inherent`} />
        <StatCard testid="rem-kpi-p90" label="Monte-Carlo P90" value={money(p.p90)} accent="0 84% 60%" sub="adverse-case loss" />
        <StatCard testid="rem-kpi-tasks" label="Open remediations" value={p.open_tasks ?? 0} accent={ACCENT} sub="prioritized queue" />
        <StatCard testid="rem-kpi-coverage" label="Remediation coverage" value={`${tac.coverage?.pct ?? 0}%`} accent="142 70% 45%" sub={`${tac.coverage?.covered ?? 0}/${tac.coverage?.open_risks ?? 0} risks`} />
        <StatCard testid="rem-kpi-compliance" label="Overall compliance" value={`${overall}%`} accent={col(overall)} sub="live control coverage" />
        <StatCard testid="rem-kpi-bench" label="vs Industry median" value={b.ratio != null ? `${b.ratio}×` : "—"} accent={benchTone} sub={b.position ? `${b.position} peers` : "no benchmark"} />
      </div>

      <AIInsight dashboard="Remediation Command Center" accent={ACCENT} auto slug="remediation-command" />

      <div data-testid="rem-benchmark-banner" className="rounded-xl border p-4" style={{ borderColor: `hsl(${benchTone} / 0.4)`, background: `hsl(${benchTone} / 0.06)` }}>
        <div className="flex items-start gap-2.5">
          <Gauge className="w-4 h-4 mt-0.5 shrink-0" style={{ color: `hsl(${benchTone})` }} />
          <div className="min-w-0">
            <div className="font-head font-bold text-sm">Strategic benchmark — {b.industry || "industry"} sector</div>
            <p className="text-xs text-muted-foreground mt-0.5">Modelled per-incident exposure {money(b.modelled_avg_sle)} is <span style={{ color: `hsl(${benchTone})` }} className="font-semibold">{b.position} the industry median</span> {money(b.industry_avg)}{b.ratio != null ? ` (${b.ratio}×)` : ""}. <span className="text-muted-foreground/70">{b.source}</span></p>
            {b.strategic_recommendation && <p className="text-xs mt-1.5" data-testid="rem-strategic-rec"><span className="font-mono uppercase text-[10px]" style={{ color: `hsl(${benchTone})` }}>Strategic recommendation</span> — {b.strategic_recommendation}</p>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <LensCard testid="lens-strategic" icon={Target} title="Strategic" subtitle="Board-level: Annualized Loss Expectancy, benchmark position & appetite."
          rating={worstRating(Object.entries(dist).filter(([, n]) => n > 0).map(([r]) => r))} compliancePct={overall} frameworks={topFw}
          metrics={[{ label: "Residual ALE", value: money(p.residual_ale), accent: "15 80% 55%" }, { label: "P90", value: money(p.p90), accent: "0 84% 60%" }, { label: "Reduction", value: `${p.reduction_pct ?? 0}%`, accent: "142 70% 45%" }]}
          explainTitle="Strategic remediation lens" explainKind="strategic financial benchmark" explainContext={{ portfolio: p, benchmark: b, drift, compliance: strat.compliance, top_risks: (strat.top_risks || []).slice(0, 5) }}>
          {!(strat.top_risks || []).length ? <EmptyState text="No quantified risks yet — run a live scan." /> : (
            <div className="space-y-1.5">
              {(strat.top_risks || []).slice(0, 4).map((r) => (
                <Row key={r.ref} testid={`strat-risk-${r.ref}`} onClick={() => openRisk(r)}>
                  <span className="truncate min-w-0"><span className="font-mono text-muted-foreground">{r.ref}</span> {r.title}{r.exceeds_appetite && <span className="text-crit ml-1">⚠</span>}</span>
                  <span className="flex items-center gap-1.5 shrink-0"><Pill label={r.rating} tone={RATE[r.rating] || ACCENT} /><span className="font-mono" style={{ color: `hsl(${ACCENT})` }}>{money(r.residual_ale)}</span></span>
                </Row>
              ))}
            </div>
          )}
        </LensCard>

        <LensCard testid="lens-tactical" icon={Wrench} title="Tactical" subtitle="SOC queue: remediation ROI, priority ranking & SLA deadlines."
          rating={tasks.length ? SEVR[tasks[0].severity] || "Medium" : "Low"} compliancePct={overall} frameworks={topFw}
          metrics={[{ label: "Open tasks", value: p.open_tasks ?? 0, accent: ACCENT }, { label: "Coverage", value: `${tac.coverage?.pct ?? 0}%`, accent: "142 70% 45%" }, { label: "Top ROI", value: tasks[0]?.remediation_roi?.roi ? `${tasks[0].remediation_roi.roi}×` : "—", accent: "0 84% 60%" }]}
          explainTitle="Tactical remediation lens" explainKind="tactical roi priority sla" explainContext={{ pipeline: tac.pipeline, coverage: tac.coverage, top_tasks: tasks.slice(0, 6) }}
          remedy={isAdmin && (
            <div className="flex items-center gap-1.5">
              <button data-testid="rem-autofix" disabled={!!busy} onClick={() => runAction("fix")} className="flex items-center gap-1 text-[11px] font-head font-bold px-2.5 py-1.5 rounded-full disabled:opacity-50" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}>{busy === "fix" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wrench className="w-3 h-3" />} Auto-remediate</button>
              <button data-testid="rem-contain" disabled={!!busy} onClick={() => runAction("contain")} className="flex items-center gap-1 text-[11px] font-head font-bold px-2.5 py-1.5 rounded-full border border-crit/40 text-crit disabled:opacity-50">{busy === "contain" ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldX className="w-3 h-3" />} Contain</button>
            </div>
          )}>
          {!tasks.length ? <EmptyState text="No open remediation tasks — the surface is clean." /> : (
            <div className="space-y-1.5">
              {tasks.slice(0, 4).map((t) => (
                <Row key={t.id} testid={`tac-task-${t.id}`} onClick={() => openTask(t)}>
                  <span className="truncate min-w-0"><span className="font-mono text-[9px] px-1 py-0.5 rounded-sm mr-1" style={{ background: `hsl(${RATE[SEVR[t.severity]] || ACCENT} / 0.15)`, color: `hsl(${RATE[SEVR[t.severity]] || ACCENT})` }}>P{t.priority_score}</span>{t.title} {t.kev && <span className="text-crit font-mono">KEV</span>}</span>
                  <span className="text-[10px] font-mono text-muted-foreground shrink-0">{t.remediation_roi?.roi}× · {t.status}</span>
                </Row>
              ))}
            </div>
          )}
        </LensCard>

        <LensCard testid="lens-exposure" icon={Boxes} title="Exposure" subtitle="Correlated: which assets carry which specific vulnerabilities & evidence."
          rating={worstRating(assets.map((a) => a.rating))} compliancePct={overall} frameworks={topFw}
          metrics={[{ label: "Assets", value: assets.length, accent: "38 92% 55%" }, { label: "With vulns", value: assetsWithVulns, accent: "0 84% 60%" }, { label: "KEV assets", value: kevAssets, accent: "0 84% 60%" }]}
          explainTitle="Exposure remediation lens" explainKind="exposure correlation evidence exploitability" explainContext={{ endpoint: exp.endpoint, assets: assets.slice(0, 6).map((a) => ({ ref: a.ref, name: a.name, effective_criticality: a.effective_criticality, rating: a.rating, vulns: a.vulns })) }}>
          {!assets.length ? <EmptyState text="No assets inventoried yet — connect a source or run a scan." /> : (
            <div className="space-y-1.5">
              {assets.slice(0, 4).map((a) => (
                <div key={a.ref} data-testid={`exp-asset-${a.ref}`} onClick={() => openAsset(a)} className="bg-secondary/30 hover:bg-secondary/60 rounded-md px-2.5 py-1.5 cursor-pointer transition-colors">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="truncate min-w-0 flex items-center gap-1.5">{a.escalated && <span title="escalated by vuln correlation" className="text-crit">▲</span>}<span className="font-medium truncate">{a.name}</span></span>
                    <span className="flex items-center gap-1.5 shrink-0"><Pill label={a.effective_criticality} tone={RATE[a.effective_criticality] || ACCENT} /><span className="text-[10px] font-mono text-muted-foreground">{a.vuln_count} vuln{a.vuln_count === 1 ? "" : "s"}</span></span>
                  </div>
                  {a.vulns?.length > 0 && <div className="text-[10px] text-muted-foreground truncate mt-0.5">{a.vulns.map((v) => (v.cve_ids || []).join(", ") || v.title).join(" · ")}</div>}
                </div>
              ))}
            </div>
          )}
        </LensCard>

        <LensCard testid="lens-compliance" icon={ShieldCheck} title="Compliance" subtitle="Every item mapped to risk, rating, probability, impact & score."
          rating={worstRating(items.map((i) => i.rating))} compliancePct={overall} frameworks={topFw}
          metrics={[{ label: "Mapped items", value: items.length, accent: ACCENT }, { label: "Overall", value: `${overall}%`, accent: col(overall) }, { label: "Weakest area", value: weakestArea ? `${weakestArea.compliance_pct}%` : "—", accent: weakestArea ? col(weakestArea.compliance_pct) : ACCENT }]}
          explainTitle="Compliance remediation lens" explainKind="compliance framework rating probability impact" explainContext={{ items: items.slice(0, 8), compliance: comp.compliance, areas: comp.areas }}>
          {!items.length ? <EmptyState text="No mapped items yet." /> : (
            <div className="space-y-1.5">
              {items.slice(0, 4).map((i) => (
                <Row key={i.ref} testid={`comp-item-${i.ref}`} onClick={() => openComp(i)}>
                  <span className="truncate min-w-0"><span className="font-mono text-muted-foreground">{i.ref}</span> {i.area} · {i.compliance_pct}%</span>
                  <span className="flex items-center gap-1.5 shrink-0"><span className="font-mono text-[10px] text-muted-foreground">{i.probability}×{i.impact}</span><Pill label={`${i.rating} ${i.score}`} tone={RATE[i.rating] || ACCENT} /></span>
                </Row>
              ))}
            </div>
          )}
        </LensCard>
      </div>

      {/* Cyber Exposure Map — every CVE correlated to a live asset */}
      <CardShell testid="rem-exposure-map" title="Cyber Exposure Map — CVE ↔ live asset" icon={Radar} accent={ACCENT}
        right={<span className="text-[10px] font-mono text-muted-foreground">{emap.length} correlated exposure(s)</span>}>
        {!emap.length ? <EmptyState icon={Network} text="No live vulnerability↔asset correlations yet — run a self-scan or connect a source." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[820px]">
              <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><tr><th className="text-left px-3 py-2">CVE / Finding</th><th className="text-left px-3 py-2">Direct linkage (asset)</th><th className="text-left px-3 py-2">Exploitability</th><th className="text-left px-3 py-2">Blast radius</th><th className="text-right px-3 py-2">$ ALE</th></tr></thead>
              <tbody>
                {emap.map((m) => {
                  const ec = RATE[m.exploitability?.label] || ACCENT;
                  return (
                    <tr key={m.id} data-testid={`exp-map-${m.id}`} onClick={() => openMap(m)} className="border-b border-border/60 hover:bg-secondary/40 cursor-pointer transition-colors">
                      <td className="px-3 py-2"><div className="font-mono text-[11px] text-ai">{(m.cve_ids || []).join(", ") || m.id}</div><div className="text-[11px] text-muted-foreground truncate max-w-[220px]">{m.finding}</div></td>
                      <td className="px-3 py-2 text-[11px] truncate max-w-[180px]">{m.asset_name}{m.internet_facing && <span className="text-crit ml-1">· internet</span>}</td>
                      <td className="px-3 py-2"><span className="font-mono font-bold px-2 py-0.5 rounded-sm text-[10px]" style={{ background: `hsl(${ec} / 0.15)`, color: `hsl(${ec})` }}>{m.exploitability?.label} {m.exploitability?.score}</span></td>
                      <td className="px-3 py-2 text-[11px] text-muted-foreground">{m.blast_radius?.count || 0} asset(s)</td>
                      <td className="px-3 py-2 text-right font-mono">{money(m.residual_ale)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardShell>

      {/* Action Center — ROI-ordered remediation queue with live status & one-click actions */}
      <CardShell testid="rem-action-center" title="Action Center — remediation by Risk-Reduction ROI" icon={AlertTriangle} accent={ACCENT}
        right={<span className="text-[10px] font-mono text-muted-foreground">{tasks.length} open</span>}>
        {!tasks.length ? <EmptyState icon={Bug} text="No open remediation tasks — run a live self-scan to populate the queue." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[960px]">
              <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><tr><th className="text-left px-3 py-2">Priority</th><th className="text-left px-3 py-2">Finding</th><th className="text-left px-3 py-2">Asset</th><th className="text-right px-3 py-2">ROI (ALE↓ / $)</th><th className="text-right px-3 py-2">SLA</th><th className="text-left px-3 py-2">Status</th><th className="text-right px-3 py-2">Action</th></tr></thead>
              <tbody>
                {tasks.map((t) => {
                  const rc = RATE[SEVR[t.severity]] || ACCENT;
                  return (
                    <tr key={t.id} data-testid={`rem-queue-${t.id}`} onClick={() => openTask(t)} className="border-b border-border/60 hover:bg-secondary/40 cursor-pointer transition-colors">
                      <td className="px-3 py-2"><span className="font-mono font-bold px-2 py-0.5 rounded-sm text-[10px]" style={{ background: `hsl(${rc} / 0.15)`, color: `hsl(${rc})` }}>P{t.priority_score}</span></td>
                      <td className="px-3 py-2"><div className="font-medium">{t.title}</div><div className="text-[10px] text-muted-foreground uppercase">{t.severity}{t.kev ? " · KEV" : ""} · {(t.cve_ids || []).join(", ")}</div></td>
                      <td className="px-3 py-2 text-[11px] text-muted-foreground truncate max-w-[150px]">{t.asset_name}</td>
                      <td className="px-3 py-2 text-right"><div className="font-mono font-bold" style={{ color: `hsl(142 70% 45%)` }}>{t.remediation_roi?.roi}×</div><div className="text-[10px] text-muted-foreground">{money(t.remediation_roi?.ale_reduced)}↓</div></td>
                      <td className="px-3 py-2 text-right font-mono text-muted-foreground">{t.sla_days}d</td>
                      <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                        <Select value={t.status} onValueChange={(v) => quickStatus(t.id, v)}>
                          <SelectTrigger data-testid={`rem-status-${t.id}`} className="w-32 h-8 text-xs bg-secondary/60"><SelectValue /></SelectTrigger>
                          <SelectContent>{["Open", "In Progress", "Remediated", "Accepted"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                        </Select>
                      </td>
                      <td className="px-3 py-2 text-right"><span className="text-[10px] font-mono text-ai flex items-center justify-end gap-0.5">Deep-dive →</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardShell>

      <CardShell testid="rem-areas" title="Per-area drilldown — risk, exposure & compliance" icon={Building2} accent={ACCENT}>
        {!areas.length ? <EmptyState text="Areas populate as risks & findings correlate." /> : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {areas.map((a) => (
              <div key={a.area} data-testid={`rem-area-${a.area.replace(/[^a-zA-Z0-9]/g, "-")}`} className="rounded-lg border border-border p-3 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-head font-bold text-sm truncate">{a.area}</div>
                  <div className="flex items-center gap-1">{a.exceeds_appetite && <span className="text-crit text-[9px] font-mono">⚠ appetite</span>}<Pill label={a.rating} tone={RATE[a.rating] || ACCENT} /></div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div><div className="text-[9px] font-mono uppercase text-muted-foreground">ALE</div><div className="font-mono text-xs">{money(a.residual_ale)}</div></div>
                  <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Tasks</div><div className="font-mono text-xs">{a.open_tasks}</div></div>
                  <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Compliant</div><div className="font-mono text-xs" style={{ color: `hsl(${col(a.compliance_pct)})` }}>{a.compliance_pct}%</div></div>
                </div>
                <div className="h-1.5 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${a.compliance_pct}%`, background: `hsl(${col(a.compliance_pct)})` }} /></div>
                <div className="text-[10px] text-muted-foreground">{a.risk_count} risk(s) · {a.compliance_pct < 55 ? "low compliance is escalating this area's rating" : a.compliance_pct < 75 ? "partial coverage — close gaps to de-risk" : "well-covered area"}.</div>
              </div>
            ))}
          </div>
        )}
      </CardShell>

      {/* Automated Action-Verification Suite + Defensibility Ledger */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CardShell testid="rem-verify-suite" title="Automated Action-Verification Suite" icon={PlugZap} accent={ACCENT}
          right={isAdmin && <button data-testid="rem-verify-run" disabled={verifyBusy} onClick={doVerify} className="flex items-center gap-1 text-[11px] font-head font-bold px-2.5 py-1.5 rounded-full disabled:opacity-50" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}>{verifyBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <PlugZap className="w-3 h-3" />} Verify live connectors</button>}>
          <p className="text-xs text-muted-foreground mb-3">Hits each external provider with a live authenticated request, confirms a real HTTP 200, and writes the raw result to the Defensibility Ledger. No mock — an unconfigured connector reports the truth, not a fake pass.</p>
          {!verify ? <EmptyState icon={PlugZap} text="Run the suite to make live authenticated calls to Stripe & Clerk and record the evidence." /> : (
            <div className="space-y-2">
              {Object.entries(verify).map(([prov, r]) => {
                const ok = r.ok; const tone = ok ? "142 70% 45%" : "0 84% 60%";
                return (
                  <div key={prov} data-testid={`rem-verify-${prov}`} className="rounded-lg bg-secondary/40 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-head font-bold text-sm capitalize flex items-center gap-1.5">{ok ? <CheckCircle2 className="w-4 h-4" style={{ color: `hsl(${tone})` }} /> : <XCircle className="w-4 h-4" style={{ color: `hsl(${tone})` }} />}{prov}</span>
                      <span className="font-mono text-[10px] px-2 py-0.5 rounded-full" style={{ background: `hsl(${tone} / 0.15)`, color: `hsl(${tone})` }}>{r.configured === false ? "NOT CONFIGURED" : `HTTP ${r.status}`}</span>
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-1 font-mono">{r.endpoint}</div>
                    <div className="text-[11px] mt-0.5 break-words">{r.summary || r.error || "OK"}</div>
                  </div>
                );
              })}
            </div>
          )}
        </CardShell>

        <CardShell testid="rem-ledger" title="Defensibility Ledger — recorded remediation evidence" icon={ScrollText} accent={ACCENT}
          right={<div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-muted-foreground">{ledger.length} record(s)</span>
            <button data-testid="ledger-export-csv" onClick={() => window.open(`${api.defaults.baseURL}/risk-engine/ledger/export?format=csv`, "_blank")} className="flex items-center gap-1 text-[10px] font-head font-bold px-2 py-1 rounded-full bg-secondary/70 hover:bg-secondary transition-colors"><Download className="w-3 h-3" /> CSV</button>
            <button data-testid="ledger-export-pdf" onClick={() => window.open(`${api.defaults.baseURL}/risk-engine/ledger/export?format=pdf`, "_blank")} className="flex items-center gap-1 text-[10px] font-head font-bold px-2 py-1 rounded-full" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}><Download className="w-3 h-3" /> PDF</button>
          </div>}>

          {!ledger.length ? <EmptyState icon={ScrollText} text="No remediation attempts recorded yet. Every Execute Fix / Verify writes an immutable, board-defensible evidence entry here with the raw provider response." /> : (
            <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
              {ledger.map((e) => <LedgerRow key={e.id} e={e} />)}
            </div>
          )}
        </CardShell>
      </div>

      <RiskDetailModal item={detail} accent={ACCENT} busy={detailBusy} result={actionResult} onClose={() => setDetail(null)} onAction={doAction} />
    </div>
  );
}
