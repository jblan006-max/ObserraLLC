import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ShieldAlert, Loader2, Layers, PlayCircle, Gauge, ShieldCheck, TrendingDown, Calculator, BarChart3, Building2, RefreshCw, Sparkles, FileText, Clock, Target, Activity, BookOpen, Cpu, Crosshair, ChevronDown, X, ChevronRight } from "lucide-react";
import { Line, XAxis, YAxis, Tooltip, ComposedChart, Area, ReferenceDot } from "recharts";
import { ChartBox } from "@/components/ChartBox";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AIInsight } from "@/components/AIInsight";
import { AIFix } from "@/components/AIFix";
import { AIExplain } from "@/components/AIExplain";
import { useDeepDive } from "@/context/DeepDiveContext";

const FAIR_ACCENT = "350 80% 58%";
const TIER = (residual) => residual >= 16 ? "0 84% 60%" : residual >= 9 ? "35 90% 55%" : "142 70% 45%";
const RATECOL = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
const fmtAle = (v) => v == null ? "—" : v >= 1e6 ? `$${(v / 1e6).toFixed(2)}M` : `$${Math.round(v / 1e3)}k`;

function RiskModal({ risk, onClose }) {
  if (!risk) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div data-testid="cyber-risk-modal" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl max-h-[86vh] overflow-y-auto bg-card border rounded-2xl p-6 space-y-4 rise"
        style={{ borderColor: `hsl(${FAIR_ACCENT} / 0.4)`, boxShadow: `inset 0 1px 0 hsl(${FAIR_ACCENT} / 0.3)` }}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[11px]" style={{ color: `hsl(${FAIR_ACCENT})` }}>{risk.ref}</div>
            <div className="font-head font-black text-xl tracking-tight break-words">{risk.title}</div>
            <div className="text-xs text-muted-foreground">{risk.owner || "unassigned"} · {risk.status}</div>
          </div>
          <button data-testid="cyber-risk-modal-close" onClick={onClose} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] font-mono font-bold px-2.5 py-1 rounded-full" style={{ background: `hsl(${TIER(risk.residual)} / 0.15)`, color: `hsl(${TIER(risk.residual)})` }}>Residual {risk.residual}/25</span>
          {risk.inherent != null && <span className="text-[10px] font-mono px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">Inherent {risk.inherent}/25</span>}
        </div>
        <AIFix entity="risk" refId={risk.ref} accent={FAIR_ACCENT} />
      </div>
    </div>
  );
}

function Stat({ label, value, unit, icon: Icon, accent, onClick, testid }) {
  const Comp = onClick ? "button" : "div";
  return (
    <Comp type={onClick ? "button" : undefined} data-testid={testid} onClick={onClick}
      className={`text-left w-full bg-card fact-border rounded-xl p-4 ${onClick ? "hover:bg-secondary/30 transition-colors cursor-pointer" : ""}`}
      style={accent ? { borderLeft: `3px solid hsl(${accent})` } : {}}>
      <div className="text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1.5">
        {Icon && <Icon className="w-3.5 h-3.5" />} {label}
        {onClick && <ChevronRight className="w-3 h-3 ml-auto" />}
      </div>
      <div className="font-head font-black text-3xl mt-1">{value}{unit}</div>
      {onClick && <div className="text-[10px] text-ai mt-0.5">Click for AI insight &amp; recommendation</div>}
    </Comp>
  );
}

export default function CyberRisk() {
  const { user, mode } = useAuth();
  const isAdmin = user?.role === "admin";
  const isExec = mode === "executive";
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const [selRisk, setSelRisk] = useState(null);
  const [metric, setMetric] = useState(null);
  const [strat, setStrat] = useState(null);

  const load = () => api.get("/cyber/overview").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);
  useEffect(() => { api.get("/risk-engine/strategic").then((r) => setStrat(r.data)).catch(() => {}); }, []);

  const treat = async (ref) => {
    setBusy(ref);
    try { await api.post(`/cyber/risks/${ref}/treat`); toast.success(`Treatment workflow opened for ${ref}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Treat failed"); }
    setBusy("");
  };

  if (!data) return <div className="flex items-center justify-center h-96" data-testid="cyber-loading"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  const aleMap = {};
  (strat?.top_risks || []).forEach((r) => { aleMap[r.ref] = r; });

  return (
    <div className="rise space-y-6" data-testid="cyber-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><ShieldAlert className="w-7 h-7 text-primary" /> Risk</h1>
        <p className="text-sm text-muted-foreground mt-1">{isExec ? "Strategic risk posture — FAIR-quantified business exposure and mitigation at a glance." : "Control-centric risk posture — a kernel-native app composed on the Obserra kernel."}</p>
        <div data-testid="cyber-composition" className="flex flex-wrap items-center gap-2 mt-3">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Layers className="w-3.5 h-3.5" /> Composed on:</span>
          {data.composition.map((c) => <span key={c} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{c}</span>)}
          {data.live_m365_users != null && <span data-testid="cyber-m365-live" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/15 text-low border border-low/30">M365 LIVE · {data.live_m365_users} users{data.live_m365_risky != null ? ` · ${data.live_m365_risky} risky` : ""}</span>}
          {data.live_risk_penalty > 0 && <span data-testid="cyber-risk-penalty" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-high/15 text-high border border-high/30">−{data.live_risk_penalty} posture (live signal)</span>}
        </div>
      </div>

      <AIInsight dashboard="Risk (FAIR)" accent={FAIR_ACCENT} auto slug="cyber-risk-fair" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Posture score" value={data.posture_score} unit="" icon={Gauge} accent="142 70% 45%" testid="cyber-stat-posture" onClick={() => setMetric({ title: "Posture score", kind: "fair-metric", context: { posture_score: data.posture_score, mitigation_pct: data.mitigation_pct, control_coverage: data.control_coverage, open_risks: data.open_risks, total_risks: data.total_risks, live_risk_penalty: data.live_risk_penalty } })} />
        <Stat label="Risk mitigation" value={data.mitigation_pct} unit="%" icon={TrendingDown} testid="cyber-stat-mitigation" onClick={() => setMetric({ title: "Risk mitigation", kind: "fair-metric", context: { mitigation_pct: data.mitigation_pct, posture_score: data.posture_score, open_risks: data.open_risks, total_risks: data.total_risks } })} />
        <Stat label="Control coverage" value={data.control_coverage} unit="%" icon={ShieldCheck} testid="cyber-stat-coverage" onClick={() => setMetric({ title: "Control coverage", kind: "fair-metric", context: { control_coverage: data.control_coverage, mitigation_pct: data.mitigation_pct, posture_score: data.posture_score } })} />
        <Stat label="Open risks" value={`${data.open_risks}/${data.total_risks}`} unit="" icon={ShieldAlert} accent="0 84% 60%" testid="cyber-stat-openrisks" onClick={() => setMetric({ title: "Open risks", kind: "fair-metric", context: { open_risks: data.open_risks, total_risks: data.total_risks, top_risks: (data.risks || []).slice(0, 6).map((r) => ({ ref: r.ref, title: r.title, residual: r.residual, status: r.status })) } })} />
      </div>

      <div className="bg-card fact-border rounded-xl overflow-x-auto" data-testid="cyber-top-risks">
        <div className="px-4 py-3 border-b border-border text-xs font-mono uppercase tracking-wider text-muted-foreground">Top residual cyber risks</div>
        <table className="w-full text-sm min-w-[720px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3">Risk</th><th className="text-left px-4 py-3">Owner</th><th className="text-left px-4 py-3">Status</th><th className="text-left px-4 py-3">Residual</th><th className="text-left px-4 py-3">Live ALE</th><th className="text-left px-4 py-3">Rating</th><th className="text-right px-4 py-3">Action</th></tr>
          </thead>
          <tbody>
            {data.risks.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">No cyber risks recorded.</td></tr>
            ) : data.risks.map((r) => (
              <tr key={r.ref} data-testid={`cyber-risk-${r.ref}`} onClick={() => setSelRisk(r)} className="border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer">
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{r.ref}</div><div className="font-medium">{r.title}</div></td>
                <td className="px-4 py-3 text-muted-foreground">{r.owner || "—"}</td>
                <td className="px-4 py-3">{r.status}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${TIER(r.residual)} / 0.15)`, color: `hsl(${TIER(r.residual)})` }}>{r.residual}/25</span></td>
                <td className="px-4 py-3 font-mono text-xs" data-testid={`cyber-ale-${r.ref}`}>{aleMap[r.ref] ? fmtAle(aleMap[r.ref].residual_ale) : "—"}</td>
                <td className="px-4 py-3">{aleMap[r.ref] ? <span data-testid={`cyber-rating-${r.ref}`} className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${RATECOL[aleMap[r.ref].rating]} / 0.15)`, color: `hsl(${RATECOL[aleMap[r.ref].rating]})` }}>{aleMap[r.ref].rating}{aleMap[r.ref].exceeds_appetite ? " ⚠" : ""}</span> : <span className="text-muted-foreground text-xs">—</span>}</td>
                <td className="px-4 py-3 text-right">
                  <div className="inline-flex items-center gap-2">
                    {isAdmin && !isExec && <button data-testid={`treat-${r.ref}`} disabled={!!busy} onClick={(e) => { e.stopPropagation(); treat(r.ref); }} className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 disabled:opacity-50">{busy === r.ref ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />} Treat</button>}
                    <span className="text-[10px] font-mono text-ai flex items-center gap-0.5 whitespace-nowrap">AI fix <ChevronRight className="w-3.5 h-3.5" /></span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">Click any risk for its AI risk rating, the reasoning behind it, and the recommended fix. Treating a risk opens a remediation workflow and alerts owners — proving the kernel loop.</p>

      <FairDashboard overview={data} />
      <FinancialBasis isAdmin={isAdmin} />
      <RiskModal risk={selRisk} onClose={() => setSelRisk(null)} />
      {metric && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setMetric(null)}>
          <div data-testid="cyber-metric-modal" onClick={(e) => e.stopPropagation()} className="w-full max-w-lg max-h-[86vh] overflow-y-auto bg-card border rounded-2xl p-6 space-y-4 rise" style={{ borderColor: `hsl(${FAIR_ACCENT} / 0.4)`, boxShadow: `inset 0 1px 0 hsl(${FAIR_ACCENT} / 0.3)` }}>
            <div className="flex items-start justify-between gap-3">
              <div className="font-head font-black text-lg tracking-tight">{metric.title}</div>
              <button data-testid="cyber-metric-close" onClick={() => setMetric(null)} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
            </div>
            <AIExplain title={metric.title} kind={metric.kind} context={metric.context} accent={FAIR_ACCENT} />
          </div>
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, sub, accent }) {
  const { openDeepDive } = useDeepDive();
  return (
    <button type="button" onClick={() => openDeepDive({ accent: accent || FAIR_ACCENT, refLabel: "FAIR KPI", title: label,
      facets: [{ label, value: String(value) }, ...(sub ? [{ label: "Basis", value: sub }] : [])],
      recommendedActions: ["Trace this figure to its top loss drivers below — the highest-$ FAIR factor (loss magnitude / threat frequency / control weakness) is where remediation cuts exposure most."],
      explainTitle: label, explainKind: "fair financial kpi ale monte-carlo roi exposure", explainContext: { kpi: { label, value, sub } } })}
      className="text-left w-full rounded-lg bg-secondary/40 p-3 cursor-pointer hover:bg-secondary/60 transition-colors" style={accent ? { borderLeft: `3px solid hsl(${accent})` } : {}}>
      <div className="text-[10px] font-mono uppercase text-muted-foreground">{label}</div>
      <div className="font-head font-black text-2xl">{value}</div>
      <div className="text-[10px] text-muted-foreground">{sub}</div>
    </button>
  );
}

const DRIVER_COLOR = { "Loss magnitude": "0 84% 60%", "Threat frequency": "35 90% 55%", "Control weakness": "190 90% 50%" };
const DRIVER_WHY = {
  "Loss magnitude": "driven by the high single-loss cost — mitigation that lowers impact/records exposed cuts $ most",
  "Threat frequency": "driven by how often the event is expected — reducing occurrence rate cuts $ most",
  "Control weakness": "driven by weak residual controls — strengthening controls cuts exposure most",
};

function FactorNode({ label, abbr, value, desc, accent = "215 15% 55%", children }) {
  return (
    <div className="min-w-0">
      <div className="rounded-md border px-3 py-2 mb-2" style={{ borderColor: `hsl(${accent} / 0.4)`, background: `hsl(${accent} / 0.06)` }}>
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="font-head font-bold text-xs">{label}</span>
          {abbr && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm" style={{ color: `hsl(${accent})`, background: `hsl(${accent} / 0.14)` }}>{abbr}</span>}
          {value != null && <span className="ml-auto font-mono text-xs font-bold" style={{ color: `hsl(${accent})` }}>{value}</span>}
        </div>
        {desc && <div className="text-[10px] text-muted-foreground mt-0.5 leading-snug">{desc}</div>}
      </div>
      {children && <div className="border-l pl-3 ml-2 mb-1" style={{ borderColor: `hsl(${accent} / 0.3)` }}>{children}</div>}
    </div>
  );
}

const GPT_MODELS = [
  { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", speed: "Slowest", cost: "$$$$", note: "max reasoning depth" },
  { id: "gpt-5.6-terra", label: "GPT-5.6 Terra", speed: "Slow", cost: "$$$", note: "high reasoning" },
  { id: "gpt-5.6-luna", label: "GPT-5.6 Luna", speed: "Slow", cost: "$$$", note: "high reasoning" },
  { id: "gpt-5.5", label: "GPT-5.5", speed: "Medium", cost: "$$", note: "strong reasoning" },
  { id: "gpt-5.4", label: "GPT-5.4", speed: "Fast", cost: "$$", note: "balanced (default)" },
  { id: "gpt-5.4-mini", label: "GPT-5.4 Mini", speed: "Fastest", cost: "$", note: "quick & economical" },
];

const FAIR_AIR_ILLUSTRATIVE = [
  { v: "Shadow GenAI", p: 5, loss: "$5M", stmt: "employees leak company-sensitive information via an open-source LLM (e.g. ChatGPT)", driver: "# of employees with access to sensitive data using unsanctioned AI tools" },
  { v: "Foundational LLM", p: 8, loss: "$10M", stmt: "a model trained without bias/integrity safeguards produces harmful or non-compliant output", driver: "% of training data without vetted permissions & provenance" },
  { v: "Hosting on LLMs", p: 6, loss: "$12M", stmt: "an LLM with undefined success criteria produces integrity-damaging output and an outage", driver: "coverage of model-output validation & defined success criteria" },
  { v: "Managed LLMs", p: 7, loss: "$15M", stmt: "a third-party LLM leaks sensitive data via prompt injection", driver: "volume of sensitive data sent to third-party LLMs × vendor control maturity" },
  { v: "Active cyber attack", p: 12, loss: "$8M", stmt: "adversaries use LLMs to enhance phishing and breach sensitive data", driver: "phishing click-rate among employees with access to large amounts of sensitive data" },
];

function FairDashboard({ overview }) {
  const [d, setD] = useState(null);
  const [nist, setNist] = useState(null);
  const [aiScenarios, setAiScenarios] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiModel, setAiModel] = useState("");
  const [aiModelSel, setAiModelSel] = useState("gpt-5.4");
  const [vec, setVec] = useState(null);
  const [vecBusy, setVecBusy] = useState(false);
  const [vecData, setVecData] = useState(null);
  const [openCtrl, setOpenCtrl] = useState(null);
  useEffect(() => {
    api.get("/financial/fair").then((r) => setD(r.data)).catch(() => {});
    api.get("/financial/nist-coverage").then((r) => setNist(r.data)).catch(() => {});
    api.get("/advisor/fair-air/latest").then((r) => { if (r.data && (r.data.scenarios || []).length) { setAiScenarios(r.data.scenarios); setAiModel(r.data.model || "AI"); } }).catch(() => {});
  }, []);
  if (!d) return null;
  const analyzeAI = async () => {
    setAiBusy(true);
    try {
      const { data } = await api.post("/advisor/fair-air", { model: aiModelSel });
      const jid = data.job_id;
      let tries = 0;
      const poll = async () => {
        try {
          const r = await api.get(`/advisor/fair-air/${jid}`);
          if (r.data.status === "done") { setAiScenarios(r.data.scenarios || []); setAiModel(r.data.model || "AI"); setAiBusy(false); toast.success("FAIR-AIR AI analysis ready"); return; }
          if (r.data.status === "error") { setAiBusy(false); toast.error("AI analysis failed"); return; }
        } catch (e) {}
        if (tries++ > 60) { setAiBusy(false); toast.error("AI analysis timed out"); return; }
        setTimeout(poll, 2000);
      };
      setTimeout(poll, 2000);
    } catch (e) { setAiBusy(false); toast.error(e.response?.data?.detail || "AI analysis failed"); }
  };
  const openVector = async (name) => {
    setVec({ name }); setVecData(null); setVecBusy(true);
    try {
      const { data } = await api.post("/advisor/fair-air/vector", { vector: name, model: aiModelSel });
      const jid = data.job_id;
      let tries = 0;
      const poll = async () => {
        try {
          const r = await api.get(`/advisor/fair-air/vector/${jid}`);
          if (r.data.status === "done") { setVecData(r.data.analysis || {}); setVecBusy(false); return; }
          if (r.data.status === "error") { setVecBusy(false); toast.error("Vector analysis failed"); return; }
        } catch (e) {}
        if (tries++ > 60) { setVecBusy(false); toast.error("Vector analysis timed out"); return; }
        setTimeout(poll, 2000);
      };
      setTimeout(poll, 2000);
    } catch (e) { setVecBusy(false); toast.error(e.response?.data?.detail || "Vector analysis failed"); }
  };
  const fmt = (n) => n == null ? "—" : n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : `$${(n / 1e3).toFixed(0)}k`;
  const p = d.portfolio;
  const k = d.kpis || {};
  const dc = (name) => DRIVER_COLOR[name] || "215 15% 55%";
  const rr = d.risks || [];
  const avgOf = (key) => rr.length ? rr.reduce((s, x) => s + (x[key] || 0), 0) / rr.length : 0;
  const avgLef = avgOf("lef").toFixed(2);
  const avgTef = avgOf("tef").toFixed(2);
  const avgVuln = avgOf("vulnerability").toFixed(2);
  const avgLM = fmt(avgOf("loss_magnitude"));
  return (
    <div className="bg-card fact-border rounded-xl p-5 space-y-5" data-testid="fair-dashboard">
      <div className="flex flex-wrap items-center gap-2">
        <Target className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">FAIR risk quantification</h2>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-secondary text-muted-foreground">Factor Analysis of Information Risk</span>
      </div>
      <div className="rounded-lg border border-ai/20 bg-ai/[0.04] p-3" data-testid="fair-pipeline">
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-3 flex items-center gap-1"><Activity className="w-3.5 h-3.5 text-ai" /> How Obserra ties the cyber model together to quantify risk</div>
        <div className="flex flex-col md:flex-row md:items-stretch gap-2">
          {[
            { t: "Signals & evidence", d: "Live connectors, security scans, control status & incidents", m: overview ? `${overview.composition?.length || 0} sources · ${overview.control_coverage}% controls` : "live inputs", a: "190 90% 50%" },
            { t: "FAIR factors", d: "Each risk scored: Loss Magnitude × Loss Event Frequency", m: `${rr.length} risks quantified`, a: "190 90% 50%" },
            { t: "Monte-Carlo", d: "3,000 iterations over magnitude & frequency uncertainty", m: "P10 · P50 · P90", a: "35 90% 55%" },
            { t: "Aggregate exposure", d: "Portfolio residual ALE + loss-exceedance curve", m: `${fmt(k.dollars_at_risk)} at risk`, a: "0 84% 60%" },
            { t: "Board decision", d: "Prioritize by $, ROI-rank remediation, CRO sign-off", m: `${k.remediation_roi}× ROI`, a: "150 60% 45%" },
          ].map((s, i, arr) => (
            <div key={s.t} className="flex md:flex-1 items-center gap-2" data-testid={`fair-pipe-${i}`}>
              <div className="flex-1 rounded-lg border p-2.5 h-full" style={{ borderColor: `hsl(${s.a} / 0.35)`, background: `hsl(${s.a} / 0.06)` }}>
                <div className="text-[10px] font-mono uppercase tracking-wide" style={{ color: `hsl(${s.a})` }}>{i + 1}. {s.t}</div>
                <div className="text-[10px] text-muted-foreground mt-1 leading-snug">{s.d}</div>
                <div className="font-mono text-xs font-bold mt-1.5">{s.m}</div>
              </div>
              {i < arr.length - 1 && <span className="hidden md:block text-muted-foreground shrink-0">→</span>}
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-lg bg-ai/5 border border-ai/20 p-3 space-y-1.5" data-testid="fair-formula">
        <div className="text-[10px] font-mono uppercase text-muted-foreground">How this is calculated (FAIR)</div>
        <div className="font-mono text-sm text-foreground">ALE = Loss Magnitude (LM) × Loss Event Frequency (LEF)</div>
        <div className="font-mono text-sm text-foreground">LEF = Threat Event Frequency (TEF) × Vulnerability</div>
        <div className="text-[10px] text-muted-foreground leading-relaxed">
          <b>LM</b> = $ cost of a single loss event (your configured SLE / per-record model). <b>TEF</b> = how often the threat acts (likelihood ÷ 5).
          <b> Vulnerability</b> = residual ÷ inherent (control weakness). <b>ALE</b> = expected annual loss; the P10–P90 band comes from a 2,000+ iteration Monte-Carlo over these factors.
        </div>
      </div>
      <div className="rounded-lg border border-border p-3" data-testid="fair-ontology">
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-3 flex items-center gap-1"><Target className="w-3.5 h-3.5" /> The FAIR model — how RISK decomposes into measurable factors</div>
        <FactorNode label="Risk" abbr="ALE" value={fmt(k.dollars_at_risk)} desc="Annualized loss exposure — expected $ loss per year (portfolio residual)." accent="0 84% 60%">
          <FactorNode label="Loss Event Frequency" abbr="LEF" value={`${avgLef}/yr`} desc="How often a loss event is expected to occur." accent="190 90% 50%">
            <FactorNode label="Threat Event Frequency" abbr="TEF" value={avgTef} desc="How often a threat acts against the asset." accent="190 90% 50%">
              <FactorNode label="Contact Frequency" desc="How often the threat comes into contact with the asset." accent="190 55% 58%" />
              <FactorNode label="Probability of Action" abbr="PoA" desc="Likelihood the threat acts once in contact." accent="190 55% 58%" />
            </FactorNode>
            <FactorNode label="Vulnerability" value={avgVuln} desc="Probability a threat action becomes a loss = residual ÷ inherent control strength." accent="190 90% 50%">
              <FactorNode label="Threat Capability" abbr="TCap" desc="Skill & resources of the threat actor." accent="190 55% 58%" />
              <FactorNode label="Resistance Strength" abbr="RS" desc="Strength of your controls against the threat." accent="190 55% 58%" />
            </FactorNode>
          </FactorNode>
          <FactorNode label="Loss Magnitude" abbr="LM" value={avgLM} desc="$ cost of a single loss event (configured SLE / per-record model)." accent="35 90% 55%">
            <FactorNode label="Primary Loss" desc="Direct costs — incident response, replacement, lost productivity." accent="35 80% 60%" />
            <FactorNode label="Secondary Risk" desc="Fallout from stakeholder reactions — fines, legal, reputation." accent="35 80% 60%">
              <FactorNode label="Secondary Loss Event Frequency" desc="How often the fallout losses occur." accent="35 70% 63%" />
              <FactorNode label="Secondary Loss Magnitude" desc="$ cost of the secondary fallout." accent="35 70% 63%" />
            </FactorNode>
          </FactorNode>
        </FactorNode>
        <div className="text-[10px] text-muted-foreground mt-1">Values are portfolio averages across your open risks; leaf factors are the FAIR sub-drivers that roll up into each parent. Source: The Open Group FAIR™ (O-RA).</div>
      </div>
      <div className="rounded-lg border border-ai/20 bg-ai/[0.04] p-3" data-testid="fair-approach">
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1 flex flex-wrap items-center gap-2"><Sparkles className="w-3.5 h-3.5 text-ai" /> FAIR-AIR — quantifying AI-related cyber risk <span className="text-[9px] font-mono px-2 py-0.5 rounded-sm bg-ai/15 text-ai border border-ai/30" data-testid="fair-air-label">FAIR-AIR · AI RISK REDUCTION</span></div>
        <p className="text-[10px] text-muted-foreground mb-3 leading-snug">FAIR adapted to AI (generative AI &amp; LLMs): translates AI threats into $ loss exposure so leaders can adopt AI securely and defensibly. Source: FAIR Institute.</p>
        <div className="rounded-md border-l-2 border-ai bg-ai/[0.06] px-3 py-2 mb-3" data-testid="fair-air-quote">
          <p className="text-[11px] italic text-foreground/90">"The purpose of this approach is to meet the business needs, not create additional obstacles to AI deployment."</p>
        </div>
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">The 5 vectors of GenAI risk (FAIR-AIR)</div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3">
          {[
            ["Shadow GenAI", "Staff using GenAI without approval — e.g. leaking sensitive data via ChatGPT."],
            ["Foundational LLM", "Building your own model — training-data permissions, bias & integrity."],
            ["Hosting on LLMs", "Hosting an LLM for use cases — undefined success criteria → bad output."],
            ["Managed LLMs", "Third-party LLM APIs — prompt-injection data leakage & vendor controls."],
            ["Active cyber attack", "Adversaries using LLMs — AI-enhanced phishing & zero-day discovery."],
          ].map(([t, s], i) => (
            <div key={t} data-testid={`fair-air-vector-${i}`} onClick={() => openVector(t)} className="text-left rounded-md border border-ai/20 bg-background/40 p-2 hover:border-ai/60 hover:bg-ai/[0.06] transition-colors cursor-pointer group">
              <div className="flex items-center justify-between gap-1"><div className="font-head font-bold text-[11px] text-ai">{t}</div><Sparkles className="w-3 h-3 text-ai opacity-0 group-hover:opacity-100 transition-opacity shrink-0" /></div>
              <div className="text-[10px] text-muted-foreground mt-0.5 leading-snug">{s}</div>
              <div className="text-[8px] font-mono uppercase text-ai/70 mt-1">Click → AI deep-dive</div>
            </div>
          ))}
        </div>
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">The 5-step FAIR-AIR method</div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {[
            ["Contextualize", "Identify the AI risk vectors in play across the org."],
            ["Scope", "Frame each scenario — asset, threat actor, method & impact."],
            ["Quantify", "Model LEF × LM with Monte-Carlo → $ loss range."],
            ["Prioritize", "Rank by $ exposure & key risk drivers."],
            ["Decide", "Pick treatment balancing security with AI-adoption goals."],
          ].map(([t, s], i) => (
            <div key={t} data-testid={`fair-step-${i}`} className="rounded-md border border-border bg-secondary/30 p-2.5">
              <div className="w-6 h-6 rounded-full bg-ai/15 text-ai flex items-center justify-center text-xs font-bold mb-1.5">{i + 1}</div>
              <div className="font-head font-bold text-xs">{t}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5 leading-snug">{s}</div>
            </div>
          ))}
        </div>
        <div className="mt-3" data-testid="fair-air-scenarios">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <div className="text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1"><Calculator className="w-3.5 h-3.5" /> Quantified scenarios &amp; key risk drivers (FAIR-AIR output)</div>
            <div className="ml-auto flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-muted-foreground" />
              <select data-testid="fair-air-model-select" value={aiModelSel} onChange={(e) => setAiModelSel(e.target.value)} disabled={aiBusy} className="text-xs bg-secondary border border-border rounded-md px-2 py-1 text-foreground disabled:opacity-60" title="Higher versions use more inference compute → more accurate reasoning (International AI Safety Report 2026)">
                {GPT_MODELS.map((m) => <option key={m.id} value={m.id}>{m.label} · {m.cost} · {m.speed}</option>)}
              </select>
              <button data-testid="fair-air-analyze-btn" onClick={analyzeAI} disabled={aiBusy} className="text-xs px-2.5 py-1 rounded-md bg-ai text-white flex items-center gap-1 disabled:opacity-60">
                {aiBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} {aiBusy ? "Analyzing…" : "Analyze with AI"}
              </button>
            </div>
          </div>
          {(() => { const mm = GPT_MODELS.find((x) => x.id === aiModelSel) || GPT_MODELS[4]; return (
          <div className="text-[9px] text-muted-foreground mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5" data-testid="fair-air-compute-note">
            <span className="inline-flex items-center gap-1"><Cpu className="w-3 h-3" /> {mm.label}: <span className="text-foreground/80">{mm.speed}</span> · <span className="text-foreground/80">cost {mm.cost}</span> · {mm.note}</span>
            <span>More inference compute (higher version) = more accurate reasoning &amp; deeper synthesis. <span className="text-foreground/70">Source: International AI Safety Report 2026 (Fig. 1.6).</span></span>
          </div>
          ); })()}
          {aiScenarios && (
            <div className="text-[10px] text-ai mb-1.5 flex items-center gap-1 flex-wrap" data-testid="fair-air-ai-badge"><Sparkles className="w-3 h-3 shrink-0" /> AI-generated by {aiModel} (advanced reasoning) · grounded in your risk, AI-system &amp; benchmark data · expected annual AI loss ≈ {fmt(aiScenarios.reduce((s, x) => s + (Number(x.probability_pct) || 0) / 100 * (Number(x.loss_usd) || 0), 0))} · auto-refreshed weekly</div>
          )}
          <div className="space-y-2">
            {(aiScenarios || FAIR_AIR_ILLUSTRATIVE).map((s, i) => (
              <div key={i} data-testid={`fair-air-scenario-${i}`} className="rounded-md border border-border bg-background/40 p-2.5">
                <div className="flex items-start gap-2 flex-wrap">
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-ai/12 text-ai shrink-0">{s.vector || s.v}</span>
                  <span className="text-[11px] leading-snug flex-1 min-w-0">{s.statement ? s.statement : <><b className="text-high">{s.p}% probability</b> in the next year that {s.stmt}, leading to <b>{s.loss}</b> in losses.</>}</span>
                </div>
                {s.why_risk && <div className="text-[10px] text-muted-foreground mt-1"><span className="font-semibold text-ai/90">Why it's a risk:</span> {s.why_risk}</div>}
                <div className="text-[10px] text-muted-foreground mt-1"><span className="font-semibold text-foreground/80">Key risk driver:</span> {s.key_driver || s.driver}</div>
                {(s.recommended_controls?.length > 0 || s.nist_functions?.length > 0) && (
                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    {s.recommended_controls?.length > 0 && <span className="text-[9px] text-muted-foreground">Controls:</span>}
                    {(s.recommended_controls || []).map((c, j) => <span key={j} className="text-[8px] font-mono px-1 py-0.5 rounded-sm bg-ai/10 text-ai">{c}</span>)}
                    {(s.nist_functions || []).map((f, j) => <span key={`n${j}`} className="text-[8px] font-mono px-1 py-0.5 rounded-sm bg-secondary text-muted-foreground">{f}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="text-[10px] text-muted-foreground mt-1.5">{aiScenarios ? "AI-produced FAIR-AIR statements grounded in your data with advanced reasoning; validate & calibrate before board use." : "Illustrative statements showing the FAIR-AIR output — a probability and a $ loss per scenario. Click \u201cAnalyze with AI\u201d to generate ones grounded in your data."}</div>
        </div>
        <div className="mt-3 rounded-md border border-border bg-secondary/20 p-2.5" data-testid="fair-nist">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5 flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5" /> Reasoning aligned to NIST AI RMF (AI 100-1) core functions</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              ["GOVERN", "Policies, roles & accountability for AI risk — CRO sign-off + the engine's autonomy guardrails."],
              ["MAP", "Context & AI risk vectors identified — Contextualize + Scope map assets, threats & impact."],
              ["MEASURE", "Risk quantified & tracked — FAIR LEF × LM + Monte-Carlo produce a defensible $ range."],
              ["MANAGE", "Risks prioritized & treated — ROI-ranked remediation, treatment & auto-remediation."],
            ].map(([fn, s], i) => (
              <div key={fn} data-testid={`fair-nist-${i}`} className="rounded-md border border-ai/15 bg-background/40 p-2">
                <div className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-ai/12 text-ai inline-block mb-1">{fn}</div>
                <div className="text-[10px] text-muted-foreground leading-snug">{s}</div>
              </div>
            ))}
          </div>
          <div className="text-[10px] text-muted-foreground mt-1.5">FAIR-AIR supplies the quantitative <b>Measure</b> layer; the four functions together make the AI-risk reasoning auditable and standards-backed. Ref: NIST AI Risk Management Framework (AI 100-1) · The Open Group FAIR™ · FAIR Institute FAIR-AIR playbook.</div>
        </div>
        {(() => {
          const CONTROLS = (nist?.controls?.length ? nist.controls : [
            { c: "AI Acceptable-Use Policy", type: "Governance", fn: "GOVERN 1.1", vec: "Shadow GenAI", cov: 100, fw: ["NIST AI RMF", "ISO 42001", "EU AI Act"] },
            { c: "Approved AI-tool catalog + SSO gating", type: "Preventive", fn: "GOVERN 2.1", vec: "Shadow GenAI", cov: 90, fw: ["NIST AI RMF", "ISO 42001", "SOC 2"] },
            { c: "AI system inventory & registry", type: "Governance", fn: "MAP 1.1", vec: "All vectors", cov: 100, fw: ["NIST AI RMF", "ISO 42001", "EU AI Act"] },
            { c: "DLP: block sensitive data to public LLMs", type: "Preventive", fn: "MANAGE 2.1", vec: "Shadow GenAI", cov: 60, fw: ["NIST AI RMF", "SOC 2", "GDPR"] },
            { c: "Training-data provenance & licensing review", type: "Governance", fn: "MAP 2.3", vec: "Foundational LLM", cov: 30, fw: ["NIST AI RMF", "EU AI Act", "GDPR"] },
            { c: "Bias & fairness testing before release", type: "Detective", fn: "MEASURE 2.11", vec: "Foundational LLM", cov: 25, fw: ["NIST AI RMF", "ISO 42001", "EU AI Act"] },
            { c: "Model-output validation & success criteria", type: "Detective", fn: "MEASURE 2.7", vec: "Hosting on LLMs", cov: 55, fw: ["NIST AI RMF", "ISO 42001"] },
            { c: "Prompt-injection testing & input filtering", type: "Preventive", fn: "MEASURE 2.7", vec: "Managed LLMs", cov: 50, fw: ["NIST AI RMF", "SOC 2"] },
            { c: "Third-party LLM vendor security assessment", type: "Governance", fn: "GOVERN 6.1", vec: "Managed LLMs", cov: 85, fw: ["NIST AI RMF", "SOC 2", "ISO 42001"] },
            { c: "Data minimization for third-party LLM calls", type: "Preventive", fn: "MANAGE 2.2", vec: "Managed LLMs", cov: 45, fw: ["NIST AI RMF", "GDPR"] },
            { c: "Phishing-resistant MFA + user awareness", type: "Preventive", fn: "MANAGE 4.1", vec: "Active cyber attack", cov: 95, fw: ["NIST AI RMF", "SOC 2"] },
            { c: "Continuous vuln scanning + CISA-KEV monitoring", type: "Detective", fn: "MEASURE 2.4", vec: "Active cyber attack", cov: 90, fw: ["NIST AI RMF", "SOC 2"] },
            { c: "Human-in-the-loop review of high-risk output", type: "Corrective", fn: "MANAGE 1.2", vec: "Hosting / Foundational", cov: 20, fw: ["NIST AI RMF", "EU AI Act"] },
            { c: "Model monitoring & drift detection", type: "Detective", fn: "MEASURE 2.12", vec: "Hosting / Foundational", cov: 30, fw: ["NIST AI RMF", "ISO 42001"] },
            { c: "AI incident-response runbook", type: "Corrective", fn: "MANAGE 4.1", vec: "All vectors", cov: 100, fw: ["NIST AI RMF", "SOC 2"] },
            { c: "FAIR-AIR quantification & board reporting", type: "Governance", fn: "MEASURE 2.1", vec: "All vectors", cov: 100, fw: ["NIST AI RMF"] },
          ]);
          const fnColor = (fn) => fn.startsWith("GOVERN") ? "265 70% 65%" : fn.startsWith("MAP") ? "190 90% 50%" : fn.startsWith("MEASURE") ? "35 90% 55%" : "142 70% 45%";
          const covColor = (v) => v >= 80 ? "142 70% 45%" : v >= 40 ? "35 90% 55%" : "0 84% 60%";
          const covLabel = (v) => v >= 80 ? "Met" : v >= 40 ? "Partial" : "Gap";
          const overall = Math.round(CONTROLS.reduce((s, c) => s + c.cov, 0) / CONTROLS.length);
          const implemented = CONTROLS.filter((c) => c.cov >= 80).length;
          const frameworks = [...new Set(CONTROLS.flatMap((c) => c.fw))];
          const byFn = ["GOVERN", "MAP", "MEASURE", "MANAGE"].map((f) => { const it = CONTROLS.filter((c) => c.fn.startsWith(f)); return { f, cov: it.length ? Math.round(it.reduce((s, c) => s + c.cov, 0) / it.length) : 0 }; });
          return (
          <div className="mt-3 rounded-md border border-border p-2.5" data-testid="fair-nist-controls">
            <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><Layers className="w-3.5 h-3.5" /> AI risks mapped to NIST AI RMF — controls coverage &amp; compliance <span className="text-[8px] font-mono px-1 py-0.5 rounded-sm" style={{ background: nist ? "hsl(142 70% 45% / 0.15)" : "hsl(215 15% 55% / 0.15)", color: nist ? "hsl(142 70% 45%)" : "hsl(215 15% 55%)" }}>{nist ? "LIVE" : "SAMPLE"}</span></div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3" data-testid="fair-nist-summary">
              <div className="rounded-md bg-secondary/40 p-2"><div className="text-[9px] font-mono uppercase text-muted-foreground">Overall coverage</div><div className="font-head font-black text-xl" style={{ color: `hsl(${covColor(overall)})` }}>{overall}%</div></div>
              <div className="rounded-md bg-secondary/40 p-2"><div className="text-[9px] font-mono uppercase text-muted-foreground">Controls met</div><div className="font-head font-black text-xl">{implemented}/{CONTROLS.length}</div></div>
              <div className="rounded-md bg-secondary/40 p-2"><div className="text-[9px] font-mono uppercase text-muted-foreground">Frameworks</div><div className="font-head font-black text-xl">{frameworks.length}</div><div className="text-[9px] text-muted-foreground truncate">{frameworks.join(" · ")}</div></div>
              <div className="rounded-md bg-secondary/40 p-2"><div className="text-[9px] font-mono uppercase text-muted-foreground mb-0.5">By NIST function</div>{byFn.map((b) => <div key={b.f} className="flex items-center gap-1 text-[9px]"><span className="w-16 font-mono shrink-0" style={{ color: `hsl(${fnColor(b.f)})` }}>{b.f}</span><div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${b.cov}%`, background: `hsl(${fnColor(b.f)})` }} /></div><span className="w-7 text-right text-muted-foreground shrink-0">{b.cov}%</span></div>)}</div>
            </div>
            <div className="max-h-72 overflow-y-auto pr-1 space-y-1.5" data-testid="fair-controls-list">
              {CONTROLS.map((r, i) => (
                <div key={i} data-testid={`fair-control-${i}`} onClick={() => setOpenCtrl(openCtrl === i ? null : i)} className="rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5 cursor-pointer hover:border-ai/40 transition-colors" title="Click for coverage drivers">
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm shrink-0 w-24 text-center" style={{ background: `hsl(${fnColor(r.fn)} / 0.15)`, color: `hsl(${fnColor(r.fn)})` }}>{r.fn}</span>
                    <span className="text-[11px] flex-1 min-w-0 truncate" title={r.c}>{r.c}</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-secondary text-muted-foreground shrink-0 hidden sm:inline">{r.type}</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm shrink-0 text-center" style={{ background: `hsl(${covColor(r.cov)} / 0.15)`, color: `hsl(${covColor(r.cov)})` }}>{r.cov}% · {covLabel(r.cov)}</span>
                    <ChevronDown className={`w-3 h-3 text-muted-foreground shrink-0 transition-transform ${openCtrl === i ? "rotate-180" : ""}`} />
                  </div>
                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    <span className="text-[9px] text-muted-foreground">Treats: <span className="text-foreground/80">{r.vec}</span></span>
                    <span className="text-muted-foreground/40">·</span>
                    <span className="text-[9px] text-muted-foreground">Compliance:</span>
                    {r.fw.map((f) => <span key={f} className="text-[8px] font-mono px-1 py-0.5 rounded-sm bg-ai/10 text-ai">{f}</span>)}
                  </div>
                  {openCtrl === i && (
                    <div className="mt-1.5 pt-1.5 border-t border-border/40 text-[10px] text-muted-foreground space-y-1" data-testid={`fair-control-detail-${i}`}>
                      <div><span className="font-semibold text-foreground/80">What drives this score:</span> {r.basis || "Sampled baseline — connect live control & scan data for a computed score."}</div>
                      <div><span className="font-semibold text-ai/90">To raise it:</span> {r.raise || "Improve the mapped controls & evidence for this NIST function."}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="text-[10px] text-muted-foreground mt-1.5">Each control shows its <b>type</b>, <b>% coverage</b>, the GenAI vector it treats, and the <b>compliance frameworks met</b> (NIST AI RMF · ISO/IEC 42001 · SOC 2 · EU AI Act · GDPR). Scroll for the full library — the goal is to meet business needs, not block AI adoption.</div>
          </div>
          );
        })()}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="fair-kpis">
        <Kpi label="$ at Risk (residual ALE)" value={fmt(k.dollars_at_risk)} sub={`down ${k.reduction_pct}% from inherent ${fmt(p.inherent_ale)}`} accent="0 84% 60%" />
        <Kpi label="Worst case (P90)" value={fmt(k.worst_case_p90)} sub="10% adverse-case scenario" />
        <Kpi label="Remediation ROI" value={`${k.remediation_roi}×`} sub={`retire ${fmt(k.remediation_reduction)} for ~${fmt(k.remediation_cost)}`} accent="150 60% 45%" />
        <Kpi label="Accepted (carried)" value={fmt(k.accepted_exposure)} sub={`${d.acceptance.count} open risks unremediated`} />
      </div>
      {d.deductions?.length > 0 && (
        <div className="rounded-lg border border-ai/20 bg-ai/5 p-3" data-testid="fair-deductions">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><Sparkles className="w-3.5 h-3.5 text-ai" /> FAIR-based deductions</div>
          <ul className="space-y-1.5">
            {d.deductions.map((t, i) => (
              <li key={i} data-testid={`fair-deduction-${i}`} className="text-xs flex gap-2"><span className="text-ai mt-0.5">▸</span><span>{t}</span></li>
            ))}
          </ul>
        </div>
      )}
      {d.kpi_references?.length > 0 && (
        <details className="rounded-lg border border-border p-3" data-testid="fair-kpi-refs">
          <summary className="text-[10px] font-mono uppercase text-muted-foreground cursor-pointer flex items-center gap-1"><BookOpen className="w-3.5 h-3.5" /> Why these KPIs — board benchmarks (Gartner · NACD · FAIR · WEF)</summary>
          <ul className="mt-3 space-y-2.5">
            {d.kpi_references.map((r, i) => (
              <li key={i} data-testid={`fair-kpi-ref-${i}`} className="text-[11px]">
                <div className="font-semibold text-foreground">{r.kpi} — <span className="text-ai">{r.source}</span></div>
                <div className="text-muted-foreground">{r.why} <a href={r.url} target="_blank" rel="noreferrer" className="text-ai underline whitespace-nowrap">source ↗</a></div>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div>
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Exposure by area · FAIR breakdown</div>
        <div className="grid md:grid-cols-2 gap-3" data-testid="fair-by-area">
          {d.by_area.map((a) => (
            <div key={a.area} data-testid={`fair-area-${a.area}`} className="rounded-lg border border-border p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="font-head font-bold text-sm">{a.area}</div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm shrink-0" style={{ background: `hsl(${dc(a.dominant_driver)} / 0.15)`, color: `hsl(${dc(a.dominant_driver)})` }}>{a.dominant_driver}</span>
              </div>
              <div className="flex items-end justify-between">
                <div><div className="font-head font-black text-xl">{fmt(a.residual_ale)}</div><div className="text-[10px] text-muted-foreground">residual ALE · {a.share_pct}% of portfolio</div></div>
                <div className="text-right text-[10px] text-muted-foreground">{a.count} risk(s)<br />↓{a.reduction_pct}% vs inherent</div>
              </div>
              <div className="h-1.5 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${a.share_pct}%`, background: `hsl(${dc(a.dominant_driver)})` }} /></div>
              <div className="grid grid-cols-2 gap-2 text-[10px] text-muted-foreground">
                <div>Avg vulnerability <span className="text-foreground font-mono">{a.avg_vulnerability}</span></div>
                <div>Avg threat freq <span className="text-foreground font-mono">{a.avg_tef}</span></div>
              </div>
              {a.top_risk && <div className="text-[10px] text-muted-foreground truncate">Top: <span className="font-mono text-ai">{a.top_risk.ref}</span> {a.top_risk.title}</div>}
              <div className="text-[10px] text-muted-foreground"><span className="font-semibold text-foreground/80">Why:</span> {DRIVER_WHY[a.dominant_driver] || ""}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-border p-3" data-testid="fair-lec">
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><Activity className="w-3.5 h-3.5" /> Loss exceedance curve · probability annual loss ≥ $X</div>
        <ChartBox height={190}>
          <ComposedChart data={d.loss_exceedance}>
            <XAxis dataKey="loss" type="number" tickFormatter={(v) => `$${(v / 1e6).toFixed(1)}M`} tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" />
            <YAxis dataKey="exceedance_pct" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" width={40} domain={[0, 100]} />
            <Tooltip formatter={(v) => `${v}% chance`} labelFormatter={(v) => `Annual loss ≥ $${(v / 1e6).toFixed(2)}M`} contentStyle={{ background: "hsl(222 18% 12%)", border: "1px solid hsl(222 12% 22%)", fontSize: 11 }} />
            <Area type="monotone" dataKey="exceedance_pct" stroke="hsl(0 84% 60%)" fill="hsl(0 84% 60% / 0.15)" strokeWidth={2} name="Exceedance" />
            {aiScenarios && aiScenarios.map((s, i) => (
              <ReferenceDot key={i} x={Number(s.loss_usd) || 0} y={Math.min(100, Math.max(0, Number(s.probability_pct) || 0))} r={5} fill="hsl(190 90% 50%)" stroke="#fff" strokeWidth={1} ifOverflow="extendDomain" />
            ))}
          </ComposedChart>
        </ChartBox>
        <div className="text-[10px] text-muted-foreground">Y-axis = probability the annual loss meets or exceeds the x-axis dollar amount (3,000-iteration Monte-Carlo over FAIR factors).{aiScenarios && <span className="text-ai"> Cyan dots = AI FAIR-AIR scenarios positioned by their $ loss &amp; probability.</span>}</div>
      </div>
      <Dialog open={!!vec} onOpenChange={(o) => { if (!o) { setVec(null); setVecData(null); } }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="fair-vector-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-ai"><Crosshair className="w-4 h-4" /> {vec?.name} — FAIR-AIR deep-dive</DialogTitle>
          </DialogHeader>
          {vecBusy && <div className="py-10 flex flex-col items-center gap-2 text-muted-foreground" data-testid="fair-vector-loading"><Loader2 className="w-6 h-6 animate-spin text-ai" /><div className="text-xs text-center">Running advanced-reasoning analysis ({aiModelSel})…<br />synthesizing across all dashboards</div></div>}
          {!vecBusy && vecData && (
            <div className="space-y-3" data-testid="fair-vector-content">
              {vecData.summary && <p className="text-sm text-foreground/90 leading-snug">{vecData.summary}</p>}
              {vecData.expected_loss_usd != null && <div className="text-xs font-mono text-high">Expected annual loss ≈ {fmt(Number(vecData.expected_loss_usd))}</div>}
              {vecData.scenarios?.length > 0 && (<div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Quantified scenarios</div><div className="space-y-1.5">{vecData.scenarios.map((sc, i) => (<div key={i} className="rounded-md border border-border bg-secondary/20 p-2 text-[11px]">{sc.statement || `${sc.probability_pct}% → ${fmt(Number(sc.loss_usd))}`}{sc.key_driver && <div className="text-[10px] text-muted-foreground mt-0.5">Driver: {sc.key_driver}</div>}</div>))}</div></div>)}
              {vecData.top_drivers?.length > 0 && (<div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Key risk drivers</div><ul className="list-disc pl-4 text-[11px] text-muted-foreground space-y-0.5">{vecData.top_drivers.map((t, i) => <li key={i}>{t}</li>)}</ul></div>)}
              {vecData.mitigations?.length > 0 && (<div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Tailored mitigations (NIST AI RMF)</div><div className="space-y-1.5">{vecData.mitigations.map((m, i) => (<div key={i} className="rounded-md border border-ai/20 bg-ai/[0.05] p-2 text-[11px]"><div className="flex items-center gap-2"><span className="font-semibold text-foreground/90 flex-1">{m.action}</span>{m.nist_ref && <span className="text-[8px] font-mono px-1 py-0.5 rounded-sm bg-ai/15 text-ai shrink-0">{m.nist_ref}</span>}</div>{m.impact && <div className="text-[10px] text-muted-foreground mt-0.5">{m.impact}</div>}</div>))}</div></div>)}
            </div>
          )}
          {!vecBusy && !vecData && <div className="py-8 text-center text-xs text-muted-foreground">No analysis returned. Try again.</div>}
        </DialogContent>
      </Dialog>
      <div className="rounded-lg border border-border overflow-x-auto" data-testid="fair-risk-table">
        <table className="w-full text-xs min-w-[780px]">
          <thead className="text-[10px] font-mono uppercase text-muted-foreground border-b border-border">
            <tr><th className="text-left px-3 py-2">Risk</th><th className="text-left px-3 py-2">Area</th><th className="text-right px-3 py-2">Loss mag.</th><th className="text-right px-3 py-2">TEF</th><th className="text-right px-3 py-2">Vuln</th><th className="text-right px-3 py-2">LEF</th><th className="text-right px-3 py-2">Residual ALE</th><th className="text-left px-3 py-2">Dominant driver</th></tr>
          </thead>
          <tbody>
            {d.risks.map((i) => (
              <tr key={i.ref} data-testid={`fair-row-${i.ref}`} className="border-b border-border/60">
                <td className="px-3 py-2"><div className="font-mono text-ai">{i.ref}</div><div className="truncate max-w-[170px]">{i.title}</div></td>
                <td className="px-3 py-2 text-muted-foreground">{i.category}</td>
                <td className="px-3 py-2 text-right">{fmt(i.loss_magnitude)}</td>
                <td className="px-3 py-2 text-right font-mono">{i.tef}</td>
                <td className="px-3 py-2 text-right font-mono">{i.vulnerability}</td>
                <td className="px-3 py-2 text-right font-mono">{i.lef}</td>
                <td className="px-3 py-2 text-right"><div className="font-bold">{fmt(i.residual_ale)}</div><div className="text-[10px] text-muted-foreground">P10 {fmt(i.p10)} · P90 {fmt(i.p90)}</div></td>
                <td className="px-3 py-2"><span className="text-[10px] font-mono px-2 py-0.5 rounded-sm" style={{ background: `hsl(${dc(i.driver)} / 0.15)`, color: `hsl(${dc(i.driver)})` }}>{i.driver}</span>{i.remediation_pending && <span className="ml-1 text-[10px] text-med">· fix pending</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {d.benchmark?.feeds?.length > 0 && (
        <div className="rounded-lg border border-border p-3" data-testid="fair-feeds">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5" /> Benchmark feeds — auto-updated{d.benchmark.last_pulled_at ? ` · last pull ${String(d.benchmark.last_pulled_at).slice(0, 16).replace("T", " ")} UTC` : ""}</div>
          <div className="space-y-1">
            {d.benchmark.feeds.map((f, i) => (
              <div key={i} data-testid={`fair-feed-${i}`} className="flex items-center justify-between text-[11px] gap-2">
                <span className="text-muted-foreground truncate">{f.metric} <span className="opacity-60">· {f.source}</span></span>
                <span className="font-mono text-foreground shrink-0">{f.value ? fmt(f.value) : "—"}</span>
              </div>
            ))}
          </div>
          <div className="text-[10px] text-muted-foreground mt-1">Feeds re-pull weekly (IBM Cost of a Data Breach · Verizon DBIR) and when you change industry; the board is notified when a figure changes. Timestamp shows the last successful pull.</div>
        </div>
      )}
      <div className="space-y-1" data-testid="fair-references">
        <p className="text-[11px] text-muted-foreground">FAIR: ALE = Loss Magnitude × Loss Event Frequency (LEF); LEF = Threat Event Frequency (TEF) × Vulnerability (control weakness = residual/inherent). Decision-support estimates, benchmarked against IBM {d.benchmark.industry} avg {fmt(d.benchmark.industry_avg)}.</p>
        {d.references?.length > 0 && (
          <div className="text-[10px] text-muted-foreground">
            <span className="font-mono uppercase tracking-wide">References</span>
            <ul className="list-disc pl-4 mt-0.5 space-y-0.5">{d.references.map((r, i) => <li key={i}>{r}</li>)}{d.benchmark.updated && <li>Benchmark table updated {d.benchmark.updated}</li>}</ul>
          </div>
        )}
      </div>
    </div>
  );
}

function FinancialBasis({ isAdmin }) {
  const [basis, setBasis] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [trend, setTrend] = useState(null);
  const [hist, setHist] = useState([]);
  const [packing, setPacking] = useState(false);
  const [packHistory, setPackHistory] = useState([]);
  const load = () => Promise.all([api.get("/financial/basis"), api.get("/financial/config"), api.get("/financial/benchmark-trend").catch(() => ({ data: { points: [] } })), api.get("/financial/signoff-history").catch(() => ({ data: { history: [] } }))])
    .then(([b, c, t, h]) => { setBasis(b.data); setCfg(c.data); setTrend(t.data); setHist(h.data.history || []); }).catch(() => {});
  useEffect(() => { load(); api.get("/reports/board-pack/history").then((r) => setPackHistory(r.data.history || [])).catch(() => {}); }, []);
  if (!basis || !cfg) return null;
  const fmt = (n) => n == null ? "—" : `$${(n / 1e6).toFixed(n < 1e6 ? 3 : 2)}M`;
  const bench = basis.benchmark;
  const ratio = basis.benchmark_ratio;
  const ratioColor = ratio == null ? "215 15% 55%" : ratio > 1.25 ? "0 84% 60%" : ratio < 0.75 ? "35 90% 55%" : "142 70% 45%";
  const save = async (patch) => {
    setSaving(true);
    try { const { data } = await api.put("/financial/config", patch); setCfg(data); await load(); toast.success("Financial model updated"); }
    catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
    setSaving(false);
  };
  const signOff = async () => { const name = window.prompt("CRO name to sign off this calibration:"); if (!name) return; try { await api.post("/financial/config/signoff", { name }); toast.success("Calibration locked & CRO-signed"); load(); } catch (e) { toast.error("Sign-off failed"); } };
  const unlock = async () => { try { await api.post("/financial/config/unlock"); toast.success("Calibration unlocked"); load(); } catch (e) { toast.error("Unlock failed"); } };
  const autofillRecords = () => { const s = cfg.suggested_records; if (s?.records) save({ method: "records", records: s.records }); };
  const boardPack = async () => {
    setPacking(true);
    try {
      const res = await api.post("/reports/board-pack.pdf", {}, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = "obserra-board-pack.pdf"; a.click();
      URL.revokeObjectURL(url);
      toast.success("Board pack downloaded");
      api.get("/reports/board-pack/history").then((r) => setPackHistory(r.data.history || [])).catch(() => {});
    } catch (e) { toast.error("Could not build board pack"); }
    setPacking(false);
  };
  const so = cfg.config.signoff;
  return (
    <div className="bg-card fact-border rounded-xl p-5 space-y-5" data-testid="financial-basis">
      <div className="flex flex-wrap items-center gap-2"><Calculator className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Financial basis &amp; benchmark</h2><span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-secondary text-muted-foreground">defensible math</span>{basis.signoff?.locked && <span data-testid="fin-approved" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/15 text-low border border-low/30">✓ Approved by {basis.signoff.name} · {String(basis.signoff.at).slice(0, 10)}{basis.signoff.stale ? " (config changed since)" : ""}</span>}<button data-testid="board-pack-btn" onClick={boardPack} disabled={packing} className="ml-auto text-xs px-2.5 py-1 rounded-md bg-ai text-white flex items-center gap-1 disabled:opacity-60">{packing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />} Board pack PDF</button></div>
      {packHistory.length > 0 && (
        <div className="rounded-lg border border-border p-3" data-testid="board-pack-history">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> Board-pack history — AI-risk exposure over time</div>
          <div className="space-y-1">
            {packHistory.slice(0, 8).map((h, i) => (
              <div key={i} data-testid={`board-pack-hist-${i}`} className="flex items-center gap-2 text-[11px] border-b border-border/40 last:border-0 py-1">
                <span className="font-mono text-muted-foreground w-24 shrink-0">{String(h.generated_at).slice(0, 10)}</span>
                <span className="flex-1 truncate">Residual ALE <span className="font-mono text-foreground">{h.residual_ale != null ? fmt(h.residual_ale) : "—"}</span> · AI exp. loss <span className="font-mono text-foreground">{h.ai_expected_loss != null ? fmt(h.ai_expected_loss) : "—"}</span></span>
                <span className="font-mono shrink-0" style={{ color: h.nist_overall >= 80 ? "hsl(142 70% 45%)" : h.nist_overall >= 40 ? "hsl(35 90% 55%)" : "hsl(0 84% 60%)" }}>NIST {h.nist_overall != null ? h.nist_overall + "%" : "—"}</span>
              </div>
            ))}
          </div>
          <div className="text-[10px] text-muted-foreground mt-1">Each row is a generated board pack — compare residual exposure, AI-risk loss &amp; NIST AI RMF coverage quarter over quarter.</div>
        </div>
      )}

      <div className="grid sm:grid-cols-3 gap-3" data-testid="fin-benchmark">
        <div className="rounded-lg bg-secondary/40 p-3">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Your modelled per-incident</div>
          <div className="font-head font-black text-2xl">{fmt(basis.modelled_avg_sle)}</div>
          <div className="text-[10px] text-muted-foreground">avg SLE · max {fmt(basis.modelled_max_sle)}</div>
        </div>
        <div className="rounded-lg bg-secondary/40 p-3">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">{bench.industry} benchmark</div>
          <div className="font-head font-black text-2xl">{fmt(bench.industry_avg)}</div>
          <div className="text-[10px] text-muted-foreground">{bench.industry_avg_source}</div>
          <div className="text-[10px] text-muted-foreground">global {fmt(bench.global_avg)} · {bench.global_avg_source}</div>
        </div>
        <div className="rounded-lg p-3" style={{ background: `hsl(${ratioColor} / 0.12)` }} data-testid="fin-ratio">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Your model vs benchmark</div>
          <div className="font-head font-black text-2xl" style={{ color: `hsl(${ratioColor})` }}>{ratio == null ? "—" : `${ratio}×`}</div>
          <div className="text-[10px] text-muted-foreground">{ratio == null ? "" : ratio > 1.25 ? "above published avg" : ratio < 0.75 ? "below published avg" : "in line with published avg"}</div>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3" data-testid="fin-ai-cost">
        <div className="rounded-lg bg-med/5 border border-med/20 p-3">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">AI-enabled breach avg</div>
          <div className="font-head font-black text-2xl">{fmt(bench.ai_breach_avg)}</div>
          <div className="text-[10px] text-muted-foreground">{bench.ai_breach_source}</div>
        </div>
        <div className="rounded-lg bg-med/5 border border-med/20 p-3">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Shadow-AI cost premium</div>
          <div className="font-head font-black text-2xl">+{fmt(bench.shadow_ai_premium)}</div>
          <div className="text-[10px] text-muted-foreground">{bench.shadow_ai_source}</div>
        </div>
      </div>
      {basis.scenario && (
        <div className="rounded-lg bg-ai/5 border border-ai/20 p-3" data-testid="fin-scenario">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Board exposure range · Monte-Carlo (P10 – expected – P90)</div>
          <div className="font-head font-black text-xl mt-1">{fmt(basis.scenario.p10)} <span className="text-muted-foreground text-sm">low</span> · {fmt(basis.scenario.p50)} <span className="text-muted-foreground text-sm">expected</span> · {fmt(basis.scenario.p90)} <span className="text-muted-foreground text-sm">high</span></div>
          <div className="text-[10px] text-muted-foreground">2,000-iteration simulation over magnitude &amp; frequency uncertainty — shows the board a defensible band, not a single point.</div>
        </div>
      )}
      {basis.items?.length > 0 && (() => {
        const rows = basis.items.slice(0, 8);
        const maxHigh = Math.max(...rows.map((i) => i.ale_high || 0), 1);
        return (
        <div className="rounded-lg border border-border p-3" data-testid="fair-waterfall">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><BarChart3 className="w-3.5 h-3.5" /> Per-risk uncertainty · P10 → P90 band</div>
          <div className="space-y-2">
            {rows.map((i) => {
              const left = ((i.ale_low || 0) / maxHigh) * 100;
              const width = Math.max(1.5, (((i.ale_high || 0) - (i.ale_low || 0)) / maxHigh) * 100);
              const mid = ((i.ale_expected || 0) / maxHigh) * 100;
              return (
                <div key={i.ref} data-testid={`fair-band-${i.ref}`} className="flex items-center gap-2">
                  <div className="w-14 shrink-0 font-mono text-[10px] text-ai text-right truncate" title={i.title}>{i.ref}</div>
                  <div className="relative flex-1 h-4 rounded-full bg-secondary/50" title={`${i.title} · P10 ${fmt(i.ale_low)} · P50 ${fmt(i.ale_expected)} · P90 ${fmt(i.ale_high)}`}>
                    <div className="absolute top-0 h-full rounded-full" style={{ left: `${left}%`, width: `${width}%`, background: "hsl(190 90% 50% / 0.55)", border: "1px solid hsl(190 90% 50%)" }} />
                    <div className="absolute top-[-2px] h-[calc(100%+4px)] w-0.5 bg-white/90" style={{ left: `${mid}%` }} />
                  </div>
                  <div className="w-24 shrink-0 text-right font-mono text-[10px] text-muted-foreground">{fmt(i.ale_low)}–{fmt(i.ale_high)}</div>
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
            <span className="inline-flex items-center gap-1"><span className="w-3 h-2 rounded-sm inline-block" style={{ background: "hsl(190 90% 50% / 0.55)", border: "1px solid hsl(190 90% 50%)" }} /> P10–P90 range</span>
            <span className="inline-flex items-center gap-1"><span className="w-0.5 h-3 inline-block bg-white/90" /> P50 expected</span>
          </div>
          <div className="text-[10px] text-muted-foreground mt-1">Bar spans the Monte-Carlo P10–P90 range per risk — longer bars = more uncertainty. Source: modelled SLE × ARO with residual-control scaling (FAIR).</div>
        </div>
        );
      })()}
      <div className="text-[11px] text-muted-foreground flex items-start gap-2"><BarChart3 className="w-3.5 h-3.5 mt-0.5 shrink-0" /> <span>DBIR medians for context — ransomware {fmt(bench.dbir_ransomware_median)}, BEC {fmt(bench.dbir_bec_median)} ({bench.dbir_source}). Benchmark source: {bench.source} · updated {bench.updated}{bench.checked_at ? ` · last checked ${new Date(bench.checked_at).toLocaleDateString()}` : ""}.</span></div>

      <div className="rounded-lg border border-border overflow-x-auto" data-testid="fin-math-table">
        <table className="w-full text-xs min-w-[720px]">
          <thead className="text-[10px] font-mono uppercase text-muted-foreground border-b border-border">
            <tr><th className="text-left px-3 py-2">Risk</th><th className="text-left px-3 py-2">SLE (source)</th><th className="text-left px-3 py-2">Derivation</th><th className="text-right px-3 py-2">Residual ALE</th></tr>
          </thead>
          <tbody>
            {basis.items.map((i) => (
              <tr key={i.ref} data-testid={`fin-row-${i.ref}`} className="border-b border-border/60">
                <td className="px-3 py-2"><div className="font-mono text-ai">{i.ref}</div><div className="truncate max-w-[180px]">{i.title}</div></td>
                <td className="px-3 py-2">${(i.sle / 1e6).toFixed(2)}M<div className="text-[10px] text-muted-foreground max-w-[220px]">{i.sle_source}</div></td>
                <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground">{i.math}</td>
                <td className="px-3 py-2 text-right"><div className="font-bold">${(i.residual_ale / 1e6).toFixed(2)}M</div><div className="text-[10px] text-muted-foreground">P10–P90 ${(i.ale_low / 1e6).toFixed(1)}–${(i.ale_high / 1e6).toFixed(1)}M</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {isAdmin && (
        <div className="rounded-lg bg-secondary/30 p-4 space-y-3" data-testid="fin-config">
          <div className="flex items-center gap-2 text-sm font-bold"><Building2 className="w-4 h-4" /> Calibrate the model (admin)
            {so?.locked
              ? <button data-testid="fin-unlock" onClick={unlock} className="ml-auto text-xs px-2.5 py-1 rounded-md bg-high/15 text-high border border-high/30">🔒 Locked — unlock to edit</button>
              : <button data-testid="fin-signoff" onClick={signOff} className="ml-auto text-xs px-2.5 py-1 rounded-md bg-low/15 text-low border border-low/30">Lock &amp; CRO sign-off</button>}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-xs flex items-center gap-2">Industry
              <select data-testid="fin-industry" value={cfg.config.industry} onChange={(e) => save({ industry: e.target.value })} className="bg-background border border-border rounded-md px-2 py-1 text-xs">
                {cfg.industries.map((x) => <option key={x} value={x}>{x}</option>)}
              </select>
            </label>
            {cfg.suggested_industry?.industry && cfg.suggested_industry.industry !== cfg.config.industry && (
              <button data-testid="fin-industry-suggest" onClick={() => save({ industry: cfg.suggested_industry.industry })} title={cfg.suggested_industry.reason}
                className="text-xs px-2.5 py-1 rounded-md bg-ai/10 text-ai border border-ai/30 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5" /> Use suggested: {cfg.suggested_industry.industry}
              </button>
            )}
            <label className="text-xs flex items-center gap-2">Method
              <select data-testid="fin-method" value={cfg.config.method} onChange={(e) => save({ method: e.target.value })} className="bg-background border border-border rounded-md px-2 py-1 text-xs">
                <option value="flat">Impact→$ table</option>
                <option value="records">Records × per-record cost</option>
              </select>
            </label>
            <label className="text-xs flex items-center gap-2"><Clock className="w-3.5 h-3.5" /> Sign-off reminder
              <select data-testid="fin-reminder-cadence" value={cfg.config.signoff_reminder_days || 60} onChange={(e) => save({ signoff_reminder_days: Number(e.target.value) })} className="bg-background border border-border rounded-md px-2 py-1 text-xs">
                <option value={30}>Every 30 days</option>
                <option value={60}>Every 60 days</option>
                <option value={90}>Every 90 days</option>
              </select>
            </label>
            <button data-testid="fin-refresh" onClick={async () => { await api.post("/financial/benchmark/refresh"); toast.success("Benchmark refreshed"); load(); }} className="text-xs px-2.5 py-1 rounded-md bg-secondary flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5" /> Refresh benchmark</button>
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
          </div>
          {cfg.config.method === "records" ? (
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-xs flex items-center gap-2">Records at risk<input data-testid="fin-records" type="number" defaultValue={cfg.config.records || 0} onBlur={(e) => save({ records: Number(e.target.value) })} className="w-32 bg-background border border-border rounded-md px-2 py-1 text-xs" /></label>
              <label className="text-xs flex items-center gap-2">$/record<input data-testid="fin-perrecord" type="number" defaultValue={cfg.config.per_record_cost || 165} onBlur={(e) => save({ per_record_cost: Number(e.target.value) })} className="w-24 bg-background border border-border rounded-md px-2 py-1 text-xs" /></label>
              <span className="text-[10px] text-muted-foreground">IBM per-record method (2023: $165/record).</span>
            </div>
          ) : (
            <div className="flex flex-wrap items-end gap-3">
              {["5", "4", "3", "2", "1"].map((k) => (
                <label key={k} className="text-xs flex flex-col gap-1">Impact {k} SLE ($)
                  <input data-testid={`fin-sle-${k}`} type="number" defaultValue={cfg.config.impact_sle[k]} onBlur={(e) => save({ impact_sle: { ...cfg.config.impact_sle, [k]: Number(e.target.value) } })} className="w-28 bg-background border border-border rounded-md px-2 py-1 text-xs" />
                </label>
              ))}
            </div>
          )}
        </div>
      )}
      {trend?.points?.length > 1 && (
        <div className="rounded-lg border border-border p-3" data-testid="fin-trend">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><TrendingDown className="w-3.5 h-3.5" /> Modelled exposure vs {trend.industry} benchmark (IBM) · peer band shaded</div>
          <ChartBox height={180}>
            <ComposedChart data={trend.points}>
              <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" />
              <YAxis tickFormatter={(v) => `$${(v / 1e6).toFixed(1)}M`} tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" width={48} />
              <Tooltip formatter={(v, n) => (n === "peer-base" || n === "Peer range") ? null : `$${(v / 1e6).toFixed(2)}M`} contentStyle={{ background: "hsl(222 18% 12%)", border: "1px solid hsl(222 12% 22%)", fontSize: 11 }} />
              <Area type="monotone" dataKey="peerBase" stackId="peer" stroke="none" fill="transparent" name="peer-base" isAnimationActive={false} />
              <Area type="monotone" dataKey="peerSpan" stackId="peer" stroke="none" fill="hsl(35 90% 55% / 0.14)" name="Peer range" isAnimationActive={false} />
              <Line type="monotone" dataKey="modelled" stroke="hsl(190 90% 50%)" strokeWidth={2} dot={false} name="Modelled" />
              <Line type="monotone" dataKey="benchmark" stroke="hsl(35 90% 55%)" strokeDasharray="4 4" strokeWidth={2} dot={false} name="IBM avg" />
            </ComposedChart>
          </ChartBox>
          {trend.peer_source && <div className="text-[10px] text-muted-foreground mt-1">Shaded band: {trend.peer_source} ({fmt(trend.peer_low)}–{fmt(trend.peer_high)}). Line source: {trend.source}.</div>}
        </div>
      )}
      {hist.length > 0 && (
        <div className="text-[10px] text-muted-foreground space-y-0.5" data-testid="fin-signoff-history">
          <div className="font-mono uppercase">Sign-off audit trail</div>
          {hist.slice(0, 6).map((h, idx) => (<div key={idx}>{h.action === "signoff" ? "🔒 Signed off" : "🔓 Unlocked"} · {h.name || h.by} · {String(h.at).slice(0, 16).replace("T", " ")}</div>))}
        </div>
      )}
      <p className="text-[11px] text-muted-foreground">{basis.disclaimer}</p>
    </div>
  );
}
