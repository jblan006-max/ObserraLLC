import { AlertTriangle, Database, Loader2, RefreshCw } from "lucide-react";

const CLASS_STYLE = {
  FACT: "bg-low/10 text-low border-low/25",
  MODELLED: "bg-med/10 text-med border-med/25",
  "AI RECOMMENDATION": "bg-ai/10 text-ai border-ai/25",
};

// Categorical palette (distinct hues) for multi-series / multi-category charts so
// slices and bars never all render the same color.
export const PALETTE = [
  "199 89% 55%", "168 76% 46%", "262 83% 66%", "41 96% 55%", "330 81% 60%",
  "142 71% 45%", "24 90% 55%", "190 90% 45%", "280 70% 62%", "350 80% 60%",
];

export function DataClassBadge({ kind = "FACT" }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[9px] font-mono font-bold uppercase tracking-wider ${
        CLASS_STYLE[kind] || CLASS_STYLE.FACT
      }`}
    >
      {kind}
    </span>
  );
}

export function Panel({ title, subtitle, actions, children, testid }) {
  return (
    <section data-testid={testid} className="bg-card fact-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="font-head font-black text-lg tracking-tight">{title}</h2>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

export function MetricCard({
  label,
  value,
  sub,
  kind = "FACT",
  icon: Icon,
  accent = "168 76% 46%",
  onClick,
  testid,
}) {
  const Component = onClick ? "button" : "div";
  return (
    <Component
      type={onClick ? "button" : undefined}
      onClick={onClick}
      data-testid={testid}
      className={`w-full text-left bg-card fact-border rounded-xl p-4 ${
        onClick ? "hover:bg-secondary/30 transition-colors" : ""
      }`}
      style={{ borderLeft: `3px solid hsl(${accent})` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          {Icon && <Icon className="w-3.5 h-3.5" />}
          {label}
        </div>
        <DataClassBadge kind={kind} />
      </div>
      <div className="font-head font-black text-2xl lg:text-3xl mt-2 break-words">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </Component>
  );
}

export function StatusPill({ value }) {
  const v = String(value || "Unknown");
  const lower = v.toLowerCase();
  const style =
    lower.includes("fail") || lower.includes("expired") || lower.includes("critical")
      ? "bg-crit/10 text-crit border-crit/25"
      : lower.includes("drift") || lower.includes("expiring") || lower.includes("high")
      ? "bg-high/10 text-high border-high/25"
      : lower.includes("watch") || lower.includes("medium")
      ? "bg-med/10 text-med border-med/25"
      : lower.includes("passing") || lower.includes("fresh") || lower.includes("low")
      ? "bg-low/10 text-low border-low/25"
      : "bg-secondary text-muted-foreground border-border";

  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full border text-[10px] font-mono font-bold ${style}`}>
      {v}
    </span>
  );
}

export function ProgressBar({ value = 0, accent = "168 76% 46%" }) {
  const width = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <div className="h-2 rounded-full bg-secondary/70 overflow-hidden">
      <div className="h-full rounded-full" style={{ width: `${width}%`, background: `hsl(${accent})` }} />
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="min-h-[55vh] flex items-center justify-center" data-testid="control-intelligence-loading">
      <div className="text-center">
        <Loader2 className="w-7 h-7 animate-spin text-primary mx-auto" />
        <div className="text-sm text-muted-foreground mt-3">Loading control intelligence</div>
      </div>
    </div>
  );
}

export function ErrorBanner({ message, onRetry, refreshing }) {
  if (!message) return null;
  return (
    <div className="rounded-xl border border-crit/30 bg-crit/5 p-4 flex items-start gap-3">
      <AlertTriangle className="w-5 h-5 text-crit shrink-0 mt-0.5" />
      <div className="min-w-0 flex-1">
        <div className="font-head font-bold text-sm">Control data incomplete</div>
        <div className="text-xs text-muted-foreground mt-1">{message}</div>
      </div>
      <button
        onClick={onRetry}
        disabled={refreshing}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-secondary/50 text-xs disabled:opacity-50"
      >
        <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
        Retry
      </button>
    </div>
  );
}

export function EmptyState({ title, text }) {
  return (
    <div className="py-12 text-center">
      <Database className="w-9 h-9 text-muted-foreground mx-auto" />
      <div className="font-head font-bold mt-3">{title}</div>
      <p className="text-sm text-muted-foreground max-w-xl mx-auto mt-2">{text}</p>
    </div>
  );
}
