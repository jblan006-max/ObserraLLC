import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Trophy, ShieldAlert, Loader2, Ticket, UserCircle2, Send, UserPlus } from "lucide-react";

// Ranked accountability board: who owns the most open Critical SoD. Admins can nudge every owner
// (emails each their hot spots) and assign an owner to any unowned area right from here.
export function SodOwnerLeaderboard() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [d, setD] = useState(null);
  const [openIdx, setOpenIdx] = useState(-1);
  const [nudgeBusy, setNudgeBusy] = useState(false);
  const [assign, setAssign] = useState({});
  const [assignBusy, setAssignBusy] = useState("");

  const load = useCallback(async () => {
    try { const { data } = await api.get("/sap/watchlist/leaderboard"); setD(data); } catch { /* noop */ }
  }, []);
  useEffect(() => {
    load();
    const h = () => load();
    window.addEventListener("sap-watchlist-changed", h);
    return () => window.removeEventListener("sap-watchlist-changed", h);
  }, [load]);

  const nudgeAll = async () => {
    if (!window.confirm("Email every owner their assigned Critical hot spots now?")) return;
    setNudgeBusy(true);
    try {
      const { data } = await api.post("/sap/watchlist/leaderboard/nudge");
      if (data.nudged > 0) toast.success(`Nudged ${data.nudged} owner(s)`, { description: "Each owner was emailed their assigned Critical hot spots." });
      else toast.info("No owners to nudge yet — assign owners to SoD areas first.");
    } catch (e) { toast.error(e?.response?.data?.detail || (e?.response?.status === 403 ? "Admin access required" : "Nudge failed")); }
    setNudgeBusy(false);
  };

  const doAssign = async (area) => {
    const owner = (assign[area] || "").trim();
    if (!owner || !owner.includes("@")) { toast.error("Enter a valid owner email"); return; }
    setAssignBusy(area);
    try {
      const { data } = await api.post("/sap/watchlist/remediate", { area, owner });
      toast.success(`${area} assigned to ${owner}`, { description: data?.ticket ? `Ticket ${data.ticket.number} opened` : "" });
      setAssign((a) => ({ ...a, [area]: "" }));
      window.dispatchEvent(new Event("sap-watchlist-changed"));
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not assign owner"); }
    setAssignBusy("");
  };

  const owners = d?.owners || [];
  const unassigned = d?.unassigned || [];
  const maxCrit = Math.max(1, ...owners.map((o) => o.Critical));

  return (
    <div className="bg-card fact-border rounded-xl p-5" data-testid="sod-leaderboard">
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <Trophy className="w-4 h-4" style={{ color: "hsl(35 90% 55%)" }} />
        <h2 className="font-head font-bold text-base">Owner Accountability Leaderboard</h2>
        <div className="flex-1" />
        {isAdmin && owners.length > 0 && (
          <button type="button" data-testid="leaderboard-nudge" onClick={nudgeAll} disabled={nudgeBusy} className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-primary/50 text-primary text-xs hover:bg-primary/10 transition-colors disabled:opacity-50">
            {nudgeBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Nudge all owners
          </button>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground mb-3">Who owns the most open Critical SoD across regions — balance remediation workload at a glance. One tap emails every owner their hot spots; assign an owner to any unowned area below.</p>

      {!d && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…</div>}

      {d && owners.length === 0 && unassigned.length === 0 && (
        <div className="text-center py-6" data-testid="leaderboard-empty">
          <UserCircle2 className="w-6 h-6 mx-auto text-muted-foreground mb-2" />
          <p className="text-xs text-muted-foreground">No SoD areas have an assigned owner yet. Assign owners below or from the SoD Risk Watchlist.</p>
        </div>
      )}

      {d && owners.length > 0 && (
        <>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="rounded-lg bg-secondary/30 p-3" data-testid="leaderboard-owners">
              <div className="font-head font-black text-2xl">{d.totals.owners}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5">Owners accountable</div>
            </div>
            <div className="rounded-lg bg-secondary/30 p-3" data-testid="leaderboard-assigned">
              <div className="font-head font-black text-2xl">{d.totals.assigned_areas}<span className="text-xs font-normal text-muted-foreground">/{d.totals.total_areas}</span></div>
              <div className="text-[10px] text-muted-foreground mt-0.5">Areas with an owner</div>
            </div>
            <div className="rounded-lg bg-secondary/30 p-3" data-testid="leaderboard-unassigned">
              <div className="font-head font-black text-2xl" style={{ color: d.totals.unassigned_critical > 0 ? "hsl(0 84% 60%)" : "hsl(142 70% 45%)" }}>{d.totals.unassigned_critical}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5">Unowned open Critical</div>
            </div>
          </div>

          <div className="space-y-2" data-testid="leaderboard-list">
            {owners.map((o, i) => (
              <div key={o.owner} data-testid={`leaderboard-owner-${i}`} className="rounded-lg border border-border/70 bg-secondary/20 overflow-hidden">
                <button type="button" data-testid={`leaderboard-owner-toggle-${i}`} onClick={() => setOpenIdx(openIdx === i ? -1 : i)} className="w-full text-left p-3 flex items-center gap-3 hover:bg-secondary/40 transition-colors">
                  <span className="font-head font-black text-lg w-6 text-center shrink-0" style={{ color: i === 0 ? "hsl(35 90% 55%)" : "hsl(var(--muted-foreground))" }}>{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">{o.owner}</div>
                    <div className="h-1.5 mt-1.5 rounded-full bg-secondary overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${Math.round((o.Critical / maxCrit) * 100)}%`, background: "hsl(0 84% 60%)" }} />
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span data-testid={`leaderboard-critical-${i}`} className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-full" style={{ background: "hsl(0 84% 60% / 0.15)", color: "hsl(0 84% 60%)" }}>{o.Critical} Critical</span>
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-full bg-secondary text-muted-foreground">{o.open} open</span>
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-full bg-secondary text-muted-foreground">{o.area_count} area{o.area_count === 1 ? "" : "s"}</span>
                  </div>
                </button>
                {openIdx === i && (
                  <div className="px-3 pb-3 space-y-1" data-testid={`leaderboard-areas-${i}`}>
                    {o.areas.map((a) => (
                      <div key={a.area} className="flex items-center gap-2 text-[11px] pl-9">
                        {a.Critical > 0 && <ShieldAlert className="w-3 h-3 shrink-0" style={{ color: "hsl(0 84% 60%)" }} />}
                        <span className="font-medium">{a.area}</span>
                        <span className="text-muted-foreground">{a.Critical} Critical · {a.open} open</span>
                        {a.ticket && <span className="inline-flex items-center gap-1 font-mono px-1.5 py-0.5 rounded-full bg-low/15 text-low ml-auto"><Ticket className="w-3 h-3" />{a.ticket}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {d && unassigned.length > 0 && (
        <div className="mt-4 border-t border-border pt-3" data-testid="leaderboard-unassigned-list">
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Unowned hot spots — assign an owner</div>
          <div className="space-y-1.5">
            {unassigned.slice(0, 8).map((a, i) => (
              <div key={a.area} data-testid={`leaderboard-unowned-${i}`} className="flex flex-wrap items-center gap-2 text-[11px] rounded-lg bg-secondary/20 border border-border/60 p-2">
                {a.Critical > 0 && <ShieldAlert className="w-3.5 h-3.5 shrink-0" style={{ color: "hsl(0 84% 60%)" }} />}
                <span className="font-medium">{a.area}</span>
                <span className="text-muted-foreground">{a.Critical} Critical · {a.open} open</span>
                {isAdmin && (
                  <div className="flex items-center gap-1.5 ml-auto" onClick={(e) => e.stopPropagation()}>
                    <input data-testid={`leaderboard-assign-input-${i}`} value={assign[a.area] || ""} onChange={(e) => setAssign((x) => ({ ...x, [a.area]: e.target.value }))} placeholder="owner@company.com" className="h-7 w-44 rounded bg-secondary/50 border border-border text-[11px] px-2 focus:outline-none focus:ring-1 focus:ring-primary" />
                    <button type="button" data-testid={`leaderboard-assign-btn-${i}`} onClick={() => doAssign(a.area)} disabled={assignBusy === a.area} className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50">
                      {assignBusy === a.area ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserPlus className="w-3 h-3" />} Assign
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
