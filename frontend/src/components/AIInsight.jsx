import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Sparkles, Loader2, Zap } from "lucide-react";

const KIND = { fact: "142 70% 45%", estimate: "35 90% 55%", prediction: "266 85% 66%" };

// AI-native analysis card. Drops onto any dashboard and asks the Obserrian Advisor to
// read that dashboard's LIVE data and return grounded findings + next actions.
export function AIInsight({ dashboard, accent = "190 90% 50%" }) {
  const { mode } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const run = async () => {
    setLoading(true); setErr("");
    try {
      const r = await api.post("/advisor/insight", { dashboard, mode: mode || "executive" });
      setData(r.data);
    } catch (e) {
      setErr(e.response?.data?.detail || "Advisor unavailable right now.");
    }
    setLoading(false);
  };

  return (
    <div data-testid={`ai-insight-${dashboard.replace(/[^a-zA-Z0-9]/g, "-")}`}
      className="rounded-xl border p-5 bg-card backdrop-blur-sm"
      style={{ borderColor: `hsl(${accent} / 0.3)`, boxShadow: `inset 0 0 44px hsl(${accent} / 0.05)` }}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg shrink-0" style={{ background: `hsl(${accent} / 0.15)` }}>
            <Sparkles className="w-4 h-4" style={{ color: `hsl(${accent})` }} strokeWidth={1.5} />
          </span>
          <div className="min-w-0">
            <div className="font-head font-bold text-sm">AI Insight — {dashboard}</div>
            <div className="text-[10px] font-mono text-muted-foreground truncate">
              {data ? `${data.model} · grounded in live data · ${new Date(data.generated_at).toLocaleTimeString()}` : "Obserrian analysis of this dashboard's live signals"}
            </div>
          </div>
        </div>
        <button data-testid={`ai-insight-run-${dashboard.replace(/[^a-zA-Z0-9]/g, "-")}`} onClick={run} disabled={loading}
          className="flex items-center gap-1.5 text-xs font-head font-bold px-3.5 py-1.5 rounded-full disabled:opacity-50 transition-transform active:scale-95 shrink-0"
          style={{ background: `hsl(${accent})`, color: "#050810" }}>
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
          {data ? "Refresh" : "Analyze"}
        </button>
      </div>

      {err && <div className="mt-3 text-xs text-crit" data-testid="ai-insight-error">{err}</div>}
      {!data && !loading && !err && (
        <p className="mt-3 text-xs text-muted-foreground">Tap <span style={{ color: `hsl(${accent})` }}>Analyze</span> — the advisor reads this dashboard's live data and returns board-grade context, findings, and next actions.</p>
      )}
      {loading && <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading live signals & reasoning…</div>}

      {data && (
        <div className="mt-4 space-y-3">
          {data.headline && <div className="font-head font-bold text-base leading-snug" style={{ color: `hsl(${accent})` }}>{data.headline}</div>}
          <ul className="space-y-2">
            {(data.insights || []).map((it, i) => (
              <li key={i} data-testid={`ai-insight-item-${i}`} className="flex items-start gap-2.5 text-sm text-foreground/90 leading-relaxed">
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
