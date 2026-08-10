import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { useDeepDive } from "@/context/DeepDiveContext";
import { api } from "@/lib/api";
import { Link } from "react-router-dom";
import { StatCard, Spinner } from "@/components/dash";
import { AIInsight } from "@/components/AIInsight";
import { ChartBox } from "@/components/ChartBox";
import {
  PieChart, Pie, Cell, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from "recharts";
import {
  Users, KeyRound, ShieldAlert, Lock, MoonStar, Ghost, UserX, GitCompare, Activity, ShieldCheck,
} from "lucide-react";

const PIE = { Critical: "#e0574a", High: "#f5a623", Medium: "#3b6ef5", Low: "#42c98e" };
const CHART_TT = { background: "hsl(215 38% 10%)", border: "1px solid hsl(215 30% 18%)", borderRadius: 8, fontSize: 12 };
const RATE_ACCENT = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "190 90% 50%", Low: "142 70% 45%" };

const SectionLabel = ({ children, icon: Icon }) => (
  <div className="col-span-full flex items-center gap-2 mt-2">
    {Icon && <Icon className="w-3.5 h-3.5 text-muted-foreground" />}
    <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">{children}</span>
    <div className="flex-1 h-px bg-border/60" />
  </div>
);

export default function AccessOverview() {
  const { mode } = useAuth();
  const { openDeepDive } = useDeepDive();
  const [d, setD] = useState(null);
  const [slaBanner, setSlaBanner] = useState(null);

  const load = useCallback(async () => {
    const { data } = await api.get("/sap/overview");
    setD(data);
    try { const b = await api.get("/deploy/audit-sla-banner"); setSlaBanner(b.data); } catch { /* non-admin: no banner */ }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  if (!d) return <Spinner />;
  const isExec = mode === "executive";
  const riskPie = ["Critical", "High", "Medium", "Low"].map((k) => ({ name: k, value: d.risk_distribution[k] || 0 }));
  const areaRows = Object.entries(d.sod.by_area).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  const maxArea = Math.max(1, ...areaRows.map((r) => r.value));

  const openRisk = (r) => openDeepDive({
    accent: RATE_ACCENT[r.rating] || "0 84% 60%", refLabel: r.ref, title: r.name,
    rating: r.rating, score: r.score,
    facets: [
      { label: "Department", value: r.department }, { label: "Employment status", value: r.status },
      { label: "Open SoD conflicts", value: r.open_conflicts }, { label: "SAP Access Risk", value: `${r.score}/100 · ${r.rating}` },
    ],
    recommendedActions: [
      r.status === "Terminated" ? "Immediately lock/de-provision residual SAP access for this terminated worker." : "Review the highest-severity SoD conflict and remove one conflicting role or attach a mitigating control.",
      "Open the identity investigation to trace access path, HR provenance and lifecycle.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-5", "ISO 27001 A.5.15"], compliancePct: null,
    explainTitle: `${r.name} — SAP access risk`, explainKind: "sap identity access risk governance",
    explainContext: { identity: r, portfolio: { open_sod: d.sod.open, avg_risk: d.avg_risk_score } },
  });

  const kpis = [
    { label: "Total SAP identities", value: d.identities, sub: `${d.accounts} accounts · ${d.systems} systems`, accent: "190 90% 50%", icon: Users, testid: "sap-kpi-identities" },
    { label: "Avg access risk score", value: `${d.avg_risk_score}`, sub: `${d.risk_distribution.Critical} critical · ${d.risk_distribution.High} high`, accent: "0 84% 60%", icon: Activity, testid: "sap-kpi-risk" },
    { label: "Open SoD conflicts", value: d.sod.open, sub: `${d.sod.by_severity.Critical} critical · ${d.sod.mitigated} mitigated`, accent: "35 90% 55%", icon: GitCompare, testid: "sap-kpi-sod" },
    { label: "Privileged accounts", value: d.privileged, sub: `${d.sap_all} hold SAP_ALL`, accent: "266 85% 66%", icon: KeyRound, testid: "sap-kpi-privileged" },
  ];
  const kpis2 = [
    { label: "Terminated w/ access", value: d.terminated_residual, sub: "Residual access — de-provision", accent: "0 84% 60%", icon: UserX, testid: "sap-kpi-residual" },
    { label: "Dormant accounts", value: d.dormant, sub: "Unused > 90 days", accent: "168 76% 46%", icon: MoonStar, testid: "sap-kpi-dormant" },
    { label: "Orphan / ownerless", value: d.orphan, sub: "No active owner / sponsor", accent: "38 92% 55%", icon: Ghost, testid: "sap-kpi-orphan" },
    { label: "HR security holds", value: d.hr_security_holds, sub: "ADP↔IZ8 conflicts", accent: "330 82% 60%", icon: GitCompare, testid: "sap-kpi-hrhold" },
  ];

  return (
    <div className="space-y-6" data-testid="sap-overview">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="sap-overview-title">
          {isExec ? "Executive SAP Access Risk" : "SAP Access Operations"}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {isExec
            ? "Board-ready view of who has access to SAP, where the toxic combinations are, and the residual governance exposure — computed live from the correlated access model."
            : "Operational access posture across identities, roles, privileged accounts, dormant/orphan access and the joiner/mover/leaver pipeline."}
        </p>
      </div>

      {slaBanner && (slaBanner.open_overdue > 0 || slaBanner.breached_7d > 0 || slaBanner.escalated_7d > 0) && (
        <Link to="/app/system-health" data-testid="sap-sla-banner"
          className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-crit/40 bg-crit/10 px-4 py-3 hover:bg-crit/15 transition-colors">
          <ShieldAlert className="w-4 h-4 text-crit shrink-0" />
          <span className="text-sm font-semibold text-crit">Audit SLA attention</span>
          <span className="text-xs text-muted-foreground">
            {slaBanner.open_overdue} open request{slaBanner.open_overdue === 1 ? "" : "s"} past SLA · {slaBanner.breached_7d} breached this week · {slaBanner.escalated_7d} escalated
          </span>
          <span className="ml-auto text-[11px] font-mono text-crit">Open System Health →</span>
        </Link>
      )}

      <AIInsight dashboard="SAP Access Overview" accent="190 90% 50%" auto slug="sap-overview" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((k) => <StatCard key={k.label} {...k} />)}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis2.map((k) => <StatCard key={k.label} {...k} />)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <SectionLabel icon={ShieldCheck}>Risk synthesis · live</SectionLabel>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="lg:col-span-4 bg-card fact-border rounded-xl p-6" data-testid="sap-risk-distribution">
          <h2 className="font-head font-bold text-lg mb-1">Identity Risk Distribution</h2>
          <p className="text-[11px] text-muted-foreground mb-3">Obserra SAP Access Risk rating across all identities.</p>
          <ResponsiveContainer width="100%" height={210}>
            <PieChart>
              <Pie data={riskPie} dataKey="value" nameKey="name" innerRadius={54} outerRadius={82} paddingAngle={3} stroke="none">
                {riskPie.map((e) => <Cell key={e.name} fill={PIE[e.name]} />)}
              </Pie>
              <Tooltip contentStyle={CHART_TT} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-x-3 gap-y-1 justify-center mt-2">
            {riskPie.map((c) => <span key={c.name} className="text-[10px] text-muted-foreground flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: PIE[c.name] }} />{c.name} {c.value}</span>)}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="lg:col-span-4 bg-card fact-border rounded-xl p-6" data-testid="sap-sod-by-area">
          <h2 className="font-head font-bold text-lg mb-1">SoD Conflicts by Risk Area</h2>
          <p className="text-[11px] text-muted-foreground mb-4">Open toxic-access combinations grouped by business process.</p>
          <div className="space-y-2.5">
            {areaRows.map((r) => (
              <div key={r.name} data-testid={`sap-area-${r.name.replace(/[^a-z0-9]/gi, "-")}`}>
                <div className="flex items-center justify-between text-xs mb-1"><span>{r.name}</span><span className="font-mono text-muted-foreground">{r.value}</span></div>
                <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className="h-full rounded-full bg-crit/70" style={{ width: `${(r.value / maxArea) * 100}%` }} /></div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="lg:col-span-4 bg-card fact-border rounded-xl p-6" data-testid="sap-trend">
          <h2 className="font-head font-bold text-lg mb-1">SoD Remediation Trend</h2>
          <p className="text-[11px] text-muted-foreground mb-3">Open conflicts over the last 6 months.</p>
          <ChartBox height={210}>
            <LineChart data={d.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 30% 18%)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis width={28} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={CHART_TT} />
              <Line type="monotone" dataKey="conflicts" stroke="hsl(0 84% 60%)" strokeWidth={2.5} dot={{ r: 3 }} />
            </LineChart>
          </ChartBox>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="lg:col-span-7 bg-card fact-border rounded-xl p-6" data-testid="sap-top-risks">
          <div className="flex items-center gap-2 mb-4"><ShieldAlert className="w-4 h-4 text-crit" /><h2 className="font-head font-bold text-lg">Highest-Risk Identities</h2></div>
          <div className="space-y-2">
            {d.top_risks.map((r) => (
              <button key={r.ref} data-testid={`sap-toprisk-${r.ref}`} onClick={() => openRisk(r)}
                className="w-full text-left flex items-center gap-3 p-3 rounded-lg bg-secondary/30 hover:bg-secondary/60 transition-colors">
                <span className="font-head font-black text-xl w-12 shrink-0" style={{ color: `hsl(${RATE_ACCENT[r.rating]})` }}>{r.score}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{r.name} <span className="text-[10px] font-mono text-muted-foreground">· {r.ref}</span></div>
                  <div className="text-[11px] text-muted-foreground">{r.department} · {r.open_conflicts} open SoD · {r.status}</div>
                </div>
                <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full shrink-0" style={{ background: `hsl(${RATE_ACCENT[r.rating]} / 0.15)`, color: `hsl(${RATE_ACCENT[r.rating]})` }}>{r.rating}</span>
              </button>
            ))}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="lg:col-span-5 bg-card fact-border rounded-xl p-6" data-testid="sap-by-legal-entity">
          <div className="flex items-center gap-2 mb-4"><Lock className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Risk by Legal Entity</h2></div>
          <div className="space-y-3">
            {d.by_legal_entity.map((e) => (
              <div key={e.legal_entity} data-testid={`sap-le-${e.legal_entity}`}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="truncate pr-2">{e.name} <span className="text-muted-foreground font-mono">· {e.legal_entity}</span></span>
                  <span className="font-mono text-muted-foreground shrink-0">{e.count} · avg {e.avg_risk}</span>
                </div>
                <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${e.avg_risk}%`, background: `hsl(${e.avg_risk >= 45 ? "0 84% 60%" : e.avg_risk >= 25 ? "35 90% 55%" : "142 70% 45%"})` }} /></div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
