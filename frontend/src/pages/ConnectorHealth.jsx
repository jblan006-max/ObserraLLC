import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { AIInsight } from "@/components/AIInsight";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Plug, Server, Clock, CheckCircle2, AlertTriangle, RefreshCw, Activity } from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const HEALTH = {
  healthy: { c: "142 70% 45%", label: "Healthy", Icon: CheckCircle2 },
  stale: { c: "35 90% 55%", label: "Stale", Icon: Clock },
  degraded: { c: "0 84% 60%", label: "Degraded", Icon: AlertTriangle },
};
const fmtAge = (m) => (m == null ? "—" : m < 60 ? `${m}m ago` : `${Math.floor(m / 60)}h ${m % 60}m ago`);

export default function ConnectorHealth() {
  const [d, setD] = useState(null);
  const [probing, setProbing] = useState(false);
  const load = useCallback(async () => { const { data } = await api.get("/sap/systems"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  const reprobe = async () => {
    setProbing(true);
    try {
      const { data } = await api.post("/sap/systems/reprobe");
      setD(data);
      const h = data.connector_health || {};
      toast.success(`Re-probed ${data.connectors.length} connector(s)`, { description: `${h.healthy || 0} healthy · ${h.stale || 0} stale · ${h.degraded || 0} degraded` });
    } catch (e) { toast.error("Re-probe failed"); }
    setProbing(false);
  };
  if (!d) return <Spinner />;
  const connected = d.connectors.filter((c) => c.status === "connected").length;
  const health = d.connector_health || { healthy: 0, stale: 0, degraded: 0 };

  return (
    <div className="space-y-6" data-testid="systems-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="systems-title">Connector Health</h1>
          <p className="text-sm text-muted-foreground mt-1">SAP landscape, source connectors and data freshness. Live API connection is enabled by supplying per-connector credentials; the current access model was ingested as a discovered snapshot with provenance.</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button size="sm" className="gap-1.5" data-testid="sys-reprobe" onClick={reprobe} disabled={probing}>
            <RefreshCw className={`w-3.5 h-3.5 ${probing ? "animate-spin" : ""}`} />{probing ? "Re-probing…" : "Re-probe all connectors"}
          </Button>
          {d.last_probe_at && <span className="text-[10px] font-mono text-muted-foreground" data-testid="sys-last-probe">Last probe {fmtDT(d.last_probe_at)}</span>}
        </div>
      </div>

      <AIInsight dashboard="Connector Health" focus="connector coverage, credential readiness and data freshness" accent="190 90% 50%" auto slug="sap-systems" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="SAP systems" value={d.systems.length} accent="210 92% 62%" icon={Server} testid="sys-count" />
        <StatCard label="Connectors" value={d.connectors.length} sub={`${connected} ingesting`} accent="190 90% 50%" icon={Plug} testid="sys-connectors" />
        <StatCard label="Production systems" value={d.systems.filter((s) => s.prod).length} accent="0 84% 60%" icon={Server} testid="sys-prod" />
        <StatCard label="Legal entities" value={d.legal_entities.length} accent="266 85% 66%" icon={Server} testid="sys-le" />
      </div>

      <div className="grid grid-cols-3 gap-4" data-testid="sys-health-summary">
        {["healthy", "stale", "degraded"].map((k) => { const H = HEALTH[k]; const I = H.Icon; return (
          <div key={k} className="bg-card fact-border rounded-xl p-4 flex items-center gap-3" data-testid={`sys-health-${k}`}>
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: `hsl(${H.c} / 0.12)` }}><I className="w-5 h-5" style={{ color: `hsl(${H.c})` }} /></div>
            <div><div className="font-head font-black text-2xl" style={{ color: `hsl(${H.c})` }}>{health[k] || 0}</div><div className="text-[11px] text-muted-foreground">{H.label} connector(s)</div></div>
          </div>
        ); })}
      </div>

      <div className="bg-card fact-border rounded-xl p-5" data-testid="sys-systems-panel">
        <h2 className="font-head font-bold text-lg mb-3">SAP Landscape</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-2">System</th><th className="p-2">Product</th><th className="p-2">Client</th><th className="p-2">Tier</th><th className="p-2">Accounts</th><th className="p-2">Dialog</th><th className="p-2">Technical</th></tr></thead>
            <tbody>
              {d.systems.map((s) => (
                <tr key={s.ref} className="border-b border-border/50" data-testid={`sys-row-${s.ref}`}>
                  <td className="p-2 font-mono font-semibold">{s.ref}</td><td className="p-2 text-xs">{s.name}</td><td className="p-2 text-xs">{s.client}</td>
                  <td className="p-2"><span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${s.prod ? "bg-crit/15 text-crit" : "bg-secondary text-muted-foreground"}`}>{s.tier}</span></td>
                  <td className="p-2 text-xs">{s.accounts}</td><td className="p-2 text-xs">{s.dialog_users}</td><td className="p-2 text-xs">{s.technical_users}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="sys-connectors-panel">
        {d.connectors.map((c) => (
          <div key={c.id} className="bg-card fact-border rounded-xl p-4" data-testid={`sys-connector-${c.id}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2"><Plug className="w-4 h-4 text-primary" /><span className="font-medium">{c.name}</span></div>
              {(() => { const H = HEALTH[c.health] || HEALTH.healthy; const I = H.Icon; return (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1" style={{ background: `hsl(${H.c} / 0.15)`, color: `hsl(${H.c})` }} data-testid={`sys-conn-health-${c.id}`}><I className="w-3 h-3" />{H.label}</span>
              ); })()}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
              <div>Category<div className="text-foreground">{c.category}</div></div>
              <div>Mode<div className="text-foreground">{c.mode}</div></div>
              <div>Records<div className="text-foreground font-mono">{c.records}</div></div>
              <div>Data freshness<div style={{ color: `hsl(${(HEALTH[c.health] || HEALTH.healthy).c})` }} className="font-mono">{fmtAge(c.age_min)}</div></div>
              <div className="col-span-2 flex items-center gap-1"><Clock className="w-3 h-3" /> Last sync {fmtDT(c.last_sync)} · Live API: {c.auth_ready ? "ready" : "pending credentials"}</div>
              {c.drift_note && <div className="col-span-2 flex items-start gap-1 text-[10px]" style={{ color: c.health === "healthy" ? undefined : `hsl(${(HEALTH[c.health] || HEALTH.healthy).c})` }} data-testid={`sys-conn-drift-${c.id}`}><Activity className="w-3 h-3 mt-0.5 shrink-0" /> {c.drift_note}</div>}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-card fact-border rounded-xl p-5" data-testid="sys-authority-panel">
        <h2 className="font-head font-bold text-lg mb-3">HR Authority Matrix (ADP / IZ8)</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
          {d.legal_entities.map((le) => (
            <div key={le.code} className="flex items-center justify-between text-sm p-2.5 rounded-lg bg-secondary/30">
              <span>{le.name} <span className="font-mono text-[10px] text-muted-foreground">· {le.code} · {le.country}</span></span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-ai/15 text-ai">{le.hr} authoritative</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
