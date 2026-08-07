import { Database, Clock, Gauge } from "lucide-react";

const sevColor = (n) => (n >= 20 ? "crit" : n >= 16 ? "high" : n >= 10 ? "med" : "low");

export function SourceBadge({ source }) {
  return (
    <span data-testid="badge-source" title={`System of origin: ${source}`}
      className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
      <Database className="w-3 h-3" /> {source}
    </span>
  );
}

export function FreshnessBadge({ freshness }) {
  const live = freshness === "live";
  return (
    <span data-testid="badge-freshness"
      className={`inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider ${live ? "text-low" : "text-muted-foreground"}`}>
      <span className="relative flex h-1.5 w-1.5">
        {live && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-low opacity-70" />}
        <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${live ? "bg-low" : "bg-muted-foreground"}`} />
      </span>
      <Clock className="w-3 h-3" /> {live ? "Live" : ">24h"}
    </span>
  );
}

export function ConfidenceBadge({ value }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 80 ? "bg-low" : pct >= 60 ? "bg-med" : "bg-high";
  return (
    <span data-testid="badge-confidence" title={`Confidence: ${pct}%`}
      className="inline-flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground">
      <Gauge className="w-3 h-3" />
      <span className="w-10 h-1.5 rounded-full bg-secondary overflow-hidden inline-block">
        <span className={`block h-full ${color}`} style={{ width: `${pct}%` }} />
      </span>
      {pct}%
    </span>
  );
}

export function DataTypeBadge({ type }) {
  const map = {
    fact: { label: "FACT", cls: "border border-border text-foreground" },
    estimate: { label: "ESTIMATE", cls: "border border-dashed border-muted-foreground/60 text-muted-foreground" },
    ai_recommendation: { label: "AI REC", cls: "ai-border text-ai" },
    prediction: { label: "PREDICTION", cls: "border border-med/60 text-med" },
  };
  const m = map[type] || map.fact;
  return (
    <span data-testid={`badge-datatype-${type}`}
      className={`inline-flex items-center px-1.5 py-0.5 rounded-sm text-[9px] font-mono tracking-widest ${m.cls}`}>
      {m.label}
    </span>
  );
}

const SEV_HSL = { crit: "0 84% 60%", high: "15 80% 55%", med: "35 90% 55%", low: "142 70% 45%" };

export function ScorePill({ value, label }) {
  const c = sevColor(value);
  const hsl = SEV_HSL[c];
  return (
    <span className="inline-flex items-center justify-center min-w-[2.2rem] px-2 py-0.5 rounded-sm font-mono text-xs font-semibold"
      style={{ backgroundColor: `hsl(${hsl} / 0.15)`, color: `hsl(${hsl})`, border: `1px solid hsl(${hsl} / 0.3)` }}>
      {label ?? value}
    </span>
  );
}

export { SEV_HSL, sevColor };

