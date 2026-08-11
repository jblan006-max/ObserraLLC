import { useMemo, useState } from "react";
import {
  AlertTriangle, CheckCircle2, FileDown, Layers, RefreshCw, ShieldCheck,
  Sparkles, Target, TrendingDown, Wrench, Zap,
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AIInsight } from "@/components/AIInsight";
import { DataClassBadge, PALETTE, Panel, ProgressBar } from "@/components/control-intelligence/shared";
import { evidenceBuckets, toNumber } from "@/lib/controlIntelligenceModels";

const TIP = { background: "#0A0E17", border: "1px solid rgba(255,255,255,.12)", borderRadius: 8, fontSize: 12 };
const shortName = (s = "") => (s.length > 14 ? s.slice(0, 13) + "…" : s);
const effAccent = (v) => (v >= 75 ? "142 70% 45%" : v >= 55 ? "35 90% 55%" : "0 84% 60%");
const pal = (i) => PALETTE[i % PALETTE.length];

function Spark({ series, color, id }) {
  const d = (series || []).map((v, i) => ({ i, v: toNumber(v) }));
  if (d.length < 2) return <div className="h-8 mt-2" />;
  return (
    <div className="h-8 mt-2 -mb-1">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={d} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={`hsl(${color})`} stopOpacity={0.45} />
              <stop offset="100%" stopColor={`hsl(${color})`} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="v" stroke={`hsl(${color})`} strokeWidth={1.5} fill={`url(#${id})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function KpiCard({ label, value, sub, kind = "FACT", icon: Icon, accent = "168 76% 46%", series, sparkId, onClick, testid }) {
  return (
    <button type="button" onClick={onClick} data-testid={testid}
      className="w-full text-left bg-card fact-border rounded-xl p-4 hover:bg-secondary/25 transition-colors"
      style={{ borderLeft: `3px solid hsl(${accent})` }}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          {Icon && <Icon className="w-3.5 h-3.5" />}{label}
        </div>
        <DataClassBadge kind={kind} />
      </div>
      <div className="font-head font-black text-2xl lg:text-3xl mt-2" style={{ color: `hsl(${accent})` }}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
      <Spark series={series} color={accent} id={sparkId} />
    </button>
  );
}

function Donut({ data, centerValue, centerLabel, testid }) {
  const total = data.reduce((s, d) => s + toNumber(d.value), 0);
  return (
    <div className="relative h-56" data-testid={testid}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="92%" paddingAngle={2} stroke="none">
            {data.map((d, i) => <Cell key={i} fill={`hsl(${d.color})`} />)}
          </Pie>
          <Tooltip contentStyle={TIP} formatter={(v, n) => [`${v}${total ? ` · ${Math.round((v / total) * 100)}%` : ""}`, n]} />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <div className="font-head font-black text-2xl">{centerValue}</div>
        <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{centerLabel}</div>
      </div>
    </div>
  );
}

function Legend({ items }) {
  return (
    <div className="space-y-2">
      {items.map((it) => (
        <div key={it.name} className="flex items-center justify-between gap-2 text-xs">
          <span className="flex items-center gap-2 min-w-0">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: `hsl(${it.color})` }} />
            <span className="truncate">{it.name}</span>
          </span>
          <span className="font-mono text-muted-foreground shrink-0">{it.label ?? it.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function MissionControlDashboard({ data, onOpenTab, onSelectControl, onExecutiveReport, reportBusy }) {
  const [showAdvisor, setShowAdvisor] = useState(false);
  const controls = data?.controls || [];
  const summary = data?.summary || {};
  const frameworks = data?.frameworks || [];
  const compliance = data?.compliance || {};
  const gaps = data?.gaps || [];
  const connectorHealth = data?.connectorHealth || { connectors: [], summary: {} };

  const total = summary.total || 0;
  const effective = summary.passing || 0;
  const ineffective = controls.filter((c) => c.status === "Failing").length;
  const atRisk = Math.max(0, total - effective - ineffective);
  const coverage = toNumber(compliance.overall);
  const overallEff = summary.averageEffectiveness || 0;

  const byDomain = useMemo(() => {
    const m = {};
    for (const c of controls) {
      const k = c.category || "Other";
      m[k] = m[k] || { domain: k, total: 0, effSum: 0, passing: 0, atRisk: 0, ineffective: 0 };
      m[k].total += 1; m[k].effSum += toNumber(c.effectiveness);
      if (c.status === "Passing") m[k].passing += 1;
      else if (c.status === "Failing") m[k].ineffective += 1;
      else m[k].atRisk += 1;
    }
    return Object.values(m)
      .map((d) => ({ ...d, avgEff: Math.round(d.effSum / d.total) }))
      .sort((a, b) => b.total - a.total);
  }, [controls]);

  const evBuckets = evidenceBuckets(controls);
  const evColors = { Fresh: "142 70% 45%", Watch: "35 90% 55%", Expiring: "15 80% 55%", Expired: "0 84% 60%" };
  const evData = evBuckets.map((b) => ({ name: b.name, value: b.value, color: evColors[b.name] }));
  const freshCount = (evBuckets.find((b) => b.name === "Fresh")?.value || 0) + (evBuckets.find((b) => b.name === "Watch")?.value || 0);
  const freshPct = total ? Math.round((freshCount / total) * 100) : 0;

  const healthData = [
    { name: "Effective", value: effective, color: "142 70% 45%" },
    { name: "At risk", value: atRisk, color: "35 90% 55%" },
    { name: "Ineffective", value: ineffective, color: "0 84% 60%" },
  ];

  const sortedFw = [...frameworks].sort((a, b) => b.coverage - a.coverage);
  const weaknesses = [...controls].sort((a, b) => toNumber(a.effectiveness) - toNumber(b.effectiveness)).slice(0, 5);
  const recent = [...controls].filter((c) => c.last_tested).sort((a, b) => new Date(b.last_tested) - new Date(a.last_tested)).slice(0, 5);
  const driftControls = controls.filter((c) => c.drift);
  const driftHigh = driftControls.filter((c) => Math.abs(toNumber(c.drift_delta)) >= 15).length;
  const driftMed = driftControls.filter((c) => { const d = Math.abs(toNumber(c.drift_delta)); return d >= 8 && d < 15; }).length;
  const driftLow = Math.max(0, driftControls.length - driftHigh - driftMed);

  const avgMaturity = summary.averageMaturity || 0;
  const monitoringPct = total ? Math.round(((total - (summary.stale || 0)) / total) * 100) : 0;
  const assurance = summary.healthScore || 0;
  const stars = Math.round(assurance / 20);
  const assuranceBars = [
    { label: "Design effectiveness", value: Math.round(avgMaturity * 20) },
    { label: "Operating effectiveness", value: overallEff },
    { label: "Evidence quality", value: freshPct },
    { label: "Continuous monitoring", value: monitoringPct },
  ];
  const remediationPct = total ? Math.round((effective / total) * 100) : 0;

  const advisor = [];
  if (atRisk > 0) advisor.push({ sev: "High", title: `${atRisk} control(s) at risk of ineffectiveness`, note: `${Math.round((atRisk / (total || 1)) * 100)}% of controls need attention.` });
  if (weaknesses[0]) advisor.push({ sev: weaknesses[0].effectiveness < 55 ? "High" : "Medium", title: `${weaknesses[0].control_id} has the lowest effectiveness (${weaknesses[0].effectiveness}%)`, note: `${weaknesses[0].name} — prioritize review.` });
  if ((summary.stale || 0) + (summary.expiring || 0) > 0) advisor.push({ sev: "Medium", title: "Evidence freshness needs attention", note: `${summary.stale || 0} expired · ${summary.expiring || 0} expiring soon.` });
  advisor.push({ sev: "Low", title: `Framework coverage ${coverage}%`, note: `${frameworks.length} frameworks mapped across the control set.` });
  if (driftControls.length > 0) advisor.push({ sev: "High", title: `${driftControls.length} control(s) show drift`, note: "Review drift patterns and root causes." });
  const sevStyle = { High: "bg-crit/10 text-crit border-crit/25", Medium: "bg-med/10 text-med border-med/25", Low: "bg-low/10 text-low border-low/25" };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 xl:grid-cols-6 gap-4">
        <KpiCard testid="ci-kpi-effectiveness" label="Overall control effectiveness" value={`${overallEff}%`} sub={`${effective}/${total} controls passing`} kind="FACT" icon={Target} accent="142 70% 45%" series={byDomain.map((d) => d.avgEff)} sparkId="sp-eff" onClick={() => onOpenTab("effectiveness")} />
        <KpiCard testid="ci-kpi-total" label="Total controls" value={total} sub="Live control catalog" kind="FACT" icon={Layers} accent="210 92% 62%" series={byDomain.map((d) => d.total)} sparkId="sp-total" onClick={() => onOpenTab("effectiveness")} />
        <KpiCard testid="ci-kpi-effective" label="Effective controls" value={effective} sub={`${total ? Math.round((effective / total) * 100) : 0}% of total`} kind="FACT" icon={CheckCircle2} accent="168 76% 46%" series={byDomain.map((d) => d.passing)} sparkId="sp-effective" onClick={() => onOpenTab("effectiveness")} />
        <KpiCard testid="ci-kpi-atrisk" label="At risk controls" value={atRisk} sub={`${total ? Math.round((atRisk / total) * 100) : 0}% of total`} kind="FACT" icon={AlertTriangle} accent="35 90% 55%" series={byDomain.map((d) => d.atRisk)} sparkId="sp-atrisk" onClick={() => onOpenTab("remediation")} />
        <KpiCard testid="ci-kpi-ineffective" label="Ineffective controls" value={ineffective} sub={`${total ? Math.round((ineffective / total) * 100) : 0}% of total`} kind="FACT" icon={TrendingDown} accent="0 84% 60%" series={byDomain.map((d) => d.ineffective)} sparkId="sp-ineff" onClick={() => onOpenTab("remediation")} />
        <KpiCard testid="ci-kpi-coverage" label="Control coverage" value={`${coverage}%`} sub="Avg framework coverage" kind="FACT" icon={ShieldCheck} accent="262 83% 66%" series={frameworks.map((f) => f.coverage)} sparkId="sp-cov" onClick={() => onOpenTab("frameworks")} />
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 grid md:grid-cols-2 gap-5">
          <Panel title="Effectiveness by control domain" subtitle="Live average effectiveness per domain — current values, no fabricated time series." testid="ci-domain-effectiveness">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byDomain.map((d) => ({ name: shortName(d.domain), eff: d.avgEff }))} margin={{ left: -12, right: 8, top: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                  <XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={54} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} width={32} />
                  <Tooltip contentStyle={TIP} cursor={{ fill: "rgba(255,255,255,.04)" }} />
                  <Bar dataKey="eff" radius={[5, 5, 0, 0]}>
                    {byDomain.map((d, i) => <Cell key={i} fill={`hsl(${pal(i)})`} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Effectiveness by domain" subtitle="Share of controls by domain, each domain a distinct color." testid="ci-domain-donut">
            <Donut data={byDomain.map((d, i) => ({ name: shortName(d.domain), value: d.total, color: pal(i) }))} centerValue={`${overallEff}%`} centerLabel="Overall" testid="ci-domain-donut-chart" />
            <div className="mt-3">
              <Legend items={byDomain.slice(0, 6).map((d, i) => ({ name: d.domain, color: pal(i), label: `${d.avgEff}%` }))} />
            </div>
          </Panel>
        </div>

        <Panel title="AI Control Advisor" subtitle="Live analysis of your control environment." testid="ci-ai-advisor" actions={<Sparkles className="w-4 h-4 text-ai" />}>
          <div className="space-y-2.5">
            {advisor.map((a, i) => (
              <div key={i} className="rounded-lg border border-border p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium text-sm leading-snug">{a.title}</div>
                  <span className={`shrink-0 text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border ${sevStyle[a.sev]}`}>{a.sev}</span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">{a.note}</div>
              </div>
            ))}
          </div>
          <button data-testid="ci-ask-advisor" onClick={() => setShowAdvisor((s) => !s)}
            className="mt-3 w-full inline-flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-md border border-ai/40 bg-ai/10 text-ai text-xs font-head font-bold">
            <Zap className="w-3.5 h-3.5" /> {showAdvisor ? "Hide AI Advisor" : "Ask AI Advisor"}
          </button>
          {showAdvisor && (
            <div className="mt-3">
              <AIInsight dashboard="Control Intelligence" accent="168 76% 46%" auto slug="control-intelligence-advisor" />
            </div>
          )}
        </Panel>
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <Panel title="Control health distribution" subtitle="Live status split across the control catalog." testid="ci-health-distribution">
          <Donut data={healthData} centerValue={total} centerLabel="Total controls" testid="ci-health-donut" />
          <div className="mt-3"><Legend items={healthData.map((d) => ({ name: d.name, color: d.color, label: `${d.value} · ${total ? Math.round((d.value / total) * 100) : 0}%` }))} /></div>
        </Panel>

        <Panel title="Framework coverage" subtitle="Coverage per mapped compliance framework (live)." testid="ci-framework-coverage">
          {sortedFw.length === 0 ? (
            <div className="text-sm text-muted-foreground">No framework coverage returned.</div>
          ) : (
            <div className="space-y-3">
              {sortedFw.map((f, i) => (
                <button key={f.framework} onClick={() => onOpenTab("frameworks")} className="w-full text-left">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="truncate flex items-center gap-1.5"><span className="w-2 h-2 rounded-full" style={{ background: `hsl(${pal(i)})` }} />{f.framework}</span>
                    <span className="font-mono text-muted-foreground shrink-0">{f.coverage}%</span>
                  </div>
                  <ProgressBar value={f.coverage} accent={pal(i)} />
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Evidence freshness" subtitle="Live evidence-expiry classification." testid="ci-evidence-freshness">
          <Donut data={evData} centerValue={`${freshPct}%`} centerLabel="Fresh" testid="ci-evidence-donut" />
          <div className="mt-3"><Legend items={evData.map((d) => ({ name: d.name, color: d.color, label: `${d.value}` }))} /></div>
        </Panel>
      </div>

      <div className="grid xl:grid-cols-2 gap-5">
        <Panel title="Top control weaknesses" subtitle="Lowest-effectiveness controls (live) — click for details, risk & fixes." testid="ci-weaknesses">
          {weaknesses.length === 0 ? <div className="text-sm text-muted-foreground">No controls available.</div> : (
            <div className="space-y-3">
              {weaknesses.map((c, i) => (
                <button key={c.control_id} onClick={() => onSelectControl(c)} className="w-full text-left">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="truncate"><span className="font-mono text-ai">{c.control_id}</span> · {c.name}</span>
                    <span className="font-mono shrink-0" style={{ color: `hsl(${pal(i)})` }}>{c.effectiveness}%</span>
                  </div>
                  <ProgressBar value={c.effectiveness} accent={pal(i)} />
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Recent control activity" subtitle="Most recently tested controls (live)." testid="ci-recent-events">
          {recent.length === 0 ? <div className="text-sm text-muted-foreground">No recent activity.</div> : (
            <div className="space-y-2">
              {recent.map((c) => (
                <button key={c.control_id} onClick={() => onSelectControl(c)} className="w-full text-left flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5 hover:bg-secondary/30">
                  <span className="flex items-center gap-2 min-w-0">
                    <CheckCircle2 className="w-4 h-4 text-low shrink-0" />
                    <span className="min-w-0">
                      <span className="text-sm font-medium truncate block">{c.name}</span>
                      <span className="text-[10px] font-mono text-muted-foreground">{c.control_id} · {c.effectiveness}%</span>
                    </span>
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground shrink-0">{c.last_tested ? new Date(c.last_tested).toLocaleDateString() : ""}</span>
                </button>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <Panel title="Remediation progress" subtitle="Modeled from live control status." testid="ci-remediation-progress" actions={<DataClassBadge kind="MODELLED" />}>
          <div className="font-head font-black text-3xl" style={{ color: "hsl(142 70% 45%)" }}>{remediationPct}%</div>
          <div className="text-xs text-muted-foreground mb-3">{effective} of {total} controls effective</div>
          <ProgressBar value={remediationPct} accent="142 70% 45%" />
          <div className="grid grid-cols-3 gap-2 mt-4 text-center">
            <div><div className="font-head font-bold text-low">{effective}</div><div className="text-[10px] text-muted-foreground">Effective</div></div>
            <div><div className="font-head font-bold text-med">{atRisk}</div><div className="text-[10px] text-muted-foreground">At risk</div></div>
            <div><div className="font-head font-bold text-crit">{ineffective}</div><div className="text-[10px] text-muted-foreground">Ineffective</div></div>
          </div>
        </Panel>

        <Panel title="Control drift detection" subtitle="Live effectiveness drift vs baseline." testid="ci-drift">
          <div className="font-head font-black text-3xl text-crit">{driftControls.length}</div>
          <div className="text-xs text-muted-foreground mb-3">Drifted controls</div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs"><span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-crit" /> High drift</span><span className="font-mono">{driftHigh}</span></div>
            <div className="flex items-center justify-between text-xs"><span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-high" /> Medium drift</span><span className="font-mono">{driftMed}</span></div>
            <div className="flex items-center justify-between text-xs"><span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-med" /> Low drift</span><span className="font-mono">{driftLow}</span></div>
          </div>
          <button data-testid="ci-drift-details" onClick={() => onOpenTab("remediation")} className="mt-4 w-full px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">View drift details</button>
        </Panel>

        <Panel title="Assurance score" subtitle="Modeled composite assurance index." testid="ci-assurance" actions={<DataClassBadge kind="MODELLED" />}>
          <div className="flex items-center gap-4">
            <div className="relative w-20 h-20 shrink-0">
              <div className="absolute inset-0 rounded-full" style={{ background: `conic-gradient(hsl(38 92% 55%) ${assurance * 3.6}deg, hsl(var(--secondary)) 0deg)` }} />
              <div className="absolute inset-1.5 rounded-full bg-card flex items-center justify-center font-head font-black text-2xl">{assurance}</div>
            </div>
            <div>
              <div className="flex items-center gap-0.5">{[0, 1, 2, 3, 4].map((i) => <span key={i} className={i < stars ? "text-med" : "text-muted-foreground/30"}>★</span>)}</div>
              <div className="text-xs text-muted-foreground mt-1">{assurance >= 80 ? "Strong" : assurance >= 60 ? "Good" : "Needs work"}</div>
            </div>
          </div>
          <div className="space-y-2 mt-4">
            {assuranceBars.map((b, i) => (
              <div key={b.label}>
                <div className="flex items-center justify-between text-[11px] mb-1"><span className="text-muted-foreground">{b.label}</span><span className="font-mono">{b.value}%</span></div>
                <ProgressBar value={b.value} accent={pal(i + 2)} />
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Quick actions" subtitle="Jump to a live control workflow." testid="ci-quick-actions">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Control inventory", sub: "Inspect all controls", icon: Layers, tab: "effectiveness", tid: "ci-qa-inventory" },
            { label: "Evidence assurance", sub: "Packs & freshness", icon: FileDown, tab: "evidence", tid: "ci-qa-evidence" },
            { label: "Remediation & drift", sub: "Prioritized queue", icon: Wrench, tab: "remediation", tid: "ci-qa-remediation" },
            { label: "Framework intelligence", sub: "Coverage & crosswalk", icon: ShieldCheck, tab: "frameworks", tid: "ci-qa-frameworks" },
          ].map((a, i) => (
            <button key={a.label} data-testid={a.tid} onClick={() => onOpenTab(a.tab)}
              className="text-left rounded-xl border border-border bg-secondary/20 p-4 hover:bg-secondary/40 transition-colors" style={{ borderTop: `2px solid hsl(${pal(i)})` }}>
              <a.icon className="w-5 h-5" style={{ color: `hsl(${pal(i)})` }} />
              <div className="font-head font-bold text-sm mt-2">{a.label}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5">{a.sub}</div>
            </button>
          ))}
        </div>
      </Panel>

      <div className="rounded-xl border border-border bg-card px-5 py-4 flex flex-wrap items-center gap-x-8 gap-y-3" data-testid="ci-footer-strip">
        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Data sources</div>
          <div className="text-sm font-head font-bold flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-low" /> {connectorHealth.summary?.healthy ?? 0} connected · {connectorHealth.connectors?.length ?? 0} total</div>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Last data refresh</div>
          <div className="text-sm font-head font-bold">{data?.generatedAt ? new Date(data.generatedAt).toLocaleTimeString() : "—"}</div>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Active frameworks</div>
          <div className="text-sm font-head font-bold">{frameworks.length}</div>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Controls monitored</div>
          <div className="text-sm font-head font-bold">{total}</div>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Open gaps</div>
          <div className="text-sm font-head font-bold">{gaps.length}</div>
        </div>
        <button data-testid="ci-footer-report" onClick={onExecutiveReport} disabled={reportBusy}
          className="ml-auto inline-flex items-center gap-1.5 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">
          {reportBusy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />} Executive Assurance Report
        </button>
      </div>
    </div>
  );
}
