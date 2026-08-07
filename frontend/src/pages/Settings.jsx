import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Settings as SettingsIcon, Loader2, Mail, Compass, PlayCircle, Users } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const OPTIONS = [
  { value: "weekly", label: "Weekly", desc: "A digest every Monday morning" },
  { value: "daily", label: "Daily", desc: "A digest every morning" },
  { value: "off", label: "Off", desc: "No digest emails" },
];

export default function Settings() {
  const { user, setUser } = useAuth();
  const [cadence, setCadence] = useState(user?.digest_cadence || "weekly");
  const [busy, setBusy] = useState(false);

  const replayTour = () => {
    const k = `obserra-tour-done-${user?.id || user?.email}`;
    localStorage.removeItem(k);
    window.dispatchEvent(new CustomEvent("obserra-replay-tour"));
  };

  const isAdmin = user?.role === "admin";
  const [recips, setRecips] = useState("");
  const [autoRecips, setAutoRecips] = useState([]);
  const [recBusy, setRecBusy] = useState(false);

  useEffect(() => {
    if (!isAdmin) return;
    api.get("/reports/recipients").then(({ data }) => {
      setRecips((data.extra || []).join(", "));
      setAutoRecips(data.auto || []);
    }).catch(() => {});
  }, [isAdmin]);

  const saveRecipients = async () => {
    setRecBusy(true);
    try {
      const emails = recips.split(/[,\n]/).map((e) => e.trim()).filter(Boolean);
      const { data } = await api.put("/reports/recipients", { emails });
      setRecips((data.extra || []).join(", "));
      toast.success("Recipients saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save"); }
    setRecBusy(false);
  };

  const save = async () => {
    setBusy(true);
    try {
      await api.patch("/auth/preferences", { digest_cadence: cadence });
      const { data } = await api.get("/auth/me");
      setUser(data);
      toast.success("Preferences saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save"); }
    setBusy(false);
  };

  return (
    <div className="rise space-y-6 max-w-2xl">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><SettingsIcon className="w-7 h-7 text-primary" /> Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Personal preferences for {user?.email}.</p>
      </div>

      <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="digest-preferences">
        <div className="flex items-center gap-2"><Mail className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Drift Digest Emails</h2></div>
        <p className="text-sm text-muted-foreground">How often would you like a summary of open control-drift alerts emailed to you?</p>
        <div className="grid sm:grid-cols-3 gap-3">
          {OPTIONS.map((o) => (
            <button key={o.value} data-testid={`digest-${o.value}`} onClick={() => setCadence(o.value)}
              className={`text-left rounded-lg p-4 border transition-colors ${cadence === o.value ? "border-primary bg-primary/10" : "border-border hover:border-primary/40"}`}>
              <div className="font-head font-bold text-sm">{o.label}</div>
              <div className="text-xs text-muted-foreground mt-1">{o.desc}</div>
            </button>
          ))}
        </div>
        <button data-testid="digest-save" disabled={busy} onClick={save}
          className="mt-2 px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />} Save preferences
        </button>
      </div>

      <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="guided-tour-settings">
        <div className="flex items-center gap-2"><Compass className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Guided Tour</h2></div>
        <p className="text-sm text-muted-foreground">Revisit the quick walkthrough of Executive vs Operational mode anytime.</p>
        <button data-testid="replay-tour" onClick={replayTour}
          className="px-5 py-2.5 rounded-md border border-primary/40 text-foreground hover:bg-primary/10 font-head font-bold text-sm flex items-center gap-2 transition-colors">
          <PlayCircle className="w-4 h-4 text-primary" /> Replay tour
        </button>
      </div>

      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="report-recipients-settings">
          <div className="flex items-center gap-2"><Users className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Board Report Recipients</h2></div>
          <p className="text-sm text-muted-foreground">The monthly board PDF is always sent to all admins &amp; executives. Add any extra recipients below (comma-separated).</p>
          {autoRecips.length > 0 && (
            <div className="text-xs text-muted-foreground">Always included: <span className="text-foreground">{autoRecips.join(", ")}</span></div>
          )}
          <textarea data-testid="recipients-input" value={recips} onChange={(e) => setRecips(e.target.value)}
            placeholder="board.chair@example.com, ciso@example.com"
            className="w-full min-h-[80px] rounded-lg bg-secondary/40 border border-border p-3 text-sm text-foreground focus:outline-none focus:border-primary/50" />
          <button data-testid="recipients-save" disabled={recBusy} onClick={saveRecipients}
            className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
            {recBusy && <Loader2 className="w-4 h-4 animate-spin" />} Save recipients
          </button>
        </div>
      )}
    </div>
  );
}
