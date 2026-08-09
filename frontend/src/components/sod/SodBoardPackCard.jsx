import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { FileText, Eye, Send, Loader2, CalendarClock } from "lucide-react";

// On-demand SAP board pack: preview THIS month's exec pack, send it now (admin), and configure the
// monthly auto-send day + recipients inline — no need to open the digest schedule.
export function SodBoardPackCard() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [open, setOpen] = useState(false);
  const [pv, setPv] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sendBusy, setSendBusy] = useState(false);
  const [cfg, setCfg] = useState(null);
  const [cfgBusy, setCfgBusy] = useState(false);

  const loadCfg = useCallback(async () => {
    try {
      const { data } = await api.get("/sap/board-pack/config");
      setCfg({ enabled: !!data.enabled, day: data.day, recipients: (data.recipients || []).join(", "), resolved: data.resolved_recipients || [] });
    } catch { /* noop */ }
  }, []);
  useEffect(() => { loadCfg(); }, [loadCfg]);

  const openPreview = async () => {
    setOpen(true); setBusy(true); setPv(null);
    try { const { data } = await api.get("/sap/board-pack/preview"); setPv(data); }
    catch (e) { toast.error(e?.response?.data?.detail || "Could not build the board pack preview"); setOpen(false); }
    setBusy(false);
  };
  const sendNow = async () => {
    if (!window.confirm(`Email this month's SAP board pack to ${pv?.recipients?.length || cfg?.resolved?.length || 0} recipient(s) now?`)) return;
    setSendBusy(true);
    try {
      const { data } = await api.post("/sap/board-pack/send", {});
      toast.success(`Board pack emailed to ${data.sent} recipient(s)`, { description: (data.recipients || []).join(", ") });
      setPv((p) => (p ? { ...p, already_sent: true, sent_at: new Date().toISOString() } : p));
    } catch (e) { toast.error(e?.response?.data?.detail || (e?.response?.status === 403 ? "Admin access required" : "Send failed")); }
    setSendBusy(false);
  };
  const saveCfg = async () => {
    setCfgBusy(true);
    try {
      const recips = (cfg.recipients || "").split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
      const day = Math.min(28, Math.max(1, Number(cfg.day) || 1));
      const { data } = await api.put("/sap/board-pack/config", { enabled: cfg.enabled, day, recipients: recips });
      setCfg((c) => ({ ...c, enabled: !!data.enabled, day: data.day, resolved: data.resolved_recipients || [] }));
      toast.success("Board pack schedule saved", { description: data.enabled ? `Auto-sends on day ${data.day} each month` : "Monthly auto-send is off" });
    } catch (e) { toast.error(e?.response?.data?.detail || (e?.response?.status === 403 ? "Admin access required" : "Save failed")); }
    setCfgBusy(false);
  };

  return (
    <div className="bg-card fact-border rounded-xl p-5" data-testid="sod-boardpack">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2"><FileText className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-base">Board Pack — on demand</h2></div>
        {cfg && (
          <span data-testid="boardpack-schedule-chip" className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-full" style={{ background: cfg.enabled ? "hsl(142 70% 45% / 0.15)" : "hsl(var(--secondary))", color: cfg.enabled ? "hsl(142 70% 38%)" : "hsl(var(--muted-foreground))" }}>
            {cfg.enabled ? `Auto-send · day ${cfg.day}` : "Auto-send off"}
          </span>
        )}
        <div className="flex-1" />
        <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="boardpack-preview-btn" onClick={openPreview}><Eye className="w-3.5 h-3.5" /> Preview board pack</Button>
        {isAdmin && (
          <Button size="sm" className="h-8 gap-1.5" data-testid="boardpack-send-btn" onClick={sendNow} disabled={sendBusy}>
            {sendBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Send now
          </Button>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground mt-1">The executive access-governance board pack (posture summary + hottest SoD areas + risk movers + 30-day remediation wins) with the full SAP analytics PDF attached. Preview it any time; admins can send immediately or schedule the monthly auto-send below.</p>

      {isAdmin && cfg && (
        <div className="mt-3 border-t border-border pt-3 grid grid-cols-1 md:grid-cols-4 gap-3 items-end" data-testid="boardpack-schedule">
          <div className="flex items-center gap-2">
            <Switch data-testid="boardpack-enable" checked={cfg.enabled} onCheckedChange={(v) => setCfg((c) => ({ ...c, enabled: v }))} />
            <span className="text-xs flex items-center gap-1"><CalendarClock className="w-3.5 h-3.5 text-muted-foreground" /> Monthly auto-send</span>
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Send on day of month</div>
            <Input type="number" min={1} max={28} data-testid="boardpack-day" value={cfg.day} onChange={(e) => setCfg((c) => ({ ...c, day: e.target.value }))} className="h-8" />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Recipients (blank = digest list)</div>
            <Input data-testid="boardpack-recipients-input" value={cfg.recipients} onChange={(e) => setCfg((c) => ({ ...c, recipients: e.target.value }))} placeholder={(cfg.resolved || []).join(", ")} className="h-8" />
          </div>
          <div className="flex justify-end">
            <Button size="sm" data-testid="boardpack-save" onClick={saveCfg} disabled={cfgBusy}>{cfgBusy ? "Saving…" : "Save schedule"}</Button>
          </div>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" data-testid="boardpack-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><FileText className="w-4 h-4 text-primary" /> Board Pack {pv?.month ? `— ${pv.month}` : ""}</DialogTitle></DialogHeader>
          {busy ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-10 justify-center" data-testid="boardpack-loading"><Loader2 className="w-4 h-4 animate-spin" /> Building this month's board pack…</div>
          ) : pv ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px]" data-testid="boardpack-recipients">
                <span className="text-[10px] font-mono uppercase text-muted-foreground">Recipients</span>
                {(pv.recipients || []).length ? pv.recipients.map((r) => (
                  <span key={r} className="font-mono px-1.5 py-0.5 rounded-full bg-secondary text-muted-foreground">{r}</span>
                )) : <span className="text-muted-foreground">No recipients set — add them below or in the digest schedule.</span>}
              </div>
              <div className="text-[11px] font-mono" data-testid="boardpack-status">
                {pv.already_sent
                  ? <span style={{ color: "hsl(142 70% 38%)" }}>Already sent this month{pv.sent_at ? ` · ${new Date(pv.sent_at).toLocaleString()}` : ""}</span>
                  : <span style={{ color: "hsl(35 90% 45%)" }}>Not yet sent this month</span>}
                {!pv.board_pack_enabled && <span className="text-muted-foreground"> · monthly auto-send is OFF</span>}
              </div>
              <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-border bg-white" data-testid="boardpack-body" dangerouslySetInnerHTML={{ __html: pv.html || "" }} />
              {isAdmin && (
                <div className="flex justify-end">
                  <Button size="sm" className="gap-1.5" data-testid="boardpack-send-confirm" onClick={sendNow} disabled={sendBusy}>
                    {sendBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Send to {(pv.recipients || []).length} recipient(s) now
                  </Button>
                </div>
              )}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
