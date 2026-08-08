import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ConfidenceBadge } from "@/components/badges";
import { AIInsight } from "@/components/AIInsight";
import { StatCard, CardShell, EmptyState, BarList, Spinner } from "@/components/dash";
import { ChartBox } from "@/components/ChartBox";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { Cpu, AlertOctagon, Ban, Eye, Bot, Sparkles, Cloud, ShieldCheck, Activity, Layers, ShieldAlert } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { AISystemModal } from "@/components/AISystemModal";
import { AIMonitor } from "@/components/AIMonitor";
import { RiskDetailModal } from "@/components/RiskDetailModal";

const ACCENT = "350 89% 60%"; // AI Governance → rose
const riskClassColor = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
const OWASP_COL = { covered: "142 70% 45%", monitored: "35 90% 55%", gap: "0 84% 60%" };
const OWASP_RATE = { gap: "High", monitored: "Medium", covered: "Low" };
const GUARD_LABEL = { input_filtering: "Input filtering", output_filtering: "Output filtering", tool_allowlist: "Tool allow-list", human_in_loop: "Human-in-loop" };

function EvalBar({ label, value }) {
  const c = value >= 80 ? "hsl(142 70% 45%)" : value >= 65 ? "hsl(35 90% 55%)" : "hsl(15 80% 55%)";
  return (
    <div>
      <div className="flex justify-between text-[10px] text-muted-foreground mb-1"><span>{label}</span><span className="font-mono">{value || "—"}</span></div>
      <div className="h-1.5 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${value}%`, background: c }} /></div>
    </div>
  );
}

export default function AIGovernance() {
  const { mode } = useAuth();
  const isExec = mode === "executive";
  const [systems, setSystems] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [live, setLive] = useState(null);
  const [an, setAn] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  const load = () => {
    api.get("/ai-systems").then((r) => setSystems(r.data));
    api.get("/ai-incidents").then((r) => setIncidents(r.data));
    api.get("/enterprise/live").then((r) => setLive(r.data)).catch(() => setLive(null));
    api.get("/dash/ai-analytics").then((r) => setAn(r.data)).catch(() => setAn(null));
  };
  useEffect(() => { load(); }, []);

  const sanction = async (ref) => {
    await api.patch(`/ai-systems/${ref}`, { status: "sanctioned" });
    toast.success(`${ref} sanctioned & brought under governance`);
    load();
  };

  if (!systems) return <Spinner />;
  const shadow = systems.filter((s) => s.status === "shadow");
  const t = an?.totals || {};
  const trend = an?.usage_trend || [];
  const byModel = (an?.by_model || []).map((m) => ({ name: m.model, value: m.queries }));
  const riskDist = Object.entries(an?.agents?.risk_dist || {}).map(([name, value]) => ({ name, value, color: riskClassColor[name] }));
  const guardCov = an?.agents?.guard_cov || {};
  const agentTotal = an?.agents?.total || 0;

  const copilot = live?.copilot, openai = live?.openai, m365 = live?.m365;
  const anyLicensed = (copilot?.live) || (openai?.live) || (m365?.live);

  // Universal deep-dives — every risk-bearing card opens the standard AI detail (rating, score,
  // grounded AI brief + recommended fixes), same pattern as the rest of the platform.
  const openOwasp = (o) => setDetail({
    refLabel: o.code, title: o.name, rating: OWASP_RATE[o.status] || "Medium",
    facets: [
      { icon: Layers, label: "OWASP LLM control", value: `${o.code} · ${o.name}` },
      { icon: ShieldCheck, label: "Coverage status", value: (o.status || "").toUpperCase() },
      { icon: Bot, label: "Agents in scope", value: agentTotal || "—" },
    ],
    recommendedActions: o.status === "gap"
      ? [`No control mapped for ${o.code}. Add a guardrail (input/output filtering, tool allow-list or human-in-loop) covering ${o.name}, then re-evaluate.`]
      : o.status === "monitored"
        ? [`${o.code} is monitored but not enforced — promote detection to a blocking guardrail to close residual exposure.`]
        : [`${o.code} is covered — sustain the guardrail and keep evaluation evidence fresh.`],
    explainTitle: `${o.code} — ${o.name}`, explainKind: "owasp-llm ai-governance guardrail coverage", explainContext: { owasp: o, guardrails: guardCov, agents: agentTotal },
  });
  const openIncident = (i) => setDetail({
    refLabel: i.ref, title: i.title, rating: i.severity,
    facets: [
      { icon: Bot, label: "System", value: i.system },
      { icon: ShieldAlert, label: "Governance mode", value: i.mode },
      { icon: Activity, label: "Status", value: i.status },
    ],
    recommendedActions: [
      `Confirm ${i.mode === "block" ? "the blocking guardrail held" : "escalation of the guardrail to block"} for ${i.system}.`,
      "Review the offending prompt/response, tighten input/output filtering, and record the evidence.",
    ],
    explainTitle: i.title, explainKind: "ai-incident governance owasp severity", explainContext: { incident: i },
  });
  const openAgentRisk = () => setDetail({
    refLabel: "AI-AGENTS", title: "AI agent risk distribution", rating: riskDist.find((r) => r.name === "Critical" && r.value > 0) ? "Critical" : riskDist.find((r) => r.name === "High" && r.value > 0) ? "High" : "Medium",
    facets: [
      { icon: Bot, label: "Registered agents", value: agentTotal || "—" },
      { icon: ShieldAlert, label: "Distribution", value: riskDist.map((r) => `${r.name}:${r.value}`).join(" · ") || "—" },
    ],
    recommendedActions: [
      "Bring highest-risk agents under a blocking guardrail set (input/output filtering + tool allow-list).",
      "Require human-in-loop for any agent with write/tool access to production systems.",
    ],
    explainTitle: "AI agent risk posture", explainKind: "ai-agent risk guardrail governance", explainContext: { risk_dist: an?.agents?.risk_dist, guardrails: guardCov, total: agentTotal },
  });
  const openGuardrails = () => setDetail({
    refLabel: "GUARDRAILS", title: "Guardrail coverage", rating: agentTotal && (guardCov.human_in_loop || 0) / agentTotal < 0.5 ? "High" : "Medium",
    facets: Object.keys(GUARD_LABEL).map((g) => ({ icon: ShieldCheck, label: GUARD_LABEL[g], value: `${guardCov[g] || 0}/${agentTotal}` })),
    recommendedActions: [
      "Close the weakest guardrail first — aim for 100% input/output filtering across all agents.",
      "Add tool allow-lists and human-in-loop to any agent that can call external tools.",
    ],
    explainTitle: "Guardrail coverage", explainKind: "guardrail coverage ai governance", explainContext: { guardrails: guardCov, total: agentTotal },
  });

  const LicTile = ({ icon: Icon, label, on, metric, unit, sub, testid }) => (
    <div data-testid={testid} className={`rounded-lg p-4 border ${on ? "border-ai/30 bg-ai/5" : "border-border bg-secondary/30"}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-sm font-head font-bold"><Icon className="w-4 h-4 text-ai" /> {label}</div>
        <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full ${on ? "bg-low/15 text-low" : "bg-secondary/60 text-muted-foreground"}`}>{on ? "LIVE" : "NOT CONNECTED"}</span>
      </div>
      <div className="font-head font-black text-2xl tracking-tight">{on && metric != null ? metric.toLocaleString() : "—"} <span className="text-xs font-mono font-normal text-muted-foreground">{on && metric != null ? unit : ""}</span></div>
      <div className="text-[11px] text-muted-foreground mt-1">{on ? (sub || "Connected") : `Connect in Available Connectors to govern ${label} licenses.`}</div>
    </div>
  );

  return (
    <div className="rise space-y-5" data-testid="ai-governance-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2" style={{ color: `hsl(${ACCENT})` }}><Bot className="w-7 h-7" strokeWidth={1.5} /> AI Governance Suite</h1>
        <p className="text-sm text-muted-foreground mt-1">{isExec ? "AI governance posture — usage analytics, sanctioned vs shadow AI, guardrail coverage & OWASP-LLM exposure. Click any card for the deep-dive." : "Live AI usage analytics, NIST AI RMF mapping, model cards, evaluations, guardrails & incidents. Click any card for the AI deep-dive."}</p>
      </div>

      {/* Usage analytics KPIs — always present */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard testid="aig-kpi-queries" label="AI queries" value={(t.queries ?? 0).toLocaleString()} accent={ACCENT} sub="advisor telemetry" />
        <StatCard testid="aig-kpi-tokens" label="Tokens" value={(t.tokens ?? 0).toLocaleString()} accent={ACCENT} sub="processed" />
        <StatCard testid="aig-kpi-cost" label="AI spend" value={`$${(t.cost ?? 0).toFixed(2)}`} accent="35 90% 55%" sub="estimated" />
        <StatCard testid="aig-kpi-models" label="Models" value={t.models ?? 0} accent={ACCENT} sub="in use" />
        <StatCard testid="aig-kpi-systems" label="AI systems" value={an?.systems?.total ?? systems.length} accent={ACCENT} sub={`${an?.systems?.sanctioned ?? 0} sanctioned`} />
        <StatCard testid="aig-kpi-shadow" label="Shadow AI" value={an?.systems?.shadow ?? shadow.length} accent="0 84% 60%" sub="unsanctioned" />
      </div>

      <AIInsight dashboard="AI Governance" accent={ACCENT} auto />

      {/* Usage trend + model breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <CardShell testid="aig-usage-trend" title="AI usage trend (14 days)" icon={Activity} accent={ACCENT}>
            {trend.length === 0 ? (
              <EmptyState icon={Activity} text="No AI usage recorded yet. Ask the Advisor a question or run an AI Insight and daily usage will stream in here." />
            ) : (
              <ChartBox height={200}>
                <AreaChart data={trend} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                  <defs><linearGradient id="aigq" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={`hsl(${ACCENT})`} stopOpacity={0.35} /><stop offset="100%" stopColor={`hsl(${ACCENT})`} stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#94a3b8" }} tickFormatter={(v) => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 9, fill: "#94a3b8" }} />
                  <Tooltip contentStyle={{ background: "#0A0E17", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 }} />
                  <Area type="monotone" dataKey="queries" name="Queries" stroke={`hsl(${ACCENT})`} strokeWidth={2.5} fill="url(#aigq)" />
                </AreaChart>
              </ChartBox>
            )}
          </CardShell>
        </div>
        <CardShell testid="aig-by-model" title="Queries by model" icon={Cpu} accent={ACCENT}>
          <BarList items={byModel} accent={ACCENT} empty="No model usage yet." />
        </CardShell>
      </div>

      {/* Agent risk + guardrails + OWASP — clickable deep-dives */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <CardShell testid="aig-risk-dist" title="AI agent risk distribution" icon={ShieldAlert} accent={ACCENT}
          right={agentTotal > 0 && <button data-testid="aig-risk-dist-dd" onClick={openAgentRisk} className="text-[10px] font-mono text-ai hover:underline">Deep-dive →</button>}>
          <div onClick={() => agentTotal > 0 && openAgentRisk()} className={agentTotal > 0 ? "cursor-pointer" : ""}>
            <BarList items={riskDist} accent={ACCENT} empty="No AI agents registered yet — register agents to classify risk." />
          </div>
        </CardShell>
        <CardShell testid="aig-guardrails" title="Guardrail coverage" icon={ShieldCheck} accent={ACCENT}
          right={agentTotal > 0 && <button data-testid="aig-guardrails-dd" onClick={openGuardrails} className="text-[10px] font-mono text-ai hover:underline">Deep-dive →</button>}>
          {agentTotal === 0 ? <EmptyState icon={ShieldCheck} text="No agents yet — guardrail coverage appears once AI agents are registered." /> : (
            <div className="space-y-3 cursor-pointer" onClick={openGuardrails}>
              {Object.keys(GUARD_LABEL).map((g) => {
                const n = guardCov[g] || 0; const pct = Math.round((n / agentTotal) * 100);
                return (
                  <div key={g} data-testid={`guard-${g}`}>
                    <div className="flex justify-between text-xs mb-1"><span>{GUARD_LABEL[g]}</span><span className="font-mono text-muted-foreground">{n}/{agentTotal}</span></div>
                    <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${pct}%`, background: `hsl(${pct >= 60 ? "142 70% 45%" : pct >= 30 ? "35 90% 55%" : "0 84% 60%"})` }} /></div>
                  </div>
                );
              })}
            </div>
          )}
        </CardShell>
        <CardShell testid="aig-owasp" title="OWASP LLM Top 10 coverage" icon={Layers} accent={ACCENT}>
          <div className="grid grid-cols-1 gap-1.5 max-h-64 overflow-y-auto pr-1">
            {(an?.owasp_llm || []).map((o) => (
              <div key={o.code} data-testid={`owasp-${o.code}`} onClick={() => openOwasp(o)}
                className="flex items-center justify-between gap-2 text-xs bg-secondary/30 hover:bg-secondary/60 rounded-md px-2.5 py-1.5 cursor-pointer transition-colors">
                <span className="truncate"><span className="font-mono text-muted-foreground">{o.code}</span> {o.name}</span>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.5 rounded-sm shrink-0" style={{ background: `hsl(${OWASP_COL[o.status]} / 0.15)`, color: `hsl(${OWASP_COL[o.status]})` }}>{o.status}</span>
              </div>
            ))}
            {(!an?.owasp_llm || an.owasp_llm.length === 0) && <EmptyState text="OWASP-LLM mapping loads with your AI inventory." />}
          </div>
        </CardShell>
      </div>

      <AIMonitor guardCov={guardCov} agentTotal={agentTotal} sanctioned={an?.systems?.sanctioned || 0} systems={an?.systems?.total || systems.length} shadow={an?.systems?.shadow ?? shadow.length} accent={ACCENT} />

      {live && (
        <CardShell testid="ai-licenses-card" title="AI Licenses & Copilot Governance" icon={ShieldCheck} accent={ACCENT}>
          <p className="text-[11px] text-muted-foreground mb-3 -mt-2">Licensed AI seats and models pulled from your connected tenants. {anyLicensed ? "" : "Connect Microsoft Copilot or ChatGPT to populate this."}</p>
          <div className="grid sm:grid-cols-3 gap-3">
            <LicTile icon={Bot} label="Microsoft Copilot" on={!!copilot?.live} metric={copilot?.seats} unit="seats licensed" sub={copilot?.seats != null ? `${copilot.seats} Copilot seats licensed` : "Connected — seats pending sync"} testid="lic-copilot" />
            <LicTile icon={Sparkles} label="ChatGPT (OpenAI)" on={!!openai?.live} metric={openai?.model_count} unit="models available" sub={openai?.model_count != null ? `${openai.model_count} models available to govern` : "Connected — models pending sync"} testid="lic-openai" />
            <LicTile icon={Cloud} label="Microsoft 365" on={!!m365?.live} metric={m365?.user_count} unit="licensed users" sub={m365?.risky_users != null ? `${m365.risky_users} risky user(s) flagged` : "Connected — users pending sync"} testid="lic-m365" />
          </div>
        </CardShell>
      )}

      {shadow.length > 0 && (
        <div className="ai-border rounded-lg p-4 flex items-center gap-3 bg-ai/5">
          <Eye className="w-5 h-5 text-ai" />
          <div className="flex-1 text-sm"><span className="font-semibold text-ai">{shadow.length} shadow AI</span> tool(s) discovered processing organizational data — governance action required.</div>
        </div>
      )}

      <Tabs defaultValue="inventory">
        <TabsList className="bg-card">
          <TabsTrigger value="inventory" data-testid="tab-inventory">Inventory & Model Cards</TabsTrigger>
          <TabsTrigger value="incidents" data-testid="tab-incidents">AI Incidents</TabsTrigger>
        </TabsList>

        <TabsContent value="inventory" className="mt-4">
          <div className="grid md:grid-cols-2 gap-4">
            {systems.map((s) => (
              <div key={s.ref} data-testid={`ai-system-${s.ref}`} onClick={() => setSelected(s)}
                className={`rounded-lg p-5 cursor-pointer hover:-translate-y-0.5 transition-transform duration-200 ${s.status === "shadow" ? "ai-border" : "bg-card fact-border"}`}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2"><Cpu className="w-4 h-4 text-muted-foreground" /><span className="font-head font-bold">{s.name}</span></div>
                    <div className="text-[11px] font-mono text-muted-foreground mt-1">{s.ref} · {s.type} · {s.provider}</div>
                  </div>
                  <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${riskClassColor[s.risk_class]} / 0.15)`, color: `hsl(${riskClassColor[s.risk_class]})` }}>{s.risk_class}</span>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground mb-3">
                  <span>Use case: <span className="text-foreground">{s.use_case}</span></span>
                  <span>NIST: <span className="text-foreground">{s.nist_profile}</span></span>
                  <span>Owner: <span className="text-foreground">{s.owner}</span></span>
                </div>
                {s.status === "shadow" ? (
                  isExec
                    ? <div className="w-full py-2 rounded-md bg-ai/10 border border-ai/30 text-ai font-head font-bold text-sm text-center">Governance decision required</div>
                    : <button data-testid={`sanction-${s.ref}`} onClick={(e) => { e.stopPropagation(); sanction(s.ref); }} className="w-full py-2 rounded-md bg-ai text-background font-head font-bold text-sm hover:opacity-90 transition-opacity">Bring under governance</button>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <EvalBar label="Bias" value={s.eval.bias} /><EvalBar label="Safety" value={s.eval.safety} />
                      <EvalBar label="Security" value={s.eval.security} /><EvalBar label="Explainability" value={s.eval.explainability} />
                    </div>
                    <div className="flex items-center justify-between pt-3 border-t border-border">
                      <div className="flex items-center gap-3">
                        <span className={`text-[10px] font-mono uppercase ${s.drift === "warning" ? "text-high" : "text-low"}`}>Drift: {s.drift}</span>
                        <span className="text-[10px] font-mono text-muted-foreground">Halluc: {s.hallucination_rate ?? "—"}%</span>
                      </div>
                      <ConfidenceBadge value={s.confidence} />
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="incidents" className="mt-4 space-y-3">
          {incidents.length === 0 && <EmptyState icon={AlertOctagon} text="No AI incidents — governance monitors sanctioned systems continuously." />}
          {incidents.map((i) => (
            <div key={i.ref} data-testid={`incident-${i.ref}`} onClick={() => openIncident(i)}
              className="bg-card fact-border rounded-lg p-4 flex items-center gap-4 cursor-pointer hover:bg-secondary/40 transition-colors">
              {i.severity === "Critical" ? <Ban className="w-5 h-5 text-crit" /> : <AlertOctagon className="w-5 h-5 text-high" />}
              <div className="flex-1">
                <div className="font-medium text-sm">{i.title}</div>
                <div className="text-[11px] font-mono text-muted-foreground">{i.ref} · {i.system} · governance mode: <span className="text-ai">{i.mode}</span></div>
              </div>
              <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${riskClassColor[i.severity]} / 0.15)`, color: `hsl(${riskClassColor[i.severity]})` }}>{i.severity}</span>
              <span className="text-xs px-2.5 py-1 rounded-md bg-secondary/60">{i.status}</span>
            </div>
          ))}
        </TabsContent>
      </Tabs>

      <AISystemModal system={selected} onClose={() => setSelected(null)} onChanged={load} />
      <RiskDetailModal item={detail} accent={ACCENT} onClose={() => setDetail(null)} />
    </div>
  );
}
