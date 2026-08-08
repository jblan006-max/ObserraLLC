import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SourceBadge, FreshnessBadge } from "@/components/badges";
import { Boxes, Loader2 } from "lucide-react";

const critColor = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };

export default function AssetIntelligence() {
  const [assets, setAssets] = useState(null);
  useEffect(() => { api.get("/assets").then((r) => setAssets(r.data)); }, []);
  if (!assets) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-5">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Boxes className="w-7 h-7 text-primary" /> Asset Intelligence</h1>
        <p className="text-sm text-muted-foreground mt-1">Unified asset inventory with criticality and internet-exposure scoring from connected sources.</p>
      </div>
      <div data-testid="assets-connect-note" className="text-xs bg-ai/5 border border-ai/20 rounded-lg px-4 py-2.5 text-muted-foreground">Your live endpoint is inventoried automatically from the self-scan. <a href="/app/connectors" className="text-ai underline">Connect Microsoft 365 (Intune)</a> to inventory managed devices, and other sources to expand this list.</div>
      {assets.length === 0 ? (
        <div data-testid="assets-empty" className="bg-card fact-border rounded-xl p-8 text-center text-sm text-muted-foreground">No assets yet — run a live scan or connect a source to populate your inventory.</div>
      ) : (
      <div className="bg-card fact-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3">Ref / Asset</th><th className="text-left px-4 py-3">Type</th><th className="text-left px-4 py-3">Criticality</th><th className="text-left px-4 py-3">Exposure</th><th className="text-left px-4 py-3">Owner</th><th className="text-left px-4 py-3">Status</th><th className="text-left px-4 py-3">Source</th></tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr key={a.ref} data-testid={`asset-${a.ref}`} className="border-b border-border/60 hover:bg-secondary/40 transition-colors">
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{a.ref}</div><div className="font-medium">{a.name}</div></td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{a.type}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${critColor[a.criticality]} / 0.15)`, color: `hsl(${critColor[a.criticality]})` }}>{a.criticality}</span></td>
                <td className="px-4 py-3 w-40">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${a.exposure}%`, background: a.exposure >= 70 ? "hsl(0 84% 60%)" : a.exposure >= 45 ? "hsl(35 90% 55%)" : "hsl(142 70% 45%)" }} /></div>
                    <span className="font-mono text-xs w-6">{a.exposure}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs">{a.owner}</td>
                <td className="px-4 py-3"><span className="text-xs px-2 py-0.5 rounded-md bg-secondary/60">{a.status}</span></td>
                <td className="px-4 py-3"><div className="flex flex-col gap-1"><SourceBadge source={a.source} /><FreshnessBadge freshness={a.freshness} /></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}
