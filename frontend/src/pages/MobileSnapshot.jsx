import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { AIInsight } from "@/components/AIInsight";
import { Loader2, ShieldCheck, DollarSign, Percent, GitBranch, TrendingUp, TrendingDown, Minus, Activity, AlertTriangle, Clock, Building2, Gauge } from "lucide-react";

const ACCENT = "222 90% 62%";
const fmtM = (v) => (v == null ? "—" : "$" + (v / 1e6).toFixed(1) + "M");
const gradeCol = (s) => (s >= 80 ? "142 70% 45%" : s >= 60 ? "35 90% 55%" : "0 84% 60%");
const Trend = ({ t }) => (t === "up" ? <TrendingUp className="w-4 h-4 text-crit" /> : t === "down" ? <TrendingDown className="w-4 h-4 text-low" /> : <Minus className="w-4 h-4 text-muted-foreground" />);
const fade = { hidden: { opacity: 0, y: 10 }, show: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.05, duration: 0.4 } }) };

export default function MobileSnapshot() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(false);
  const load = () => { setErr(false); api.get("/metrics/dashboard").then((r) => setD(r.data)).catch(() => setErr(true)); };
  useEffect(() => { load(); }, []);

  if (err) return (
    <div className="max-w-md mx-auto text-center py-24 space-y-4 rise" data-testid="snapshot-error">
      <p className="text-lg font-head font-bold">Couldn't load your snapshot</p>
      <p className="text-sm text-muted-foreground">The metrics service didn't respond. Please try again.</p>
      <button data-testid="snapshot-retry" onClick={load} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm">Retry</button>
    </div>
  );
  if (!d) return <div className="flex items-center justify-center h-72"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  const m = d.executive || {};
  const op = d.operational || {};
  const score = m.health?.score || 0;
  const kpis = [
    { icon: DollarSign, label: "Residual exposure / yr", value: fmtM(m.exposure_residual_ale), accent: "15 80% 55%" },
    { icon: ShieldCheck, label: "Exposure avoided", value: fmtM(m.exposure_avoided), accent: "142 70% 45%" },
    { icon: Percent, label: "Risk reduction", value: `${m.risk_reduction_pct ?? 0}%`, accent: "190 90% 50%" },
    { icon: GitBranch, label: "Decisions required", value: (m.decisions_required || []).length, accent: "35 90% 55%" },
    { icon: AlertTriangle, label: "Critical risks", value: op.kpis?.critical_risks ?? 0, accent: "0 84% 60%" },
    { icon: Gauge, label: "Health index", value: `${score}${m.health?.grade ? ` · ${m.health.grade}` : ""}`, accent: gradeCol(score) },
  ];
  const metrics = [
    { icon: Clock, label: "MTTR", value: op.mttr_hours != null ? `${op.mttr_hours}h` : "—" },
    { icon: Activity, label: "Open incidents", value: op.incidents_open ?? 0 },
    { icon: ShieldCheck, label: "Patching coverage", value: op.patching_coverage_pct != null ? `${op.patching_coverage_pct}%` : "—" },
    { icon: Building2, label: "High-risk vendors", value: op.high_risk_vendors ?? 0 },
  ];
  const recs = m.decisions_required || [];

  return (
    <div className="max-w-2xl mx-auto space-y-5 rise" data-testid="mobile-snapshot-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2" style={{ color: `hsl(${ACCENT})` }}>
          <Activity className="w-7 h-7" strokeWidth={1.5} /> Executive Snapshot
        </h1>
        <p className="text-sm text-muted-foreground mt-1">Your board-level risk posture at a glance — live $-impact, decisions awaiting authority, and an AI read on what matters now.</p>
      </div>

      {/* AI summary up top, like every other dashboard */}
      <AIInsight dashboard="Executive Snapshot" accent={ACCENT} auto slug="exec-snapshot" />

      {/* Executive KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="snapshot-kpis">
        {kpis.map((s, i) => (
          <motion.div key={s.label} custom={i} variants={fade} initial="hidden" animate="show"
            data-testid={`snap-kpi-${s.label.split(" ")[0].toLowerCase()}`} className="bg-card fact-border rounded-xl p-4" style={{ borderTop: `2px solid hsl(${s.accent} / 0.6)` }}>
            <s.icon className="w-4 h-4 mb-2" style={{ color: `hsl(${s.accent})` }} />
            <div className="font-head font-black text-2xl tracking-tight" style={{ color: `hsl(${s.accent})` }}>{s.value}</div>
            <div className="text-[11px] text-muted-foreground mt-0.5 leading-tight">{s.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Operational metrics cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="snapshot-metrics">
        {metrics.map((s) => (
          <div key={s.label} data-testid={`snap-metric-${s.label.split(" ")[0].toLowerCase()}`} className="bg-card fact-border rounded-lg p-3.5">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground"><s.icon className="w-3 h-3" /> {s.label}</div>
            <div className="font-head font-black text-xl tracking-tight mt-0.5">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Summary & recommendations */}
      <div className="bg-card fact-border rounded-xl p-5" data-testid="snapshot-recommendations">
        <div className="flex items-center gap-2 mb-3"><GitBranch className="w-4 h-4" style={{ color: `hsl(35 90% 55%)` }} /><h2 className="font-head font-bold text-lg">Recommendations & decisions</h2></div>
        <p className="text-sm text-muted-foreground mb-3">
          Residual exposure is <span className="text-high font-semibold">{fmtM(m.exposure_residual_ale)}</span>, down <span className="text-low font-semibold">{m.risk_reduction_pct ?? 0}%</span> from inherent.
          {recs.length ? ` ${recs.length} decision(s) await executive authority.` : " No decisions currently need executive sign-off — sustain controls and evidence freshness."}
        </p>
        {recs.length > 0 && (
          <div className="space-y-2">
            {recs.slice(0, 5).map((r) => (
              <div key={r.ref} data-testid={`snap-decision-${r.ref}`} className="flex items-start gap-3 bg-secondary/30 rounded-lg px-3 py-2.5">
                <span className="px-1.5 py-0.5 rounded-sm text-[10px] font-mono font-bold shrink-0 bg-med/15 text-med">{r.ref}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{r.title}</div>
                  {r.predicted_impact && <div className="text-[11px] text-muted-foreground">Projected impact: {r.predicted_impact}</div>}
                </div>
                {r.required_authority && <span className="text-[10px] font-mono text-ai shrink-0">{r.required_authority}</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Top risks */}
      <motion.div custom={6} variants={fade} initial="hidden" animate="show" className="bg-card fact-border rounded-xl p-5" data-testid="snapshot-top-risks">
        <div className="text-sm font-head font-bold mb-3">Top risks by business impact</div>
        <div className="space-y-2.5">
          {(m.top_strategic_risks || []).slice(0, 5).map((r) => {
            const c = r.residual >= 16 ? "0 84% 60%" : r.residual >= 9 ? "35 90% 55%" : "142 70% 45%";
            return (
              <div key={r.ref} data-testid={`snap-risk-${r.ref}`} className="flex items-center gap-3">
                <span className="px-1.5 py-0.5 rounded-sm text-[10px] font-mono font-bold shrink-0" style={{ background: `hsl(${c} / 0.15)`, color: `hsl(${c})` }}>{r.residual}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{r.title}</div>
                  {r.business_impact && <div className="text-[10px] text-high truncate">{r.business_impact}</div>}
                </div>
                <Trend t={r.trend} />
              </div>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}
