import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { APP_VERSION_LABEL } from "@/version";
import { Sparkles, Loader2, Zap, ShieldAlert, Lightbulb, ChevronDown, ShieldCheck, ScanEye, TriangleAlert } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

// Obserrian CRA Analyst (per-dashboard grounded briefing), CraExplain / CraExplainToggle
// (per-item AI summary · risk · risk details · fix), and AiAssurance (hallucination monitor).
// Every AI answer is scored by the platform grounding verifier via POST /cra/ground.

const DOT = { fact: "bg-primary", estimate: "bg-ai", risk: "bg-crit", prediction: "bg-primary" };
const KIND_TEXT = { fact: "text-primary", estimate: "text-ai", risk: "text-crit", prediction: "text-primary" };
const SEV_CLASS = {
  risk: "border-crit/25 bg-crit/10 text-crit",
  watch: "border-high/25 bg-high/10 text-high",
  opportunity: "border-low/25 bg-low/10 text-low",
  info: "border-ai/25 bg-ai/10 text-ai",
};
const AI_HEX = "#12b4d6";

const _tabCache = new Map();
const _groundCache = new Map();

function groundTone(score) {
  if (score == null) return { cls: "border-border bg-secondary/40 text-muted-foreground", Icon: ScanEye };
  if (score >= 80) return { cls: "border-low/30 bg-low/10 text-low", Icon: ShieldCheck };
  if (score >= 50) return { cls: "border-high/30 bg-high/10 text-high", Icon: TriangleAlert };
  return { cls: "border-crit/30 bg-crit/10 text-crit", Icon: TriangleAlert };
}

export function GroundingBadge({ state }) {
  if (!state) return null;
  if (state.loading) {
    return (
      <span data-testid="cra-grounding-badge" className="inline-flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded-full border border-border bg-secondary/40 text-muted-foreground">
        <Loader2 className="w-3 h-3 animate-spin" /> Grounding…
      </span>
    );
  }
  const { score, label, flagged_count } = state;
  const t = groundTone(score);
  const flagged = flagged_count || 0;
  const title = (state.claims && state.claims.length)
    ? state.claims.map((c) => `${c.status === "unsupported" ? "⚠" : c.status === "supported" ? "✓" : "·"} ${c.claim}`).join("\n")
    : "No factual claims required verification.";
  return (
    <span
      data-testid="cra-grounding-badge"
      data-grounding-score={score == null ? "" : String(score)}
      title={title}
      className={`inline-flex items-center gap-1.5 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${t.cls}`}
    >
      <t.Icon className="w-3 h-3" />
      <span data-testid="cra-grounding-score">{score == null ? "—" : `${score}%`}</span> {label}
      {flagged > 0 && <span className="opacity-80">· {flagged} flagged</span>}
    </span>
  );
}

function useGrounding(cacheKey, payload, answer, ready) {
  const [state, setState] = useState(() => _groundCache.get(cacheKey) || null);
  const firedRef = useRef("");
  useEffect(() => {
    if (!ready || !answer) return;
    const hit = _groundCache.get(cacheKey);
    if (hit) { setState(hit); return; }
    if (firedRef.current === cacheKey) return;
    firedRef.current = cacheKey;
    setState({ loading: true });
    api.post("/cra/ground", { ...payload, answer })
      .then((r) => { _groundCache.set(cacheKey, r.data); setState(r.data); })
      .catch(() => setState(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey, ready, answer]);
  return state;
}

export function CraTabAnalyst({ tab }) {
  const [data, setData] = useState(() => _tabCache.get(tab) || null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const r = await api.post("/cra/dashboard-insight", { tab });
      _tabCache.set(tab, r.data);
      setData(r.data);
    } catch {
      /* keep last */
    }
    setLoading(false);
  };

  useEffect(() => {
    const hit = _tabCache.get(tab);
    if (hit) { setData(hit); return; }
    setData(null); run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const answer = data ? [data.headline, ...(data.insights || []).map((i) => i.text), ...(data.actions || [])].filter(Boolean).join(" ") : "";
  const grounding = useGrounding(`insight:${tab}:${answer.length}`, { kind: "insight", tab }, answer, !!data);

  return (
    <div data-testid={`cra-tab-analyst-${tab}`} className="rounded-xl border border-ai/25 bg-ai/5 p-5">
      <div className="flex items-start gap-2.5">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg shrink-0 bg-ai/15">
          <Sparkles className="w-4 h-4 text-ai" strokeWidth={1.5} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="font-head font-bold text-sm">Obserrian CRA Analyst</div>
            <GroundingBadge state={grounding} />
            <button
              data-testid={`cra-tab-analyst-refresh-${tab}`}
              onClick={run}
              disabled={loading}
              className="flex items-center gap-1.5 text-[11px] font-head font-bold px-3 py-1 rounded-full bg-ai text-background disabled:opacity-50 transition-transform active:scale-95 shrink-0"
            >
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />} {data ? "Refresh" : "Analyze"}
            </button>
          </div>
          <div className="text-[10px] font-mono text-muted-foreground truncate">
            {data ? `${data.model} · Obserra CRA ${APP_VERSION_LABEL} · grounded in live data${data.generated_at ? ` · ${new Date(data.generated_at).toLocaleTimeString()}` : ""}` : `Live CRA summary for this dashboard · Obserra CRA ${APP_VERSION_LABEL}`}
          </div>
        </div>
      </div>

      {loading && !data && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading the live CRA posture &amp; summarizing…</div>
      )}

      {data && (
        <div className="mt-4 space-y-3">
          {data.headline && <div className="font-head font-bold text-base leading-snug text-ai" data-testid={`cra-tab-analyst-headline-${tab}`}>{data.headline}</div>}
          <ul className="space-y-2">
            {(data.insights || []).map((it, i) => (
              <li key={i} data-testid={`cra-tab-analyst-insight-${tab}-${i}`} className="flex items-start gap-2.5 text-sm text-foreground/90 leading-relaxed">
                <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${DOT[it.kind] || "bg-ai"}`} />
                <span>{it.text} {it.kind && <span className={`text-[9px] font-mono uppercase tracking-wider align-middle ${KIND_TEXT[it.kind] || "text-ai"}`}>· {it.kind}</span>}</span>
              </li>
            ))}
          </ul>
          {(data.actions || []).length > 0 && (
            <div className="pt-3 border-t border-border">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">Recommended actions</div>
              <ul className="space-y-1">
                {data.actions.map((a, i) => (
                  <li key={i} className="text-sm flex items-start gap-2"><span className="text-ai">→</span> {a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function CraExplain({ title, kind = "item", context = {}, className = "" }) {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);
  const ctxKey = JSON.stringify({ title, kind, context });

  useEffect(() => {
    let ok = true;
    setLoading(true); setD(null);
    api.post("/cra/explain", { title, kind, context })
      .then((r) => { if (ok) { setD(r.data); setLoading(false); } })
      .catch(() => { if (ok) setLoading(false); });
    return () => { ok = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctxKey]);

  const answer = d ? [d.summary, d.risk_detail, d.recommendation, ...(d.steps || [])].filter(Boolean).join(" ") : "";
  const grounding = useGrounding(`explain:${kind}:${title}:${answer.length}`, { kind, title, context }, answer, !!d);

  const sevClass = d ? (SEV_CLASS[d.severity] || SEV_CLASS.info) : SEV_CLASS.info;
  return (
    <div data-testid="cra-explain" className={`rounded-lg border border-ai/30 bg-ai/5 p-3 ${className}`}>
      <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-ai"><Sparkles className="w-3 h-3" /> Obserrian AI · summary, risk &amp; fixes</div>
        <div className="flex items-center gap-2">
          <GroundingBadge state={grounding} />
          {d?.risk && <span data-testid="cra-explain-risk" className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${sevClass}`}>{String(d.risk).toUpperCase()} RISK</span>}
        </div>
      </div>
      {loading && !d && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing this item…</div>}
      {!loading && !d && <div className="text-xs text-muted-foreground">AI advisor is temporarily unavailable.</div>}
      {d && (
        <div className="space-y-2.5">
          {d.summary && <p className="text-sm text-foreground/90 leading-relaxed" data-testid="cra-explain-summary">{d.summary}</p>}
          {d.risk_detail && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-0.5 flex items-center gap-1"><ShieldAlert className="w-3 h-3" /> Risk details</div>
              <p className="text-sm text-foreground/90" data-testid="cra-explain-risk-detail">{d.risk_detail}</p>
            </div>
          )}
          {d.recommendation && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-0.5 flex items-center gap-1"><Lightbulb className="w-3 h-3 text-ai" /> Fix &amp; recommendation</div>
              <p className="text-sm text-foreground/90" data-testid="cra-explain-recommendation">{d.recommendation}</p>
            </div>
          )}
          {d.steps?.length > 0 && (
            <ul className="space-y-1">
              {d.steps.map((s, i) => <li key={i} className="text-[12px] flex items-start gap-2"><span className="text-ai">→</span> {s}</li>)}
            </ul>
          )}
          {d.model && <div className="text-[9px] font-mono text-muted-foreground pt-1">{d.model} · Obserra CRA {APP_VERSION_LABEL} · grounded in live data</div>}
        </div>
      )}
    </div>
  );
}

export function CraExplainToggle({ title, kind = "item", context = {}, label = "AI risk & fix" }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen((o) => !o)} data-testid="cra-explain-toggle" className="inline-flex items-center gap-1.5 text-[11px] font-head font-bold text-ai hover:underline">
        <Sparkles className="w-3 h-3" /> {label} <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="mt-2"><CraExplain title={title} kind={kind} context={context} /></div>}
    </div>
  );
}

const SURFACE_LABEL = (s) => {
  const p = (s || "").split(":");
  if (p[1] === "insight") return `Dashboard analyst · ${p[2] || ""}`;
  if (p[1] === "explain") return `Item advisor · ${p[2] || ""}`;
  return s;
};

function GroundingTrend({ trend, days }) {
  const points = (trend || []).filter((p) => p != null);
  if (!points.length || !points.some((p) => p.score != null)) {
    return (
      <div className="rounded-xl border border-border bg-card p-5" data-testid="cra-ai-monitor-trend">
        <div className="font-head font-bold text-sm mb-1">{days}-day grounding trend</div>
        <div className="text-[11px] font-mono text-muted-foreground">No grounding checks in this window yet — open any analyst or item advisor and scores will chart here.</div>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-border bg-card p-5" data-testid="cra-ai-monitor-trend">
      <div className="font-head font-bold text-sm mb-1">{days}-day grounding trend</div>
      <div className="text-[11px] font-mono text-muted-foreground mb-3">Average grounding score per day — watch for accuracy drift</div>
      <div style={{ width: "100%", height: 130 }}>
        <ResponsiveContainer>
          <AreaChart data={points} margin={{ top: 6, right: 10, left: -18, bottom: 0 }}>
            <defs>
              <linearGradient id="craGroundGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={AI_HEX} stopOpacity={0.35} />
                <stop offset="100%" stopColor={AI_HEX} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" hide />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} width={30} />
            <Tooltip
              contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "hsl(var(--muted-foreground))" }}
              formatter={(v) => [v == null ? "—" : `${v}%`, "Grounding"]}
            />
            <Area type="monotone" dataKey="score" stroke={AI_HEX} strokeWidth={2} fill="url(#craGroundGrad)" connectNulls dot={{ r: 2, fill: AI_HEX }} activeDot={{ r: 4 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function AiAssurance() {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const load = (n) => {
    const win = n || days;
    setLoading(true);
    api.get(`/cra/ai-monitor?days=${win}`).then((r) => { setD(r.data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { load(days); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [days]);

  const t = groundTone(d?.avg_score);
  return (
    <div className="space-y-5" data-testid="cra-ai-monitor">
      <div className="rounded-xl border border-ai/25 bg-ai/5 p-5">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-start gap-2.5">
            <span className="inline-flex items-center justify-center w-9 h-9 rounded-lg shrink-0 bg-ai/15"><ScanEye className="w-5 h-5 text-ai" strokeWidth={1.5} /></span>
            <div>
              <div className="font-head font-black text-xl tracking-tight">AI Assurance · Hallucination Monitor</div>
              <div className="text-[11px] font-mono text-muted-foreground">Every Obserrian CRA AI answer is scored against the live data that produced it · Obserra CRA {APP_VERSION_LABEL} · last {days} days</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-full border border-border overflow-hidden" data-testid="cra-ai-monitor-range">
              {[7, 30, 90].map((n) => (
                <button key={n} data-testid={`cra-ai-monitor-range-${n}`} onClick={() => setDays(n)}
                  className={`text-[11px] font-head font-bold px-2.5 py-1 transition-colors ${days === n ? "bg-ai text-background" : "text-muted-foreground hover:bg-secondary/50"}`}>{n}d</button>
              ))}
            </div>
            <button onClick={() => load()} disabled={loading} className="flex items-center gap-1.5 text-[11px] font-head font-bold px-3 py-1.5 rounded-full bg-ai text-background disabled:opacity-50">
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />} Refresh
            </button>
          </div>
        </div>
      </div>

      {loading && !d && <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading the AI assurance monitor…</div>}

      {d && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className={`rounded-xl border p-5 ${t.cls}`} data-testid="cra-ai-monitor-score">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider opacity-80"><t.Icon className="w-3.5 h-3.5" /> Avg grounding score</div>
              <div className="font-head font-black text-4xl mt-1">{d.avg_score == null ? "—" : `${d.avg_score}%`}</div>
              <div className="text-xs font-mono mt-1">{d.label}</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-5" data-testid="cra-ai-monitor-checks">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">AI answers checked</div>
              <div className="font-head font-black text-4xl mt-1">{d.total_checks}</div>
              <div className="text-xs font-mono text-muted-foreground mt-1">grounding checks logged</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-5" data-testid="cra-ai-monitor-flagged">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Answers with flagged claims</div>
              <div className={`font-head font-black text-4xl mt-1 ${d.flagged_total > 0 ? "text-crit" : "text-low"}`}>{d.flagged_total}</div>
              <div className="text-xs font-mono text-muted-foreground mt-1">unsupported figure/ref detected</div>
            </div>
          </div>

          <GroundingTrend trend={d.trend} days={days} />

          {d.by_surface?.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5">
              <div className="font-head font-bold text-sm mb-3">Grounding by AI surface</div>
              <div className="space-y-2">
                {d.by_surface.map((s) => {
                  const st = groundTone(s.avg_score);
                  return (
                    <div key={s.surface} className="flex items-center justify-between gap-3 text-sm border-b border-border/60 pb-2 last:border-0">
                      <span className="font-mono text-xs text-foreground/90">{SURFACE_LABEL(s.surface)}</span>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-[11px] font-mono text-muted-foreground">{s.count} checks{s.flagged > 0 ? ` · ${s.flagged} flagged` : ""}</span>
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${st.cls}`}>{s.avg_score == null ? "—" : `${s.avg_score}%`}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-border bg-card p-5">
            <div className="font-head font-bold text-sm mb-3">Recent AI answers &amp; verdicts</div>
            {d.recent?.length === 0 && <div className="text-sm text-muted-foreground">No CRA AI answers scored yet — open any dashboard analyst or item advisor and the grounding score will appear here.</div>}
            <div className="space-y-2">
              {(d.recent || []).map((r, i) => {
                const st = groundTone(r.score);
                return (
                  <div key={i} data-testid={`cra-ai-monitor-row-${i}`} className="flex items-start justify-between gap-3 border-b border-border/60 pb-2 last:border-0">
                    <div className="min-w-0">
                      <div className="text-sm text-foreground/90 truncate">{r.question || SURFACE_LABEL(r.surface)}</div>
                      <div className="text-[10px] font-mono text-muted-foreground">{SURFACE_LABEL(r.surface)} · {r.at ? new Date(r.at).toLocaleString() : ""}</div>
                      {r.flagged_count > 0 && (r.claims || []).filter((c) => c.status === "unsupported").slice(0, 2).map((c, j) => (
                        <div key={j} className="text-[11px] text-crit flex items-start gap-1 mt-0.5"><TriangleAlert className="w-3 h-3 mt-0.5 shrink-0" /> {c.claim}</div>
                      ))}
                    </div>
                    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border shrink-0 ${st.cls}`}>{r.score == null ? "—" : `${r.score}%`}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
