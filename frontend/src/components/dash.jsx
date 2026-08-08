import { Loader2 } from "lucide-react";

// Reusable dense dashboard primitives — every dashboard renders these card shells
// ALWAYS (even with zero data), so a page is never blank; empty datasets show a
// graceful "connect / no data yet" state inside a live, functional card.

export function StatCard({ label, value, sub, accent = "199 89% 48%", testid }) {
  return (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-4 flex flex-col justify-between min-h-[96px] hover:-translate-y-0.5 transition-transform duration-200"
      style={{ borderTop: `2px solid hsl(${accent} / 0.65)` }}>
      <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-head font-black text-3xl tracking-tight mt-1" style={{ color: `hsl(${accent})` }}>
        {value === null || value === undefined || value === "" ? "—" : value}
      </div>
      {sub && <div className="text-[11px] text-muted-foreground mt-0.5 leading-tight">{sub}</div>}
    </div>
  );
}

export function CardShell({ title, icon: Icon, accent = "199 89% 48%", right, children, testid, className = "" }) {
  return (
    <div data-testid={testid} className={`bg-card fact-border rounded-xl p-5 h-full flex flex-col ${className}`}
      style={{ boxShadow: `inset 0 1px 0 hsl(${accent} / 0.3)` }}>
      <div className="flex items-center justify-between gap-2 mb-4">
        <div className="flex items-center gap-2 min-w-0">
          {Icon && <Icon className="w-4 h-4 shrink-0" style={{ color: `hsl(${accent})` }} strokeWidth={1.5} />}
          <h2 className="font-head font-bold text-base truncate">{title}</h2>
        </div>
        {right}
      </div>
      <div className="flex-1 min-h-0">{children}</div>
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
