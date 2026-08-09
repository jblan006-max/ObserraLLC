import { Activity } from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const DOT_COLOR = { ok: "142 70% 45%", degraded: "35 90% 55%", down: "0 84% 60%" };
const RANGES = [{ label: "24h", h: 24 }, { label: "7d", h: 168 }, { label: "30d", h: 720 }];

export function HealthTile({ label, value, sub, accent, icon: Icon, ok, testid }) {
  return (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-4 flex items-start gap-3" style={{ borderTop: `2px solid hsl(${accent} / 0.65)` }}>
      <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: `hsl(${accent} / 0.12)` }}>
        <Icon className="w-5 h-5" style={{ color: `hsl(${accent})` }} strokeWidth={1.6} />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          {label}
          {ok !== undefined && <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-low" : "bg-crit"}`} />}
        </div>
        <div className="font-head font-black text-2xl tracking-tight mt-0.5" style={{ color: `hsl(${accent})` }}>{value}</div>
        {sub && <div className="text-[11px] text-muted-foreground mt-0.5 leading-tight truncate">{sub}</div>}
      </div>
    </div>
  );
}

function bucketize(points, hours) {
  const now = Date.now();
  const start = now - hours * 3600 * 1000;
  const cols = hours <= 24 ? 48 : hours <= 168 ? 84 : 60;
  const width = (now - start) / cols;
  const rank = { ok: 0, degraded: 1, down: 2 };
  const buckets = Array.from({ length: cols }, (_, i) => ({ status: null, count: 0, start: start + i * width }));
  (points || []).forEach((p) => {
    const t = new Date(p.at).getTime();
    if (t < start || t > now) return;
    const idx = Math.min(cols - 1, Math.max(0, Math.floor((t - start) / width)));
    const b = buckets[idx];
    b.count++;
    if (b.status === null || rank[p.status] > rank[b.status]) b.status = p.status;
  });
  return buckets;
}

export function UptimeStrip({ points, range, setRange }) {
  const pts = points || [];
  const upPct = pts.length ? Math.round((pts.filter((p) => p.healthy).length / pts.length) * 100) : null;
  const buckets = bucketize(pts, range);
  return (
    <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-uptime-panel">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          <h2 className="font-head font-bold text-lg">Uptime</h2>
          {upPct != null && <span className="text-xs font-mono text-muted-foreground" data-testid="sh-uptime-pct">{upPct}% healthy · {pts.length} samples</span>}
        </div>
        <div className="flex items-center gap-1 bg-secondary/50 rounded-lg p-0.5" data-testid="sh-uptime-range">
          {RANGES.map((r) => (
            <button key={r.h} data-testid={`sh-range-${r.label}`} onClick={() => setRange(r.h)}
              className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${range === r.h ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
              {r.label}
            </button>
          ))}
        </div>
      </div>
      {pts.length ? (
        <div className="flex items-end gap-[2px] flex-wrap" data-testid="sh-uptime-dots">
          {buckets.map((b, i) => (
            <span key={i} title={`${fmtDT(new Date(b.start).toISOString())} — ${b.status || "no data"}`}
              className="w-2 h-6 rounded-sm transition-transform hover:scale-125"
              style={{ background: b.status ? `hsl(${DOT_COLOR[b.status]})` : "hsl(var(--muted-foreground) / 0.15)" }}
              data-testid={`sh-uptime-dot-${i}`} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground" data-testid="sh-uptime-empty">Collecting health samples — dots appear as the platform records status over time (auto every ~12 min and nightly).</p>
      )}
    </div>
  );
}

export function Sparkline({ points, testid }) {
  const vals = (points || []).map((p) => (p.median_hours == null ? null : p.median_hours));
  const nums = vals.filter((v) => v != null);
  if (nums.length < 2) return <span className="text-[11px] text-muted-foreground" data-testid={testid}>Not enough history yet</span>;
  const max = Math.max(...nums, 1);
  const w = 128, h = 26, n = vals.length;
  const step = n > 1 ? w / (n - 1) : w;
  const y = (v) => (h - (v / max) * (h - 4) - 2);
  const line = vals.map((v, i) => (v == null ? null : `${(i * step).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(" ");
  const last = nums[nums.length - 1];
  return (
    <span className="inline-flex items-center gap-2" data-testid={testid} title="Weekly median response time (hours)">
      <svg width={w} height={h} className="overflow-visible" aria-hidden="true">
        <polyline points={line} fill="none" stroke="hsl(var(--primary))" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
        {vals.map((v, i) => (v == null ? null : <circle key={i} cx={(i * step).toFixed(1)} cy={y(v).toFixed(1)} r="1.6" fill="hsl(var(--primary))" />))}
      </svg>
      <span className="text-[11px] font-mono text-muted-foreground">{last}h latest</span>
    </span>
  );
}

// Per-room on-time vs breached SLA response heatmap.
export function SlaHeatmap({ rooms, org, testid }) {
  const items = (rooms || []).filter((r) => (r.on_time + r.breached + r.pending) > 0);
  const orgHas = org && (org.on_time + org.breached + org.pending) > 0;
  if (!items.length && !orgHas) return null;
  const Row = ({ r, label }) => {
    const total = (r.on_time || 0) + (r.breached || 0) + (r.pending || 0);
    const pct = (v) => (total ? `${(v / total) * 100}%` : "0%");
    const tone = r.on_time_pct == null ? "text-muted-foreground" : r.on_time_pct >= 80 ? "text-low" : r.on_time_pct >= 50 ? "text-high" : "text-crit";
    return (
      <div className="flex items-center gap-2" data-testid={`sh-heatmap-row-${label}`}>
        <span className="text-[11px] w-24 truncate shrink-0" title={label}>{label}</span>
        <div className="flex-1 min-w-[120px] h-3 rounded-full overflow-hidden flex bg-secondary/60"
          title={`On-time ${r.on_time} · Breached ${r.breached} · Pending ${r.pending} (SLA ${r.sla_hours}h)`}>
          <div className="h-full bg-low" style={{ width: pct(r.on_time) }} />
          <div className="h-full bg-crit" style={{ width: pct(r.breached) }} />
          <div className="h-full bg-high/60" style={{ width: pct(r.pending) }} />
        </div>
        <span className={`text-[11px] font-mono w-12 text-right shrink-0 ${tone}`}>{r.on_time_pct == null ? "—" : `${r.on_time_pct}%`}</span>
      </div>
    );
  };
  return (
    <div className="mt-3 space-y-1.5" data-testid={testid || "sh-sla-heatmap"}>
      <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
        <span>SLA response heatmap</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-low inline-block" /> on-time</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-crit inline-block" /> breached</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-high/60 inline-block" /> pending</span>
      </div>
      {orgHas && <Row r={org} label="All rooms" />}
      {items.map((r) => <Row key={r.label} r={r} label={r.label} />)}
    </div>
  );
}
