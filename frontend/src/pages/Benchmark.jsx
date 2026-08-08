import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ChartBox } from "@/components/ChartBox";
import { ComposedChart, Area, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { BarChart3, Loader2, TrendingUp, DollarSign, Building2, Gauge } from "lucide-react";
import { RiskDetailModal } from "@/components/RiskDetailModal";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const fmtM = (v) => v == null ? "—" : "$" + (v / 1e6).toFixed(2) + "M";
const CHART_TT = { background: "hsl(215 38% 10%)", border: "1px solid hsl(215 30% 18%)", borderRadius: 8, fontSize: 12 };
const ACCENT = "190 90% 50%";

export default function Benchmark() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [cfg, setCfg] = useState(null);
  const [basis, setBasis] = useState(null);
  const [trend, setTrend] = useState(null);
  const [peer, setPeer] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deep, setDeep] = useState(null);

  const load = () => Promise.all([
    api.get("/financial/config"),
    api.get("/financial/basis"),
    api.get("/financial/benchmark-trend"),
    api.get("/benchmark").catch(() => ({ data: null })),
  ]).then(([c, b, t, p]) => { setCfg(c.data); setBasis(b.data); setTrend(t.data); setPeer(p.data); });

  useEffect(() => { load(); }, []);

  const changeIndustry = async (industry) => {
    setSaving(true);
    try { await api.put("/financial/config", { industry }); toast.success(`Benchmarks set to ${industry}`); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not change industry"); }
    setSaving(false);
  };

  if (!cfg || !basis) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  const bench = basis.benchmark || {};
  const industry = cfg.config?.industry || bench.industry;
  const modelled = basis.modelled_avg_sle;
  const ratio = basis.benchmark_ratio;
  const cards = [
    { k: "industry", label: `${bench.industry || industry} avg breach`, value: fmtM(bench.industry_avg), raw: bench.industry_avg, src: "IBM Cost of a Data Breach — industry table", accent: "35 90% 55%" },
    { k: "global", label: "Global avg breach", value: fmtM(bench.global_avg), raw: bench.global_avg, src: "IBM 2026 — global average", accent: "190 90% 50%" },
    { k: "ai", label: "AI-enabled breach avg", value: fmtM(bench.ai_breach_avg), raw: bench.ai_breach_avg, src: "IBM 2026 — AI-enabled", accent: "266 85% 66%" },
    { k: "shadow", label: "Shadow-AI cost premium", value: fmtM(bench.shadow_ai_premium), raw: bench.shadow_ai_premium, src: "IBM 2025 — shadow-AI premium", accent: "0 84% 60%" },
    { k: "ransom", label: "Ransomware median loss", value: fmtM(bench.dbir_ransomware_median), raw: bench.dbir_ransomware_median, src: "Verizon DBIR 2025", accent: "15 80% 55%" },
    { k: "modelled", label: "Your modelled avg / incident", value: fmtM(modelled), raw: modelled, src: ratio != null ? `${ratio}× vs industry avg` : "modelled from your risks", accent: "142 70% 45%" },
  ];
  const trendPts = trend?.points || [];

  const openBench = (c) => {
    const above = c.raw != null && modelled != null && modelled > c.raw;
    setDeep({
      refLabel: "BENCHMARK", title: c.label,
      rating: c.k === "modelled" ? (ratio >= 1 ? "High" : ratio >= 0.7 ? "Medium" : "Low") : undefined,
      score: c.k === "modelled" && ratio != null ? Math.min(100, Math.round(ratio * 60)) : undefined,
      ale: c.raw,
      facets: [
        { icon: DollarSign, label: "Figure", value: c.value },
        { icon: Building2, label: "Source", value: c.src },
        { icon: Gauge, label: "Your modelled avg / incident", value: fmtM(modelled) },
        { icon: TrendingUp, label: "Position", value: ratio != null ? `${ratio}× vs ${industry} avg` : "—" },
      ],
      recommendedActions: c.k === "modelled"
        ? [ratio >= 1
            ? `Your modelled per-incident exposure (${fmtM(modelled)}) is ${ratio}× the ${industry} average — prioritise controls that cut breach likelihood/impact (MFA everywhere, EDR coverage, backup immutability) to pull the ratio below 1×.`
            : `Your modelled exposure (${fmtM(modelled)}) sits below the ${industry} average (${ratio}×) — sustain controls and keep the financial basis CRO-signed.`]
        : [above
            ? `Your modelled avg/incident (${fmtM(modelled)}) exceeds this ${c.label.toLowerCase()} — treat it as the floor for your board loss scenarios and fund reduction where ROI is highest.`
            : `Your modelled avg/incident (${fmtM(modelled)}) is below this published figure — use it to sanity-check that your FAIR inputs aren't understated.`],
      explainTitle: c.label, explainKind: "benchmark breach-cost industry comparison financial-basis",
      explainContext: { metric: c, modelled_avg_sle: modelled, benchmark_ratio: ratio, industry, benchmark: bench },
    });
  };

  const openPeer = (m) => setDeep({
    refLabel: "PEER", title: m.name,
    rating: m.percentile >= 75 ? "Low" : m.percentile >= 50 ? "Medium" : "High",
    score: m.you,
    facets: [
      { icon: Gauge, label: "You", value: m.you },
      { icon: Building2, label: "Peer median", value: m.peer_median },
      { icon: TrendingUp, label: "Top quartile", value: m.top_quartile },
      { icon: BarChart3, label: "Percentile", value: `${m.percentile}th` },
    ],
    recommendedActions: [
      m.you >= m.top_quartile
        ? `${m.name}: you're at/above the top quartile — sustain and use as a board proof-point.`
        : `${m.name}: close the gap to the top quartile (${m.top_quartile}) — this is where peers in ${peer?.peer_set || "your set"} concentrate investment.`,
    ],
    explainTitle: `Peer posture — ${m.name}`, explainKind: "peer benchmark posture percentile", explainContext: { metric: m, peer_set: peer?.peer_set },
  });

  return (
    <div className="rise space-y-6" data-testid="benchmark-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><BarChart3 className="w-7 h-7 text-primary" /> Peer Benchmarking</h1>
          <p className="text-sm text-muted-foreground mt-1">Your modelled exposure vs. published breach-cost figures for <span className="text-foreground">{industry}</span>. Click any card for the AI deep-dive — rating, position vs your model &amp; a grounded recommendation.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Industry</span>
          {isAdmin ? (
            <Select value={industry} onValueChange={changeIndustry} disabled={saving}>
              <SelectTrigger data-testid="benchmark-industry-select" className="w-56 bg-card"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(cfg.industries || []).map((i) => <SelectItem key={i} value={i}>{i}</SelectItem>)}
              </SelectContent>
            </Select>
          ) : (
            <span data-testid="benchmark-industry-static" className="text-sm font-medium px-3 py-1.5 rounded-md bg-secondary/60">{industry}</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4" data-testid="benchmark-cards">
        {cards.map((c) => (
          <button key={c.k} type="button" data-testid={`benchmark-card-${c.k}`} onClick={() => openBench(c)}
            className="text-left bg-card fact-border rounded-xl p-5 hover:-translate-y-0.5 hover:border-ai/40 transition-all duration-200">
            <div className="text-xs text-muted-foreground mb-1">{c.label}</div>
            <div className="font-head font-black text-2xl lg:text-3xl tracking-tight" style={{ color: `hsl(${c.accent})` }}>{c.value}</div>
            <div className="text-[10px] font-mono text-muted-foreground mt-1">{c.src}</div>
            <div className="text-[10px] text-ai mt-1">Click for AI insight &amp; recommendation</div>
          </button>
        ))}
      </div>

      <div className="bg-card fact-border rounded-xl p-6" data-testid="benchmark-trend">
        <div className="flex items-center justify-between mb-1">
          <h2 className="font-head font-bold text-lg flex items-center gap-2"><TrendingUp className="w-4 h-4 text-ai" /> Exposure vs Industry — trend</h2>
          <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full border ${trend?.real ? "bg-low/15 text-low border-low/30" : "bg-secondary/60 text-muted-foreground border-border"}`}>{trend?.real ? "LIVE" : "MODELED"}</span>
        </div>
        <p className="text-[11px] text-muted-foreground mb-3">Modelled per-incident exposure against the {industry} benchmark and an estimated 25th–75th percentile peer band.</p>
        {trendPts.length ? (
          <ChartBox height={240}>
            <ComposedChart data={trendPts}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 30% 18%)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis width={48} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${Math.round(v / 1e6)}M`} />
              <Tooltip contentStyle={CHART_TT} formatter={(v) => fmtM(v)} />
              <Area dataKey="peerBase" stackId="peer" stroke="none" fill="transparent" />
              <Area dataKey="peerSpan" stackId="peer" stroke="none" fill="hsl(190 90% 50% / 0.08)" name="Peer band" />
              <Line type="monotone" dataKey="benchmark" stroke="hsl(35 90% 55%)" strokeWidth={2} dot={false} name="Industry avg" />
              <Line type="monotone" dataKey="modelled" stroke="hsl(190 90% 50%)" strokeWidth={2.5} dot={{ r: 3, fill: "hsl(190 90% 50%)" }} name="Your modelled" />
            </ComposedChart>
          </ChartBox>
        ) : <div className="text-sm text-muted-foreground py-12 text-center">Run a live scan to build your exposure trend.</div>}
        <div className="flex flex-wrap gap-4 mt-2 text-[10px] font-mono text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-ai inline-block" /> Your modelled</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 inline-block" style={{ background: "hsl(35 90% 55%)" }} /> Industry avg</span>
          <span className="flex items-center gap-1"><span className="w-3 h-2 inline-block rounded-sm" style={{ background: "hsl(190 90% 50% / 0.2)" }} /> Peer band</span>
        </div>
      </div>

      {peer?.metrics?.length > 0 && (
        <div className="space-y-4" data-testid="benchmark-peer">
          <h2 className="font-head font-bold text-lg">Posture vs. {peer.peer_set} peers</h2>
          {peer.metrics.map((m) => (
            <button key={m.name} type="button" data-testid={`benchmark-peer-${m.name.replace(/\s+/g, "-").toLowerCase()}`} onClick={() => openPeer(m)}
              className="w-full text-left bg-card fact-border rounded-xl p-5 hover:border-ai/40 transition-colors">
              <div className="flex items-center justify-between mb-3">
                <div className="font-head font-bold text-sm">{m.name}</div>
                <div className="text-xs font-mono text-muted-foreground">{m.percentile}th percentile · <span className="text-ai">deep-dive →</span></div>
              </div>
              <div className="relative h-8 bg-secondary/50 rounded-md overflow-hidden">
                <div className="absolute top-0 bottom-0 w-px bg-muted-foreground/60" style={{ left: `${m.peer_median}%` }} title={`Peer median ${m.peer_median}`} />
                <div className="absolute top-0 bottom-0 w-px bg-low/70" style={{ left: `${m.top_quartile}%` }} title={`Top quartile ${m.top_quartile}`} />
                <div className="h-full rounded-md flex items-center justify-end pr-2" style={{ width: `${m.you}%`, background: "linear-gradient(90deg, hsl(var(--ai) / 0.4), hsl(var(--ai) / 0.75))" }}>
                  <span className="text-xs font-head font-bold text-white">{m.you}</span>
                </div>
              </div>
              <div className="flex gap-4 mt-2 text-[10px] font-mono text-muted-foreground">
                <span>You: {m.you}</span><span>Peer median: {m.peer_median}</span><span className="text-low">Top quartile: {m.top_quartile}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      <p className="text-[11px] text-muted-foreground" data-testid="benchmark-source">Source: {bench.source} · Updated {bench.updated}. These are published industry figures used to benchmark your modelled exposure — decision-support, not guarantees.</p>

      <RiskDetailModal item={deep} accent={ACCENT} onClose={() => setDeep(null)} />
    </div>
  );
}
