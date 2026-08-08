import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ShieldAlert, Loader2, Layers, PlayCircle, Gauge, ShieldCheck, TrendingDown, Calculator, BarChart3, Building2, RefreshCw } from "lucide-react";

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
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><ShieldAlert className="w-7 h-7 text-primary" /> Cyber Risk</h1>
        <p className="text-sm text-muted-foreground mt-1">{isExec ? "Strategic cyber risk posture — business exposure and mitigation at a glance." : "Control-centric cyber risk posture — a kernel-native app composed on the Obserra kernel."}</p>
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

      <FinancialBasis isAdmin={isAdmin} />
    </div>
  );
}

function FinancialBasis({ isAdmin }) {
  const [basis, setBasis] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const load = () => Promise.all([api.get("/financial/basis"), api.get("/financial/config")])
    .then(([b, c]) => { setBasis(b.data); setCfg(c.data); }).catch(() => {});
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
  const so = cfg.config.signoff;
  return (
    <div className="bg-card fact-border rounded-xl p-5 space-y-5" data-testid="financial-basis">
      <div className="flex flex-wrap items-center gap-2"><Calculator className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Financial basis &amp; benchmark</h2><span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-secondary text-muted-foreground">defensible math</span>{basis.signoff?.locked && <span data-testid="fin-approved" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/15 text-low border border-low/30">✓ Approved by {basis.signoff.name} · {String(basis.signoff.at).slice(0, 10)}{basis.signoff.stale ? " (config changed since)" : ""}</span>}</div>

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
      {basis.scenario && (
        <div className="rounded-lg bg-ai/5 border border-ai/20 p-3" data-testid="fin-scenario">
          <div className="text-[10px] font-mono uppercase text-muted-foreground">Board exposure range · Monte-Carlo (P10 – expected – P90)</div>
          <div className="font-head font-black text-xl mt-1">{fmt(basis.scenario.p10)} <span className="text-muted-foreground text-sm">low</span> · {fmt(basis.scenario.p50)} <span className="text-muted-foreground text-sm">expected</span> · {fmt(basis.scenario.p90)} <span className="text-muted-foreground text-sm">high</span></div>
          <div className="text-[10px] text-muted-foreground">2,000-iteration simulation over magnitude &amp; frequency uncertainty — shows the board a defensible band, not a single point.</div>
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
                <td className="px-3 py-2 text-right font-bold">${(i.residual_ale / 1e6).toFixed(2)}M</td>
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
            <label className="text-xs flex items-center gap-2">Method
              <select data-testid="fin-method" value={cfg.config.method} onChange={(e) => save({ method: e.target.value })} className="bg-background border border-border rounded-md px-2 py-1 text-xs">
                <option value="flat">Impact→$ table</option>
                <option value="records">Records × per-record cost</option>
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
      <p className="text-[11px] text-muted-foreground">{basis.disclaimer}</p>
    </div>
  );
}
