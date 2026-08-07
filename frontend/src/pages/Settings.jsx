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
      if (data.dropped?.length) toast.warning(`Saved. Skipped invalid: ${data.dropped.join(", ")}`);
      else toast.success("Recipients saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save"); }
    setRecBusy(false);
  };

  const [testBusy, setTestBusy] = useState(false);
  const sendTest = async () => {
    setTestBusy(true);
    try {
      const { data } = await api.post("/reports/test-email");
      toast.success(`Test board report sent to ${data.to}`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not send test"); }
    setTestBusy(false);
  };

  const [brand, setBrand] = useState({ enabled: false, company_name: "", has_logo: false });
  const [brandLogo, setBrandLogo] = useState("");
  const [brandBusy, setBrandBusy] = useState(false);

  useEffect(() => {
    if (!isAdmin) return;
    api.get("/reports/branding").then(({ data }) => setBrand(data)).catch(() => {});
  }, [isAdmin]);

  const onLogoPick = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!["image/png", "image/jpeg"].includes(file.type)) {
      toast.error("Logo must be a PNG or JPEG image");
      e.target.value = ""; return;
    }
    if (file.size > 1.5 * 1024 * 1024) {
      toast.error("Logo too large — please use an image under 1.5MB");
      e.target.value = ""; return;
    }
    const reader = new FileReader();
    reader.onload = () => setBrandLogo(reader.result);
    reader.readAsDataURL(file);
  };

  const saveBranding = async () => {
    setBrandBusy(true);
    try {
      const { data } = await api.put("/reports/branding", {
        enabled: brand.enabled, company_name: brand.company_name, logo: brandLogo || "",
      });
      setBrand(data); setBrandLogo("");
      toast.success("Report branding saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save branding"); }
    setBrandBusy(false);
  };

  const removeBranding = async () => {
    setBrandBusy(true);
    try {
      const { data } = await api.put("/reports/branding", { enabled: false, company_name: "", remove_logo: true });
      setBrand(data); setBrandLogo("");
      toast.success("Reset to Obserra branding");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not reset"); }
    setBrandBusy(false);
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
          <div className="flex items-center gap-3 flex-wrap">
            <button data-testid="recipients-save" disabled={recBusy} onClick={saveRecipients}
              className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
              {recBusy && <Loader2 className="w-4 h-4 animate-spin" />} Save recipients
            </button>
            <button data-testid="send-test-report" disabled={testBusy} onClick={sendTest}
              className="px-5 py-2.5 rounded-md border border-primary/40 text-foreground hover:bg-primary/10 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
              {testBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4 text-primary" />} Send me a test now
            </button>
          </div>
        </div>
      )}

      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="report-branding-settings">
          <div className="flex items-center gap-2"><SettingsIcon className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Report Branding</h2></div>
          <p className="text-sm text-muted-foreground">Board reports use Obserra branding by default. Turn on custom branding to put your own company name and logo on generated PDFs and decks.</p>
          <label className="flex items-center gap-3 text-sm cursor-pointer">
            <input type="checkbox" data-testid="branding-enabled" checked={brand.enabled}
              onChange={(e) => setBrand({ ...brand, enabled: e.target.checked })} className="w-4 h-4 accent-primary" />
            <span>Use custom company branding on reports</span>
          </label>
          <div>
            <label className="text-xs text-muted-foreground">Company name</label>
            <input data-testid="branding-name" value={brand.company_name}
              onChange={(e) => setBrand({ ...brand, company_name: e.target.value })}
              placeholder="Acme Corp — Security & Risk"
              className="mt-1 w-full rounded-lg bg-secondary/40 border border-border p-2.5 text-sm text-foreground focus:outline-none focus:border-primary/50" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Company logo (PNG, transparent recommended){brand.has_logo ? " — a logo is on file" : ""}</label>
            <input type="file" accept="image/png,image/jpeg" data-testid="branding-logo" onChange={onLogoPick}
              className="mt-1 block w-full text-xs text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:text-primary-foreground file:px-3 file:py-1.5 file:text-xs file:font-medium" />
            {brandLogo && <img src={brandLogo} alt="logo preview" className="mt-2 h-12 w-auto object-contain bg-secondary/40 rounded p-1" />}
          </div>
          <button data-testid="branding-save" disabled={brandBusy} onClick={saveBranding}
            className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
            {brandBusy && <Loader2 className="w-4 h-4 animate-spin" />} Save branding
          </button>
        </div>
      )}
    </div>
  );
}
