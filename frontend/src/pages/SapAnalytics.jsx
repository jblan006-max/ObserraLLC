import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { useDeepDive } from "@/context/DeepDiveContext";
import {
  PieChart, Pie, Cell, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from "recharts";
import { Users, Gauge, ShieldAlert, KeyRound, Activity, BarChart3, Globe, Layers } from "lucide-react";

const CHART_TT = { background: "hsl(215 38% 10%)", border: "1px solid hsl(215 30% 18%)", borderRadius: 8, fontSize: 12 };
const REGION_COLORS = ["#3b6ef5", "#42c98e", "#f5a623", "#a06cf0", "#e0574a"];

const BarList = ({ items, color = "hsl(210 92% 62%)", testid, onItemClick }) => {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="space-y-2.5" data-testid={testid}>
      {items.map((i, idx) => {
        const inner = (
          <>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="truncate pr-2">{i.name}</span>
              <span className="font-mono text-muted-foreground shrink-0">{i.value}</span>
            </div>
            <div className="h-2.5 rounded-full bg-secondary/60 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(i.value / max) * 100}%`, background: i.privileged ? "hsl(266 85% 66%)" : color }} />
            </div>
          </>
        );
        return onItemClick ? (
          <button key={i.name} type="button" onClick={() => onItemClick(i)} className="w-full text-left cursor-pointer hover:opacity-80 transition-opacity" data-testid={`${testid}-item-${idx}`}>{inner}</button>
        ) : (
          <div key={i.name}>{inner}</div>
        );
      })}
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
  const { openDeepDive } = useDeepDive();
  const load = useCallback(async () => { const { data } = await api.get("/sap/analytics"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;
  const k = d.kpis;
  const riskPie = ["Critical", "High", "Medium", "Low"].map((r) => ({ name: r, value: d.risk_distribution[r] || 0 }));
  const RISK_COLORS = { Critical: "#e0574a", High: "#f5a623", Medium: "#3b6ef5", Low: "#42c98e" };
  const openRole = (i) => openDeepDive({
    accent: i.privileged ? "266 85% 66%" : "210 92% 62%", refLabel: `Role · ${i.name}`, title: `${i.name} — ${i.value} holder(s)`,
    rating: i.privileged ? "High" : i.value > 40 ? "Medium" : "Low", score: i.privileged ? 72 : Math.min(70, 20 + i.value),
    facets: [{ label: "Role", value: i.name }, { label: "Holders", value: i.value }, { label: "Type", value: i.privileged ? "Privileged / wide-authority" : "Standard" }],
    recommendedActions: [`Review the ${i.value} holder(s) of ${i.name} for least privilege${i.privileged ? " — treat as firefighter/privileged with time-boxed, logged access" : ""}.`, "Recertify all holders against job need and add the role to continuous SoD monitoring."],
    complianceRefs: ["SOX ITGC", "NIST AC-6", "ISO 27001 A.5.18"],
    explainTitle: `${i.name} — role assignment concentration`, explainKind: "SAP role least-privilege review", explainContext: { role: i.name, holders: i.value, privileged: !!i.privileged },
  });
  const openSodArea = (i) => openDeepDive({
    accent: "0 84% 60%", refLabel: `SoD · ${i.name}`, title: `${i.name} — ${i.value} open SoD conflict(s)`,
    rating: i.value > 10 ? "Critical" : i.value > 3 ? "High" : "Medium", score: Math.min(99, 40 + i.value * 4),
    facets: [{ label: "Business area", value: i.name }, { label: "Open conflicts", value: i.value }, { label: "Share of open", value: `${Math.round((i.value / Math.max(1, k.open_sod)) * 100)}%` }],
    recommendedActions: [`Prioritise remediating the ${i.value} open SoD conflict(s) in ${i.name} — remove one side of each toxic role pair or apply a monitored mitigating control.`, "Enable auto-remediation for Critical conflicts in this area, then recertify the affected roles."],
    complianceRefs: ["SOX ITGC", "NIST AC-5", "ISO 27001 A.5.3"],
    explainTitle: `${i.name} — SoD conflict concentration`, explainKind: "SAP SoD conflict area remediation", explainContext: { area: i.name, open_conflicts: i.value, total_open: k.open_sod },
  });
  const openDept = (i) => openDeepDive({
    accent: "190 90% 50%", refLabel: `Dept · ${i.name}`, title: `${i.name} — ${i.value} SAP user(s)`, rating: "Medium", score: Math.min(80, 30 + Math.round(i.value / 2)),
    facets: [{ label: "Department", value: i.name }, { label: "SAP users", value: i.value }],
    recommendedActions: [`Run an access recertification campaign for ${i.name} to confirm least-privilege across its ${i.value} SAP user(s).`, "Investigate any dormant or terminated-with-access identities in this department first."],
    complianceRefs: ["SOX ITGC", "NIST AC-2"], explainTitle: `${i.name} — departmental SAP access`, explainKind: "SAP department access recertification", explainContext: { department: i.name, users: i.value },
  });
  const openLicense = (i) => openDeepDive({
    accent: "142 70% 45%", refLabel: `License · ${i.name}`, title: `${i.name} — ${i.value} assignment(s)`, rating: "Low", score: 30,
    facets: [{ label: "License type", value: i.name }, { label: "Assignments", value: i.value }],
    recommendedActions: [`Right-size ${i.name} licences — reclaim assignments from dormant or deactivated accounts to cut spend.`, "Reconcile license type against actual SAP usage and downgrade over-provisioned users."],
    explainTitle: `${i.name} — SAP license optimisation`, explainKind: "SAP license right-sizing", explainContext: { license_type: i.name, count: i.value },
  });

  return (
    <div className="space-y-6" data-testid="sap-analytics">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="analytics-title">SAP Analytics & Metrics</h1>
        <p className="text-sm text-muted-foreground mt-1">Live access, license, risk and governance metrics across the SAP landscape.</p>
      </div>

      <SapInsight dashboard="SAP Analytics" focus="access, license and risk analytics" accent="199 89% 48%" auto slug="sap-analytics" />

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
        <Panel title="Top 10 Roles by Assignment" sub="Most-assigned SAP roles (purple = privileged). Click a role to drill in." icon={Layers} className="lg:col-span-6">
          <BarList items={d.top_roles} testid="an-top-roles" onItemClick={openRole} />
        </Panel>
        <Panel title="Open SoD Conflicts by Area" sub="Toxic combinations grouped by business process. Click an area to drill in." icon={ShieldAlert} className="lg:col-span-6">
          <BarList items={d.sod_by_area} color="hsl(0 84% 60%)" testid="an-sod-area" onItemClick={openSodArea} />
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Panel title="Users by Department" icon={Users} className="lg:col-span-5">
          <BarList items={d.by_department} color="hsl(190 90% 50%)" testid="an-by-dept" onItemClick={openDept} />
        </Panel>
        <Panel title="License Type Breakdown" icon={Gauge} className="lg:col-span-4">
          <BarList items={d.license_breakdown} color="hsl(142 70% 45%)" testid="an-license-breakdown" onItemClick={openLicense} />
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
