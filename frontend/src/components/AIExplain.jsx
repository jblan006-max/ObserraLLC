import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Sparkles, Loader2 } from "lucide-react";

const SEV = { risk: "0 84% 60%", watch: "35 90% 55%", opportunity: "142 70% 45%", info: "199 70% 50%" };

// Lightweight AI insight + recommendation for a clicked item that isn't a CVE-grounded entity
// (spend lines, graph nodes, generic cards). Grounded in the supplied live context.
export function AIExplain({ title, kind = "item", context = {}, accent = "266 85% 66%" }) {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(false);
  const ctxKey = JSON.stringify(context);

  useEffect(() => {
    let ok = true; setLoading(true);
    api.post("/advisor/explain", { title, kind, context })
      .then((r) => { if (ok) setD(r.data); })
      .catch(() => { if (ok) setD(null); })
      .finally(() => { if (ok) setLoading(false); });
    return () => { ok = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, kind, ctxKey]);

  const sc = d ? (SEV[d.severity] || accent) : accent;
  return (
    <div data-testid="ai-explain" className="rounded-lg p-3 border" style={{ borderColor: `hsl(${accent} / 0.35)`, background: `hsl(${accent} / 0.05)` }}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider" style={{ color: `hsl(${accent})` }}><Sparkles className="w-3 h-3" /> AI insight &amp; recommendation</div>
        {d?.severity && <span data-testid="ai-explain-severity" className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full" style={{ background: `hsl(${sc} / 0.15)`, color: `hsl(${sc})` }}>{String(d.severity).toUpperCase()}</span>}
      </div>
      {loading && !d && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing this item…</div>}
      {d && (
        <div className="space-y-2">
          {d.summary && <p className="text-sm text-foreground/90 leading-relaxed" data-testid="ai-explain-summary">{d.summary}</p>}
          {d.recommendation && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: `hsl(${accent})` }}>Recommendation</div>
              <p className="text-sm text-foreground/90" data-testid="ai-explain-recommendation">{d.recommendation}</p>
            </div>
          )}
          {d.steps?.length > 0 && (
            <ul className="space-y-1">
              {d.steps.map((s, i) => <li key={i} className="text-[12px] flex items-start gap-2"><span style={{ color: `hsl(${accent})` }}>→</span> {s}</li>)}
            </ul>
          )}
          {d.model && <div className="text-[9px] font-mono text-muted-foreground pt-1">{d.model} · grounded in live data</div>}
        </div>
      )}
    </div>
  );
}
