import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ShieldCheck, Loader2 } from "lucide-react";

const LABEL_STYLE = {
  "Grounded": "text-low",
  "Partially grounded": "text-med",
  "Unverified": "text-crit",
};

const scoreColor = (s) => (s == null ? "text-muted-foreground" : s >= 80 ? "text-low" : s >= 50 ? "text-med" : "text-crit");

const Stat = ({ label, value, cls = "text-foreground", testid }) => (
  <div className="rounded-lg border border-border bg-card p-4" data-testid={testid}>
    <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{label}</div>
    <div className={`text-2xl font-head font-bold mt-1 ${cls}`}>{value}</div>
  </div>
);

export default function AIGroundingMonitor() {
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      api.get("/hallucination/summary?days=30").then((r) => setSummary(r.data)).catch(() => setSummary(null)),
      api.get("/hallucination/log?limit=50").then((r) => setEvents(r.data.events || [])).catch(() => setEvents([])),
    ]).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-6" data-testid="ai-grounding-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-head font-bold flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-ai" /> AI Grounding Monitor
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Every AI answer is checked against your live control data. Ungrounded claims are flagged — warn-only, nothing is blocked.
          </p>
        </div>
        <button onClick={load} data-testid="grounding-refresh" className="text-xs font-head font-bold px-3 py-2 rounded-md border border-border bg-secondary/40 hover:bg-secondary transition-colors">Refresh</button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
      ) : (
        <>
          <div className="grid sm:grid-cols-4 gap-4" data-testid="grounding-summary">
            <Stat label="Answers checked (30d)" value={summary?.total ?? 0} testid="grounding-total" />
            <Stat label="Avg grounding score" value={summary?.avg_score ?? "—"} cls={scoreColor(summary?.avg_score)} testid="grounding-avg" />
            <Stat label="Flagged answers" value={`${summary?.flagged ?? 0} · ${summary?.flagged_pct ?? 0}%`} cls={(summary?.flagged_pct || 0) > 0 ? "text-med" : "text-low"} testid="grounding-flagged" />
            <Stat label="Surfaces monitored" value={(summary?.by_surface || []).length} testid="grounding-surfaces" />
          </div>

          {(summary?.by_surface || []).length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4" data-testid="grounding-by-surface">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">By AI surface</div>
              <div className="space-y-1.5">
                {summary.by_surface.map((s) => (
                  <div key={s.surface} data-testid={`grounding-surface-${s.surface}`} className="flex items-center justify-between text-xs">
                    <span className="font-mono">{s.surface}</span>
                    <span className="text-muted-foreground">
                      {s.count} checked · <span className={scoreColor(s.avg_score)}>avg {s.avg_score ?? "—"}</span> · {s.flagged} flagged
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-lg border border-border bg-card p-4" data-testid="grounding-log">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">Recent AI answers</div>
            {events.length === 0 ? (
              <div className="text-sm text-muted-foreground">No AI answers checked yet. Ask the Obserrian Advisor a question to populate this.</div>
            ) : (
              <div className="divide-y divide-border">
                {events.map((e, i) => (
                  <div key={i} data-testid={`grounding-event-${i}`} className="py-2">
                    <button onClick={() => setOpen(open === i ? null : i)} className="w-full text-left flex items-center justify-between gap-3">
                      <span className="truncate text-xs text-foreground/90">{e.question || (e.answer || "").slice(0, 80) || "(answer)"}</span>
                      <span className="flex items-center gap-2 shrink-0 text-[11px] font-mono">
                        <span className="text-muted-foreground">{e.surface}</span>
                        <span className={`font-bold ${LABEL_STYLE[e.label] || "text-muted-foreground"}`}>{e.label} · {e.score}</span>
                        {e.flagged_count > 0 && <span className="text-crit">{e.flagged_count}⚠</span>}
                      </span>
                    </button>
                    {open === i && (
                      <div className="mt-2 text-[11px] space-y-2">
                        <div className="text-muted-foreground whitespace-pre-wrap bg-secondary/30 rounded p-2 max-h-40 overflow-y-auto">{e.answer}</div>
                        {(e.claims || []).length > 0 && (
                          <ul className="space-y-1">
                            {e.claims.map((c, j) => (
                              <li key={j} className="flex items-start gap-1.5">
                                <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${c.status === "supported" ? "bg-low" : c.status === "unsupported" ? "bg-crit" : "bg-muted-foreground"}`} />
                                <span><span className="uppercase text-[8px] font-mono text-muted-foreground mr-1">{c.status}</span>{c.claim}{c.note ? ` — ${c.note}` : ""}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                        <div className="font-mono text-muted-foreground">{new Date(e.at).toLocaleString()} · {e.model || "—"} · {e.method}</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
