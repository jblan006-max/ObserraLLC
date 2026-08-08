import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ShieldAlert, Loader2, Layers, PlayCircle, Gauge, ShieldCheck, TrendingDown, Calculator, BarChart3, Building2, RefreshCw, Sparkles, FileText, Clock, Target, Activity, BookOpen } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ComposedChart, Area, BarChart, Bar } from "recharts";

const TIER = (residual) => residual >= 16 ? "0 84% 60%" : residual >= 9 ? "35 90% 55%" : "142 70% 45%";

function Stat({ label, value, unit, icon: Icon, accent }) {
  return (
    <div className="bg-card fact-border rounded-xl p-4" style={accent ? { borderLeft: `3px solid hsl(${accent})` } : {}}>
      <div className="text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1.5">
        {Icon && <Icon className="w-3.5 h-3.5" />} {label}
      </div>
      <div className="font-head font-black text-3xl mt-1">{value}{unit}</div>
    </div>
  );
}

export default function CyberRisk() {
  const { user, mode } = useAuth();
  const isAdmin = user?.role === "admin";
  const isExec = mode === "executive";
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");

  const load = () => api.get("/cyber/overview").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);

  const treat = async (ref) => {
    setBusy(ref);
    try { await api.post(`/cyber/risks/${ref}/treat`); toast.success(`Treatment workflow opened for ${ref}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Treat failed"); }
    setBusy("");
  };

  if (!data) return <div className="flex items-center justify-center h-96" data-testid="cyber-loading"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6" data-testid="cyber-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><ShieldAlert className="w-7 h-7 text-primary" /> Risk</h1>
        <p className="text-sm text-muted-foreground mt-1">{isExec ? "Strategic risk posture — FAIR-quantified business exposure and mitigation at a glance." : "Control-centric risk posture — a kernel-native app composed on the Obserra kernel."}</p>
        <div data-testid="cyber-composition" className="flex flex-wrap items-center gap-2 mt-3">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Layers className="w-3.5 h-3.5" /> Composed on:</span>
          {data.composition.map((c) => <span key={c} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{c}</span>)}
          {data.live_m365_users != null && <span data-testid="cyber-m365-live" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/15 text-low border border-low/30">M365 LIVE · {data.live_m365_users} users{data.live_m365_risky != null ? ` · ${data.live_m365_risky} risky` : ""}</span>}
          {data.live_risk_penalty > 0 && <span data-testid="cyber-risk-penalty" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-high/15 text-high border border-high/30">−{data.live_risk_penalty} posture (live signal)</span>}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Posture score" value={data.posture_score} unit="" icon={Gauge} accent="142 70% 45%" />
        <Stat label="Risk mitigation" value={data.mitigation_pct} unit="%" icon={TrendingDown} />
        <Stat label="Control coverage" value={data.control_coverage} unit="%" icon={ShieldCheck} />
        <Stat label="Open risks" value={`${data.open_risks}/${data.total_risks}`} unit="" icon={ShieldAlert} accent="0 84% 60%" />
      </div>

      <div className="bg-card fact-border rounded-xl overflow-x-auto" data-testid="cyber-top-risks">
        <div className="px-4 py-3 border-b border-border text-xs font-mono uppercase tracking-wider text-muted-foreground">Top residual cyber risks</div>
        <table className="w-full text-sm min-w-[720px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3">Risk</th><th className="text-left px-4 py-3">Owner</th><th className="text-left px-4 py-3">Status</th><th className="text-left px-4 py-3">Residual</th><th className="text-right px-4 py-3">Action</th></tr>
          </thead>
          <tbody>
            {data.risks.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No cyber risks recorded.</td></tr>
            ) : data.risks.map((r) => (
              <tr key={r.ref} data-testid={`cyber-risk-${r.ref}`} className="border-b border-border/60 hover:bg-secondary/40 transition-colors">
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{r.ref}</div><div className="font-medium">{r.title}</div></td>
                <td className="px-4 py-3 text-muted-foreground">{r.owner || "—"}</td>
                <td className="px-4 py-3">{r.status}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${TIER(r.residual)} / 0.15)`, color: `hsl(${TIER(r.residual)})` }}>{r.residual}/25</span></td>
                <td className="px-4 py-3 text-right">
                  {isAdmin && !isExec ? <button data-testid={`treat-${r.ref}`} disabled={!!busy} onClick={() => treat(r.ref)} className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 disabled:opacity-50">{busy === r.ref ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />} Treat</button> : <span className="text-[11px] text-muted-foreground">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">Treating a risk opens a remediation workflow and alerts owners — proving the kernel loop.</p>

      <FairDashboard />
      <FinancialBasis isAdmin={isAdmin} />
    </div>
  );
}

function Kpi({ label, value, sub, accent }) {
  return (
    <div className="rounded-lg bg-secondary/40 p-3" style={accent ? { borderLeft: `3px solid hsl(${accent})` } : {}}>
      <div className="text-[10px] font-mono uppercase text-muted-foreground">{label}</div>
      <div className="font-head font-black text-2xl">{value}</div>
      <div className="text-[10px] text-muted-foreground">{sub}</div>
    </div>
  );
}

const DRIVER_COLOR = { "Loss magnitude": "0 84% 60%", "Threat frequency": "35 90% 55%", "Control weakness": "190 90% 50%" };
const DRIVER_WHY = {
  "Loss magnitude": "driven by the high single-loss cost — mitigation that lowers impact/records exposed cuts $ most",
  "Threat frequency": "driven by how often the event is expected — reducing occurrence rate cuts $ most",
  "Control weakness": "driven by weak residual controls — strengthening controls cuts exposure most",
};

function FairDashboard() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/financial/fair").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return null;
  const fmt = (n) => n == null ? "—" : n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : `$${(n / 1e3).toFixed(0)}k`;
  const p = d.portfolio;
  const k = d.kpis || {};
  const dc = (name) => DRIVER_COLOR[name] || "215 15% 55%";
  return (
    <div className="bg-card fact-border rounded-xl p-5 space-y-5" data-testid="fair-dashboard">
      <div className="flex flex-wrap items-center gap-2">
        <Target className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">FAIR risk quantification</h2>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-secondary text-muted-foreground">Factor Analysis of Information Risk</span>
      </div>
      <div className="rounded-lg bg-ai/5 border border-ai/20 p-3 space-y-1.5" data-testid="fair-formula">
        <div className="text-[10px] font-mono uppercase text-muted-foreground">How this is calculated (FAIR)</div>
        <div className="font-mono text-sm text-foreground">ALE = Loss Magnitude (LM) × Loss Event Frequency (LEF)</div>
        <div className="font-mono text-sm text-foreground">LEF = Threat Event Frequency (TEF) × Vulnerability</div>
        <div className="text-[10px] text-muted-foreground leading-relaxed">
          <b>LM</b> = $ cost of a single loss event (your configured SLE / per-record model). <b>TEF</b> = how often the threat acts (likelihood ÷ 5).
          <b> Vulnerability</b> = residual ÷ inherent (control weakness). <b>ALE</b> = expected annual loss; the P10–P90 band comes from a 2,000+ iteration Monte-Carlo over these factors.
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="fair-kpis">
        <Kpi label="$ at Risk (residual ALE)" value={fmt(k.dollars_at_risk)} sub={`down ${k.reduction_pct}% from inherent ${fmt(p.inherent_ale)}`} accent="0 84% 60%" />
        <Kpi label="Worst case (P90)" value={fmt(k.worst_case_p90)} sub="10% adverse-case scenario" />
        <Kpi label="Remediation ROI" value={`${k.remediation_roi}×`} sub={`retire ${fmt(k.remediation_reduction)} for ~${fmt(k.remediation_cost)}`} accent="150 60% 45%" />
        <Kpi label="Accepted (carried)" value={fmt(k.accepted_exposure)} sub={`${d.acceptance.count} open risks unremediated`} />
      </div>
      {d.deductions?.length > 0 && (
        <div className="rounded-lg border border-ai/20 bg-ai/5 p-3" data-testid="fair-deductions">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><Sparkles className="w-3.5 h-3.5 text-ai" /> FAIR-based deductions</div>
          <ul className="space-y-1.5">
            {d.deductions.map((t, i) => (
              <li key={i} data-testid={`fair-deduction-${i}`} className="text-xs flex gap-2"><span className="text-ai mt-0.5">▸</span><span>{t}</span></li>
            ))}
          </ul>
        </div>
      )}
      {d.kpi_references?.length > 0 && (
        <details className="rounded-lg border border-border p-3" data-testid="fair-kpi-refs">
          <summary className="text-[10px] font-mono uppercase text-muted-foreground cursor-pointer flex items-center gap-1"><BookOpen className="w-3.5 h-3.5" /> Why these KPIs — board benchmarks (Gartner · NACD · FAIR · WEF)</summary>
          <ul className="mt-3 space-y-2.5">
            {d.kpi_references.map((r, i) => (
              <li key={i} data-testid={`fair-kpi-ref-${i}`} className="text-[11px]">
                <div className="font-semibold text-foreground">{r.kpi} — <span className="text-ai">{r.source}</span></div>
                <div className="text-muted-foreground">{r.why} <a href={r.url} target="_blank" rel="noreferrer" className="text-ai underline whitespace-nowrap">source ↗</a></div>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div>
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Exposure by area · FAIR breakdown</div>
        <div className="grid md:grid-cols-2 gap-3" data-testid="fair-by-area">
          {d.by_area.map((a) => (
            <div key={a.area} data-testid={`fair-area-${a.area}`} className="rounded-lg border border-border p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="font-head font-bold text-sm">{a.area}</div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm shrink-0" style={{ background: `hsl(${dc(a.dominant_driver)} / 0.15)`, color: `hsl(${dc(a.dominant_driver)})` }}>{a.dominant_driver}</span>
              </div>
              <div className="flex items-end justify-between">
                <div><div className="font-head font-black text-xl">{fmt(a.residual_ale)}</div><div className="text-[10px] text-muted-foreground">residual ALE · {a.share_pct}% of portfolio</div></div>
                <div className="text-right text-[10px] text-muted-foreground">{a.count} risk(s)<br />↓{a.reduction_pct}% vs inherent</div>
              </div>
              <div className="h-1.5 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${a.share_pct}%`, background: `hsl(${dc(a.dominant_driver)})` }} /></div>
              <div className="grid grid-cols-2 gap-2 text-[10px] text-muted-foreground">
                <div>Avg vulnerability <span className="text-foreground font-mono">{a.avg_vulnerability}</span></div>
                <div>Avg threat freq <span className="text-foreground font-mono">{a.avg_tef}</span></div>
              </div>
              {a.top_risk && <div className="text-[10px] text-muted-foreground truncate">Top: <span className="font-mono text-ai">{a.top_risk.ref}</span> {a.top_risk.title}</div>}
              <div className="text-[10px] text-muted-foreground"><span className="font-semibold text-foreground/80">Why:</span> {DRIVER_WHY[a.dominant_driver] || ""}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-border p-3" data-testid="fair-lec">
        <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><Activity className="w-3.5 h-3.5" /> Loss exceedance curve · probability annual loss ≥ $X</div>
        <ResponsiveContainer width="100%" height={190}>
          <ComposedChart data={d.loss_exceedance}>
            <XAxis dataKey="loss" type="number" tickFormatter={(v) => `$${(v / 1e6).toFixed(1)}M`} tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" />
            <YAxis dataKey="exceedance_pct" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" width={40} domain={[0, 100]} />
            <Tooltip formatter={(v) => `${v}% chance`} labelFormatter={(v) => `Annual loss ≥ $${(v / 1e6).toFixed(2)}M`} contentStyle={{ background: "hsl(222 18% 12%)", border: "1px solid hsl(222 12% 22%)", fontSize: 11 }} />
            <Area type="monotone" dataKey="exceedance_pct" stroke="hsl(0 84% 60%)" fill="hsl(0 84% 60% / 0.15)" strokeWidth={2} name="Exceedance" />
          </ComposedChart>
        </ResponsiveContainer>
        <div className="text-[10px] text-muted-foreground">Y-axis = probability the annual loss meets or exceeds the x-axis dollar amount (3,000-iteration Monte-Carlo over FAIR factors).</div>
      </div>
      <div className="rounded-lg border border-border overflow-x-auto" data-testid="fair-risk-table">
        <table className="w-full text-xs min-w-[780px]">
          <thead className="text-[10px] font-mono uppercase text-muted-foreground border-b border-border">
            <tr><th className="text-left px-3 py-2">Risk</th><th className="text-left px-3 py-2">Area</th><th className="text-right px-3 py-2">Loss mag.</th><th className="text-right px-3 py-2">TEF</th><th className="text-right px-3 py-2">Vuln</th><th className="text-right px-3 py-2">LEF</th><th className="text-right px-3 py-2">Residual ALE</th><th className="text-left px-3 py-2">Dominant driver</th></tr>
          </thead>
          <tbody>
            {d.risks.map((i) => (
              <tr key={i.ref} data-testid={`fair-row-${i.ref}`} className="border-b border-border/60">
                <td className="px-3 py-2"><div className="font-mono text-ai">{i.ref}</div><div className="truncate max-w-[170px]">{i.title}</div></td>
                <td className="px-3 py-2 text-muted-foreground">{i.category}</td>
                <td className="px-3 py-2 text-right">{fmt(i.loss_magnitude)}</td>
                <td className="px-3 py-2 text-right font-mono">{i.tef}</td>
                <td className="px-3 py-2 text-right font-mono">{i.vulnerability}</td>
                <td className="px-3 py-2 text-right font-mono">{i.lef}</td>
                <td className="px-3 py-2 text-right"><div className="font-bold">{fmt(i.residual_ale)}</div><div className="text-[10px] text-muted-foreground">P10 {fmt(i.p10)} · P90 {fmt(i.p90)}</div></td>
                <td className="px-3 py-2"><span className="text-[10px] font-mono px-2 py-0.5 rounded-sm" style={{ background: `hsl(${dc(i.driver)} / 0.15)`, color: `hsl(${dc(i.driver)})` }}>{i.driver}</span>{i.remediation_pending && <span className="ml-1 text-[10px] text-med">· fix pending</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-1" data-testid="fair-references">
        <p className="text-[11px] text-muted-foreground">FAIR: ALE = Loss Magnitude × Loss Event Frequency (LEF); LEF = Threat Event Frequency (TEF) × Vulnerability (control weakness = residual/inherent). Decision-support estimates, benchmarked against IBM {d.benchmark.industry} avg {fmt(d.benchmark.industry_avg)}.</p>
        {d.references?.length > 0 && (
          <div className="text-[10px] text-muted-foreground">
            <span className="font-mono uppercase tracking-wide">References</span>
            <ul className="list-disc pl-4 mt-0.5 space-y-0.5">{d.references.map((r, i) => <li key={i}>{r}</li>)}{d.benchmark.updated && <li>Benchmark table updated {d.benchmark.updated}</li>}</ul>
          </div>
        )}
      </div>
    </div>
  );
}

function FinancialBasis({ isAdmin }) {
  const [basis, setBasis] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [trend, setTrend] = useState(null);
  const [hist, setHist] = useState([]);
  const [packing, setPacking] = useState(false);
  const load = () => Promise.all([api.get("/financial/basis"), api.get("/financial/config"), api.get("/financial/benchmark-trend").catch(() => ({ data: { points: [] } })), api.get("/financial/signoff-history").catch(() => ({ data: { history: [] } }))])
    .then(([b, c, t, h]) => { setBasis(b.data); setCfg(c.data); setTrend(t.data); setHist(h.data.history || []); }).catch(() => {});
  useEffect(() => { load(); }, []);
  if (!basis || !cfg) return null;
  const fmt = (n) => n == null ? "—" : `$${(n / 1e6).toFixed(n < 1e6 ? 3 : 2)}M`;
  const bench = basis.benchmark;
  const ratio = basis.benchmark_ratio;
  const ratioColor = ratio == null ? "215 15% 55%" : ratio > 1.25 ? "0 84% 60%" : ratio < 0.75 ? "35 90% 55%" : "142 70% 45%";
  const save = async (patch) => {
    setSaving(true);
    try { const { data } = await api.put("/financial/config", patch); setCfg(data); await load(); toast.success("Financial model updated"); }
    catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
    setSaving(false);
  };
  const signOff = async () => { const name = window.prompt("CRO name to sign off this calibration:"); if (!name) return; try { await api.post("/financial/config/signoff", { name }); toast.success("Calibration locked & CRO-signed"); load(); } catch (e) { toast.error("Sign-off failed"); } };
  const unlock = async () => { try { await api.post("/financial/config/unlock"); toast.success("Calibration unlocked"); load(); } catch (e) { toast.error("Unlock failed"); } };
  const autofillRecords = () => { const s = cfg.suggested_records; if (s?.records) save({ method: "records", records: s.records }); };
  const boardPack = async () => {
    setPacking(true);
    try {
      const res = await api.post("/reports/board-pack.pdf", {}, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = "obserra-board-pack.pdf"; a.click();
      URL.revokeObjectURL(url);
      toast.success("Board pack downloaded");
    } catch (e) { toast.error("Could not build board pack"); }
    setPacking(false);
  };
  const so = cfg.config.signoff;
  return (
    <div className="bg-card fact-border rounded-xl p-5 space-y-5" data-testid="financial-basis">
      <div className="flex flex-wrap items-center gap-2"><Calculator className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Financial basis &amp; benchmark</h2><span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-secondary text-muted-foreground">defensible math</span>{basis.signoff?.locked && <span data-testid="fin-approved" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/15 text-low border border-low/30">✓ Approved by {basis.signoff.name} · {String(basis.signoff.at).slice(0, 10)}{basis.signoff.stale ? " (config changed since)" : ""}</span>}<button data-testid="board-pack-btn" onClick={boardPack} disabled={packing} className="ml-auto text-xs px-2.5 py-1 rounded-md bg-ai text-white flex items-center gap-1 disabled:opacity-60">{packing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />} Board pack PDF</button></div>

      <div className="grid sm:grid-cols-3 gap-3" data-testid="fin-benchmark">
        <div className="rounded-lg bg-secondary/40 p-3">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Your modelled per-incident</div>
          <div className="font-head font-black text-2xl">{fmt(basis.modelled_avg_sle)}</div>
          <div className="text-[10px] text-muted-foreground">avg SLE · max {fmt(basis.modelled_max_sle)}</div>
        </div>
        <div className="rounded-lg bg-secondary/40 p-3">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">{bench.industry} benchmark</div>
          <div className="font-head font-black text-2xl">{fmt(bench.industry_avg)}</div>
          <div className="text-[10px] text-muted-foreground">{bench.industry_avg_source}</div>
          <div className="text-[10px] text-muted-foreground">global {fmt(bench.global_avg)} · {bench.global_avg_source}</div>
        </div>
        <div className="rounded-lg p-3" style={{ background: `hsl(${ratioColor} / 0.12)` }} data-testid="fin-ratio">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Your model vs benchmark</div>
          <div className="font-head font-black text-2xl" style={{ color: `hsl(${ratioColor})` }}>{ratio == null ? "—" : `${ratio}×`}</div>
          <div className="text-[10px] text-muted-foreground">{ratio == null ? "" : ratio > 1.25 ? "above published avg" : ratio < 0.75 ? "below published avg" : "in line with published avg"}</div>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3" data-testid="fin-ai-cost">
        <div className="rounded-lg bg-med/5 border border-med/20 p-3">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">AI-enabled breach avg</div>
          <div className="font-head font-black text-2xl">{fmt(bench.ai_breach_avg)}</div>
          <div className="text-[10px] text-muted-foreground">{bench.ai_breach_source}</div>
        </div>
        <div className="rounded-lg bg-med/5 border border-med/20 p-3">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Shadow-AI cost premium</div>
          <div className="font-head font-black text-2xl">+{fmt(bench.shadow_ai_premium)}</div>
          <div className="text-[10px] text-muted-foreground">{bench.shadow_ai_source}</div>
        </div>
      </div>
      {basis.scenario && (
        <div className="rounded-lg bg-ai/5 border border-ai/20 p-3" data-testid="fin-scenario">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Board exposure range · Monte-Carlo (P10 – expected – P90)</div>
          <div className="font-head font-black text-xl mt-1">{fmt(basis.scenario.p10)} <span className="text-muted-foreground text-sm">low</span> · {fmt(basis.scenario.p50)} <span className="text-muted-foreground text-sm">expected</span> · {fmt(basis.scenario.p90)} <span className="text-muted-foreground text-sm">high</span></div>
          <div className="text-[10px] text-muted-foreground">2,000-iteration simulation over magnitude &amp; frequency uncertainty — shows the board a defensible band, not a single point.</div>
        </div>
      )}
      {basis.items?.length > 0 && (
        <div className="rounded-lg border border-border p-3" data-testid="fin-waterfall">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><BarChart3 className="w-3.5 h-3.5" /> Per-risk uncertainty · P10 → P90 band</div>
          <ResponsiveContainer width="100%" height={Math.max(170, basis.items.slice(0, 8).length * 34)}>
            <BarChart layout="vertical" data={basis.items.slice(0, 8).map((i) => ({ ref: i.ref, low: i.ale_low, span: Math.max(0, i.ale_high - i.ale_low), p10: i.ale_low, p50: i.ale_expected, p90: i.ale_high, title: i.title }))} margin={{ left: 4, right: 16 }}>
              <XAxis type="number" tickFormatter={(v) => `$${(v / 1e6).toFixed(1)}M`} tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" />
              <YAxis type="category" dataKey="ref" tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" width={64} />
              <Tooltip cursor={{ fill: "hsl(222 18% 18% / 0.4)" }} content={({ active, payload }) => (active && payload?.length) ? (
                <div className="rounded-md p-2 text-[11px]" style={{ background: "hsl(222 18% 12%)", border: "1px solid hsl(222 12% 22%)" }}>
                  <div className="font-bold text-ai">{payload[0].payload.ref}</div>
                  <div className="max-w-[220px] text-muted-foreground">{payload[0].payload.title}</div>
                  <div>P10 {fmt(payload[0].payload.p10)} · P50 {fmt(payload[0].payload.p50)} · P90 {fmt(payload[0].payload.p90)}</div>
                </div>) : null} />
              <Bar dataKey="low" stackId="a" fill="transparent" />
              <Bar dataKey="span" stackId="a" fill="hsl(190 90% 50%)" radius={[3, 3, 3, 3]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="text-[10px] text-muted-foreground mt-1">Bar spans the Monte-Carlo P10–P90 range per risk — longer bars = more uncertainty. Source: modelled SLE × ARO with residual-control scaling (FAIR).</div>
        </div>
      )}
      <div className="text-[11px] text-muted-foreground flex items-start gap-2"><BarChart3 className="w-3.5 h-3.5 mt-0.5 shrink-0" /> <span>DBIR medians for context — ransomware {fmt(bench.dbir_ransomware_median)}, BEC {fmt(bench.dbir_bec_median)} ({bench.dbir_source}). Benchmark source: {bench.source} · updated {bench.updated}{bench.checked_at ? ` · last checked ${new Date(bench.checked_at).toLocaleDateString()}` : ""}.</span></div>

      <div className="rounded-lg border border-border overflow-x-auto" data-testid="fin-math-table">
        <table className="w-full text-xs min-w-[720px]">
          <thead className="text-[10px] font-mono uppercase text-muted-foreground border-b border-border">
            <tr><th className="text-left px-3 py-2">Risk</th><th className="text-left px-3 py-2">SLE (source)</th><th className="text-left px-3 py-2">Derivation</th><th className="text-right px-3 py-2">Residual ALE</th></tr>
          </thead>
          <tbody>
            {basis.items.map((i) => (
              <tr key={i.ref} data-testid={`fin-row-${i.ref}`} className="border-b border-border/60">
                <td className="px-3 py-2"><div className="font-mono text-ai">{i.ref}</div><div className="truncate max-w-[180px]">{i.title}</div></td>
                <td className="px-3 py-2">${(i.sle / 1e6).toFixed(2)}M<div className="text-[10px] text-muted-foreground max-w-[220px]">{i.sle_source}</div></td>
                <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground">{i.math}</td>
                <td className="px-3 py-2 text-right"><div className="font-bold">${(i.residual_ale / 1e6).toFixed(2)}M</div><div className="text-[10px] text-muted-foreground">P10–P90 ${(i.ale_low / 1e6).toFixed(1)}–${(i.ale_high / 1e6).toFixed(1)}M</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {isAdmin && (
        <div className="rounded-lg bg-secondary/30 p-4 space-y-3" data-testid="fin-config">
          <div className="flex items-center gap-2 text-sm font-bold"><Building2 className="w-4 h-4" /> Calibrate the model (admin)
            {so?.locked
              ? <button data-testid="fin-unlock" onClick={unlock} className="ml-auto text-xs px-2.5 py-1 rounded-md bg-high/15 text-high border border-high/30">🔒 Locked — unlock to edit</button>
              : <button data-testid="fin-signoff" onClick={signOff} className="ml-auto text-xs px-2.5 py-1 rounded-md bg-low/15 text-low border border-low/30">Lock &amp; CRO sign-off</button>}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-xs flex items-center gap-2">Industry
              <select data-testid="fin-industry" value={cfg.config.industry} onChange={(e) => save({ industry: e.target.value })} className="bg-background border border-border rounded-md px-2 py-1 text-xs">
                {cfg.industries.map((x) => <option key={x} value={x}>{x}</option>)}
              </select>
            </label>
            {cfg.suggested_industry?.industry && cfg.suggested_industry.industry !== cfg.config.industry && (
              <button data-testid="fin-industry-suggest" onClick={() => save({ industry: cfg.suggested_industry.industry })} title={cfg.suggested_industry.reason}
                className="text-xs px-2.5 py-1 rounded-md bg-ai/10 text-ai border border-ai/30 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5" /> Use suggested: {cfg.suggested_industry.industry}
              </button>
            )}
            <label className="text-xs flex items-center gap-2">Method
              <select data-testid="fin-method" value={cfg.config.method} onChange={(e) => save({ method: e.target.value })} className="bg-background border border-border rounded-md px-2 py-1 text-xs">
                <option value="flat">Impact→$ table</option>
                <option value="records">Records × per-record cost</option>
              </select>
            </label>
            <label className="text-xs flex items-center gap-2"><Clock className="w-3.5 h-3.5" /> Sign-off reminder
              <select data-testid="fin-reminder-cadence" value={cfg.config.signoff_reminder_days || 60} onChange={(e) => save({ signoff_reminder_days: Number(e.target.value) })} className="bg-background border border-border rounded-md px-2 py-1 text-xs">
                <option value={30}>Every 30 days</option>
                <option value={60}>Every 60 days</option>
                <option value={90}>Every 90 days</option>
              </select>
            </label>
            <button data-testid="fin-refresh" onClick={async () => { await api.post("/financial/benchmark/refresh"); toast.success("Benchmark refreshed"); load(); }} className="text-xs px-2.5 py-1 rounded-md bg-secondary flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5" /> Refresh benchmark</button>
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
          </div>
          {cfg.config.method === "records" ? (
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-xs flex items-center gap-2">Records at risk<input data-testid="fin-records" type="number" defaultValue={cfg.config.records || 0} onBlur={(e) => save({ records: Number(e.target.value) })} className="w-32 bg-background border border-border rounded-md px-2 py-1 text-xs" /></label>
              <label className="text-xs flex items-center gap-2">$/record<input data-testid="fin-perrecord" type="number" defaultValue={cfg.config.per_record_cost || 165} onBlur={(e) => save({ per_record_cost: Number(e.target.value) })} className="w-24 bg-background border border-border rounded-md px-2 py-1 text-xs" /></label>
              <span className="text-[10px] text-muted-foreground">IBM per-record method (2023: $165/record).</span>
            </div>
          ) : (
            <div className="flex flex-wrap items-end gap-3">
              {["5", "4", "3", "2", "1"].map((k) => (
                <label key={k} className="text-xs flex flex-col gap-1">Impact {k} SLE ($)
                  <input data-testid={`fin-sle-${k}`} type="number" defaultValue={cfg.config.impact_sle[k]} onBlur={(e) => save({ impact_sle: { ...cfg.config.impact_sle, [k]: Number(e.target.value) } })} className="w-28 bg-background border border-border rounded-md px-2 py-1 text-xs" />
                </label>
              ))}
            </div>
          )}
        </div>
      )}
      {trend?.points?.length > 1 && (
        <div className="rounded-lg border border-border p-3" data-testid="fin-trend">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1"><TrendingDown className="w-3.5 h-3.5" /> Modelled exposure vs {trend.industry} benchmark (IBM) · peer band shaded</div>
          <ResponsiveContainer width="100%" height={180}>
            <ComposedChart data={trend.points}>
              <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" />
              <YAxis tickFormatter={(v) => `$${(v / 1e6).toFixed(1)}M`} tick={{ fontSize: 10 }} stroke="hsl(215 15% 55%)" width={48} />
              <Tooltip formatter={(v, n) => (n === "peer-base" || n === "Peer range") ? null : `$${(v / 1e6).toFixed(2)}M`} contentStyle={{ background: "hsl(222 18% 12%)", border: "1px solid hsl(222 12% 22%)", fontSize: 11 }} />
              <Area type="monotone" dataKey="peerBase" stackId="peer" stroke="none" fill="transparent" name="peer-base" isAnimationActive={false} />
              <Area type="monotone" dataKey="peerSpan" stackId="peer" stroke="none" fill="hsl(35 90% 55% / 0.14)" name="Peer range" isAnimationActive={false} />
              <Line type="monotone" dataKey="modelled" stroke="hsl(190 90% 50%)" strokeWidth={2} dot={false} name="Modelled" />
              <Line type="monotone" dataKey="benchmark" stroke="hsl(35 90% 55%)" strokeDasharray="4 4" strokeWidth={2} dot={false} name="IBM avg" />
            </ComposedChart>
          </ResponsiveContainer>
          {trend.peer_source && <div className="text-[10px] text-muted-foreground mt-1">Shaded band: {trend.peer_source} ({fmt(trend.peer_low)}–{fmt(trend.peer_high)}). Line source: {trend.source}.</div>}
        </div>
      )}
      {hist.length > 0 && (
        <div className="text-[10px] text-muted-foreground space-y-0.5" data-testid="fin-signoff-history">
          <div className="font-mono uppercase">Sign-off audit trail</div>
          {hist.slice(0, 6).map((h, idx) => (<div key={idx}>{h.action === "signoff" ? "🔒 Signed off" : "🔓 Unlocked"} · {h.name || h.by} · {String(h.at).slice(0, 16).replace("T", " ")}</div>))}
        </div>
      )}
      <p className="text-[11px] text-muted-foreground">{basis.disclaimer}</p>
    </div>
  );
}
