import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { ShieldCheck, Loader2, AlertTriangle, ArrowRight, CheckCircle2, XCircle, Grid3x3 } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const col = (v) => (v >= 75 ? "142 70% 45%" : v >= 55 ? "35 90% 55%" : "0 84% 60%");
const STATUS_COL = { "Failing": "0 84% 60%", "Evidence Stale": "35 90% 55%", "Drifting": "266 85% 66%", "Passing": "142 70% 45%" };
const CRIT_COL = { "Critical": "0 84% 60%", "High": "15 80% 55%", "Medium": "35 90% 55%", "Low": "142 70% 45%" };
const fade = { hidden: { opacity: 0, y: 12 }, show: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.05, duration: 0.4 } }) };

function Posture({ d }) {
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <motion.div custom={0} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-4 bg-card fact-border rounded-xl p-6 flex flex-col items-center justify-center text-center">
          <div className="text-xs text-muted-foreground mb-1">Overall alignment</div>
          <div data-testid="compliance-overall" className="font-head font-black text-6xl tracking-tight" style={{ color: `hsl(${col(d.overall || 0)})` }}>{d.overall || 0}%</div>
          <div className="text-[11px] text-muted-foreground mt-2">{d.passing}/{d.total_controls} controls passing across {d.frameworks?.length || 0} frameworks</div>
        </motion.div>

        <motion.div custom={1} variants={fade} initial="hidden" animate="show" className="col-span-full lg:col-span-8 bg-card fact-border rounded-xl p-6">
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
        <div className="flex items-center gap-2 mb-4"><AlertTriangle className="w-4 h-4 text-high" /><h2 className="font-head font-bold text-lg">Top gaps to close first</h2></div>
        {(!d.gaps || d.gaps.length === 0) ? (
          <div className="text-sm text-low py-6 text-center">✓ All mapped controls are passing — no open compliance gaps.</div>
        ) : (
          <div className="space-y-3">
            {d.gaps.map((g, i) => (
              <div key={g.control_id} data-testid={`gap-${g.control_id}`} className="flex items-start gap-4 p-4 rounded-lg bg-secondary/30">
                <span className="font-head font-black text-lg text-muted-foreground w-6 shrink-0">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-mono text-xs text-muted-foreground">{g.control_id}</span>
                    <span className="text-sm font-medium">{g.name}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${STATUS_COL[g.status] || "0 84% 60%"} / 0.15)`, color: `hsl(${STATUS_COL[g.status] || "0 84% 60%"})` }}>{g.status}</span>
                    <span className="text-[10px] text-muted-foreground">· {g.effectiveness}% effective · {g.owner}</span>
                  </div>
                  <div className="text-xs text-foreground/80 flex items-start gap-1"><ArrowRight className="w-3.5 h-3.5 mt-0.5 text-ai shrink-0" /> {g.recommendation}</div>
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {g.frameworks.map((fw) => <span key={fw} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-high/10 text-high border border-high/20">{fw}</span>)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}

function Crosswalk({ x }) {
  const [q, setQ] = useState("");
  const [fw, setFw] = useState("all");
  const cols = fw === "all" ? x.frameworks : [fw];
  const ql = q.trim().toLowerCase();
  const rows = x.rows.filter((r) => {
    if (fw !== "all" && (!r.mappings[fw] || r.mappings[fw].length === 0)) return false;
    if (!ql) return true;
    const hay = [r.control_id, r.name, r.category, r.criticality, ...Object.values(r.mappings).flat()].join(" ").toLowerCase();
    return hay.includes(ql);
  });
  const [detail, setDetail] = useState(null);
  const [dLoading, setDLoading] = useState(false);
  useEffect(() => {
    if (fw === "all") { setDetail(null); return; }
    setDLoading(true);
    api.get(`/controls/framework/${encodeURIComponent(fw)}`).then((r) => setDetail(r.data)).catch(() => setDetail(null)).finally(() => setDLoading(false));
  }, [fw]);
  const detailControls = (detail?.controls || []).filter((c) => {
    if (!ql) return true;
    return `${c.id} ${c.group} ${(c.mapped_to || []).map((m) => m.control_id + " " + m.name).join(" ")}`.toLowerCase().includes(ql);
  });
  return (
    <div className="space-y-6" data-testid="crosswalk-panel">
      {/* Per-framework compliant vs not summary — click to focus a framework */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {x.summary.map((s) => {
          const ok = s.status === "Compliant";
          const active = fw === s.framework;
          return (
            <button key={s.framework} type="button" onClick={() => setFw(active ? "all" : s.framework)}
              data-testid={`crosswalk-summary-${s.framework.replace(/[^a-zA-Z0-9]/g, "-")}`}
              className={`text-left rounded-xl p-4 border transition-all ${active ? "ring-2 ring-primary" : ""} ${ok ? "border-low/30 bg-low/5" : "border-high/30 bg-high/5"}`}>
              <div className="flex items-center justify-between">
                <div className="font-head font-bold text-sm">{s.framework}</div>
                {ok ? <CheckCircle2 className="w-4 h-4 text-low" /> : <XCircle className="w-4 h-4 text-high" />}
              </div>
              <div className="text-[10px] text-muted-foreground leading-tight mt-0.5">{s.full_name}</div>
              <div className="font-head font-black text-2xl tracking-tight mt-2" style={{ color: `hsl(${col(s.compliant_pct)})` }}>{s.compliant_pct}%</div>
              <div className="text-[11px] text-muted-foreground">{s.compliant}/{s.assessed_controls} assessed controls compliant</div>
              <div className="text-[10px] text-muted-foreground/70 mt-0.5">{s.mapped_ref_count} of {s.catalog_controls?.toLocaleString?.() ?? s.catalog_controls} catalog controls mapped · {s.coverage_pct}% coverage</div>
              <span className={`inline-block mt-2 text-[9px] font-mono px-2 py-0.5 rounded-full ${ok ? "bg-low/15 text-low" : "bg-high/15 text-high"}`}>{s.status}</span>
            </button>
          );
        })}
      </div>

      {/* Compliance by control criticality */}
      {x.by_criticality && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="crosswalk-criticality">
          <div className="flex items-center gap-2 mb-3"><AlertTriangle className="w-4 h-4 text-high" /><h2 className="font-head font-bold text-lg">Compliance by control criticality</h2></div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {x.by_criticality.map((b) => (
              <div key={b.criticality} data-testid={`crit-tier-${b.criticality}`} className="rounded-lg p-4 border" style={{ borderColor: `hsl(${CRIT_COL[b.criticality]} / 0.35)`, background: `hsl(${CRIT_COL[b.criticality]} / 0.06)` }}>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full" style={{ background: `hsl(${CRIT_COL[b.criticality]} / 0.15)`, color: `hsl(${CRIT_COL[b.criticality]})` }}>{b.criticality}</span>
                  <span className="text-[10px] text-muted-foreground">{b.controls} control{b.controls === 1 ? "" : "s"}</span>
                </div>
                <div className="font-head font-black text-2xl tracking-tight mt-2" style={{ color: `hsl(${col(b.compliant_pct)})` }} data-testid={`crit-pct-${b.criticality}`}>{b.compliant_pct}%</div>
                <div className="text-[11px] text-muted-foreground">{b.compliant}/{b.controls} compliant · {b.non_compliant} open</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Framework selector + search + browser/matrix */}
      <div className="bg-card fact-border rounded-xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2"><Grid3x3 className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-lg">{fw === "all" ? "Control crosswalk — Obserra controls mapped" : `Every ${fw} control — alignment`}</h2></div>
          <div className="flex items-center gap-2">
            <select data-testid="crosswalk-framework-select" value={fw} onChange={(e) => setFw(e.target.value)} className="bg-secondary/60 rounded-md px-3 py-2 text-xs outline-none focus:ring-1 focus:ring-primary">
              <option value="all">All frameworks (mapping)</option>
              {x.frameworks.map((f) => <option key={f} value={f}>{f} — every control</option>)}
            </select>
            <input data-testid="crosswalk-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search controls, IDs, refs…" className="bg-secondary/60 rounded-md px-3 py-2 text-xs outline-none focus:ring-1 focus:ring-primary w-56" />
          </div>
        </div>

        {fw !== "all" ? (
          <div data-testid="framework-browser">
            {dLoading || !detail ? (
              <div className="flex items-center justify-center h-40"><Loader2 className="w-5 h-5 animate-spin text-primary" /></div>
            ) : (
              <>
                <div className="flex flex-wrap gap-2 mb-3 text-[11px]">
                  <span className="px-2 py-1 rounded-md bg-secondary/60" data-testid="fw-total">{detail.total.toLocaleString()} controls</span>
                  <span className="px-2 py-1 rounded-md bg-low/15 text-low" data-testid="fw-aligned">{detail.aligned} aligned</span>
                  <span className="px-2 py-1 rounded-md bg-high/15 text-high" data-testid="fw-gap">{detail.gap} gap</span>
                  <span className="px-2 py-1 rounded-md bg-secondary/60 text-muted-foreground" data-testid="fw-unassessed">{detail.not_assessed.toLocaleString()} not assessed</span>
                  <span className="px-2 py-1 rounded-md bg-ai/10 text-ai">{detail.coverage_pct}% catalog coverage</span>
                </div>
                <div className="text-[11px] text-muted-foreground mb-2">{detailControls.length.toLocaleString()} shown</div>
                <div className="max-h-[520px] overflow-auto rounded-lg border border-border divide-y divide-border" data-testid="framework-control-list">
                  {detailControls.map((c) => {
                    const sc = c.status === "aligned" ? "142 70% 45%" : c.status === "gap" ? "0 84% 60%" : "215 15% 55%";
                    const label = c.status === "aligned" ? "Aligned" : c.status === "gap" ? "Gap" : "Not assessed";
                    return (
                      <div key={c.id} data-testid={`fw-control-${c.id}`} className="flex items-start gap-3 px-3 py-2.5">
                        {c.status === "aligned" ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" style={{ color: `hsl(${sc})` }} /> : c.status === "gap" ? <XCircle className="w-4 h-4 mt-0.5 shrink-0" style={{ color: `hsl(${sc})` }} /> : <span className="w-3.5 h-3.5 mt-0.5 shrink-0 rounded-full border border-muted-foreground/40" />}
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-[12px] font-medium">{c.id}</span>
                            <span className="text-[10px] text-muted-foreground">{c.group}</span>
                          </div>
                          {c.mapped_to.length > 0 && (
                            <div className="text-[10px] text-muted-foreground mt-0.5">Covered by {c.mapped_to.map((m) => `${m.control_id} ${m.name}`).join(", ")}</div>
                          )}
                        </div>
                        <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full shrink-0" style={{ background: `hsl(${sc} / 0.15)`, color: `hsl(${sc})` }}>{label}</span>
                      </div>
                    );
                  })}
                  {detailControls.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground" data-testid="framework-empty">No controls match your search.</div>}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm min-w-[880px]" data-testid="crosswalk-table">
              <thead>
                <tr className="text-left">
                  <th className="py-2 pr-3 text-xs font-mono uppercase tracking-wider text-muted-foreground sticky left-0 bg-card">Control</th>
                  <th className="py-2 px-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">Status</th>
                  {x.frameworks.map((f) => (<th key={f} className="py-2 px-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">{f}</th>))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.control_id} data-testid={`crosswalk-row-${r.control_id}`} className="border-t border-border align-top">
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
                    {x.frameworks.map((f) => {
                      const ids = r.mappings[f] || [];
                      return (
                        <td key={f} className="py-3 px-2">
                          {ids.length === 0 ? (<span className="text-[10px] text-muted-foreground/60 italic">n/a</span>) : (
                            <div className="flex flex-wrap gap-1">{ids.map((id) => (<span key={id} className={`text-[9px] font-mono px-1.5 py-0.5 rounded-sm border ${r.compliant ? "bg-low/10 text-low border-low/20" : "bg-high/10 text-high border-high/20"}`}>{id}</span>))}</div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-[11px] text-muted-foreground mt-3">Pick a framework to browse <span className="text-foreground">every control</span> and its alignment (Aligned = a mapped Obserra control is passing · Gap = mapped but failing/stale · Not assessed = no Obserra control mapped yet). "All frameworks" shows Obserra's controls and their exact mapped control IDs.</p>
      </div>
    </div>
  );
}

export default function CompliancePosture() {
  const [d, setD] = useState(null);
  const [x, setX] = useState(null);
  useEffect(() => {
    api.get("/controls/compliance").then((r) => setD(r.data)).catch(() => setD({ frameworks: [], gaps: [] }));
    api.get("/controls/crosswalk").then((r) => setX(r.data)).catch(() => setX({ frameworks: [], rows: [], summary: [] }));
  }, []);
  if (!d) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6" data-testid="compliance-posture-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><ShieldCheck className="w-7 h-7 text-primary" /> Compliance Posture</h1>
        <p className="text-sm text-muted-foreground mt-1">Alignment and an exact control crosswalk across NIST 800-53, CIS v8, SOC 2, SSDF, PCI DSS &amp; ISO 27001 — showing what's compliant versus what isn't.</p>
      </div>

      <Tabs defaultValue="posture">
        <TabsList className="bg-card">
          <TabsTrigger value="posture" data-testid="tab-posture">Posture &amp; Gaps</TabsTrigger>
          <TabsTrigger value="crosswalk" data-testid="tab-crosswalk">Control Crosswalk</TabsTrigger>
        </TabsList>
        <TabsContent value="posture" className="mt-5"><Posture d={d} /></TabsContent>
        <TabsContent value="crosswalk" className="mt-5">
          {x ? <Crosswalk x={x} /> : <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>}
        </TabsContent>
      </Tabs>
    </div>
  );
}
