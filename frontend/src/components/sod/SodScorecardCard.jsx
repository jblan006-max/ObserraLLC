// Extracted from SodCommandCenter for maintainability (no behavior change).
import { Button } from "@/components/ui/button";
import { Download, TrendingUp, FileText, Sparkles } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { ScoreTile, TrendTip } from "@/components/sod/sodPrimitives";
import { useSod } from "@/context/SodContext";

export function SodScorecardCard() {
  const { data, exportScorecard, loadWhy, scorecard, why, whyBusy } = useSod();
  return (
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
  );
}
