import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Radio, RefreshCw, AlertTriangle } from "lucide-react";

const relTime = (iso) => {
  if (!iso) return "never";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

const STATE = {
  connected: { label: "HEALTHY", cls: "bg-low/15 text-low" },
  credentials_required: { label: "NO CREDS", cls: "bg-med/15 text-med" },
  auth_failed: { label: "AUTH FAILED", cls: "bg-crit/15 text-crit" },
  unreachable: { label: "UNREACHABLE", cls: "bg-crit/15 text-crit" },
  error: { label: "ERROR", cls: "bg-med/15 text-med" },
};

// Connector Health widget — every probed catalog connector + every legacy live connector, each
// showing its last re-probe time and a red badge the moment it silently degrades (daily cron).
export function ConnectorHealth({ accent = "199 89% 48%", testid = "connector-health-widget" }) {
  const [d, setD] = useState(null);
  const load = () => api.get("/connectors/health").then((r) => setD(r.data)).catch(() => setD({ connectors: [], summary: {} }));
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);
  if (!d) return null;
  const items = d.connectors || [];
  const s = d.summary || {};
  return (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2"><Radio className="w-4 h-4" style={{ color: `hsl(${accent})` }} /><h2 className="font-head font-bold text-lg">Connector Health</h2></div>
        <div className="flex items-center gap-2">
          {s.degraded > 0 && <span data-testid="connector-health-degraded" className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-crit/15 text-crit"><AlertTriangle className="w-3 h-3" /> {s.degraded} degraded</span>}
          <span className="text-[10px] font-mono text-muted-foreground">{s.healthy || 0}/{s.total || 0} healthy · daily re-probe {relTime(s.last_check)}</span>
        </div>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No connectors probed yet. Connect a source in Available Connectors — the daily health check re-probes every provider and flags any silent credential expiry right here.</p>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {items.map((c) => {
            const m = STATE[c.state] || { label: (c.state || "").toUpperCase(), cls: "bg-secondary/60 text-muted-foreground" };
            return (
              <div key={c.id} data-testid={`conn-health-${c.id}`} className={`rounded-lg p-3 border ${c.degraded ? "border-crit/40 bg-crit/5" : "border-border bg-secondary/30"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm truncate">{c.name}</span>
                  <span data-testid={`conn-health-${c.id}-badge`} className={`shrink-0 text-[9px] font-mono px-2 py-0.5 rounded-full ${m.cls}`}>{m.label}</span>
                </div>
                <div className="text-[10px] font-mono text-muted-foreground mt-1 flex items-center gap-1"><RefreshCw className="w-2.5 h-2.5" /> re-probed {relTime(c.checked_at)}</div>
                <div className="text-[9px] uppercase tracking-wide text-muted-foreground/70 mt-0.5 truncate">{c.category}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
