import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, Download, Link2, Loader2, Target, TrendingDown, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { AIExplain } from "@/components/AIExplain";
import { DataClassBadge, PALETTE, ProgressBar, StatusPill } from "@/components/control-intelligence/shared";

const pal = (i) => PALETTE[i % PALETTE.length];
const norm = (s) => String(s || "").trim().toLowerCase();

// controls whose framework map references this framework (live control feed)
function mappedControls(controls, frameworkName) {
  const target = norm(frameworkName);
  return (controls || [])
    .map((c) => {
      const fw = c.frameworks || {};
      const key = Object.keys(fw).find((k) => norm(k) === target || norm(k).includes(target) || target.includes(norm(k)));
      if (!key) return null;
      const refs = Array.isArray(fw[key]) ? fw[key] : fw[key] ? [String(fw[key])] : [];
      return { control: c, refs };
    })
    .filter(Boolean);
}

export default function FrameworkDetailModal({ framework, controls, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const name = framework.framework;
  const controlsTotal = Number(framework.controls || 0);
  const passing = Number(framework.passing || 0);
  const coverage = Number(framework.coverage || 0);
  const gap = Math.max(0, controlsTotal - passing);
  const mapped = mappedControls(controls, name);

  const [busy, setBusy] = useState(false);
  const exportPdf = async () => {
    setBusy(true);
    try {
      const nonPassing = mapped.filter((m) => m.control.status !== "Passing");
      const blocks = [
        { heading: `${name} — Framework Assurance`, lines: [
          `Coverage: ${coverage}%`,
          `Passing controls: ${passing}/${controlsTotal}`,
          `Open gaps: ${gap}`,
          `Risk level (modelled): ${riskLevel}`,
        ] },
        { heading: "Mapped controls (live feed)", lines: mapped.length
          ? mapped.map((m) => `[${m.control.control_id}] ${m.control.name} — ${m.control.status}, effectiveness ${m.control.effectiveness}%` + (m.refs.length ? ` (refs: ${m.refs.join(", ")})` : ""))
          : ["No controls map to this framework in the current feed."] },
        { heading: "Gaps / attention", lines: nonPassing.length
          ? nonPassing.map((m) => `[${m.control.control_id}] ${m.control.name} — ${m.control.status}`)
          : ["No open gaps — all mapped controls are passing."] },
        { heading: "Defensibility", lines: ["Coverage, passing counts and control mappings are FACT values from the live Obserra control feed. Risk level is MODELLED. AI narrative is a recommendation."] },
      ];
      const res = await api.post("/studio/report/pdf", {
        title: `${name} Framework Assurance`,
        ai_narrative: `Single-framework assurance deep-dive for ${name}, generated from the live Obserra control feed.`,
        blocks,
      }, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `obserra-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-assurance.pdf`;
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      toast.success(`${name} assurance PDF generated.`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to export framework PDF.");
    } finally {
      setBusy(false);
    }
  };

  const riskLevel = coverage >= 80 ? "Low" : coverage >= 60 ? "Medium" : coverage >= 40 ? "High" : "Critical";
  const riskAccent = coverage >= 80 ? "142 70% 45%" : coverage >= 60 ? "35 90% 55%" : coverage >= 40 ? "24 90% 55%" : "0 84% 60%";

  const explainContext = {
    framework: name,
    coverage_percent: coverage,
    passing_controls: passing,
    total_controls: controlsTotal,
    gap_count: gap,
    mapped_controls: mapped.slice(0, 40).map((m) => ({
      control_id: m.control.control_id, name: m.control.name, status: m.control.status,
      effectiveness: m.control.effectiveness, refs: m.refs,
    })),
  };

  return createPortal((
    <div className="fixed inset-0 z-[70] bg-black/65 backdrop-blur-sm flex items-center justify-center p-4" data-testid="ci-framework-detail-modal">
      <div className="w-full max-w-4xl max-h-[92vh] overflow-y-auto bg-card fact-border rounded-xl">
        <div className="sticky top-0 z-10 bg-card border-b border-border px-5 py-4 flex items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[10px] text-ai">COMPLIANCE FRAMEWORK</div>
            <h2 className="font-head font-black text-2xl mt-1">{name}</h2>
            <div className="flex flex-wrap gap-1.5 mt-2">
              <StatusPill value={coverage >= 75 ? "Strong" : coverage >= 55 ? "Watch" : "High gap"} />
              <DataClassBadge kind="FACT" />
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={exportPdf} disabled={busy} data-testid="ci-framework-export"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Export PDF
            </button>
            <button onClick={onClose} data-testid="ci-framework-detail-close" className="p-2 rounded-md hover:bg-secondary"><X className="w-5 h-5" /></button>
          </div>
        </div>

        <div className="p-5 space-y-5">
          {/* Details + Scoring */}
          <div className="grid md:grid-cols-4 gap-3">
            <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground flex items-center gap-1"><Target className="w-3 h-3" /> Coverage (score)</div><div className="font-head font-black text-2xl mt-1" style={{ color: `hsl(${riskAccent})` }}>{coverage}%</div></div>
            <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Passing controls</div><div className="font-head font-black text-2xl mt-1">{passing}/{controlsTotal}</div></div>
            <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground flex items-center gap-1"><TrendingDown className="w-3 h-3" /> Open gaps</div><div className="font-head font-black text-2xl mt-1">{gap}</div></div>
            <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Risk</div><div className="font-head font-black text-2xl mt-1" style={{ color: `hsl(${riskAccent})` }}>{riskLevel}</div></div>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-1"><span className="text-muted-foreground">Coverage score</span><span className="font-mono">{coverage}%</span></div>
            <ProgressBar value={coverage} accent={riskAccent} />
          </div>

          {/* AI recommendations & fixes */}
          <AIExplain title={`${name} framework coverage`} kind="compliance framework coverage control alignment gaps remediation" context={explainContext} accent="262 83% 66%" />

          {/* Control alignment — ties framework -> live controls feed */}
          <div>
            <div className="font-head font-bold flex items-center gap-2"><Link2 className="w-4 h-4 text-ai" /> Control alignment</div>
            <div className="text-xs text-muted-foreground mt-1">Controls from the live Obserra control feed mapped to {name}.</div>
            {mapped.length === 0 ? (
              <div className="text-sm text-muted-foreground mt-3">No controls map to this framework in the current feed.</div>
            ) : (
              <div className="mt-3 space-y-2 max-h-96 overflow-y-auto">
                {mapped.map((m, i) => (
                  <div key={m.control.control_id} className="rounded-lg border border-border p-3" style={{ borderLeft: `3px solid hsl(${pal(i)})` }}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-mono text-[10px] text-ai">{m.control.control_id}</div>
                        <div className="font-medium text-sm truncate">{m.control.name}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="font-mono text-xs" style={{ color: `hsl(${m.control.effectiveness >= 75 ? "142 70% 45%" : m.control.effectiveness >= 55 ? "35 90% 55%" : "0 84% 60%"})` }}>{m.control.effectiveness}%</span>
                        <StatusPill value={m.control.status} />
                      </div>
                    </div>
                    {m.refs.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {m.refs.map((r) => <span key={r} className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">{r}</span>)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  ), document.body);
}
