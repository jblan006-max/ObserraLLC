import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import {
  PieChart, Pie, Cell, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from "recharts";
import { Users, Gauge, ShieldAlert, KeyRound, Activity, BarChart3, Globe, Layers } from "lucide-react";

const CHART_TT = { background: "hsl(215 38% 10%)", border: "1px solid hsl(215 30% 18%)", borderRadius: 8, fontSize: 12 };
const REGION_COLORS = ["#3b6ef5", "#42c98e", "#f5a623", "#a06cf0", "#e0574a"];

const BarList = ({ items, color = "hsl(210 92% 62%)", testid }) => {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="space-y-2.5" data-testid={testid}>
      {items.map((i) => (
        <div key={i.name}>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="truncate pr-2">{i.name}</span>
            <span className="font-mono text-muted-foreground shrink-0">{i.value}</span>
          </div>
          <div className="h-2.5 rounded-full bg-secondary/60 overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${(i.value / max) * 100}%`, background: i.privileged ? "hsl(266 85% 66%)" : color }} />
          </div>
        </div>
      ))}
    </div>
  );
};

const Panel = ({ title, sub, icon: Icon, children, className = "" }) => (
  <div className={`bg-card fact-border rounded-xl p-5 ${className}`}>
    <div className="flex items-center gap-2 mb-1">{Icon && <Icon className="w-4 h-4 text-primary" />}<h2 className="font-head font-bold text-base">{title}</h2></div>
    {sub && <p className="text-[11px] text-muted-foreground mb-3">{sub}</p>}
    {children}
  </div>
);

export default function SapAnalytics() {
  const [d, setD] = useState(null);
  const load = useCallback(async () => { const { data } = await api.get("/sap/analytics"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;
  const k = d.kpis;
  const riskPie = ["Critical", "High", "Medium", "Low"].map((r) => ({ name: r, value: d.risk_distribution[r] || 0 }));
  const RISK_COLORS = { Critical: "#e0574a", High: "#f5a623", Medium: "#3b6ef5", Low: "#42c98e" };

  return (
    <div className="space-y-6" data-testid="sap-analytics">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="analytics-title">SAP Analytics & Metrics</h1>
        <p className="text-sm text-muted-foreground mt-1">Live access, license, risk and governance metrics across the SAP landscape.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="SAP identities" value={k.identities} sub={`${k.accounts} accounts`} accent="190 90% 50%" icon={Users} testid="an-identities" />
        <StatCard label="License usage" value={`${k.license_usage_pct}%`} sub={`${k.activated} active · ${k.deactivated} deactivated`} accent="142 70% 45%" icon={Gauge} testid="an-license" />
        <StatCard label="Avg risk score" value={k.avg_risk} sub={`${k.critical_sod} critical SoD`} accent="0 84% 60%" icon={Activity} testid="an-risk" />
        <StatCard label="Open SoD conflicts" value={k.open_sod} sub={`${k.privileged} privileged · ${k.sap_all} SAP_ALL`} accent="35 90% 55%" icon={ShieldAlert} testid="an-sod" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Dormant access" value={k.dormant} sub="Unused > 90d" accent="168 76% 46%" icon={KeyRound} testid="an-dormant" />
        <StatCard label="Orphan accounts" value={k.orphan} sub="Ownerless" accent="38 92% 55%" icon={KeyRound} testid="an-orphan" />
        <StatCard label="Terminated w/ access" value={k.terminated_residual} sub="Residual" accent="0 84% 60%" icon={ShieldAlert} testid="an-residual" />
        <StatCard label="SAML mapping" value={`${k.saml_coverage_pct}%`} sub="SSO-mapped identities" accent="266 85% 66%" icon={Globe} testid="an-saml" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Panel title="Top 10 Roles by Assignment" sub="Most-assigned SAP roles (purple = privileged)." icon={Layers} className="lg:col-span-6">
          <BarList items={d.top_roles} testid="an-top-roles" />
        </Panel>
        <Panel title="Open SoD Conflicts by Area" sub="Toxic combinations grouped by business process." icon={ShieldAlert} className="lg:col-span-6">
          <BarList items={d.sod_by_area} color="hsl(0 84% 60%)" testid="an-sod-area" />
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Panel title="Users by Department" icon={Users} className="lg:col-span-5">
          <BarList items={d.by_department} color="hsl(190 90% 50%)" testid="an-by-dept" />
        </Panel>
        <Panel title="License Type Breakdown" icon={Gauge} className="lg:col-span-4">
          <BarList items={d.license_breakdown} color="hsl(142 70% 45%)" testid="an-license-breakdown" />
        </Panel>
        <Panel title="Users by Region" icon={Globe} className="lg:col-span-3">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={d.by_region} dataKey="value" nameKey="name" innerRadius={44} outerRadius={72} paddingAngle={3} stroke="none">
                {d.by_region.map((e, i) => <Cell key={e.name} fill={REGION_COLORS[i % REGION_COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={CHART_TT} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-2 justify-center">
            {d.by_region.map((c, i) => <span key={c.name} className="text-[10px] text-muted-foreground flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: REGION_COLORS[i % REGION_COLORS.length] }} />{c.name} {c.value}</span>)}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Panel title="Activation / Deactivation Trend" sub="Last 6 months." icon={BarChart3} className="lg:col-span-8">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={d.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 30% 18%)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis width={26} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip contentStyle={CHART_TT} />
              <Line type="monotone" dataKey="activated" stroke="#42c98e" strokeWidth={2.5} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="deactivated" stroke="#e0574a" strokeWidth={2.5} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="Risk Distribution" icon={Activity} className="lg:col-span-4">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={riskPie} dataKey="value" nameKey="name" innerRadius={44} outerRadius={72} paddingAngle={3} stroke="none">
                {riskPie.map((e) => <Cell key={e.name} fill={RISK_COLORS[e.name]} />)}
              </Pie>
              <Tooltip contentStyle={CHART_TT} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-2 justify-center">
            {riskPie.map((c) => <span key={c.name} className="text-[10px] text-muted-foreground flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: RISK_COLORS[c.name] }} />{c.name} {c.value}</span>)}
          </div>
        </Panel>
      </div>
    </div>
  );
}
