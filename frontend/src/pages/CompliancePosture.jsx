import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ShieldCheck, Loader2, AlertTriangle, ArrowRight, CheckCircle2, XCircle, Grid3x3, ChevronRight, Sparkles } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { AIInsight } from "@/components/AIInsight";
import { ControlDetailModal } from "@/components/ControlDetailModal";
import { useDeepDive } from "@/context/DeepDiveContext";

const ACCENT = "160 84% 39%"; // Compliance → emerald
const col = (v) => (v >= 75 ? "142 70% 45%" : v >= 55 ? "35 90% 55%" : "0 84% 60%");
const STATUS_COL = { "Failing": "0 84% 60%", "Evidence Stale": "35 90% 55%", "Drifting": "266 85% 66%", "Passing": "142 70% 45%" };
const CRIT_COL = { "Critical": "0 84% 60%", "High": "15 80% 55%", "Medium": "35 90% 55%", "Low": "142 70% 45%" };
const STCOL = { aligned: "142 70% 45%", met: "199 70% 50%", gap: "0 84% 60%", not_assessed: "215 15% 55%" };
const STLABEL = { aligned: "Aligned", met: "Met", gap: "Gap", not_assessed: "Not assessed" };
const fade = { hidden: { opacity: 0, y: 12 }, show: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.05, duration: 0.4 } }) };

function riskOf(compliant, eff) {
  if (!compliant) return eff != null && eff < 55 ? { r: "Critical", c: "0 84% 60%" } : { r: "High", c: "15 80% 55%" };
  if (eff != null && eff < 75) return { r: "Medium", c: "35 90% 55%" };
  return { r: "Low", c: "142 70% 45%" };
}
const RiskBadge = ({ compliant, eff, testid }) => {
  const { r, c } = riskOf(compliant, eff);
  return <span data-testid={testid} className="text-[9px] font-mono font-bold px-2 py-0.5 rounded-full whitespace-nowrap" style={{ background: `hsl(${c} / 0.15)`, color: `hsl(${c})` }}>{r} RISK</span>;
};

function Posture({ d, onOpen }) {
  const { openDeepDive } = useDeepDive();
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <motion.div custom={0} variants={fade} initial="hidden" animate="show" role="button" tabIndex={0}
          onClick={() => openDeepDive({ accent: ACCENT, refLabel: "COMPLIANCE", title: "Overall compliance alignment", score: d.overall || 0, rating: (d.overall || 0) >= 75 ? "Low" : (d.overall || 0) >= 55 ? "Medium" : "High", facets: [{ label: "Overall alignment", value: `${d.overall || 0}%` }, { label: "Controls passing", value: `${d.passing}/${d.total_controls}` }, { label: "Frameworks", value: String(d.frameworks?.length || 0) }], complianceRefs: (d.frameworks || []).map((f) => f.framework), recommendedActions: ["Close the highest-criticality open gaps first to raise overall alignment fastest.", "Attach independent evidence or run a live self-scan to promote Met → Aligned controls."], explainTitle: "Overall compliance alignment", explainKind: "compliance overall alignment posture frameworks", explainContext: { overall: d.overall, passing: d.passing, total: d.total_controls, frameworks: d.frameworks } })}
          className="col-span-full lg:col-span-4 bg-card fact-border rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer hover:-translate-y-0.5 transition-transform duration-200">
          <div className="text-xs text-muted-foreground mb-1">Overall alignment</div>
          <div data-testid="compliance-overall" className="font-head font-black text-6xl tracking-tight" style={{ color: `hsl(${col(d.overall || 0)})` }}>{d.overall || 0}%</div>
          <div className="text-[11px] text-muted-foreground mt-2">{d.passing}/{d.total_controls} controls passing across {d.frameworks?.length || 0} frameworks</div>
        </motion.div>

        <motion.div custom={1} variants={fade} initial="hidden" animate="show" role="button" tabIndex={0}
          onClick={() => openDeepDive({ accent: ACCENT, refLabel: "COMPLIANCE", title: "Alignment by framework", facets: (d.frameworks || []).map((f) => ({ label: f.framework, value: `${f.coverage}% · ${f.passing}/${f.controls}` })), recommendedActions: ["Focus on the lowest-coverage framework first — closing its mapped gaps lifts multiple overlapping controls at once."], explainTitle: "Compliance alignment by framework", explainKind: "compliance framework alignment coverage", explainContext: { frameworks: d.frameworks } })}
          className="col-span-full lg:col-span-8 bg-card fact-border rounded-xl p-6 cursor-pointer hover:-translate-y-0.5 transition-transform duration-200">
          <h2 className="font-head font-bold text-lg mb-4">Alignment by framework</h2>
          <div className="space-y-4">
            {d.frameworks.map((f) => (
              <div key={f.framework} data-testid={`framework-row-${f.framework.replace(/[^a-zA-Z0-9]/g, "-")}`}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="font-medium">{f.framework}</span>
                  <span className="font-mono text-xs" style={{ color: `hsl(${col(f.coverage)})` }}>{f.coverage}% · {f.passing}/{f.controls}</span>
                </div>
                <div className="h-2 rounded-full bg-secondary/60 overflow-hidden">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${f.coverage}%` }} transition={{ duration: 0.8, ease: "easeOut" }} className="h-full rounded-full" style={{ background: `hsl(${col(f.coverage)})` }} />
                </div>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {f.mapped_refs.slice(0, 8).map((r) => <span key={r} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{r}</span>)}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      <motion.div custom={2} variants={fade} initial="hidden" animate="show" className="bg-card fact-border rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4"><AlertTriangle className="w-4 h-4 text-high" /><h2 className="font-head font-bold text-lg">Top gaps to close first</h2><span className="text-[11px] text-muted-foreground">— click any gap for the AI risk rating &amp; recommended action</span></div>
        {(!d.gaps || d.gaps.length === 0) ? (
          <div className="text-sm text-low py-6 text-center">✓ All mapped controls are passing — no open compliance gaps.</div>
        ) : (
          <div className="space-y-3">
            {d.gaps.map((g, i) => (
              <button key={g.control_id} type="button" data-testid={`gap-${g.control_id}`}
                onClick={() => onOpen({ ref: g.control_id, title: g.name, subtitle: `${g.status} · ${g.effectiveness}% effective · ${g.owner || "unassigned"}`,
                  obserraId: g.control_id, status: g.status, effectiveness: g.effectiveness,
                  why: g.recommendation, mappings: null })}
                className="w-full text-left flex items-start gap-4 p-4 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors">
                <span className="font-head font-black text-lg text-muted-foreground w-6 shrink-0">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-mono text-xs text-muted-foreground">{g.control_id}</span>
                    <span className="text-sm font-medium">{g.name}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${STATUS_COL[g.status] || "0 84% 60%"} / 0.15)`, color: `hsl(${STATUS_COL[g.status] || "0 84% 60%"})` }}>{g.status}</span>
                    <RiskBadge compliant={false} eff={g.effectiveness} testid={`gap-risk-${g.control_id}`} />
                  </div>
                  <div className="text-xs text-foreground/80 flex items-start gap-1"><ArrowRight className="w-3.5 h-3.5 mt-0.5 text-ai shrink-0" /> {g.recommendation}</div>
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {g.frameworks.map((fw) => <span key={fw} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-high/10 text-high border border-high/20">{fw}</span>)}
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0 mt-1" />
              </button>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}

// One catalog control row — a rich card showing status, risk, score & the recommended fix,
// clickable to open the full AI analysis + AI-written remediation.
function fixLine(c) {
  if (c.status === "gap") return c.why || "Author a compensating control, attach evidence and re-scan to close this gap.";
  if (c.status === "met") return "Met by default from the hardened baseline — attach independent evidence or run a live self-scan to strengthen Met → Aligned.";
  if (c.status === "aligned") return c.why || "Evidence-backed by passing control(s) — maintain the control and re-attest before evidence expires.";
  return "Not assessed — map a compensating control and collect evidence.";
}

function ControlRow({ c, fw, onOpen }) {
  const sc = STCOL[c.status] || STCOL.met;
  const label = STLABEL[c.status] || "—";
  const isGap = c.status === "gap";
  const scoreCol = c.score >= 75 ? "142 70% 45%" : c.score >= 55 ? "35 90% 55%" : "0 84% 60%";
  return (
    <button type="button" data-testid={`fw-control-${c.id}`}
      onClick={() => onOpen({ ref: c.id, title: c.id, subtitle: `${fw} · ${c.group}`,
        obserraId: (c.mapped_to && c.mapped_to[0]) ? c.mapped_to[0].control_id : null,
        status: c.status, why: c.why, mappedTo: c.mapped_to, recommendation: fixLine(c) })}
      className="w-full text-left flex flex-col gap-1.5 px-3 py-3 hover:bg-secondary/40 transition-colors">
      <div className="flex items-center gap-2 flex-wrap">
        {c.status === "aligned" || c.status === "met" ? <CheckCircle2 className="w-4 h-4 shrink-0" style={{ color: `hsl(${sc})` }} /> : isGap ? <XCircle className="w-4 h-4 shrink-0" style={{ color: `hsl(${sc})` }} /> : <span className="w-3.5 h-3.5 shrink-0 rounded-full border border-muted-foreground/40" />}
        <span className="font-mono text-[12px] font-medium">{c.id}</span>
        <span className="text-[10px] text-muted-foreground truncate max-w-[200px]">{c.group}</span>
        <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${sc} / 0.15)`, color: `hsl(${sc})` }}>{label}</span>
        <RiskBadge compliant={!isGap} eff={isGap ? c.score : 90} testid={`fw-risk-${c.id}`} />
        <span data-testid={`fw-score-${c.id}`} className="text-[9px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${scoreCol} / 0.12)`, color: `hsl(${scoreCol})` }}>Score {c.score}/100</span>
        <span className="ml-auto text-[9px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1 shrink-0" style={{ background: "hsl(266 85% 66% / 0.12)", color: "hsl(266 85% 66%)" }}><Sparkles className="w-3 h-3" /> AI risk &amp; fix <ChevronRight className="w-3 h-3" /></span>
      </div>
      <div className="text-[11px] text-foreground/75 flex items-start gap-1 pl-6"><ArrowRight className="w-3 h-3 mt-0.5 shrink-0 text-ai" /> <span className="line-clamp-2">{fixLine(c)}</span></div>
      {c.mapped_to?.length > 0 && <div className="text-[10px] text-muted-foreground pl-6 truncate">Covered by {c.mapped_to.map((m) => `${m.control_id} ${m.name}`).join(", ")}</div>}
    </button>
  );
}

function Crosswalk({ x, reload, onOpen }) {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState("__every__"); // __every__ | <framework> | __grid__
  const [cache, setCache] = useState({});
  const [loading, setLoading] = useState(false);
  const [nonce, setNonce] = useState(0);
  const [running, setRunning] = useState(false);
  const [critFilter, setCritFilter] = useState(null);
  const frameworks = x.frameworks;
  const ql = q.trim().toLowerCase();
  const totalControls = x.summary.reduce((s, f) => s + (f.total || 0), 0);

  useEffect(() => {
    let cancelled = false;
    const need = mode === "__grid__" ? [] : (mode === "__every__" ? frameworks : [mode]);
    const missing = need.filter((f) => !cache[f]);
    if (missing.length === 0) { setLoading(false); return; }
    setLoading(true);
    Promise.all(missing.map((f) => api.get(`/controls/framework/${encodeURIComponent(f)}`).then((r) => [f, r.data]).catch(() => [f, null])))
      .then((pairs) => {
        if (cancelled) return;
        setCache((c) => { const n = { ...c }; for (const [f, dt] of pairs) if (dt) n[f] = dt; return n; });
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, nonce]);

  const runTest = async () => {
    setRunning(true);
    toast.info("Running live self-scan (headers, CORS, OSV CVEs, CISA KEV)…");
    try { const { data } = await api.post("/self-scan/run"); toast.success(`Self-test done — score ${data.score}/100 · compliance updated`); if (reload) reload(); setCache({}); setNonce((n) => n + 1); }
    catch { toast.error("Self-test failed"); }
    setRunning(false);
  };

  const match = (c, fw) => !ql || `${c.id} ${c.group} ${fw} ${(c.mapped_to || []).map((m) => m.control_id + " " + m.name).join(" ")}`.toLowerCase().includes(ql);
  const groups = (mode === "__every__" ? frameworks : mode === "__grid__" ? [] : [mode])
    .map((fw) => ({ fw, detail: cache[fw], ctrls: (cache[fw]?.controls || []).filter((c) => match(c, fw)) }));
  const shownCount = groups.reduce((s, g) => s + g.ctrls.length, 0);

  // Obserra mapping grid rows
  const critScope = (mode === "__every__" || mode === "__grid__") ? "all" : mode;
  const critRows = critScope === "all" ? x.rows : x.rows.filter((r) => (r.mappings[mode] || []).length > 0);
  const byCrit = ["Critical", "High", "Medium", "Low"].map((t) => {
    const grp = critRows.filter((r) => r.criticality === t);
    const comp = grp.filter((r) => r.compliant).length;
    return { criticality: t, controls: grp.length, compliant: comp, non_compliant: grp.length - comp,
             compliant_pct: grp.length ? Math.round(comp / grp.length * 100) : 0 };
  });
  const gridRows = x.rows.filter((r) => {
    if (critFilter && r.criticality !== critFilter) return false;
    if (!ql) return true;
    return [r.control_id, r.name, r.category, r.criticality, ...Object.values(r.mappings).flat()].join(" ").toLowerCase().includes(ql);
  });

  return (
    <div className="space-y-6" data-testid="crosswalk-panel">
      {/* Per-framework compliant vs not summary — click to focus that framework's full list */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {x.summary.map((s) => {
          const ok = s.status === "Compliant";
          const active = mode === s.framework;
          return (
            <button key={s.framework} type="button" onClick={() => { setCritFilter(null); setMode(active ? "__every__" : s.framework); }}
              data-testid={`crosswalk-summary-${s.framework.replace(/[^a-zA-Z0-9]/g, "-")}`}
              className={`text-left rounded-xl p-4 border transition-all ${active ? "ring-2 ring-primary" : ""} ${ok ? "border-low/30 bg-low/5" : "border-high/30 bg-high/5"}`}>
              <div className="flex items-center justify-between gap-1">
                <div className="font-head font-bold text-sm truncate">{s.framework} · <span style={{ color: `hsl(${col(s.meeting_pct)})` }}>{s.meeting_pct}%</span></div>
                {ok ? <CheckCircle2 className="w-4 h-4 text-low shrink-0" /> : <XCircle className="w-4 h-4 text-high shrink-0" />}
              </div>
              <div className="text-[10px] text-muted-foreground leading-tight mt-0.5">{s.full_name}</div>
              <div className="font-head font-black text-2xl tracking-tight mt-2" style={{ color: `hsl(${col(s.meeting_pct)})` }}>{s.meeting_pct}%</div>
              <div className="text-[10px] font-mono text-muted-foreground">Score {s.meeting_pct}/100 · {s.meeting.toLocaleString()}/{s.total.toLocaleString()} met</div>
              <div className="text-[10px] text-muted-foreground/70 mt-0.5">{s.aligned} evidence-aligned · {s.met.toLocaleString()} met by default · {s.gap} gap{s.gap === 1 ? "" : "s"}</div>
              <span className={`inline-block mt-2 text-[9px] font-mono px-2 py-0.5 rounded-full ${ok ? "bg-low/15 text-low" : "bg-high/15 text-high"}`}>{s.status}</span>
            </button>
          );
        })}
      </div>

      {/* Compliance by control criticality — live, recomputed for the selected framework */}
      <div className="bg-card fact-border rounded-xl p-5" data-testid="crosswalk-criticality">
        <div className="flex items-center gap-2 mb-3 flex-wrap"><AlertTriangle className="w-4 h-4 text-high" /><h2 className="font-head font-bold text-lg">Compliance by control criticality</h2>
          <span className="text-[11px] text-muted-foreground">— {critScope === "all" ? "all mapped controls" : critScope} · {critRows.length} control{critRows.length === 1 ? "" : "s"} · click a tier to filter</span></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {byCrit.map((b) => {
            const active = critFilter === b.criticality;
            return (
              <button key={b.criticality} type="button" data-testid={`crit-tier-${b.criticality}`}
                onClick={() => { setMode("__grid__"); setCritFilter(active ? null : b.criticality); }}
                className={`text-left rounded-lg p-4 border transition-all ${active ? "ring-2 ring-primary" : ""}`} style={{ borderColor: `hsl(${CRIT_COL[b.criticality]} / 0.35)`, background: `hsl(${CRIT_COL[b.criticality]} / 0.06)` }}>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full" style={{ background: `hsl(${CRIT_COL[b.criticality]} / 0.15)`, color: `hsl(${CRIT_COL[b.criticality]})` }}>{b.criticality}</span>
                  <span className="text-[10px] text-muted-foreground">{b.controls} control{b.controls === 1 ? "" : "s"}</span>
                </div>
                <div className="font-head font-black text-2xl tracking-tight mt-2" style={{ color: `hsl(${col(b.compliant_pct)})` }} data-testid={`crit-pct-${b.criticality}`}>{b.compliant_pct}%</div>
                <div className="text-[11px] text-muted-foreground">{b.compliant}/{b.controls} compliant · {b.non_compliant} open</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Full framework → control browser */}
      <div className="bg-card fact-border rounded-xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2 min-w-0"><Grid3x3 className="w-4 h-4 text-primary shrink-0" /><h2 className="font-head font-bold text-lg truncate">
            {mode === "__grid__" ? "Obserra control mapping grid" : mode === "__every__" ? `Every control · all frameworks (${totalControls.toLocaleString()})` : `Every ${mode} control`}
          </h2></div>
          <div className="flex flex-wrap items-center gap-2">
            <button data-testid="crosswalk-run-scan" onClick={runTest} disabled={running} className="px-3 py-2 rounded-md bg-crit/15 text-crit text-xs font-head font-bold disabled:opacity-50">{running ? "Testing…" : "Run self-test"}</button>
            <select data-testid="crosswalk-framework-select" value={mode} onChange={(e) => { setCritFilter(null); setMode(e.target.value); }} className="bg-secondary/60 rounded-md px-3 py-2 text-xs outline-none focus:ring-1 focus:ring-primary">
              <option value="__every__">Every control · all frameworks</option>
              {frameworks.map((f) => <option key={f} value={f}>{f} — every control</option>)}
              <option value="__grid__">Obserra control mapping grid</option>
            </select>
            <input data-testid="crosswalk-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search controls, IDs, refs…" className="bg-secondary/60 rounded-md px-3 py-2 text-xs outline-none focus:ring-1 focus:ring-primary w-56" />
          </div>
        </div>

        {mode === "__grid__" ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm min-w-[980px]" data-testid="crosswalk-table">
              <thead>
                <tr className="text-left">
                  <th className="py-2 pr-3 text-xs font-mono uppercase tracking-wider text-muted-foreground sticky left-0 bg-card">Control</th>
                  <th className="py-2 px-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">Status</th>
                  <th className="py-2 px-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">Risk</th>
                  {frameworks.map((f) => (<th key={f} className="py-2 px-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">{f}</th>))}
                  <th className="py-2 px-2" />
                </tr>
              </thead>
              <tbody>
                {gridRows.map((r) => (
                  <tr key={r.control_id} data-testid={`crosswalk-row-${r.control_id}`} onClick={() => onOpen({ ref: r.control_id, title: r.name, subtitle: `${r.category} · owner ${r.owner || "—"}`,
                    obserraId: r.control_id, status: r.status, criticality: r.criticality, effectiveness: r.effectiveness,
                    why: `Obserra control status: ${r.status} at ${r.effectiveness}% effectiveness. ${r.compliant ? "Passing — evidence current." : "Not passing — remediation required."}`,
                    mappings: r.mappings })}
                    className="border-t border-border hover:bg-secondary/40 transition-colors cursor-pointer align-top">
                    <td className="py-3 pr-3 sticky left-0 bg-card">
                      <div className="flex items-center gap-2">
                        {r.compliant ? <CheckCircle2 className="w-4 h-4 text-low shrink-0" /> : <XCircle className="w-4 h-4 text-high shrink-0" />}
                        <div>
                          <div className="font-mono text-[11px] text-muted-foreground">{r.control_id}</div>
                          <div className="font-medium text-[13px] leading-tight">{r.name}</div>
                          <div className="text-[10px] text-muted-foreground">{r.category}</div>
                          <span className="inline-block mt-1 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm" style={{ background: `hsl(${CRIT_COL[r.criticality] || "35 90% 55%"} / 0.15)`, color: `hsl(${CRIT_COL[r.criticality] || "35 90% 55%"})` }} data-testid={`crosswalk-crit-${r.control_id}`}>{r.criticality}</span>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-2">
                      <span data-testid={`crosswalk-verdict-${r.control_id}`} className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${STATUS_COL[r.status] || "0 84% 60%"} / 0.15)`, color: `hsl(${STATUS_COL[r.status] || "0 84% 60%"})` }}>{r.compliant ? "Compliant" : "Non-compliant"}</span>
                      <div className="text-[10px] text-muted-foreground mt-1">{r.status} · {r.effectiveness}%</div>
                    </td>
                    <td className="py-3 px-2"><RiskBadge compliant={r.compliant} eff={r.effectiveness} testid={`crosswalk-risk-${r.control_id}`} /></td>
                    {frameworks.map((f) => {
                      const ids = r.mappings[f] || [];
                      return (
                        <td key={f} className="py-3 px-2">
                          {ids.length === 0 ? (<span className="text-[10px] text-muted-foreground/60 italic">n/a</span>) : (
                            <div className="flex flex-wrap gap-1">{ids.map((id) => (<span key={id} className={`text-[9px] font-mono px-1.5 py-0.5 rounded-sm border ${r.compliant ? "bg-low/10 text-low border-low/20" : "bg-high/10 text-high border-high/20"}`}>{id}</span>))}</div>
                          )}
                        </td>
                      );
                    })}
                    <td className="py-3 px-2"><ChevronRight className="w-4 h-4 text-muted-foreground" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center h-40"><Loader2 className="w-5 h-5 animate-spin text-primary" /></div>
        ) : (
          <div data-testid="framework-browser">
            <div className="text-[11px] text-muted-foreground mb-2">{shownCount.toLocaleString()} control{shownCount === 1 ? "" : "s"} shown · click any control for its AI risk rating &amp; recommended action</div>
            <div className="max-h-[640px] overflow-auto rounded-lg border border-border" data-testid="framework-control-list">
              {groups.map(({ fw, detail, ctrls }) => (
                <div key={fw}>
                  <div className="sticky top-0 z-10 bg-card/95 backdrop-blur px-3 py-2 border-b border-border flex flex-wrap items-center gap-2">
                    <span className="font-head font-bold text-sm">{fw}</span>
                    {detail && <>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-secondary/60">{detail.total.toLocaleString()} total</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-low/15 text-low">{detail.aligned} aligned</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-ai/10 text-ai">{detail.met.toLocaleString()} met</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-high/15 text-high">{detail.gap} gap</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md text-muted-foreground">{detail.meeting_pct}% meeting</span>
                    </>}
                    <span className="ml-auto text-[10px] text-muted-foreground">{ctrls.length.toLocaleString()} shown</span>
                  </div>
                  <div className="divide-y divide-border">
                    {ctrls.length === 0 ? <div className="py-4 text-center text-xs text-muted-foreground">No matching controls in {fw}.</div>
                      : ctrls.map((c) => <ControlRow key={`${fw}-${c.id}`} c={c} fw={fw} onOpen={onOpen} />)}
                  </div>
                </div>
              ))}
              {shownCount === 0 && <div className="py-8 text-center text-sm text-muted-foreground" data-testid="framework-empty">No controls match your search.</div>}
            </div>
          </div>
        )}
        <p className="text-[11px] text-muted-foreground mt-3">Every framework requirement is listed (<span className="text-low">Aligned</span> = evidence-backed · <span className="text-ai">Met</span> = baseline assumption, unverified · <span className="text-high">Gap</span> = open finding). <span className="text-foreground">Click any control</span> for its AI risk rating &amp; recommended action. Alignment updates automatically from the latest Security Scanner run — run a live self-scan or connect a source for independent evidence.</p>
      </div>
    </div>
  );
}

export default function CompliancePosture() {
  const [d, setD] = useState(null);
  const [x, setX] = useState(null);
  const [focus, setFocus] = useState(null);
  useEffect(() => {
    api.get("/controls/compliance").then((r) => setD(r.data)).catch(() => setD({ frameworks: [], gaps: [] }));
    api.get("/controls/crosswalk").then((r) => setX(r.data)).catch(() => setX({ frameworks: [], rows: [], summary: [] }));
  }, []);
  if (!d) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6" data-testid="compliance-posture-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2" style={{ color: `hsl(${ACCENT})` }}><ShieldCheck className="w-7 h-7" strokeWidth={1.5} /> Compliance Posture</h1>
        <p className="text-sm text-muted-foreground mt-1">Complete framework-to-control mapping across NIST 800-53, CIS v8, SOC 2, SSDF, PCI DSS &amp; ISO 27001 — every control shows its risk rating and the recommended action to close it.</p>
      </div>

      <AIInsight dashboard="Compliance Posture" accent={ACCENT} auto slug="compliance-posture" />

      <Tabs defaultValue="crosswalk">
        <TabsList className="bg-card">
          <TabsTrigger value="crosswalk" data-testid="tab-crosswalk">Framework → Control Mapping</TabsTrigger>
          <TabsTrigger value="posture" data-testid="tab-posture">Posture &amp; Gaps</TabsTrigger>
        </TabsList>
        <TabsContent value="crosswalk" className="mt-5">
          {x ? <Crosswalk x={x} reload={() => api.get("/controls/crosswalk").then((r) => setX(r.data))} onOpen={setFocus} /> : <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>}
        </TabsContent>
        <TabsContent value="posture" className="mt-5"><Posture d={d} onOpen={setFocus} /></TabsContent>
      </Tabs>

      <ControlDetailModal focus={focus} accent={ACCENT} onClose={() => setFocus(null)} />
    </div>
  );
}
