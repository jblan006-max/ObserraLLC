import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { HealthGauge } from "@/components/HealthGauge";
import { EvidenceLineageModal } from "@/components/EvidenceLineageModal";
import { SourceBadge, FreshnessBadge, ConfidenceBadge, DataTypeBadge, ScorePill } from "@/components/badges";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { TrendingUp, TrendingDown, Minus, AlertTriangle, ShieldAlert, Cpu, GitBranch, Loader2, Plug } from "lucide-react";

const Trend = ({ t }) => t === "up" ? <TrendingUp className="w-3.5 h-3.5 text-low" /> : t === "down" ? <TrendingDown className="w-3.5 h-3.5 text-crit" /> : <Minus className="w-3.5 h-3.5 text-muted-foreground" />;

export default function Overview() {
  const { mode } = useAuth();
  const [data, setData] = useState(null);
  const [lineage, setLineage] = useState(null);

  useEffect(() => { api.get("/overview").then((r) => setData(r.data)); }, []);

  if (!data) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  const { health, kpis, top_risks, recommendations, connector } = data;

  return (
    <div className="rise space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight">
            {mode === "executive" ? "Executive Intelligence" : "Operational Command"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {mode === "executive" ? "Enterprise health, business impact & board-ready recommendations." : "Control-level posture, evidence and remediation workflows."}
          </p>
        </div>
        {connector && (
          <div className="flex items-center gap-2 text-xs px-3 py-2 rounded-md bg-card border border-border">
            <Plug className="w-3.5 h-3.5 text-low" />
            <span className="font-medium">{connector.name}</span>
            <FreshnessBadge freshness={connector.freshness} />
            <span className="text-muted-foreground font-mono">{connector.records_ingested?.toLocaleString()} recs</span>
          </div>
        )}
      </div>

      {mode === "executive" ? (
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-6">
          <div className="col-span-full lg:col-span-8 bg-card fact-border rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-head font-bold text-lg">Enterprise Health Index</h2>
              <div className="flex items-center gap-3"><FreshnessBadge freshness={health.freshness} /><DataTypeBadge type="fact" /></div>
            </div>
            <div className="grid md:grid-cols-2 gap-4 items-center">
              <HealthGauge score={health.score} grade={health.grade} />
              <div className="space-y-2.5">
                {health.components.map((c) => (
                  <div key={c.name} className="flex items-center gap-3">
                    <span className="text-xs w-32 truncate text-muted-foreground">{c.name}</span>
                    <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${c.score}%`, background: c.score >= 75 ? "hsl(142 70% 45%)" : c.score >= 60 ? "hsl(35 90% 55%)" : "hsl(15 80% 55%)" }} />
                    </div>
                    <span className="font-mono text-xs w-8 text-right">{c.score}</span>
                    <Trend t={c.trend} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="col-span-full lg:col-span-4 bg-card fact-border rounded-lg p-6 flex flex-col">
            <h2 className="font-head font-bold text-lg mb-3">6-Month Trend</h2>
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={health.history}>
                <YAxis domain={[50, 80]} hide />
                <Line type="monotone" dataKey="score" stroke="hsl(190 90% 50%)" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 gap-3 mt-4">
              <MiniKpi label="Business exposure" value="$11.0M" type="estimate" />
              <MiniKpi label="Trend vs Q1" value="+8 pts" type="fact" />
            </div>
          </div>

          <KpiCard className="lg:col-span-3" icon={ShieldAlert} label="Critical Risks" value={kpis.critical_risks} accent="crit" />
          <KpiCard className="lg:col-span-3" icon={AlertTriangle} label="Open Risks" value={kpis.open_risks} accent="high" />
          <KpiCard className="lg:col-span-3" icon={Cpu} label="Shadow AI Detected" value={kpis.shadow_ai} accent="ai" />
          <KpiCard className="lg:col-span-3" icon={GitBranch} label="Pending Decisions" value={kpis.pending_recs} accent="med" />

          <div className="col-span-full lg:col-span-12 bg-card fact-border rounded-lg p-6">
            <h2 className="font-head font-bold text-lg mb-4">Priority Recommendations</h2>
            <div className="grid md:grid-cols-2 gap-4">
              {recommendations.map((r) => (
                <div key={r.ref} className="ai-border rounded-lg p-4 hover:-translate-y-0.5 transition-transform duration-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs text-ai">{r.ref}</span>
                    <DataTypeBadge type="ai_recommendation" />
                  </div>
                  <div className="font-medium text-sm mb-2">{r.title}</div>
                  <div className="text-xs text-muted-foreground mb-3">{r.predicted_impact}</div>
                  <div className="flex items-center justify-between">
                    <ConfidenceBadge value={r.confidence} />
                    <span className="text-[10px] font-mono text-muted-foreground">Authority: {r.required_authority}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard icon={ShieldAlert} label="Critical Risks" value={kpis.critical_risks} accent="crit" />
            <KpiCard icon={AlertTriangle} label="Open Risks" value={kpis.open_risks} accent="high" />
            <KpiCard icon={Cpu} label="AI Systems" value={kpis.ai_systems} accent="ai" />
            <KpiCard icon={GitBranch} label="Open Incidents" value={kpis.open_incidents} accent="med" />
          </div>

          <div className="bg-card fact-border rounded-lg overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
              <h2 className="font-head font-bold">Top Residual Risks</h2>
              <span className="text-[10px] font-mono text-muted-foreground uppercase">click a row → evidence lineage</span>
            </div>
            <table className="w-full text-sm">
              <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
                <tr>
                  <th className="text-left px-5 py-2.5">Ref</th>
                  <th className="text-left px-5 py-2.5">Risk</th>
                  <th className="text-left px-5 py-2.5">Inherent</th>
                  <th className="text-left px-5 py-2.5">Residual</th>
                  <th className="text-left px-5 py-2.5">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {top_risks.map((r) => (
                  <tr key={r.ref} data-testid={`overview-risk-${r.ref}`} onClick={() => setLineage(r.ref)}
                    className="border-b border-border/60 hover:bg-secondary/40 cursor-pointer transition-colors">
                    <td className="px-5 py-3 font-mono text-xs text-ai">{r.ref}</td>
                    <td className="px-5 py-3">{r.title}</td>
                    <td className="px-5 py-3"><ScorePill value={r.inherent} /></td>
                    <td className="px-5 py-3"><ScorePill value={r.residual} /></td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <SourceBadge source={r.source} /><ConfidenceBadge value={r.confidence} /><DataTypeBadge type={r.data_type} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <EvidenceLineageModal riskRef={lineage} onClose={() => setLineage(null)} />
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, accent, className = "" }) {
  const hsl = { crit: "0 84% 60%", high: "15 80% 55%", med: "35 90% 55%", ai: "190 90% 50%" }[accent];
  return (
    <div className={`bg-card fact-border rounded-lg p-5 hover:-translate-y-0.5 transition-transform duration-200 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <Icon className="w-4 h-4" style={{ color: `hsl(${hsl})` }} />
      </div>
      <div className="font-head font-black text-4xl tracking-tight" style={{ color: `hsl(${hsl})` }}>{value}</div>
    </div>
  );
}

function MiniKpi({ label, value, type }) {
  return (
    <div className={`rounded-md p-3 ${type === "estimate" ? "estimate-border" : "fact-border"}`}>
      <div className="text-[10px] text-muted-foreground mb-1">{label}</div>
      <div className="font-head font-bold text-lg">{value}</div>
      <div className="mt-1"><DataTypeBadge type={type} /></div>
    </div>
  );
}
