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
import { ConfidenceBadge, DataTypeBadge, FreshnessBadge } from "@/components/badges";
import {
  AreaChart, Area, ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, LineChart, Line, XAxis, CartesianGrid,
} from "recharts";
import {
  TrendingUp, TrendingDown, Minus, ShieldAlert, AlertTriangle, Cpu, GitBranch, Loader2,
  FileText, Zap, Activity, DollarSign, Percent, ShieldCheck, Wallet, Bug, Clock, Building,
  Gauge, MailWarning, Layers, Plug, Bot, Download, Filter,
} from "lucide-react";

const RECMAP = { "CR-001": "entra_enforce_pim", "CR-004": "casb_quarantine_shadow", "CR-002": "tenable_patch_critical", "CR-005": "entra_enforce_mfa" };
const PIE = ["#3b6ef5", "#12b4d6", "#f5a623", "#e0574a", "#42c98e", "#8a7bf0"];
const Trend = ({ t }) => t === "up" ? <TrendingUp className="w-3.5 h-3.5 text-crit" /> : t === "down" ? <TrendingDown className="w-3.5 h-3.5 text-low" /> : <Minus className="w-3.5 h-3.5 text-muted-foreground" />;
const fade = { hidden: { opacity: 0, y: 12 }, show: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.04, duration: 0.4, ease: "easeOut" } }) };
const fmtM = (v) => v == null ? "—" : "$" + (v / 1e6).toFixed(1) + "M";
const CHART_TT = { background: "hsl(215 38% 10%)", border: "1px solid hsl(215 30% 18%)", borderRadius: 8, fontSize: 12 };

const SectionLabel = ({ children, icon: Icon }) => (
  <div className="col-span-full flex items-center gap-2 mt-2">
    {Icon && <Icon className="w-3.5 h-3.5 text-muted-foreground" />}
    <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">{children}</span>
    <div className="flex-1 h-px bg-border/60" />
  </div>
);

function MetricCard({ icon: Icon, label, value, unit, accent, sub, testid }) {
  return (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-5 group hover:-translate-y-0.5 transition-transform duration-200">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        {Icon && <Icon className="w-4 h-4" style={accent ? { color: `hsl(${accent})` } : { color: "hsl(var(--muted-foreground))" }} />}
      </div>
      <div className="font-head font-black text-3xl tracking-tight" style={accent ? { color: `hsl(${accent})` } : {}}>{value}{unit}</div>
      {sub && <div className="text-[11px] text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

function QuarterChart({ title, data, kind = "bar", color = "hsl(190 90% 50%)", suffix = "", accent, source, testid }) {
  return (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-3 gap-2">
        <h3 className="font-head font-bold text-sm" style={accent ? { color: `hsl(${accent})` } : {}}>{title}</h3>
        {source && <span data-testid={`${testid}-source`} className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full border shrink-0 ${source === "live" ? "bg-low/15 text-low border-low/30" : "bg-secondary/60 text-muted-foreground border-border"}`}>{source === "live" ? "LIVE" : "MODELED"}</span>}
      </div>
      <ResponsiveContainer width="100%" height={150}>
        {kind === "bar" ? (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 30% 18%)" vertical={false} />
            <XAxis dataKey="quarter" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={CHART_TT} formatter={(v) => [`${v}${suffix}`, ""]} />
            <Bar dataKey="value" radius={[4, 4, 0, 0]} fill={color} />
          </BarChart>
        ) : (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 30% 18%)" vertical={false} />
            <XAxis dataKey="quarter" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={CHART_TT} formatter={(v) => [`${v}${suffix}`, ""]} />
            <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} dot={{ r: 3, fill: color }} />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function ExecutiveOverview({ health, m, momentum, activity, onLineage }) {
  const [actFilter, setActFilter] = useState("all");
  const actKinds = { upgrades: ["auto-upgrade", "auto-applied"], rollbacks: ["rollback"], containment: ["contained"], fixes: ["auto-fix"], approvals: ["needs-approval"] };
  const filteredActivity = (activity || []).filter((e) => actFilter === "all" || (actKinds[actFilter] || []).includes(e.kind));
  const exportActivity = () => {
    const rows = [["timestamp", "type", "title", "detail"], ...filteredActivity.map((e) => [e.ts, e.kind, (e.title || "").replace(/"/g, "'"), (e.detail || "").replace(/"/g, "'")])];
    const csv = rows.map((r) => r.map((c) => `"${c ?? ""}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = "autonomy-activity.csv"; a.click(); URL.revokeObjectURL(url);
  };
  const strategicKpis = [
    { icon: DollarSign, label: "Residual exposure / yr", value: fmtM(m.exposure_residual_ale), accent: "15 80% 55%", sub: "Modeled annualized loss", testid: "exec-kpi-residual" },
    { icon: ShieldCheck, label: "Exposure avoided", value: fmtM(m.exposure_avoided), accent: "142 70% 45%", sub: "Inherent − residual", testid: "exec-kpi-avoided" },
    { icon: Percent, label: "Risk reduction", value: m.risk_reduction_pct, unit: "%", accent: "190 90% 50%", sub: "vs inherent exposure", testid: "exec-kpi-reduction" },
    { icon: Wallet, label: "Risk-adjusted exposure", value: fmtM(m.risk_adjusted), accent: "35 90% 55%", sub: "Confidence-weighted", testid: "exec-kpi-adjusted" },
  ];
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-5" data-testid="executive-overview">
      {/* 1 — Live intelligence (charts & data first) */}
      <SectionLabel icon={Activity}>Live intelligence</SectionLabel>
      <motion.div custom={0} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-7 bg-card fact-border rounded-xl p-6 flex flex-col">
        <h2 className="font-head font-bold text-lg mb-1">Posture Trend</h2>
        <p className="text-[11px] text-muted-foreground mb-2">Board-level trajectory of enterprise health.</p>
        <ResponsiveContainer width="100%" height={190}>
          <AreaChart data={m.health.history}>
            <defs><linearGradient id="eg1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="hsl(190 90% 50%)" stopOpacity={0.6} /><stop offset="100%" stopColor="hsl(190 90% 50%)" stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 30% 18%)" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={CHART_TT} />
            <Area type="monotone" dataKey="score" stroke="hsl(190 90% 50%)" strokeWidth={2.5} fill="url(#eg1)" />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>
      <motion.div custom={1} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-5 bg-card fact-border rounded-xl p-6 relative overflow-hidden">
        <div className="absolute -right-10 -top-10 w-40 h-40 rounded-full bg-primary/5 blur-2xl" />
        <div className="flex items-center justify-between mb-2 relative">
          <h2 className="font-head font-bold text-lg">Enterprise Health Index</h2>
          <FreshnessBadge freshness="live" />
        </div>
        <HealthGauge score={health?.score || 0} grade={health?.grade || "—"} />
      </motion.div>

      <motion.div custom={2} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-7 bg-card fact-border rounded-xl p-6">
        <h2 className="font-head font-bold text-lg mb-4">Top Risks by Business Impact</h2>
        <div className="space-y-3">
          {m.top_strategic_risks.map((r) => {
            const c = r.residual >= 16 ? "0 84% 60%" : r.residual >= 9 ? "35 90% 55%" : "142 70% 45%";
            return (
              <div key={r.ref} data-testid={`exec-risk-${r.ref}`} onClick={() => onLineage(r.ref)} className="flex items-center gap-4 p-3 rounded-lg bg-secondary/30 hover:bg-secondary/50 cursor-pointer transition-colors">
                <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold shrink-0" style={{ background: `hsl(${c} / 0.15)`, color: `hsl(${c})` }}>{r.residual}/25</span>
                <div className="min-w-0 flex-1"><div className="font-medium text-sm truncate">{r.title}</div><div className="text-[11px] text-high">{r.business_impact}</div></div>
                <Trend t={r.trend} />
              </div>
            );
          })}
        </div>
      </motion.div>
      <motion.div custom={3} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-5 bg-card fact-border rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4"><GitBranch className="w-4 h-4 text-med" /><h2 className="font-head font-bold text-lg">Decisions Required</h2></div>
        {m.decisions_required.length === 0 ? <div className="text-sm text-muted-foreground py-6 text-center">No decisions awaiting executive authority.</div> : (
          <div className="space-y-3">
            {m.decisions_required.map((d) => (
              <div key={d.ref} data-testid={`exec-decision-${d.ref}`} className="ai-border rounded-lg p-3">
                <div className="font-medium text-sm mb-0.5">{d.title}</div>
                <div className="text-[11px] text-muted-foreground mb-1">{d.predicted_impact}</div>
                <span className="text-[10px] font-mono text-med">Authority: {d.required_authority}</span>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      {momentum && (
        <motion.div custom={4} variants={fade} initial="hidden" animate="show" className="col-span-full bg-card fact-border rounded-xl p-6" data-testid="exec-remediation-momentum">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <div className="flex items-center gap-2"><Activity className="w-4 h-4 text-low" /><h2 className="font-head font-bold text-lg">Remediation Momentum <span className="text-xs font-normal text-muted-foreground">· last {momentum.window_days} days</span></h2></div>
            <div className="text-right">
              <div className="text-[10px] font-mono uppercase text-muted-foreground">Risk reduction score</div>
              <div className="font-head font-black text-3xl" data-testid="exec-risk-reduction-score" style={{ color: `hsl(${momentum.score >= 66 ? "142 70% 45%" : momentum.score >= 33 ? "35 90% 55%" : "0 84% 60%"})` }}>{momentum.score}<span className="text-lg text-muted-foreground">/100</span></div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-secondary/30 rounded-lg p-3"><div className="text-[10px] text-muted-foreground">Remediations</div><div className="font-head font-bold text-xl text-low">{momentum.remediation_count}</div></div>
            <div className="bg-secondary/30 rounded-lg p-3"><div className="text-[10px] text-muted-foreground">Evidence logged</div><div className="font-head font-bold text-xl text-ai">{momentum.evidence_count}</div></div>
            <div className="bg-secondary/30 rounded-lg p-3"><div className="text-[10px] text-muted-foreground">Recs applied</div><div className="font-head font-bold text-xl">{momentum.applied_recommendations}</div></div>
          </div>
          <div className="h-2 rounded-full bg-secondary overflow-hidden mb-4"><div className="h-full transition-all duration-500" style={{ width: `${momentum.score}%`, background: `hsl(${momentum.score >= 66 ? "142 70% 45%" : momentum.score >= 33 ? "35 90% 55%" : "0 84% 60%"})` }} /></div>
          {momentum.trend && momentum.trend.length > 0 && (
            <div className="mb-4" data-testid="exec-momentum-trend">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Score trajectory (weekly)</div>
              <ResponsiveContainer width="100%" height={110}>
                <AreaChart data={momentum.trend}>
                  <defs><linearGradient id="mg1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="hsl(142 70% 45%)" stopOpacity={0.5} /><stop offset="100%" stopColor="hsl(142 70% 45%)" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 30% 18%)" vertical={false} />
                  <XAxis dataKey="week" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={CHART_TT} formatter={(v) => [`${v}/100`, "Score"]} />
                  <Area type="monotone" dataKey="score" stroke="hsl(142 70% 45%)" strokeWidth={2.5} fill="url(#mg1)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
          {momentum.activity.length === 0 ? <p className="text-xs text-muted-foreground">No remediation activity yet — logs added on Controls or Vendors appear here.</p> : (
            <div className="space-y-2" data-testid="exec-remediation-activity">
              {momentum.activity.map((it, i) => (
                <div key={i} data-testid="exec-activity-item" className="flex items-center gap-3 text-xs">
                  <span className="font-mono uppercase text-[9px] px-1.5 py-0.5 rounded-sm shrink-0" style={{ background: it.kind === "remediation" ? "#3b6ef533" : it.kind === "evidence" ? "#42c98e33" : "#94a3b833", color: it.kind === "remediation" ? "#3b6ef5" : it.kind === "evidence" ? "#42c98e" : "#94a3b8" }}>{it.kind}</span>
                  <span className="font-mono text-ai text-[11px] shrink-0">{it.entity}</span>
                  <span className="min-w-0 truncate flex-1 text-foreground/80">{it.text}</span>
                  <span className="text-[10px] text-muted-foreground shrink-0">{new Date(it.ts).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      )}

      {activity && activity.length > 0 && (
        <motion.div custom={5} variants={fade} initial="hidden" animate="show" className="col-span-full bg-card fact-border rounded-xl p-6" data-testid="exec-autonomy-activity">
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <Bot className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Autonomy Activity <span className="text-xs font-normal text-muted-foreground">· AI fixes shipping live</span></h2>
            <div className="flex-1" />
            <Filter className="w-3.5 h-3.5 text-muted-foreground" />
            {["all", "upgrades", "rollbacks", "containment", "fixes", "approvals"].map((k) => (
              <button key={k} data-testid={`activity-filter-${k}`} onClick={() => setActFilter(k)} className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full transition-colors ${actFilter === k ? "bg-ai text-white" : "bg-secondary text-muted-foreground hover:text-foreground"}`}>{k}</button>
            ))}
            <button data-testid="activity-export" onClick={exportActivity} className="text-[10px] px-2 py-0.5 rounded-md bg-secondary flex items-center gap-1 hover:text-foreground"><Download className="w-3 h-3" /> Export</button>
          </div>
          <div className="space-y-2">
            {filteredActivity.length === 0 ? <p className="text-xs text-muted-foreground" data-testid="autonomy-empty">No activity of this type yet.</p> : filteredActivity.slice(0, 12).map((e) => {
              const map = { "auto-fix": ["#42c98e", "AUTO-FIX"], "auto-upgrade": ["#12b4d6", "UPGRADE"], "auto-applied": ["#42c98e", "APPLIED"], rollback: ["#f5a623", "ROLLBACK"], "needs-approval": ["#e0574a", "APPROVAL"], contained: ["#8a7bf0", "CONTAINED"], digest: ["#94a3b8", "DIGEST"], restart: ["#12b4d6", "RESTART"] };
              const [c, lbl] = map[e.kind] || ["#94a3b8", (e.kind || "EVENT").toUpperCase()];
              return (
                <div key={e.id} data-testid="autonomy-item" className="flex items-center gap-3 text-xs">
                  <span className="font-mono uppercase text-[9px] px-1.5 py-0.5 rounded-sm shrink-0" style={{ background: `${c}22`, color: c }}>{lbl}</span>
                  <span className="min-w-0 flex-1 truncate"><span className="text-foreground/90 font-medium">{e.title}</span>{e.detail ? <span className="text-muted-foreground"> — {e.detail}</span> : null}</span>
                  <span className="text-[10px] text-muted-foreground shrink-0">{new Date(e.ts).toLocaleString()}</span>
                </div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* 2 — Status */}
      <SectionLabel icon={Gauge}>Status</SectionLabel>
      {strategicKpis.map((k, i) => (
        <motion.div key={k.label} custom={4 + i} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard {...k} /></motion.div>
      ))}
    </div>
  );
}

function OperationalOverview({ d, an, audit, intg, running, runAction, onLineage, m }) {
  const { recommendations } = d;
  const op = m.operational;
  const COUNT_KPIS = [
    { icon: ShieldAlert, label: "Critical Risks", value: op.kpis.critical_risks, accent: "0 84% 60%" },
    { icon: AlertTriangle, label: "Open Risks", value: op.kpis.open_risks, accent: "15 80% 55%" },
    { icon: Cpu, label: "Shadow AI", value: op.kpis.shadow_ai, accent: "190 90% 50%" },
    { icon: GitBranch, label: "Pending Decisions", value: op.kpis.pending_recs, accent: "35 90% 55%" },
  ];
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-5" data-testid="operational-overview">
      {/* 1 — Live intelligence (charts & data first) */}
      <SectionLabel icon={Activity}>Live intelligence</SectionLabel>
      <motion.div custom={0} variants={fade} initial="hidden" animate="show" className="col-span-full md:col-span-2 lg:col-span-6"><QuarterChart testid="chart-nist" title="NIST Control Maturity by Quarter" data={op.nist_maturity_by_quarter} kind="bar" color="hsl(142 70% 45%)" suffix="%" accent="142 70% 45%" source={op.sources?.nist} /></motion.div>
      <motion.div custom={1} variants={fade} initial="hidden" animate="show" className="col-span-full md:col-span-2 lg:col-span-6"><QuarterChart testid="chart-vendor" title="Third-Party Vendor Risk by Quarter" data={op.vendor_risk_by_quarter} kind="line" color="hsl(35 90% 55%)" suffix="/100" accent="35 90% 55%" source={op.sources?.vendor} /></motion.div>
      <motion.div custom={2} variants={fade} initial="hidden" animate="show" className="col-span-full md:col-span-2 lg:col-span-6"><QuarterChart testid="chart-phishing" title="Phishing Click Rate by Quarter" data={op.phishing_click_rate_by_quarter} kind="line" color="hsl(0 84% 60%)" suffix="%" accent="0 84% 60%" source={op.sources?.phishing} /></motion.div>
      <motion.div custom={3} variants={fade} initial="hidden" animate="show" className="col-span-full md:col-span-2 lg:col-span-6"><QuarterChart testid="chart-patching" title="Patching Coverage by Quarter" data={op.patching_coverage_by_quarter} kind="bar" color="hsl(190 90% 50%)" suffix="%" accent="190 90% 50%" source={op.sources?.patching} /></motion.div>

      <motion.div custom={4} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-7 bg-card fact-border rounded-xl p-6">
        <h2 className="font-head font-bold text-lg mb-4">Risk Heatmap <span className="text-xs font-normal text-muted-foreground">· click a cell for evidence</span></h2>
        <RiskHeatmap matrix={an.matrix} onSelect={onLineage} />
      </motion.div>
      <motion.div custom={5} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-5 bg-card fact-border rounded-xl p-6">
        <h2 className="font-head font-bold text-lg mb-2">Risk by Category</h2>
        <ResponsiveContainer width="100%" height={210}>
          <PieChart>
            <Pie data={an.by_category} dataKey="value" nameKey="name" innerRadius={54} outerRadius={82} paddingAngle={3} stroke="none">
              {an.by_category.map((_, i) => <Cell key={i} fill={PIE[i % PIE.length]} />)}
            </Pie>
            <Tooltip contentStyle={CHART_TT} />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex flex-wrap gap-x-3 gap-y-1 justify-center mt-2">
          {an.by_category.map((c, i) => <span key={c.name} className="text-[10px] text-muted-foreground flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: PIE[i % PIE.length] }} />{c.name}</span>)}
        </div>
      </motion.div>

      <motion.div custom={6} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-8 bg-card fact-border rounded-xl p-6">
        <h2 className="font-head font-bold text-lg mb-4">Remediation Recommendations</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {recommendations.map((r) => (
            <div key={r.ref} className="ai-border rounded-lg p-4 flex flex-col hover:-translate-y-0.5 transition-transform duration-200">
              <div className="flex items-center justify-between mb-2"><span className="font-mono text-xs text-ai">{r.ref} → {r.risk_ref}</span><DataTypeBadge type="ai_recommendation" /></div>
              <div className="font-medium text-sm mb-1">{r.title}</div>
              <div className="text-xs text-muted-foreground mb-3">{r.predicted_impact}</div>
              <div className="flex items-center justify-between mt-auto">
                <ConfidenceBadge value={r.confidence} />
                {RECMAP[r.risk_ref] && r.status !== "Applied" ? (
                  <button data-testid={`apply-${r.ref}`} disabled={!!running} onClick={() => runAction(RECMAP[r.risk_ref])} className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-1.5 rounded-md bg-ai text-background hover:opacity-90 transition-opacity disabled:opacity-50">
                    {running === RECMAP[r.risk_ref] ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />} Apply
                  </button>
                ) : r.status === "Applied" ? <span className="text-xs text-low">✓ Applied</span> : <span className="text-[10px] font-mono text-muted-foreground">{r.required_authority}</span>}
              </div>
            </div>
          ))}
        </div>
      </motion.div>
      <motion.div custom={7} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-4 bg-card fact-border rounded-xl p-6">
        <div className="flex items-center gap-2 mb-3"><Activity className="w-4 h-4 text-low" /><h2 className="font-head font-bold text-lg">Live Activity</h2></div>
        <div className="space-y-3">
          {audit.map((l, i) => (
            <div key={i} className="flex gap-3 text-xs">
              <span className="w-1.5 h-1.5 mt-1.5 rounded-full bg-ai shrink-0" />
              <div className="min-w-0"><div className="font-mono text-ai text-[11px]">{l.action}</div><div className="text-foreground/80 truncate">{l.detail}</div><div className="text-[10px] text-muted-foreground">{new Date(l.ts).toLocaleTimeString()}</div></div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* 2 — Status */}
      <SectionLabel icon={Gauge}>Status</SectionLabel>
      {COUNT_KPIS.map((k, i) => (
        <motion.div key={k.label} custom={8 + i} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3">
          <MetricCard icon={k.icon} label={k.label} value={<CountUp value={k.value} />} accent={k.accent} testid={`op-kpi-${k.label.toLowerCase().replace(/ /g, "-")}`} />
        </motion.div>
      ))}
      <motion.div custom={12} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard testid="op-ai-usage" icon={Zap} label="AI usage (month)" value={<CountUp value={op.ai_usage.queries_month} />} accent="266 85% 66%" sub={`${op.ai_usage.tokens_month.toLocaleString()} tokens · ${op.ai_usage.policy_violations} policy violations`} /></motion.div>
      <motion.div custom={13} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard testid="op-patching" icon={Bug} label="Patching coverage" value={op.patching_coverage_pct} unit="%" accent="142 70% 45%" sub="Timely vuln remediation" /></motion.div>
      <motion.div custom={14} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard testid="op-incidents" icon={AlertTriangle} label="Incidents / remediations" value={<><CountUp value={op.incidents_total} />/<CountUp value={op.remediations} /></>} accent="15 80% 55%" sub={`${op.incidents_open} open incidents`} /></motion.div>
      <motion.div custom={15} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard testid="op-vendor" icon={Building} label="Third-party risk" value={op.vendor_portfolio_risk} unit="/100" accent="35 90% 55%" sub={`${op.high_risk_vendors} high/critical vendors`} /></motion.div>
      <motion.div custom={16} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard testid="op-mttd" icon={Clock} label="MTTD" value={op.mttd_hours} unit="h" accent="190 90% 50%" sub="Mean time to detect" /></motion.div>
      <motion.div custom={17} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard testid="op-mttr" icon={Gauge} label="MTTR" value={op.mttr_hours} unit="h" accent="266 85% 66%" sub="Mean time to remediate" /></motion.div>
      <motion.div custom={18} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard testid="op-phishing" icon={MailWarning} label="Phishing click rate" value={op.phishing_click_rate_by_quarter.at(-1)?.value} unit="%" accent="0 84% 60%" sub="Latest quarter" /></motion.div>
      <motion.div custom={19} variants={fade} initial="hidden" animate="show" className="col-span-6 md:col-span-2 lg:col-span-3"><MetricCard testid="op-nist" icon={Layers} label="NIST control maturity" value={op.nist_maturity_by_quarter.at(-1)?.value} unit="%" accent="142 70% 45%" sub="Avg control effectiveness" /></motion.div>

      {/* 3 — Connectors & one-click remediation */}
      <SectionLabel icon={Plug}>Connectors &amp; remediation</SectionLabel>
      <motion.div custom={20} variants={fade} initial="hidden" animate="show" className="col-span-full">
        <SyncTicker />
        <IntegrationsPanel integrations={intg} onAction={runAction} running={running} />
      </motion.div>
    </div>
  );
}

export default function Overview() {
  const { mode, user } = useAuth();
  const [d, setD] = useState(null);
  const [an, setAn] = useState(null);
  const [audit, setAudit] = useState([]);
  const [intg, setIntg] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [running, setRunning] = useState(null);
  const [lineage, setLineage] = useState(null);
  const [report, setReport] = useState(false);
  const [momentum, setMomentum] = useState(null);
  const [autonomy, setAutonomy] = useState([]);

  const load = useCallback(async () => {
    const [o, a, au, ig, mt, rm, ac] = await Promise.all([
      api.get("/overview"), api.get("/analytics"), api.get("/audit-logs"), api.get("/integrations"), api.get("/metrics/dashboard"), api.get("/remediation/activity"),
      api.get("/self-scan/activity").catch(() => ({ data: { events: [] } })),
    ]);
    setD(o.data); setAn(a.data); setAudit(au.data.slice(0, 8)); setIntg(ig.data); setMetrics(mt.data); setMomentum(rm.data); setAutonomy(ac.data.events || []);
  }, []);

  useEffect(() => { load(); const t = setInterval(() => load(), 20000); return () => clearInterval(t); }, [load]);

  const runAction = async (action_id) => {
    setRunning(action_id);
    try {
      const { data } = await api.post("/actions/run", { action_id });
      toast.success(data.message || "Directory synced", { duration: 5000 });
      await load();
    } catch { toast.error("Action failed"); }
    setRunning(null);
  };

  if (!d || !an || !metrics) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const isExec = mode === "executive";

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4 }}>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="overview-title">
            {isExec ? "Executive Overview" : "Operational Command"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isExec ? "Strategic, board-ready intelligence — financial exposure, risk reduction & decisions required." : "Operational control posture — AI usage, patching, MTTD/MTTR, incidents & remediation workflows."}
          </p>
        </motion.div>
        {isExec && (
          <button data-testid="board-report-btn" onClick={() => setReport(true)} className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ai/15 border border-ai/40 text-ai font-head font-bold text-sm hover:bg-ai/25 transition-colors">
            <FileText className="w-4 h-4" /> Generate Board Report
          </button>
        )}
      </div>

      {isExec
        ? <ExecutiveOverview health={d.health} m={metrics.executive} momentum={momentum} activity={autonomy} onLineage={setLineage} />
        : <OperationalOverview d={d} an={an} audit={audit} intg={intg} running={running} runAction={runAction} onLineage={setLineage} m={metrics} />}

      <BoardReportModal open={report} onClose={() => setReport(false)} />
      <EvidenceLineageModal riskRef={lineage} onClose={() => setLineage(null)} />
    </div>
  );
}
