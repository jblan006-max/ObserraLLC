import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { HealthGauge } from "@/components/HealthGauge";
import { RiskHeatmap } from "@/components/RiskHeatmap";
import { IntegrationsPanel } from "@/components/IntegrationsPanel";
import { SyncTicker } from "@/components/SyncTicker";
import { BoardReportModal } from "@/components/BoardReportModal";
import { EvidenceLineageModal } from "@/components/EvidenceLineageModal";
import { CountUp } from "@/components/CountUp";
import { SourceBadge, FreshnessBadge, ConfidenceBadge, DataTypeBadge, ScorePill } from "@/components/badges";
import { AreaChart, Area, ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { TrendingUp, TrendingDown, Minus, ShieldAlert, AlertTriangle, Cpu, GitBranch, Loader2, FileText, Zap, Activity } from "lucide-react";

const RECMAP = { "CR-001": "entra_enforce_pim", "CR-004": "casb_quarantine_shadow", "CR-002": "tenable_patch_critical", "CR-005": "entra_enforce_mfa" };
const PIE = ["#3b6ef5", "#12b4d6", "#f5a623", "#e0574a", "#42c98e", "#8a7bf0"];
const Trend = ({ t }) => t === "up" ? <TrendingUp className="w-3.5 h-3.5 text-low" /> : t === "down" ? <TrendingDown className="w-3.5 h-3.5 text-crit" /> : <Minus className="w-3.5 h-3.5 text-muted-foreground" />;
const fade = { hidden: { opacity: 0, y: 12 }, show: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.05, duration: 0.4, ease: "easeOut" } }) };

export default function Overview() {
  const { mode } = useAuth();
  const [d, setD] = useState(null);
  const [an, setAn] = useState(null);
  const [fin, setFin] = useState(null);
  const [audit, setAudit] = useState([]);
  const [intg, setIntg] = useState([]);
  const [running, setRunning] = useState(null);
  const [lineage, setLineage] = useState(null);
  const [report, setReport] = useState(false);

  const load = useCallback(async (silent) => {
    const [o, a, au, ig, f] = await Promise.all([
      api.get("/overview"), api.get("/analytics"), api.get("/audit-logs"), api.get("/integrations"), api.get("/financials"),
    ]);
    setD(o.data); setAn(a.data); setAudit(au.data.slice(0, 8)); setIntg(ig.data); setFin(f.data);
  }, []);

  useEffect(() => { load(); const t = setInterval(() => load(true), 20000); return () => clearInterval(t); }, [load]);

  const runAction = async (action_id) => {
    setRunning(action_id);
    try {
      const { data } = await api.post("/actions/run", { action_id });
      toast.success(data.message || "Directory synced", { duration: 5000 });
      await load(true);
    } catch { toast.error("Action failed"); }
    setRunning(null);
  };

  if (!d || !an) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const { health, kpis, recommendations } = d;

  const KPIS = [
    { icon: ShieldAlert, label: "Critical Risks", value: kpis.critical_risks, accent: "0 84% 60%" },
    { icon: AlertTriangle, label: "Open Risks", value: kpis.open_risks, accent: "15 80% 55%" },
    { icon: Cpu, label: "Shadow AI", value: kpis.shadow_ai, accent: "190 90% 50%" },
    { icon: GitBranch, label: "Pending Decisions", value: kpis.pending_recs, accent: "35 90% 55%" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4 }}>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight">
            {mode === "executive" ? "Executive Overview" : "Operational Command"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {mode === "executive" ? "Board-ready intelligence — health, business impact & one-click remediation." : "Live control posture, evidence & remediation workflows."}
          </p>
        </motion.div>
        <button data-testid="board-report-btn" onClick={() => setReport(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ai/15 border border-ai/40 text-ai font-head font-bold text-sm hover:bg-ai/25 transition-colors">
          <FileText className="w-4 h-4" /> Generate Board Report
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-5">
        {/* Health */}
        <motion.div custom={0} variants={fade} initial="hidden" animate="show"
          className="col-span-full lg:col-span-8 bg-card fact-border rounded-xl p-6 relative overflow-hidden">
          <div className="absolute -right-10 -top-10 w-40 h-40 rounded-full bg-primary/5 blur-2xl" />
          <div className="flex items-center justify-between mb-2 relative">
            <h2 className="font-head font-bold text-lg">Enterprise Health Index</h2>
            <div className="flex items-center gap-3"><FreshnessBadge freshness={health.freshness} /><DataTypeBadge type="fact" /></div>
          </div>
          <div className="grid md:grid-cols-2 gap-4 items-center relative">
            <HealthGauge score={health.score} grade={health.grade} />
            <div className="space-y-2.5">
              {health.components.map((c) => (
                <div key={c.name} className="flex items-center gap-3">
                  <span className="text-xs w-32 truncate text-muted-foreground">{c.name}</span>
                  <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
                    <motion.div className="h-full rounded-full" initial={{ width: 0 }} animate={{ width: `${c.score}%` }} transition={{ duration: 0.8, ease: "easeOut" }}
                      style={{ background: c.score >= 75 ? "hsl(142 70% 45%)" : c.score >= 60 ? "hsl(35 90% 55%)" : "hsl(15 80% 55%)" }} />
                  </div>
                  <span className="font-mono text-xs w-8 text-right"><CountUp value={c.score} /></span>
                  <Trend t={c.trend} />
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Trend */}
        <motion.div custom={1} variants={fade} initial="hidden" animate="show"
          className="col-span-full lg:col-span-4 bg-card fact-border rounded-xl p-6 flex flex-col">
          <h2 className="font-head font-bold text-lg mb-2">Posture Trend</h2>
          <ResponsiveContainer width="100%" height={120}>
            <AreaChart data={health.history}>
              <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(190 90% 50%)" stopOpacity={0.6} />
                <stop offset="100%" stopColor="hsl(190 90% 50%)" stopOpacity={0} />
              </linearGradient></defs>
              <Area type="monotone" dataKey="score" stroke="hsl(190 90% 50%)" strokeWidth={2.5} fill="url(#g1)" />
            </AreaChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div className="estimate-border rounded-md p-3"><div className="text-[10px] text-muted-foreground">Residual exposure/yr</div><div className="font-head font-bold text-lg text-high">{fin ? "$" + (fin.total_residual_ale / 1e6).toFixed(1) + "M" : "—"}</div><DataTypeBadge type="estimate" /></div>
            <div className="fact-border rounded-md p-3"><div className="text-[10px] text-muted-foreground">Exposure avoided</div><div className="font-head font-bold text-lg text-low">{fin ? "$" + (fin.avoided / 1e6).toFixed(1) + "M" : "—"}</div><DataTypeBadge type="fact" /></div>
          </div>
        </motion.div>

        {/* KPIs */}
        {KPIS.map((k, i) => (
          <motion.div key={k.label} custom={2 + i} variants={fade} initial="hidden" animate="show"
            className="col-span-6 lg:col-span-3 bg-card fact-border rounded-xl p-5 group hover:-translate-y-0.5 transition-transform duration-200"
            style={{ boxShadow: `inset 0 0 0 1px hsl(${k.accent} / 0.0)` }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">{k.label}</span>
              <k.icon className="w-4 h-4" style={{ color: `hsl(${k.accent})` }} />
            </div>
            <div className="font-head font-black text-4xl tracking-tight" style={{ color: `hsl(${k.accent})` }}>
              <CountUp value={k.value} />
            </div>
          </motion.div>
        ))}

        {/* Integrations */}
        <motion.div custom={6} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-12">
          <div className="flex items-center gap-2 mb-3"><Zap className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-lg">Connected Integrations · One-click Remediation</h2></div>
          <SyncTicker />
          <IntegrationsPanel integrations={intg} onAction={runAction} running={running} />
        </motion.div>

        {/* Heatmap + Donut */}
        <motion.div custom={7} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-7 bg-card fact-border rounded-xl p-6">
          <h2 className="font-head font-bold text-lg mb-4">Risk Heatmap <span className="text-xs font-normal text-muted-foreground">· click a cell for evidence</span></h2>
          <RiskHeatmap matrix={an.matrix} onSelect={setLineage} />
        </motion.div>
        <motion.div custom={8} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-5 bg-card fact-border rounded-xl p-6">
          <h2 className="font-head font-bold text-lg mb-2">Risk by Category</h2>
          <ResponsiveContainer width="100%" height={210}>
            <PieChart>
              <Pie data={an.by_category} dataKey="value" nameKey="name" innerRadius={54} outerRadius={82} paddingAngle={3} stroke="none">
                {an.by_category.map((_, i) => <Cell key={i} fill={PIE[i % PIE.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "hsl(215 38% 10%)", border: "1px solid hsl(215 30% 18%)", borderRadius: 8, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-x-3 gap-y-1 justify-center mt-2">
            {an.by_category.map((c, i) => <span key={c.name} className="text-[10px] text-muted-foreground flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: PIE[i % PIE.length] }} />{c.name}</span>)}
          </div>
        </motion.div>

        {/* Recommendations */}
        <motion.div custom={9} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-8 bg-card fact-border rounded-xl p-6">
          <h2 className="font-head font-bold text-lg mb-4">Top Recommendations</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {recommendations.map((r) => (
              <div key={r.ref} className="ai-border rounded-lg p-4 flex flex-col hover:-translate-y-0.5 transition-transform duration-200">
                <div className="flex items-center justify-between mb-2"><span className="font-mono text-xs text-ai">{r.ref} → {r.risk_ref}</span><DataTypeBadge type="ai_recommendation" /></div>
                <div className="font-medium text-sm mb-1">{r.title}</div>
                <div className="text-xs text-muted-foreground mb-3">{r.predicted_impact}</div>
                <div className="flex items-center justify-between mt-auto">
                  <ConfidenceBadge value={r.confidence} />
                  {RECMAP[r.risk_ref] && r.status !== "Applied" ? (
                    <button data-testid={`apply-${r.ref}`} disabled={!!running} onClick={() => runAction(RECMAP[r.risk_ref])}
                      className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-1.5 rounded-md bg-ai text-background hover:opacity-90 transition-opacity disabled:opacity-50">
                      {running === RECMAP[r.risk_ref] ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />} Apply
                    </button>
                  ) : r.status === "Applied" ? <span className="text-xs text-low">✓ Applied</span> : <span className="text-[10px] font-mono text-muted-foreground">{r.required_authority}</span>}
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Activity feed */}
        <motion.div custom={10} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-4 bg-card fact-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-3"><Activity className="w-4 h-4 text-low" /><h2 className="font-head font-bold text-lg">Live Activity</h2></div>
          <div className="space-y-3">
            {audit.map((l, i) => (
              <div key={i} className="flex gap-3 text-xs">
                <span className="w-1.5 h-1.5 mt-1.5 rounded-full bg-ai shrink-0" />
                <div className="min-w-0">
                  <div className="font-mono text-ai text-[11px]">{l.action}</div>
                  <div className="text-foreground/80 truncate">{l.detail}</div>
                  <div className="text-[10px] text-muted-foreground">{new Date(l.ts).toLocaleTimeString()}</div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      <BoardReportModal open={report} onClose={() => setReport(false)} />
      <EvidenceLineageModal riskRef={lineage} onClose={() => setLineage(null)} />
    </div>
  );
}
