import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUrlState } from "@/hooks/useUrlState";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { EvidenceLineageModal } from "@/components/EvidenceLineageModal";
import { EvidenceModal } from "@/components/EvidenceModal";
import { AssetDetailModal } from "@/components/AssetDetailModal";
import { AIFix } from "@/components/AIFix";
import { AutoActions } from "@/components/AutoActions";
import { SourceBadge, FreshnessBadge, ConfidenceBadge, DataTypeBadge, ScorePill } from "@/components/badges";
import { AIInsight } from "@/components/AIInsight";
import { StatCard, CardShell, EmptyState, BarList, Spinner } from "@/components/dash";
import { ChartBox } from "@/components/ChartBox";
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { Search, Info, DollarSign, X, Grid3x3, TrendingUp, TrendingDown, Minus, AlertTriangle, ShieldOff, Flag, Boxes, Loader2, Wrench, ShieldX, Radio, Bug } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ACCENT = "243 75% 63%"; // Risk Register → indigo
const STATUS = ["Open", "In Progress", "Remediated", "Accepted"];
const BAND_COL = { Low: "142 70% 45%", Moderate: "48 96% 53%", High: "28 90% 55%", Extreme: "0 84% 60%" };
const money = (n) => (n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}k` : `$${Math.round(n || 0)}`);
const SLE_BY_IMPACT = { 5: 8000000, 4: 3000000, 3: 1000000, 2: 300000, 1: 75000 };
const RATECOL = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
// Live ALE straight from the Unified Risk Correlation Engine (backend residual_ale); fall back to
// the modelled magnitude only if the engine hasn't attached a figure to a row yet.
const rowExposure = (r) => r.residual_ale != null ? money(r.residual_ale)
  : money(Math.round((SLE_BY_IMPACT[r.impact] || 1e6) * (r.likelihood / 5) * (r.residual / Math.max(r.inherent, 1))));
const TrendIcon = ({ t }) => t === "up" ? <TrendingUp className="w-3.5 h-3.5 text-crit" /> : t === "down" ? <TrendingDown className="w-3.5 h-3.5 text-low" /> : <Minus className="w-3.5 h-3.5 text-muted-foreground" />;

function QuantMatrix({ matrix, onPick }) {
  const at = (imp, lik) => matrix.find((m) => m.impact === imp && m.likelihood === lik) || { score: imp * lik, count: 0, band: "Low", refs: [] };
  return (
    <div data-testid="risk-matrix">
      <div className="flex gap-2">
        <div className="flex flex-col justify-around text-[9px] font-mono text-muted-foreground py-0.5 writing-mode-vertical">
          {[5, 4, 3, 2, 1].map((i) => <span key={i} className="flex-1 flex items-center justify-center">{i}</span>)}
        </div>
        <div className="flex-1">
          <div className="grid grid-cols-5 gap-1">
            {[5, 4, 3, 2, 1].map((imp) => [1, 2, 3, 4, 5].map((lik) => {
              const c = at(imp, lik);
              return (
                <button key={`${imp}-${lik}`} data-testid={`risk-matrix-cell-${imp}-${lik}`} onClick={() => c.count && onPick(c.refs)} disabled={!c.count}
                  title={`Impact ${imp} × Likelihood ${lik} · score ${c.score} · ${c.count} risk(s)`}
                  className="aspect-[5/3] rounded-md flex flex-col items-center justify-center transition-transform hover:scale-[1.03] disabled:cursor-default"
                  style={{ background: `hsl(${BAND_COL[c.band]} / ${c.count ? 0.85 : 0.14})` }}>
                  <span className={`font-head font-black text-sm ${c.count ? "text-white/95" : "text-muted-foreground/70"}`}>{c.score}</span>
                  {c.count > 0 && <span className="text-[9px] font-mono text-white/90">{c.count} risk{c.count > 1 ? "s" : ""}</span>}
                </button>
              );
            }))}
          </div>
          <div className="grid grid-cols-5 gap-1 mt-1 text-[9px] font-mono text-muted-foreground text-center">
            {[1, 2, 3, 4, 5].map((i) => <span key={i}>{i}</span>)}
          </div>
          <div className="text-center text-[9px] font-mono text-muted-foreground mt-1">Impact →</div>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mt-3">
        {Object.entries(BAND_COL).map(([b, c]) => (
          <span key={b} className="flex items-center gap-1 text-[10px] font-mono"><span className="w-3 h-3 rounded-sm" style={{ background: `hsl(${c})` }} /> {b}</span>
        ))}
      </div>
    </div>
  );
}

export default function RiskRegister() {
  const { mode, user } = useAuth();
  const isExec = mode === "executive";
  const isAdmin = user?.role === "admin";
  const [risks, setRisks] = useState(null);
  const [rr, setRr] = useState(null);
  const [assets, setAssets] = useState([]);
  const [lineage, setLineage] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [selected, setSelected] = useState(null);
  const [remedy, setRemedy] = useState("");
  const [assetModal, setAssetModal] = useState(null);
  const [q, setQ] = useUrlState("q", "");
  const [cat, setCat] = useUrlState("cat", "all");

  const load = () => api.get("/risks").then((r) => setRisks(r.data));
  useEffect(() => {
    load();
    api.get("/dash/risk-register").then((r) => setRr(r.data)).catch(() => setRr(null));
    api.get("/assets").then((r) => setAssets(r.data || [])).catch(() => setAssets([]));
  }, []);

  const updateStatus = async (ref, status) => { await api.patch(`/risks/${ref}`, { status }); toast.success(`${ref} → ${status}`); load(); };
  const autoRemediate = async () => {
    setRemedy("fix");
    try { const { data } = await api.post("/self-scan/autofix"); toast.success(data.message || "AI Autofix launched — scanning, verifying & queuing upgrades"); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not launch autofix"); }
    setRemedy("");
  };
  const blockContain = async () => {
    setRemedy("block");
    try { const { data } = await api.post("/self-scan/containment/scan"); toast.success(`Containment evaluated — ${data.active} active response(s)`); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not run containment"); }
    setRemedy("");
  };

  if (!risks) return <Spinner />;
  const categories = ["all", ...Array.from(new Set(risks.map((r) => r.category)))];
  const filtered = risks.filter((r) => (cat === "all" || r.category === cat) && (r.title.toLowerCase().includes(q.toLowerCase()) || r.ref.toLowerCase().includes(q.toLowerCase())));
  const k = rr?.kpis || {};
  const markers = rr?.loss?.markers || {};
  const hist = rr?.loss?.histogram || [];
  const maxHist = Math.max(1, ...hist.map((h) => h.count));
  const lossLo = hist[0]?.x || 0, lossHi = hist[hist.length - 1]?.x || 1;
  const markPos = (v) => lossHi > lossLo ? `${Math.min(100, Math.max(0, ((v - lossLo) / (lossHi - lossLo)) * 100))}%` : "0%";
  const bandCounts = (rr?.matrix || []).reduce((a, m) => { a[m.band] = (a[m.band] || 0) + m.count; return a; }, {});
  const trendPoints = (rr?.trending?.points || []).map((p) => ({ ...p, bandSpan: Math.max(0, p.high - p.low) }));
  const topAssets = [...assets].sort((a, b) => (b.exposure || 0) - (a.exposure || 0)).slice(0, 5);
  const critColor = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };

  return (
    <div className="rise space-y-5" data-testid="risk-register-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2" style={{ color: `hsl(${ACCENT})` }}><Grid3x3 className="w-7 h-7" strokeWidth={1.5} /> Cyber Risk Register</h1>
        <p className="text-sm text-muted-foreground mt-1">{isExec ? "Board risk portfolio — quantified exposure, appetite trending and top risks tied to assets, vulnerabilities and controls." : "Asset → vulnerability → control → residual risk register with FAIR quantification, KRIs, ownership and evidence lineage."}</p>
      </div>

      {/* KPI row — always present */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard testid="rr-kpi-total" label="Total risks" value={k.total ?? risks.length} accent={ACCENT} sub="in register" />
        <StatCard testid="rr-kpi-open" label="Open" value={k.open ?? risks.filter((r) => r.status !== "Remediated").length} accent="35 90% 55%" sub="not remediated" />
        <StatCard testid="rr-kpi-critical" label="Critical" value={k.critical ?? risks.filter((r) => r.residual >= 16).length} accent="0 84% 60%" sub="residual ≥ 16" />
        <StatCard testid="rr-kpi-exposure" label="$ Residual exposure" value={money(k.residual_exposure ?? 0)} accent="15 80% 55%" sub="annualised (ALE)" />
        <StatCard testid="rr-kpi-worst" label="Worst case (P90)" value={money(k.worst_case_p90 ?? 0)} accent="0 84% 60%" sub="adverse scenario" />
        <StatCard testid="rr-kpi-controls" label="Avg control eff." value={`${k.avg_control_eff ?? 0}%`} accent="142 70% 45%" sub={`${k.controls ?? 0} controls`} />
      </div>

      <AIInsight dashboard="Cyber Risk Register" accent={ACCENT} auto />

      <AutoActions accent={ACCENT} />

      {/* Portfolio reporting row 1: heatmap + top risks + rating breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <CardShell testid="rr-heatmap" title="Risk heatmap — Impact × Likelihood" icon={Grid3x3} accent={ACCENT}>
          <QuantMatrix matrix={rr?.matrix || []} onPick={(refs) => setSelected(risks.find((r) => r.ref === refs[0]))} />
        </CardShell>

        <CardShell testid="rr-top-risks" title="Top risks by $ exposure" icon={AlertTriangle} accent={ACCENT}>
          {!(rr?.top_risks || []).length ? <EmptyState text="No risks yet — run a live scan to populate the register." /> : (
            <div className="space-y-2.5">
              {rr.top_risks.slice(0, 6).map((r) => {
                const max = rr.top_risks[0].exposure || 1;
                return (
                  <button key={r.ref} data-testid={`rr-toprisk-${r.ref}`} onClick={() => setSelected(risks.find((x) => x.ref === r.ref))} className="w-full text-left">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="truncate pr-2 flex items-center gap-1"><TrendIcon t={r.trend} /> <span className="font-mono text-muted-foreground">{r.ref}</span> {r.title}</span>
                      <span className="font-mono shrink-0" style={{ color: `hsl(${ACCENT})` }}>{money(r.exposure)}</span>
                    </div>
                    <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${(r.exposure / max) * 100}%`, background: `hsl(${ACCENT})` }} /></div>
                  </button>
                );
              })}
            </div>
          )}
        </CardShell>

        <CardShell testid="rr-rating" title="Risk rating breakdown" icon={Flag} accent={ACCENT}>
          <div className="grid grid-cols-2 gap-3">
            {["Extreme", "High", "Moderate", "Low"].map((b) => (
              <div key={b} data-testid={`rr-band-${b}`} className="rounded-lg p-3 border" style={{ borderColor: `hsl(${BAND_COL[b]} / 0.35)`, background: `hsl(${BAND_COL[b]} / 0.07)` }}>
                <div className="text-[10px] font-mono uppercase" style={{ color: `hsl(${BAND_COL[b]})` }}>{b}</div>
                <div className="font-head font-black text-2xl tracking-tight">{bandCounts[b] || 0}</div>
                <div className="text-[10px] text-muted-foreground">risk cells</div>
              </div>
            ))}
          </div>
        </CardShell>
      </div>

      {/* Portfolio reporting row 2: loss distribution + trending vs appetite */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CardShell testid="rr-loss" title="Portfolio loss exposure (Monte-Carlo)" icon={DollarSign} accent={ACCENT}>
          {!hist.length ? <EmptyState text="Loss distribution appears once risks are quantified." /> : (
            <>
              <div className="relative h-40 flex items-end gap-0.5">
                {hist.map((h, i) => (
                  <div key={i} className="flex-1 rounded-t-sm" style={{ height: `${(h.count / maxHist) * 100}%`, background: `hsl(${ACCENT} / 0.65)` }} title={`${money(h.x)} · ${h.count}`} />
                ))}
                {["p10", "ml", "p50", "p90"].map((m) => markers[m] != null && (
                  <div key={m} className="absolute top-0 bottom-0 border-l border-dashed" style={{ left: markPos(markers[m]), borderColor: m === "p90" ? "hsl(0 84% 60%)" : m === "p50" ? "hsl(280 82% 64%)" : "hsl(215 20% 65%)" }}>
                    <span className="absolute -top-0.5 left-1 text-[8px] font-mono uppercase" style={{ color: m === "p90" ? "hsl(0 84% 60%)" : m === "p50" ? "hsl(280 82% 64%)" : "hsl(215 20% 65%)" }}>{m}</span>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5 mt-3 text-center">
                {[["min", "Min"], ["p10", "10%"], ["ml", "Likely"], ["p50", "Median"], ["p90", "90%"], ["max", "Max"]].map(([kk, lbl]) => (
                  <div key={kk} className="bg-secondary/30 rounded-md p-1.5"><div className="text-[9px] font-mono uppercase text-muted-foreground">{lbl}</div><div className="text-[11px] font-mono font-bold">{money(markers[kk] || 0)}</div></div>
                ))}
              </div>
            </>
          )}
        </CardShell>

        <CardShell testid="rr-trending" title="Risk trending vs appetite" icon={TrendingUp} accent={ACCENT}
          right={<span className="text-[10px] font-mono text-muted-foreground">appetite {money(rr?.trending?.appetite || 0)}</span>}>
          {!trendPoints.length ? <EmptyState text="Trending appears as exposure snapshots accrue." /> : (
            <ChartBox height={200}>
              <ComposedChart data={trendPoints} margin={{ top: 6, right: 8, left: -14, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="period" tick={{ fontSize: 9, fill: "#94a3b8" }} />
                <YAxis tick={{ fontSize: 9, fill: "#94a3b8" }} tickFormatter={(v) => money(v)} />
                <Tooltip contentStyle={{ background: "#0A0E17", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 }} formatter={(v) => money(v)} />
                <Area dataKey="low" stackId="b" stroke="none" fill="transparent" />
                <Area dataKey="bandSpan" stackId="b" stroke="none" fill={`hsl(${ACCENT} / 0.22)`} name="Exposure range" />
                <Line type="monotone" dataKey="expected" stroke={`hsl(${ACCENT})`} strokeWidth={2.5} dot={false} name="Aggregated loss exposure" />
                <Line type="monotone" dataKey="appetite" stroke="hsl(320 80% 60%)" strokeWidth={2} strokeDasharray="5 4" dot={false} name="Risk appetite" />
              </ComposedChart>
            </ChartBox>
          )}
        </CardShell>
      </div>

      {/* Portfolio reporting row 3: control deficiencies + initiatives + top assets */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <CardShell testid="rr-deficiencies" title="Top control deficiencies" icon={ShieldOff} accent={ACCENT}>
          {!(rr?.control_deficiencies || []).length ? <EmptyState text="Control effectiveness loads with your control library." /> : (
            <div className="space-y-2.5">
              {rr.control_deficiencies.slice(0, 6).map((c) => (
                <div key={c.control_id} data-testid={`rr-deficiency-${c.control_id}`}>
                  <div className="flex items-center justify-between text-xs mb-1"><span className="truncate pr-2"><span className="font-mono text-muted-foreground">{c.control_id}</span> {c.name} {c.framework && <span className="text-[9px] font-mono text-primary/80">· {c.framework}</span>}</span><span className="font-mono text-crit shrink-0">{c.deficiency}%</span></div>
                  <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${c.deficiency}%`, background: `hsl(${c.deficiency >= 45 ? "0 84% 60%" : c.deficiency >= 25 ? "35 90% 55%" : "142 70% 45%"})` }} /></div>
                </div>
              ))}
            </div>
          )}
        </CardShell>

        <CardShell testid="rr-initiatives" title="Top security initiatives" icon={Flag} accent={ACCENT}>
          {!(rr?.initiatives || []).length ? <EmptyState text="Initiatives track open recommendations & remediations." /> : (
            <div className="space-y-3">
              {rr.initiatives.map((i) => (
                <div key={i.ref} data-testid={`rr-init-${i.ref}`}>
                  <div className="flex items-center justify-between text-xs mb-1"><span className="truncate pr-2">{i.title}</span><span className="font-mono text-muted-foreground shrink-0">{i.progress}%</span></div>
                  <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${i.progress}%`, background: `hsl(${ACCENT})` }} /></div>
                </div>
              ))}
            </div>
          )}
        </CardShell>

        <CardShell testid="rr-top-assets" title="Top highest-risk assets" icon={Boxes} accent={ACCENT}>
          {!topAssets.length ? <EmptyState text="Connect a source or run a scan to inventory assets." /> : (
            <div className="space-y-2">
              {topAssets.map((a) => (
                <button key={a.ref} data-testid={`rr-asset-${a.ref}`} onClick={() => setAssetModal(a.ref)}
                  className="w-full flex items-center justify-between gap-2 text-xs bg-secondary/30 hover:bg-secondary/60 rounded-md px-3 py-2 text-left transition-colors">
                  <div className="min-w-0"><div className="font-medium truncate">{a.name}</div><div className="text-[10px] text-muted-foreground truncate">{a.owner} · tap for metadata, CVEs &amp; fixes</div></div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-sm" style={{ background: `hsl(${critColor[a.criticality]} / 0.15)`, color: `hsl(${critColor[a.criticality]})` }}>{a.criticality}</span>
                    <span className="font-mono">{a.exposure}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardShell>
      </div>

      {/* Portfolio reporting row 4: control effectiveness + threat intel + findings */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <CardShell testid="rr-controls-cat" title="Control effectiveness by domain" icon={ShieldOff} accent={ACCENT}>
          <BarList items={(rr?.controls_by_category || []).map((c) => ({ name: `${c.name} (${c.count})`, value: c.value, color: c.value >= 80 ? "142 70% 45%" : c.value >= 60 ? "35 90% 55%" : "0 84% 60%" }))} accent={ACCENT} empty="Control library loads here." />
        </CardShell>
        <CardShell testid="rr-threat-intel" title="Live threat intelligence feeds" icon={Radio} accent={ACCENT}>
          {!(rr?.threat_intel || []).length ? <EmptyState text="Threat feeds sync on each scan." /> : (
            <div className="space-y-2">
              {rr.threat_intel.map((f) => (
                <div key={f.key} data-testid={`rr-feed-${f.key}`} className="flex items-center justify-between gap-2 text-xs bg-secondary/30 rounded-md px-3 py-2">
                  <div className="min-w-0"><div className="font-medium truncate">{f.label}</div><div className="text-[10px] font-mono text-muted-foreground">v{f.version || "—"}{f.count != null ? ` · ${Number(f.count).toLocaleString()} entries` : ""}</div></div>
                  <span className={`font-mono text-[9px] px-1.5 py-0.5 rounded-full shrink-0 ${String(f.status || "").startsWith("live") ? "bg-low/15 text-low" : "bg-secondary/60 text-muted-foreground"}`}>{f.status}</span>
                </div>
              ))}
            </div>
          )}
        </CardShell>
        <CardShell testid="rr-findings-sev" title="Live scan findings" icon={Bug} accent={ACCENT}
          right={<span className="text-[10px] font-mono text-muted-foreground">{rr?.findings?.passed ?? 0}/{rr?.findings?.total ?? 0} passed</span>}>
          <div className="grid grid-cols-2 gap-2">
            {[["critical", "Critical", "0 84% 60%"], ["high", "High", "15 80% 55%"], ["medium", "Medium", "35 90% 55%"], ["low", "Low", "142 70% 45%"]].map(([kk, lbl, col]) => (
              <div key={kk} className="rounded-lg p-3 border" style={{ borderColor: `hsl(${col} / 0.35)`, background: `hsl(${col} / 0.06)` }}>
                <div className="text-[10px] font-mono uppercase" style={{ color: `hsl(${col})` }}>{lbl}</div>
                <div className="font-head font-black text-2xl">{rr?.findings?.by_severity?.[kk] ?? 0}</div>
              </div>
            ))}
          </div>
          <div className="text-[11px] text-muted-foreground mt-3">{rr?.findings?.deps_scanned ?? 0} deps scanned · <span className="text-crit">{rr?.findings?.vuln_deps ?? 0} vulnerable</span></div>
        </CardShell>
      </div>

      {/* Live vulnerabilities & auto-remediation */}
      <CardShell testid="rr-vulns" title="Live vulnerabilities & findings" icon={Bug} accent={ACCENT}
        right={isAdmin && (
          <div className="flex items-center gap-1.5">
            <button data-testid="rr-autofix" disabled={!!remedy} onClick={autoRemediate} className="flex items-center gap-1 text-[11px] font-head font-bold px-2.5 py-1.5 rounded-full disabled:opacity-50" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}>{remedy === "fix" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wrench className="w-3 h-3" />} Auto-remediate</button>
            <button data-testid="rr-contain" disabled={!!remedy} onClick={blockContain} className="flex items-center gap-1 text-[11px] font-head font-bold px-2.5 py-1.5 rounded-full border border-crit/40 text-crit disabled:opacity-50">{remedy === "block" ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldX className="w-3 h-3" />} Block / contain</button>
          </div>
        )}>
        {!(rr?.findings?.list || []).length ? <EmptyState icon={Bug} text="No scan findings yet — run a live self-scan on Security Scanner." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><tr><th className="text-left px-3 py-2">Finding</th><th className="text-left px-3 py-2">Severity</th><th className="text-left px-3 py-2">CVE / KEV</th><th className="text-left px-3 py-2">Maps to</th><th className="text-left px-3 py-2">Remediation</th></tr></thead>
              <tbody>
                {rr.findings.list.map((f) => {
                  const sc = f.severity === "critical" ? "0 84% 60%" : f.severity === "high" ? "15 80% 55%" : f.severity === "medium" ? "35 90% 55%" : f.severity === "low" ? "142 70% 45%" : "199 20% 60%";
                  return (
                    <tr key={f.id} data-testid={`rr-finding-${f.id}`} className="border-b border-border/60">
                      <td className="px-3 py-2"><div className="font-medium">{f.title}</div><div className="text-[10px] text-muted-foreground">{f.category}</div></td>
                      <td className="px-3 py-2"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold uppercase" style={{ background: `hsl(${sc} / 0.15)`, color: `hsl(${sc})` }}>{f.status === "pass" ? "pass" : f.severity}</span></td>
                      <td className="px-3 py-2 font-mono text-[11px]">{(f.cve_ids || []).join(", ") || "—"} {f.kev && <span className="ml-1 text-crit">KEV</span>}</td>
                      <td className="px-3 py-2 text-[11px] text-muted-foreground">{(f.control_refs || []).slice(0, 2).join(", ") || "—"}</td>
                      <td className="px-3 py-2 text-[11px] text-muted-foreground max-w-xs truncate">{f.remediation}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardShell>

      {/* Detailed register */}
      <div className="flex flex-wrap gap-3 sticky top-16 z-20 -mx-4 px-4 sm:mx-0 sm:px-0 py-2 bg-background/90 backdrop-blur">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input data-testid="risk-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search risks…" className="w-full bg-card border border-border rounded-md pl-9 pr-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <Select value={cat} onValueChange={setCat}>
          <SelectTrigger data-testid="risk-category-filter" className="w-52 bg-card"><SelectValue /></SelectTrigger>
          <SelectContent>{categories.map((c) => <SelectItem key={c} value={c}>{c === "all" ? "All categories" : c}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      <div className="md:flex md:gap-5 md:items-start">
      <div className="min-w-0 flex-1 space-y-4">
      <div className="md:hidden space-y-3" data-testid="risk-cards-mobile">
        {filtered.map((r) => (
          <div key={r.ref} data-testid={`risk-card-${r.ref}`} onClick={() => setLineage(r.ref)} className="bg-card fact-border rounded-lg p-4 space-y-2 active:bg-secondary/40 transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0"><div className="font-mono text-[11px] text-ai">{r.ref}</div><div className="font-medium text-sm">{r.title}</div><div className="text-[11px] text-high">{r.business_impact}</div></div>
              <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
                {isExec ? <span className="text-[10px] px-2 py-0.5 rounded-md bg-secondary/60">{r.status}</span> : (
                  <Select value={r.status} onValueChange={(v) => updateStatus(r.ref, v)}>
                    <SelectTrigger className="w-28 h-8 text-xs bg-secondary/60"><SelectValue /></SelectTrigger>
                    <SelectContent>{STATUS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                  </Select>
                )}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>{r.category}</span><span className="flex items-center gap-1">Inh <ScorePill value={r.inherent} /></span><span className="flex items-center gap-1">Res <ScorePill value={r.residual} /></span>
            </div>
            <button data-testid={`evidence-m-${r.ref}`} onClick={(e) => { e.stopPropagation(); setEvidence(r.ref); }} className="flex items-center gap-1 text-xs font-mono text-high"><DollarSign className="w-3 h-3" />{rowExposure(r)} exposure <Info className="w-3 h-3 opacity-60" /></button>
          </div>
        ))}
      </div>

      <div className="hidden md:block bg-card fact-border rounded-lg overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr>
              <th className="text-left px-4 py-3">Ref / Risk</th><th className="text-left px-4 py-3">Category</th>
              <th className="text-left px-4 py-3">Inh.</th><th className="text-left px-4 py-3">Res.</th>
              <th className="text-left px-4 py-3">$ Exposure</th><th className="text-left px-4 py-3">Owner</th>
              <th className="text-left px-4 py-3">KRI</th><th className="text-left px-4 py-3">Evidence</th><th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.ref} data-testid={`risk-row-${r.ref}`} onClick={() => setSelected(r)} className={`border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer ${selected?.ref === r.ref ? "bg-secondary/50" : ""}`}>
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{r.ref}</div><div className="font-medium max-w-xs">{r.title}</div><div className="text-[11px] text-muted-foreground mt-0.5">{r.business_impact}</div></td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{r.category}</td>
                <td className="px-4 py-3"><ScorePill value={r.inherent} /></td>
                <td className="px-4 py-3"><div className="flex flex-col gap-1 items-start"><ScorePill value={r.residual} />{r.rating && <span data-testid={`rr-rating-${r.ref}`} className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-sm" style={{ background: `hsl(${RATECOL[r.rating]} / 0.15)`, color: `hsl(${RATECOL[r.rating]})` }}>{r.rating}</span>}</div></td>
                <td className="px-4 py-3"><button data-testid={`evidence-${r.ref}`} onClick={(e) => { e.stopPropagation(); setEvidence(r.ref); }} className="flex items-center gap-1 text-xs font-mono text-high hover:text-foreground transition-colors"><DollarSign className="w-3 h-3" />{rowExposure(r)}<Info className="w-3 h-3 opacity-60" /></button></td>
                <td className="px-4 py-3 text-xs">{r.owner}</td>
                <td className="px-4 py-3 text-[11px] font-mono text-muted-foreground max-w-[140px]">{r.kri}</td>
                <td className="px-4 py-3"><div className="flex flex-col gap-1"><SourceBadge source={r.source} /><div className="flex items-center gap-2"><FreshnessBadge freshness={r.freshness} /><DataTypeBadge type={r.data_type} /></div><ConfidenceBadge value={r.confidence} /></div></td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                  {isExec ? <span data-testid={`risk-status-badge-${r.ref}`} className="text-xs px-2.5 py-1 rounded-md bg-secondary/60">{r.status}</span> : (
                    <Select value={r.status} onValueChange={(v) => updateStatus(r.ref, v)}>
                      <SelectTrigger data-testid={`risk-status-${r.ref}`} className="w-32 h-8 text-xs bg-secondary/60"><SelectValue /></SelectTrigger>
                      <SelectContent>{STATUS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                    </Select>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>

      <aside data-testid="risk-detail-pane" className="hidden md:block md:w-72 lg:w-80 shrink-0 md:sticky md:top-28 bg-card fact-border rounded-xl p-4 space-y-3">
        {!selected ? (
          <EmptyState icon={Grid3x3} text="Select a risk from the register or heatmap to inspect residual, KRIs, evidence lineage and live remediation." />
        ) : (
          <>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0"><div className="font-mono text-[11px] text-ai">{selected.ref}</div><div className="font-head font-bold text-sm">{selected.title}</div></div>
              <button data-testid="risk-detail-close" onClick={() => setSelected(null)} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-xs text-high">{selected.business_impact}</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-secondary/40 rounded-md p-2 space-y-1"><div className="text-[10px] text-muted-foreground">Inherent</div><ScorePill value={selected.inherent} /></div>
              <div className="bg-secondary/40 rounded-md p-2 space-y-1"><div className="text-[10px] text-muted-foreground">Residual</div><ScorePill value={selected.residual} /></div>
            </div>
            <div className="text-xs space-y-1">
              <div className="flex justify-between gap-2"><span className="text-muted-foreground">Category</span><span className="text-right">{selected.category}</span></div>
              <div className="flex justify-between gap-2"><span className="text-muted-foreground">Owner</span><span className="text-right">{selected.owner}</span></div>
              <div className="flex justify-between gap-2"><span className="text-muted-foreground">$ Exposure</span><span className="font-mono text-high">{rowExposure(selected)}</span></div>
              <div className="flex justify-between gap-2"><span className="text-muted-foreground">Status</span><span className="text-right">{selected.status}</span></div>
            </div>
            <div className="text-[11px] font-mono text-muted-foreground bg-secondary/30 rounded-md p-2">KRI: {selected.kri}</div>
            <AIFix entity="risk" refId={selected.ref} accent={ACCENT} />
            <div className="flex flex-col gap-1.5"><SourceBadge source={selected.source} /><div className="flex flex-wrap items-center gap-2"><FreshnessBadge freshness={selected.freshness} /><DataTypeBadge type={selected.data_type} /><ConfidenceBadge value={selected.confidence} /></div></div>
            <div className="flex gap-2 pt-1">
              <button data-testid="risk-detail-lineage" onClick={() => setLineage(selected.ref)} className="flex-1 text-xs px-3 py-2 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors">Full lineage</button>
              <button data-testid="risk-detail-evidence" onClick={() => setEvidence(selected.ref)} className="flex-1 text-xs px-3 py-2 rounded-md bg-secondary/60 hover:bg-secondary transition-colors">Evidence</button>
            </div>
            {isAdmin && (
              <div className="pt-2 border-t border-border/60 space-y-1.5">
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Live remediation</div>
                <button data-testid="risk-detail-autofix" disabled={!!remedy} onClick={autoRemediate} className="w-full flex items-center justify-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-md disabled:opacity-50" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}>{remedy === "fix" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wrench className="w-3.5 h-3.5" />} Auto-remediate</button>
                <button data-testid="risk-detail-contain" disabled={!!remedy} onClick={blockContain} className="w-full flex items-center justify-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-md border border-crit/40 text-crit hover:bg-crit/10 transition-colors disabled:opacity-50">{remedy === "block" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldX className="w-3.5 h-3.5" />} Block / contain</button>
              </div>
            )}
          </>
        )}
      </aside>
      </div>

      <EvidenceLineageModal riskRef={lineage} onClose={() => setLineage(null)} />
      <EvidenceModal kind="risk" refId={evidence} onClose={() => setEvidence(null)} />
      <AssetDetailModal assetRef={assetModal} findings={rr?.findings?.list || []} accent={ACCENT} onClose={() => setAssetModal(null)} />
    </div>
  );
}
