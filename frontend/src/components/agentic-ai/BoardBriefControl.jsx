import { useEffect, useState } from "react";
import { CalendarClock, Loader2, Mail, Send } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

// Board Brief Scheduler — one-click Resend + cron cadence for the AI security executive brief.
export default function BoardBriefControl() {
  const [sch, setSch] = useState({ enabled: false, cadence: "monthly" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api.get("/agents/board-brief/schedule")
      .then(({ data }) => setSch(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async (next) => {
    setSaving(true);
    try {
      const { data } = await api.put("/agents/board-brief/schedule", next);
      setSch(data);
      toast.success(data.enabled ? `Board brief scheduled ${data.cadence}.` : "Board brief schedule turned off.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not save schedule.");
    } finally {
      setSaving(false);
    }
  };

  const sendNow = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/agents/board-brief/send");
      toast.success(`Executive brief emailed to ${data.sent} recipient(s).`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not send the brief.");
    } finally {
      setSending(false);
    }
  };

  if (loading) return null;

  return (
    <div
      data-testid="board-brief-control"
      className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card/60 px-3 py-2"
    >
      <CalendarClock className="w-4 h-4 text-ai" />
      <span className="text-[11px] font-head font-bold uppercase tracking-wider text-muted-foreground">Board brief</span>
      <button
        data-testid="board-brief-toggle"
        onClick={() => save({ enabled: !sch.enabled, cadence: sch.cadence })}
        disabled={saving}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold border transition-colors disabled:opacity-50 ${
          sch.enabled ? "bg-low/15 text-low border-low/30" : "bg-secondary/50 text-muted-foreground border-border"
        }`}
      >
        {saving && <Loader2 className="w-3 h-3 animate-spin" />}
        {sch.enabled ? "Scheduled" : "Off"}
      </button>
      <select
        data-testid="board-brief-cadence"
        value={sch.cadence}
        onChange={(e) => save({ enabled: sch.enabled, cadence: e.target.value })}
        disabled={saving}
        className="bg-secondary/60 rounded-md px-2 py-1 text-[11px] font-mono outline-none"
      >
        <option value="weekly">Weekly</option>
        <option value="monthly">Monthly</option>
      </select>
      <button
        data-testid="board-brief-send"
        onClick={sendNow}
        disabled={sending}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary text-primary-foreground text-[11px] font-head font-bold disabled:opacity-50"
      >
        {sending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
        Email now
      </button>
    </div>
  );
}
