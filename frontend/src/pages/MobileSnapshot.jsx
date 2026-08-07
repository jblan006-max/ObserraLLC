import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Loader2, ShieldCheck, DollarSign, Percent, GitBranch, TrendingUp, TrendingDown, Minus } from "lucide-react";

const fmtM = (v) => (v == null ? "—" : "$" + (v / 1e6).toFixed(1) + "M");
const gradeCol = (s) => (s >= 80 ? "142 70% 45%" : s >= 60 ? "35 90% 55%" : "0 84% 60%");
const Trend = ({ t }) => (t === "up" ? <TrendingUp className="w-4 h-4 text-crit" /> : t === "down" ? <TrendingDown className="w-4 h-4 text-low" /> : <Minus className="w-4 h-4 text-muted-foreground" />);
const fade = { hidden: { opacity: 0, y: 10 }, show: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.06, duration: 0.4 } }) };

export default function MobileSnapshot() {
  const [m, setM] = useState(null);
  useEffect(() => { api.get("/metrics/dashboard").then((r) => setM(r.data.executive)).catch(() => setM(null)); }, []);
  if (!m) return <div className="flex items-center justify-center h-72"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const score = m.health?.score || 0;
  const stats = [
    { icon: DollarSign, label: "Residual exposure / yr", value: fmtM(m.exposure_residual_ale), accent: "15 80% 55%" },
    { icon: ShieldCheck, label: "Exposure avoided", value: fmtM(m.exposure_avoided), accent: "142 70% 45%" },
    { icon: Percent, label: "Risk reduction", value: `${m.risk_reduction_pct}%`, accent: "190 90% 50%" },
    { icon: GitBranch, label: "Decisions required", value: m.decisions_required.length, accent: "35 90% 55%" },
  ];
  return (
    <div className="max-w-md mx-auto space-y-4 rise" data-testid="mobile-snapshot-page">
      <div>
        <h1 className="font-head font-black text-2xl tracking-tight">Executive Snapshot</h1>
        <p className="text-xs text-muted-foreground mt-0.5">Your board-level risk posture at a glance.</p>
      </div>

      <motion.div custom={0} variants={fade} initial="hidden" animate="show" className="bg-card fact-border rounded-2xl p-6 text-center">
        <div className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Enterprise Health Index</div>
        <div className="font-head font-black text-6xl tracking-tight" style={{ color: `hsl(${gradeCol(score)})` }}>{score}</div>
        <div className="text-sm font-head font-bold mt-1" style={{ color: `hsl(${gradeCol(score)})` }}>Grade {m.health?.grade || "—"}</div>
      </motion.div>

      <div className="grid grid-cols-2 gap-3">
        {stats.map((s, i) => (
          <motion.div key={s.label} custom={i + 1} variants={fade} initial="hidden" animate="show" data-testid={`snap-${s.label.split(" ")[0].toLowerCase()}`} className="bg-card fact-border rounded-xl p-4">
            <s.icon className="w-4 h-4 mb-2" style={{ color: `hsl(${s.accent})` }} />
            <div className="font-head font-black text-2xl tracking-tight" style={{ color: `hsl(${s.accent})` }}>{s.value}</div>
            <div className="text-[11px] text-muted-foreground mt-0.5 leading-tight">{s.label}</div>
          </motion.div>
        ))}
      </div>

      <motion.div custom={5} variants={fade} initial="hidden" animate="show" className="bg-card fact-border rounded-xl p-4">
        <div className="text-sm font-head font-bold mb-3">Top risks by business impact</div>
        <div className="space-y-2.5">
          {m.top_strategic_risks.slice(0, 4).map((r) => {
            const c = r.residual >= 16 ? "0 84% 60%" : r.residual >= 9 ? "35 90% 55%" : "142 70% 45%";
            return (
              <div key={r.ref} data-testid={`snap-risk-${r.ref}`} className="flex items-center gap-3">
                <span className="px-1.5 py-0.5 rounded-sm text-[10px] font-mono font-bold shrink-0" style={{ background: `hsl(${c} / 0.15)`, color: `hsl(${c})` }}>{r.residual}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{r.title}</div>
                  <div className="text-[10px] text-high truncate">{r.business_impact}</div>
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
