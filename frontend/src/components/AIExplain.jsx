import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Sparkles, Loader2 } from "lucide-react";

const SEV = { risk: "0 84% 60%", watch: "35 90% 55%", opportunity: "142 70% 45%", info: "199 70% 50%" };
const money = (n) => n == null ? null : n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}k` : `$${Math.round(n)}`;

// Module-level cache so hovering a card can WARM its AI brief; clicking then shows it instantly.
const _cache = new Map();
const _key = (title, kind, context, groundOnly) => JSON.stringify({ title, kind, context, groundOnly });

export function prefetchExplain(title, kind = "item", context = {}, groundOnly = false) {
  if (!title) return Promise.resolve(null);
  const key = _key(title, kind, context, groundOnly);
  const hit = _cache.get(key);
  if (hit) return hit.promise || Promise.resolve(hit.data);
  const promise = api.post("/advisor/explain", { title, kind, context, ground_only_context: groundOnly })
    .then((r) => { _cache.set(key, { data: r.data }); return r.data; })
    .catch(() => { _cache.delete(key); return null; });
  _cache.set(key, { promise });
  return promise;
}

// Lightweight AI insight + recommendation + board-defensible $ impact for a clicked item.
// Grounded in the supplied live context (see backend /advisor/explain).
export function AIExplain({ title, kind = "item", context = {}, accent = "266 85% 66%", groundOnly = false }) {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(false);
  const ctxKey = JSON.stringify(context);

  useEffect(() => {
    const key = _key(title, kind, context, groundOnly);
    const hit = _cache.get(key);
    if (hit?.data) { setD(hit.data); setLoading(false); return; }
    let ok = true; setLoading(true); setD(null);
    (hit?.promise || prefetchExplain(title, kind, context, groundOnly)).then((data) => {
      if (ok) { setD(data); setLoading(false); }
    });
    return () => { ok = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, kind, ctxKey, groundOnly]);

  const sc = d ? (SEV[d.severity] || accent) : accent;
  const hasImpact = d && (d.at_stake != null || d.reduction_if_fixed != null);
  const pct = d && d.at_stake && d.reduction_if_fixed ? Math.round(Math.min(100, (d.reduction_if_fixed / d.at_stake) * 100)) : null;
  return (
    <div data-testid="ai-explain" className="rounded-lg p-3 border" style={{ borderColor: `hsl(${accent} / 0.35)`, background: `hsl(${accent} / 0.05)` }}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider" style={{ color: `hsl(${accent})` }}><Sparkles className="w-3 h-3" /> AI insight &amp; recommendation</div>
        {d?.severity && <span data-testid="ai-explain-severity" className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full" style={{ background: `hsl(${sc} / 0.15)`, color: `hsl(${sc})` }}>{String(d.severity).toUpperCase()}</span>}
      </div>
      {hasImpact && (
        <div data-testid="ai-impact" className="flex flex-wrap items-center gap-2 mb-2">
          {d.at_stake != null && (
            <span data-testid="ai-impact-atstake" className="text-xs font-mono font-bold px-2.5 py-1 rounded-md" style={{ background: "hsl(15 80% 55% / 0.15)", color: "hsl(15 80% 55%)" }}>
              {money(d.at_stake)} at stake{d.at_stake_scope === "portfolio" ? " · portfolio" : ""}
            </span>
          )}
          {d.reduction_if_fixed != null && (
            <span data-testid="ai-impact-reduction" className="text-xs font-mono font-bold px-2.5 py-1 rounded-md" style={{ background: "hsl(142 70% 45% / 0.15)", color: "hsl(142 70% 45%)" }}>
              ~{money(d.reduction_if_fixed)}{pct != null ? ` (${pct}%)` : ""} reduction if fixed{d.reduction_scope === "modelled" ? " · modelled" : d.reduction_scope === "portfolio" ? " · portfolio" : ""}
            </span>
          )}
        </div>
      )}
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
