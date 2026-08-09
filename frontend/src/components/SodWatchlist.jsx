import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useDeepDive } from "@/context/DeepDiveContext";
import { Star, ShieldAlert, Loader2, Flame } from "lucide-react";

const SEV = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "199 89% 48%", Low: "142 70% 45%" };

// Per-auditor pinned SoD business areas. Self-contained: fetches its own watchlist, pins/unpins,
// and opens the standard deep-dive. Stays in sync across pages via a `sap-watchlist-changed` event.
export function SodWatchlist() {
  const { openDeepDive } = useDeepDive();
  const [wl, setWl] = useState(null);
  const [add, setAdd] = useState("");

  const load = useCallback(async () => {
    const { data } = await api.get("/sap/watchlist");
    setWl(data);
  }, []);
  useEffect(() => {
    load();
    const h = () => load();
    window.addEventListener("sap-watchlist-changed", h);
    return () => window.removeEventListener("sap-watchlist-changed", h);
  }, [load]);

  const changed = () => window.dispatchEvent(new Event("sap-watchlist-changed"));
  const pin = async (area) => { if (!area) return; await api.post("/sap/watchlist", { area }); setAdd(""); changed(); };
  const unpin = async (area) => { await api.delete(`/sap/watchlist?area=${encodeURIComponent(area)}`); changed(); };

  const totalOpen = wl ? wl.available.reduce((s, a) => s + a.open, 0) : 0;
  const openArea = (s) => openDeepDive({
    accent: "0 84% 60%", refLabel: `SoD · ${s.area}`, title: `${s.area} — ${s.open} open SoD conflict(s)`,
    rating: s.open > 10 ? "Critical" : s.open > 3 ? "High" : s.open > 0 ? "Medium" : "Low", score: Math.min(99, 40 + s.open * 4),
    facets: [{ label: "Business area", value: s.area }, { label: "Open conflicts", value: s.open }, { label: "Critical", value: s.Critical }, { label: "Share of open", value: `${Math.round((s.open / Math.max(1, totalOpen)) * 100)}%` }],
    recommendedActions: [`Prioritise remediating the ${s.open} open SoD conflict(s) in ${s.area} — remove one side of each toxic role pair or apply a monitored mitigating control.`, "Enable auto-remediation for Critical conflicts in this area, then recertify the affected roles."],
    complianceRefs: ["SOX ITGC", "NIST AC-5", "ISO 27001 A.5.3"],
    explainTitle: `${s.area} — SoD conflict concentration`, explainKind: "SAP SoD conflict area remediation", explainContext: { area: s.area, open_conflicts: s.open, total_open: totalOpen },
  });

  const pinnedAreas = new Set((wl?.pinned || []).map((p) => p.area));
  const addable = (wl?.available || []).filter((a) => !pinnedAreas.has(a.area));

  return (
    <div className="bg-card fact-border rounded-xl p-5" data-testid="sod-watchlist">
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <Star className="w-4 h-4" style={{ color: "hsl(35 90% 55%)", fill: "hsl(35 90% 55%)" }} />
          <h2 className="font-head font-bold text-base">SoD Risk Watchlist</h2>
        </div>
        {wl && (
          <select data-testid="watchlist-add" value={add} onChange={(e) => pin(e.target.value)} className="h-8 rounded-md bg-secondary/50 border border-border text-xs px-2 focus:outline-none focus:ring-1 focus:ring-primary">
            <option value="">+ Pin an area…</option>
            {addable.map((a) => <option key={a.area} value={a.area}>{a.area} ({a.open} open)</option>)}
          </select>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground mb-3">Your pinned SoD business areas — hottest first. Click to drill into remediation.</p>
      {!wl && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…</div>}
      {wl && wl.pinned.length === 0 && (
        <div className="text-center py-6" data-testid="watchlist-empty">
          <ShieldAlert className="w-6 h-6 mx-auto text-muted-foreground mb-2" />
          <p className="text-xs text-muted-foreground">No areas pinned yet. Pin the SoD areas you own so their hot spots surface here every login.</p>
        </div>
      )}
      {wl && wl.pinned.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="watchlist-pinned">
          {wl.pinned.map((s, idx) => (
            <div key={s.area} data-testid={`watchlist-item-${idx}`} className="rounded-lg border border-border/70 bg-secondary/20 p-3 cursor-pointer hover:border-primary/50 transition-colors" onClick={() => openArea(s)}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    {s.Critical > 0 && <Flame className="w-3.5 h-3.5 shrink-0" style={{ color: "hsl(0 84% 60%)" }} />}
                    <span className="text-sm font-semibold truncate">{s.area}</span>
                  </div>
                  <div className="font-head font-black text-2xl mt-1" style={{ color: s.open > 0 ? "hsl(0 84% 60%)" : "hsl(142 70% 45%)" }}>{s.open}<span className="text-xs font-normal text-muted-foreground ml-1">open</span></div>
                </div>
                <button type="button" data-testid={`watchlist-unpin-${idx}`} onClick={(e) => { e.stopPropagation(); unpin(s.area); }} className="shrink-0 p-1 rounded hover:bg-secondary/60 transition-colors" title="Unpin from watchlist">
                  <Star className="w-4 h-4" style={{ color: "hsl(35 90% 55%)", fill: "hsl(35 90% 55%)" }} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {["Critical", "High", "Medium", "Low"].map((sv) => s[sv] > 0 ? (
                  <span key={sv} className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-full" style={{ background: `hsl(${SEV[sv]} / 0.15)`, color: `hsl(${SEV[sv]})` }}>{s[sv]} {sv}</span>
                ) : null)}
                {s.open === 0 && <span className="text-[10px] text-muted-foreground">Clean — no open conflicts</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
