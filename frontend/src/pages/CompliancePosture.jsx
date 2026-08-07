import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { ShieldCheck, Loader2, AlertTriangle, ArrowRight } from "lucide-react";

const col = (v) => (v >= 75 ? "142 70% 45%" : v >= 55 ? "35 90% 55%" : "0 84% 60%");
const STATUS_COL = { "Failing": "0 84% 60%", "Evidence Stale": "35 90% 55%", "Drifting": "266 85% 66%" };
const fade = { hidden: { opacity: 0, y: 12 }, show: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.05, duration: 0.4 } }) };

export default function CompliancePosture() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/controls/compliance").then((r) => setD(r.data)).catch(() => setD({ frameworks: [], gaps: [] })); }, []);
  if (!d) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-8" data-testid="compliance-posture-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><ShieldCheck className="w-7 h-7 text-primary" /> Compliance Posture</h1>
        <p className="text-sm text-muted-foreground mt-1">Leadership view of alignment across NIST CSF 2.0, NIST 800-53, ISO 27001, SOC 2 &amp; CISA CPG — and the gaps to close first.</p>
      </div>

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
