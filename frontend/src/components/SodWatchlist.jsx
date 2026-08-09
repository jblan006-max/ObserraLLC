import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useDeepDive } from "@/context/DeepDiveContext";
import { toast } from "sonner";
import { Star, ShieldAlert, Loader2, Flame, Bell, BellOff, Ticket, UserPlus } from "lucide-react";

const SEV = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "199 89% 48%", Low: "142 70% 45%" };

// One pinned SoD area: hot-spot count + severity, a Critical-threshold nudge toggle, and a one-tap
// "assign owner + open ServiceNow remediation ticket". Holds its own owner-input/threshold state.
function WatchlistCard({ s, idx, onOpen, onUnpin, onAlert, onRemediate }) {
  const [thr, setThr] = useState(s.threshold || 1);
  const [showAssign, setShowAssign] = useState(false);
  const [owner, setOwner] = useState(s.owner || "");
  const [busy, setBusy] = useState(false);
  const stop = (e) => e.stopPropagation();

  const doRemediate = async (e) => {
    stop(e);
    setBusy(true);
    try {
      const t = await onRemediate(s.area, owner);
      if (t) toast.success(`Ticket ${t.number} opened for ${s.area}`);
      setShowAssign(false);
    } catch {
      toast.error("Could not open the remediation ticket");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid={`watchlist-item-${idx}`} className="rounded-lg border border-border/70 bg-secondary/20 p-3 cursor-pointer hover:border-primary/50 transition-colors" onClick={() => onOpen(s)}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            {s.Critical > 0 && <Flame className="w-3.5 h-3.5 shrink-0" style={{ color: "hsl(0 84% 60%)" }} />}
            <span className="text-sm font-semibold truncate">{s.area}</span>
          </div>
          <div className="font-head font-black text-2xl mt-1" style={{ color: s.open > 0 ? "hsl(0 84% 60%)" : "hsl(142 70% 45%)" }}>{s.open}<span className="text-xs font-normal text-muted-foreground ml-1">open</span></div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button type="button" data-testid={`watchlist-alert-${idx}`} onClick={(e) => { stop(e); onAlert(s.area, !s.alert, Math.max(1, parseInt(thr) || 1)); }} className="p-1 rounded hover:bg-secondary/60 transition-colors" title={s.alert ? `Nudging owner when Critical ≥ ${s.threshold}` : "Enable Critical-threshold nudge"}>
            {s.alert ? <Bell className="w-4 h-4" style={{ color: "hsl(35 90% 55%)" }} /> : <BellOff className="w-4 h-4 text-muted-foreground" />}
          </button>
          <button type="button" data-testid={`watchlist-unpin-${idx}`} onClick={(e) => { stop(e); onUnpin(s.area); }} className="p-1 rounded hover:bg-secondary/60 transition-colors" title="Unpin from watchlist">
            <Star className="w-4 h-4" style={{ color: "hsl(35 90% 55%)", fill: "hsl(35 90% 55%)" }} />
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 mt-2">
        {["Critical", "High", "Medium", "Low"].map((sv) => s[sv] > 0 ? (
          <span key={sv} className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-full" style={{ background: `hsl(${SEV[sv]} / 0.15)`, color: `hsl(${SEV[sv]})` }}>{s[sv]} {sv}</span>
        ) : null)}
        {s.open === 0 && <span className="text-[10px] text-muted-foreground">Clean — no open conflicts</span>}
      </div>

      {s.alert && (
        <div className="flex items-center gap-1.5 mt-2 text-[10px] text-muted-foreground" onClick={stop}>
          <Bell className="w-3 h-3" style={{ color: "hsl(35 90% 55%)" }} /> Nudge owner when Critical ≥
          <input type="number" min={1} data-testid={`watchlist-threshold-${idx}`} value={thr} onChange={(e) => setThr(e.target.value)} onBlur={() => onAlert(s.area, true, Math.max(1, parseInt(thr) || 1))} className="w-12 h-6 rounded bg-secondary/50 border border-border text-center text-[11px]" />
        </div>
      )}

      <div className="mt-2 pt-2 border-t border-border/60" onClick={stop}>
        {s.ticket ? (
          <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
            <span data-testid={`watchlist-ticket-${idx}`} className="inline-flex items-center gap-1 font-mono px-1.5 py-0.5 rounded-full bg-low/15 text-low"><Ticket className="w-3 h-3" />{s.ticket.number}</span>
            <span className="text-muted-foreground truncate">→ {s.owner || "unassigned"}</span>
            <button type="button" data-testid={`watchlist-reassign-${idx}`} onClick={() => setShowAssign((v) => !v)} className="text-primary hover:underline ml-auto">Reassign</button>
          </div>
        ) : !showAssign ? (
          <button type="button" data-testid={`watchlist-assign-${idx}`} onClick={() => setShowAssign(true)} className="inline-flex items-center gap-1.5 text-[11px] text-primary hover:underline"><UserPlus className="w-3.5 h-3.5" /> Assign owner &amp; open ticket</button>
        ) : null}
        {showAssign && (
          <div className="flex items-center gap-1.5 mt-1.5">
            <input data-testid={`watchlist-owner-input-${idx}`} value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="owner@company.com" className="flex-1 h-7 rounded bg-secondary/50 border border-border text-[11px] px-2 focus:outline-none focus:ring-1 focus:ring-primary" />
            <button type="button" data-testid={`watchlist-remediate-${idx}`} onClick={doRemediate} disabled={busy} className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50">{busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Ticket className="w-3 h-3" />} Open ticket</button>
          </div>
        )}
      </div>
    </div>
  );
}

// Per-auditor pinned SoD business areas. Self-contained: fetches its own watchlist, pins/unpins,
// toggles nudge alerts, opens remediation tickets, and opens the standard deep-dive. Stays in sync
// across pages via a `sap-watchlist-changed` window event.
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
  const setAlert = async (area, alert, threshold) => { await api.post("/sap/watchlist/alert", { area, alert, threshold }); changed(); };
  const remediate = async (area, owner) => {
    const { data } = await api.post("/sap/watchlist/remediate", { area, owner });
    changed();
    return data.ticket;
  };

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
      <p className="text-[11px] text-muted-foreground mb-3">Your pinned SoD business areas — hottest first. Click to drill in; toggle the bell to get nudged when a hot spot crosses your Critical threshold; open a remediation ticket in one tap.</p>
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
            <WatchlistCard key={s.area} s={s} idx={idx} onOpen={openArea} onUnpin={unpin} onAlert={setAlert} onRemediate={remediate} />
          ))}
        </div>
      )}
    </div>
  );
}
