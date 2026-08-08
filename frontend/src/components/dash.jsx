import { Loader2 } from "lucide-react";
import { useDeepDive } from "@/context/DeepDiveContext";

// Reusable dense dashboard primitives — every dashboard renders these card shells
// ALWAYS (even with zero data), so a page is never blank; empty datasets show a
// graceful "connect / no data yet" state inside a live, functional card.
// Every KPI/summary card is CLICKABLE → opens the universal deep-dive (live rating,
// grounded AI recommendations, honest action hub). Cards may pass a rich `detail`
// item; otherwise one is auto-built from the metric so no card is ever inert.

function autoDetail({ label, value, sub, accent }) {
  const v = value === null || value === undefined || value === "" ? "—" : String(value);
  return {
    refLabel: "KPI METRIC", title: label, accent,
    facets: [
      { label: "Current value", value: v },
      ...(sub ? [{ label: "Context", value: sub }] : []),
    ],
    recommendedActions: [
      `Review the live drivers behind “${label}” and action the highest-$ contributors first — changes re-price into the Strategic Risk Score on the next scan.`,
    ],
    explainTitle: label, explainKind: "kpi metric dashboard live",
    explainContext: { metric: { label, value: v, sub } },
  };
}

export function StatCard({ label, value, sub, accent = "199 89% 48%", testid, detail }) {
  const { openDeepDive } = useDeepDive();
  const item = detail || autoDetail({ label, value, sub, accent });
  return (
    <button type="button" data-testid={testid} onClick={() => openDeepDive({ accent, ...item })}
      className="group text-left w-full bg-card fact-border rounded-xl p-4 flex flex-col justify-between min-h-[96px] cursor-pointer hover:-translate-y-0.5 transition-transform duration-200"
      style={{ borderTop: `2px solid hsl(${accent} / 0.65)` }}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{label}</div>
        <span className="text-[9px] font-mono text-ai opacity-0 group-hover:opacity-100 transition-opacity shrink-0">Deep-dive →</span>
      </div>
      <div className="font-head font-black text-3xl tracking-tight mt-1" style={{ color: `hsl(${accent})` }}>
        {value === null || value === undefined || value === "" ? "—" : value}
      </div>
      {sub && <div className="text-[11px] text-muted-foreground mt-0.5 leading-tight">{sub}</div>}
    </button>
  );
}

export function CardShell({ title, icon: Icon, accent = "199 89% 48%", right, children, testid, className = "", detail }) {
  const { openDeepDive } = useDeepDive();
  const clickable = !!detail;
  return (
    <div data-testid={testid} className={`bg-card fact-border rounded-xl p-5 h-full flex flex-col ${className}`}
      style={{ boxShadow: `inset 0 1px 0 hsl(${accent} / 0.3)` }}>
      <div className="flex items-center justify-between gap-2 mb-4">
        {clickable ? (
          <button type="button" data-testid={testid ? `${testid}-deepdive` : undefined}
            onClick={() => openDeepDive({ accent, ...detail })}
            className="group flex items-center gap-2 min-w-0 text-left cursor-pointer hover:opacity-90 transition-opacity">
            {Icon && <Icon className="w-4 h-4 shrink-0" style={{ color: `hsl(${accent})` }} strokeWidth={1.5} />}
            <h2 className="font-head font-bold text-base truncate">{title}</h2>
            <span className="text-[9px] font-mono text-ai opacity-0 group-hover:opacity-100 transition-opacity shrink-0">↗</span>
          </button>
        ) : (
          <div className="flex items-center gap-2 min-w-0">
            {Icon && <Icon className="w-4 h-4 shrink-0" style={{ color: `hsl(${accent})` }} strokeWidth={1.5} />}
            <h2 className="font-head font-bold text-base truncate">{title}</h2>
          </div>
        )}
        {right}
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  );
}

// Clickable wrapper for bespoke (non-primitive) cards on legacy dashboards — makes any
// card open the universal deep-dive while preserving its existing markup/styling.
export function ClickCard({ detail, className = "", children, testid, style }) {
  const { openDeepDive } = useDeepDive();
  return (
    <div data-testid={testid} role="button" tabIndex={0}
      onClick={() => detail && openDeepDive(detail)}
      onKeyDown={(e) => { if (detail && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openDeepDive(detail); } }}
      className={`group cursor-pointer transition-transform duration-200 hover:-translate-y-0.5 ${className}`}
      style={style}>
      {children}
    </div>
  );
}

export function EmptyState({ icon: Icon, text, cta, testid }) {
  return (
    <div data-testid={testid} className="flex flex-col items-center justify-center text-center gap-2 py-8 px-4 h-full rounded-lg border border-dashed border-muted-foreground/25">
      {Icon && <Icon className="w-6 h-6 text-muted-foreground/50" strokeWidth={1.5} />}
      <p className="text-xs text-muted-foreground max-w-xs leading-relaxed">{text}</p>
      {cta}
    </div>
  );
}

export function BarList({ items, accent = "199 89% 48%", empty = "No data yet — connect a live source to populate." }) {
  if (!items || !items.length) return <EmptyState text={empty} />;
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="space-y-2.5">
      {items.map((it) => (
        <div key={it.name} data-testid={`barlist-${String(it.name).replace(/[^a-zA-Z0-9]/g, "-")}`}>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="truncate pr-2">{it.name}</span>
            <span className="font-mono text-muted-foreground shrink-0">{it.value}</span>
          </div>
          <div className="h-2 rounded-full bg-secondary/60 overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(it.value / max) * 100}%`, background: `hsl(${it.color || accent})` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function Spinner() {
  return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
}
