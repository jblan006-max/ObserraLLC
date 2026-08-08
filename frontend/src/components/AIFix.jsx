import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Sparkles, Loader2, ShieldAlert } from "lucide-react";

const RATE = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };

// Reusable AI risk-rating + fix block. Rating is grounded in compliance-control gaps + CVE/KEV
// analysis (server-side); the recommendation is AI-written. Drops into any detail view.
export function AIFix({ entity, refId, accent = "266 85% 66%" }) {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!refId) { setD(null); return; }
    let ok = true; setLoading(true);
    api.post("/advisor/fix", { entity, ref: refId })
      .then((r) => { if (ok) setD(r.data); })
      .catch(() => { if (ok) setD(null); })
      .finally(() => { if (ok) setLoading(false); });
    return () => { ok = false; };
  }, [entity, refId]);

  const rc = d ? RATE[d.rating] || accent : accent;
  return (
    <div data-testid="ai-fix" className="rounded-lg p-3 border" style={{ borderColor: `hsl(${accent} / 0.35)`, background: `hsl(${accent} / 0.05)` }}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider" style={{ color: `hsl(${accent})` }}><Sparkles className="w-3 h-3" /> AI risk rating &amp; fix</div>
        {d && <span data-testid="ai-fix-rating" className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full" style={{ background: `hsl(${rc} / 0.15)`, color: `hsl(${rc})` }}>{d.rating} RISK · {d.score}/100</span>}
      </div>
      {loading && !d && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing controls, CVE &amp; KEV signals…</div>}
      {d && (
        <div className="space-y-2">
          {d.rationale?.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><ShieldAlert className="w-3 h-3" /> Why this rating</div>
              <ul className="space-y-1" data-testid="ai-fix-rationale">
                {d.rationale.map((r, i) => <li key={i} className="text-[11px] text-foreground/85 flex gap-1.5"><span style={{ color: `hsl(${rc})` }}>•</span> {r}</li>)}
              </ul>
            </div>
          )}
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: `hsl(${accent})` }}>AI recommendation to fix</div>
            <p className="text-sm text-foreground/90 leading-relaxed" data-testid="ai-fix-recommendation">{d.recommendation}</p>
            {d.steps?.length > 0 && (
              <ul className="mt-1.5 space-y-1">
                {d.steps.map((s, i) => <li key={i} className="text-[12px] flex items-start gap-2"><span style={{ color: `hsl(${accent})` }}>→</span> {s}</li>)}
              </ul>
            )}
          </div>
          {d.model && <div className="text-[9px] font-mono text-muted-foreground pt-1">{d.model} · grounded in live scan + controls</div>}
        </div>
      )}
    </div>
  );
}
