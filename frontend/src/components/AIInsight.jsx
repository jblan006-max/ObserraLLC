import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Sparkles, Loader2, Zap } from "lucide-react";

const KIND = { fact: "142 70% 45%", estimate: "35 90% 55%", risk: "0 84% 60%", prediction: "266 85% 66%" };

// Obserra-standard AI analyst summary for SAP UAC dashboards. Auto-runs on mount and
// asks the grounded SAP advisor (GET /api/sap/insight) to read the LIVE access model
// and return a board-grade headline + findings + next actions.
export function AIInsight({ dashboard, accent = "190 90% 50%", auto = false, slug, focus }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const ranRef = useRef(false);
  const tid = slug || dashboard.replace(/[^a-zA-Z0-9]/g, "-");

  const run = async () => {
    setLoading(true); setErr("");
    try {
      const r = await api.get(`/sap/insight${focus ? `?focus=${encodeURIComponent(focus)}` : ""}`);
      setData(r.data);
    } catch (e) {
      setErr(e.response?.data?.detail || "Advisor unavailable right now.");
    }
    setLoading(false);
  };

  useEffect(() => {
    if (auto && !ranRef.current) { ranRef.current = true; run(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto]);

  return (
    <div data-testid={`sap-insight-${tid}`}
      className="rounded-xl border p-5 bg-card backdrop-blur-sm"
      style={{ borderColor: `hsl(${accent} / 0.35)`, boxShadow: `inset 0 0 48px hsl(${accent} / 0.06)` }}>
      <div className="flex items-start gap-2.5">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg shrink-0" style={{ background: `hsl(${accent} / 0.15)` }}>
          <Sparkles className="w-4 h-4" style={{ color: `hsl(${accent})` }} strokeWidth={1.5} />
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="font-head font-bold text-sm">AI Analyst — {dashboard}</div>
            <button data-testid={`sap-insight-run-${tid}`} onClick={run} disabled={loading}
              className="flex items-center gap-1.5 text-[11px] font-head font-bold px-3 py-1 rounded-full disabled:opacity-50 transition-transform active:scale-95 shrink-0"
              style={{ background: `hsl(${accent})`, color: "#050810" }}>
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              {data ? "Refresh" : "Analyze"}
            </button>
          </div>
          <div className="text-[10px] font-mono text-muted-foreground truncate">
            {data ? `${data.model} · grounded in the live SAP access model · ${new Date(data.generated_at).toLocaleTimeString()}` : "Live summary of your SAP access posture"}
          </div>
        </div>
      </div>

      {err && <div className="mt-3 text-xs text-crit" data-testid="sap-insight-error">{err}</div>}
      {loading && !data && <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading the live access model &amp; summarizing…</div>}

      {data && (
        <div className="mt-4 space-y-3">
          {data.headline && <div className="font-head font-bold text-base leading-snug" style={{ color: `hsl(${accent})` }}>{data.headline}</div>}
          <ul className="space-y-2">
            {(data.insights || []).map((it, i) => (
              <li key={i} data-testid={`sap-insight-item-${i}`} className="flex items-start gap-2.5 text-sm text-foreground/90 leading-relaxed">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: `hsl(${KIND[it.kind] || accent})` }} />
                <span>{it.text} {it.kind && <span className="text-[9px] font-mono uppercase tracking-wider align-middle" style={{ color: `hsl(${KIND[it.kind] || accent})` }}>· {it.kind}</span>}</span>
              </li>
            ))}
          </ul>
          {(data.actions || []).length > 0 && (
            <div className="pt-3 border-t border-border">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">Recommended actions</div>
              <ul className="space-y-1">
                {data.actions.map((a, i) => (
                  <li key={i} className="text-sm flex items-start gap-2"><span style={{ color: `hsl(${accent})` }}>→</span> {a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
