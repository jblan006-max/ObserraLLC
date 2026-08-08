import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AIInsight } from "@/components/AIInsight";
import { Gauge, TrendingUp, DollarSign, ShieldAlert, Activity } from "lucide-react";

const ACCENT = "222 90% 62%";
const money = (n) => n == null ? "—" : n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}k` : `$${Math.round(n || 0)}`;

// Enterprise-wide Executive Briefing — synthesizes the Unified Risk Correlation Engine (ALE,
// peer-benchmark deviation, predictive drift) into a single board-level 'State of the Business'.
export function ExecBriefing() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/risk-engine/strategic").then((r) => setS(r.data)).catch(() => setS(null)); }, []);
  if (!s) return null;
  const p = s.portfolio || {}, b = s.benchmark || {}, drift = s.drift || {};
  const benchTone = b.position === "above" ? "0 84% 60%" : b.position === "below" ? "35 90% 55%" : "142 70% 45%";
  const alert = b.outlier || drift.trending_critical;
  const kpis = [
    { icon: DollarSign, label: "Aggregate ALE at risk", value: money(p.residual_ale), accent: "15 80% 55%" },
    { icon: ShieldAlert, label: "Monte-Carlo P90", value: money(p.p90), accent: "0 84% 60%" },
    { icon: Gauge, label: "Peer deviation", value: b.delta_pct != null ? `${b.delta_pct > 0 ? "+" : ""}${b.delta_pct}%` : "—", accent: benchTone },
    { icon: TrendingUp, label: "Risk drift (MoM)", value: drift.pct != null ? `${drift.pct > 0 ? "+" : ""}${drift.pct}%` : "flat", accent: drift.direction === "up" ? "0 84% 60%" : "142 70% 45%" },
    { icon: Activity, label: "Compliance health", value: `${s.compliance?.overall_pct ?? 0}%`, accent: "142 70% 45%" },
  ];
  return (
    <div className="col-span-full bg-card fact-border rounded-xl p-6 space-y-4" data-testid="exec-briefing">
      <div className="flex items-center gap-2"><Activity className="w-4 h-4" style={{ color: `hsl(${ACCENT})` }} /><h2 className="font-head font-bold text-lg">Executive Briefing — State of the Business</h2></div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {kpis.map((k) => (
          <div key={k.label} data-testid={`exec-brief-${k.label.replace(/[^a-zA-Z0-9]/g, "-")}`} className="rounded-lg bg-secondary/40 p-3" style={{ borderTop: `2px solid hsl(${k.accent} / 0.6)` }}>
            <div className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider text-muted-foreground"><k.icon className="w-3 h-3" /> {k.label}</div>
            <div className="font-head font-black text-2xl tracking-tight mt-0.5" style={{ color: `hsl(${k.accent})` }}>{k.value}</div>
          </div>
        ))}
      </div>
      {alert && (
        <div data-testid="exec-strategic-alert" className="rounded-lg border p-3 flex items-start gap-2.5" style={{ borderColor: `hsl(${benchTone} / 0.4)`, background: `hsl(${benchTone} / 0.06)` }}>
          <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" style={{ color: `hsl(${benchTone})` }} />
          <div><div className="font-head font-bold text-sm">Strategic alert</div><p className="text-xs text-muted-foreground mt-0.5">{b.strategic_recommendation || drift.note}</p></div>
        </div>
      )}
      <AIInsight dashboard="Executive Briefing" accent={ACCENT} auto slug="exec-briefing" />
    </div>
  );
}
