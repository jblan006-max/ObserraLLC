import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { Plug, Server, Clock, CheckCircle2, AlertTriangle } from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const FRESH = { fresh: "142 70% 45%", stale: "35 90% 55%", "n/a": "220 10% 55%" };

export default function SapSystems() {
  const [d, setD] = useState(null);
  const load = useCallback(async () => { const { data } = await api.get("/sap/systems"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;
  const connected = d.connectors.filter((c) => c.status === "connected").length;

  return (
    <div className="space-y-6" data-testid="systems-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="systems-title">Connector Health</h1>
        <p className="text-sm text-muted-foreground mt-1">SAP landscape, source connectors and data freshness. Live API connection is enabled by supplying per-connector credentials; the current access model was ingested as a discovered snapshot with provenance.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="SAP systems" value={d.systems.length} accent="210 92% 62%" icon={Server} testid="sys-count" />
        <StatCard label="Connectors" value={d.connectors.length} sub={`${connected} ingesting`} accent="190 90% 50%" icon={Plug} testid="sys-connectors" />
        <StatCard label="Production systems" value={d.systems.filter((s) => s.prod).length} accent="0 84% 60%" icon={Server} testid="sys-prod" />
        <StatCard label="Legal entities" value={d.legal_entities.length} accent="266 85% 66%" icon={Server} testid="sys-le" />
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
              {c.status === "connected"
                ? <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-low/15 text-low flex items-center gap-1"><CheckCircle2 className="w-3 h-3" />Ingesting</span>
                : <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber/15 text-amber flex items-center gap-1"><AlertTriangle className="w-3 h-3" />Needs credentials</span>}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
              <div>Category<div className="text-foreground">{c.category}</div></div>
              <div>Mode<div className="text-foreground">{c.mode}</div></div>
              <div>Records<div className="text-foreground font-mono">{c.records}</div></div>
              <div>Freshness<div style={{ color: `hsl(${FRESH[c.freshness] || "220 10% 55%"})` }} className="font-mono">{c.freshness}</div></div>
              <div className="col-span-2 flex items-center gap-1"><Clock className="w-3 h-3" /> Last sync {fmtDT(c.last_sync)} · Live API: {c.auth_ready ? "ready" : "pending credentials"}</div>
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
