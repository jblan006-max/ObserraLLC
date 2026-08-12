import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { api, API } from "@/lib/api";
import { toast } from "sonner";
import { Settings as SettingsIcon, Loader2, Mail, Compass, PlayCircle, Users, RotateCcw, Image as ImageIcon, Server, Package, FileText, RefreshCw, Send, Bookmark, X, Lock, Sparkles, MessageSquare } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SsoCard } from "@/components/SsoCard";
import { RuntimeConnectorCard } from "@/components/RuntimeConnectorCard";

const OPTIONS = [
  { value: "weekly", label: "Weekly", desc: "A digest every Monday morning" },
  { value: "daily", label: "Daily", desc: "A digest every morning" },
  { value: "off", label: "Off", desc: "No digest emails" },
];

function ChatAlertsCard() {
  const [st, setSt] = useState(null);
  const [teams, setTeams] = useState("");
  const [slack, setSlack] = useState("");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const load = () => api.get("/self-scan/alerts").then(({ data }) => setSt(data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const saveAlerts = async () => {
    if (!teams && !slack) { toast.error("Paste a Slack or Teams webhook URL first."); return; }
    setBusy(true);
    try { await api.put("/self-scan/alerts", { teams_url: teams || undefined, slack_url: slack || undefined }); setTeams(""); setSlack(""); load(); toast.success("Chat webhook saved — proof-of-control posts will start flowing."); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not save"); }
    setBusy(false);
  };
  const test = async () => {
    setTesting(true);
    try { await api.post("/self-scan/alerts/test"); toast.success("Test alert sent to your channel."); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not send test"); }
    setTesting(false);
  };
  return (
    <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="chat-alerts-settings">
      <div className="flex items-center gap-2"><MessageSquare className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Slack / Teams Alerts</h2></div>
      <p className="text-sm text-muted-foreground">Paste an incoming-webhook URL and Obserra posts governance events — including every kill-switch fire-drill proof-of-control receipt and Control Assurance SLA breaches — straight to your channel.</p>
      <div className="space-y-3">
        <div>
          <label className="text-xs text-muted-foreground">Slack incoming webhook{st?.slack_url_set && <span className="text-low"> · configured ({st.slack_masked})</span>}</label>
          <input data-testid="alerts-slack-url" value={slack} onChange={(e) => setSlack(e.target.value)} placeholder="https://hooks.slack.com/services/…"
            className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Microsoft Teams webhook{st?.teams_url_set && <span className="text-low"> · configured ({st.teams_masked})</span>}</label>
          <input data-testid="alerts-teams-url" value={teams} onChange={(e) => setTeams(e.target.value)} placeholder="https://outlook.office.com/webhook/…"
            className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
        </div>
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <button data-testid="alerts-save" disabled={busy} onClick={saveAlerts} className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">{busy && <Loader2 className="w-4 h-4 animate-spin" />} Save webhook</button>
        {(st?.slack_url_set || st?.teams_url_set) && (
          <button data-testid="alerts-test" disabled={testing} onClick={test} className="px-5 py-2.5 rounded-md border border-primary/40 text-foreground hover:bg-primary/10 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">{testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4 text-primary" />} Send test alert</button>
        )}
      </div>
    </div>
  );
}

export default function Settings() {
  const { user, setUser } = useAuth();
  const [cadence, setCadence] = useState(user?.digest_cadence || "weekly");
  const [busy, setBusy] = useState(false);

  const [licenses, setLicenses] = useState([]);

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

  const [brand, setBrand] = useState({ enabled: false, company_name: "", has_logo: false, accent: "" });
  const [brandLogo, setBrandLogo] = useState("");
  const [brandBusy, setBrandBusy] = useState(false);
  const [previewTheme, setPreviewTheme] = useState("dark");
  const [previewBust, setPreviewBust] = useState(Date.now());
  const previewSrc = `${API}/reports/branding/preview?theme=${previewTheme}&t=${previewBust}`;
  const [dlBusy, setDlBusy] = useState("");

  const downloadFile = async (path, filename, key) => {
    setDlBusy(key);
    try {
      const res = await api.get(path, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error(e.response?.data?.detail || "Download failed"); }
    setDlBusy("");
  };

  const [regenBusy, setRegenBusy] = useState(false);
  const regenGuides = async () => {
    setRegenBusy(true);
    try {
      await api.post("/deploy/regenerate-guides");
      toast.success("Guides regenerated from the latest screenshots");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not regenerate"); }
    setRegenBusy(false);
  };

  const [tourBusy, setTourBusy] = useState(false);
  const regenTourImages = async () => {
    setTourBusy(true);
    try {
      const { data } = await api.post("/deploy/regenerate-tour", {}, { timeout: 180000 });
      toast.success(`Tour images refreshed to match the current UI (${data.images?.length || 0} screens)`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not regenerate tour images"); }
    setTourBusy(false);
  };

  const [allVisualsBusy, setAllVisualsBusy] = useState(false);
  const refreshAllVisuals = async () => {
    setAllVisualsBusy(true);
    try {
      await api.post("/deploy/refresh-visuals");
      toast.success("Refreshing all visuals in the background — you'll get a notification when it's done (~1 min).");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not start refresh"); }
    setAllVisualsBusy(false);
  };

  const [resetBusy, setResetBusy] = useState(false);
  const resetDemo = async () => {
    if (!window.confirm("Reset to the demo dataset? This clears this organization's demo data and reloads the sample dataset.")) return;
    setResetBusy(true);
    try {
      const { data } = await api.post("/deploy/reset-demo");
      toast.success(`Demo dataset restored — ${data.persons} identities, ${data.accounts} accounts.`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not reset demo data"); }
    setResetBusy(false);
  };

  const [emailTo, setEmailTo] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);
  const [book, setBook] = useState([]);
  useEffect(() => { api.get("/deploy/recipients").then((r) => setBook(r.data.recipients || [])).catch(() => {}); }, []);
  const saveRecipient = async () => {
    if (!emailTo) return;
    const next = Array.from(new Set([...book, emailTo]));
    try { const { data } = await api.put("/deploy/recipients", { recipients: next }); setBook(data.recipients); toast.success("Saved to IT distribution list"); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not save"); }
  };
  const removeRecipient = async (e) => {
    const next = book.filter((x) => x !== e);
    try { const { data } = await api.put("/deploy/recipients", { recipients: next }); setBook(data.recipients); } catch { /* noop */ }
  };
  const emailDocs = async () => {
    setEmailBusy(true);
    try {
      await api.post("/deploy/email-docs", { to: emailTo });
      toast.success(`Guide + package emailed to ${emailTo}`);
      setEmailTo("");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not send email"); }
    setEmailBusy(false);
  };
  const [allBusy, setAllBusy] = useState(false);
  const emailAll = async () => {
    setAllBusy(true);
    try {
      const { data } = await api.post("/deploy/email-docs-all");
      toast.success(`Guide + package emailed to ${data.count} recipient(s)`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not send to list"); }
    setAllBusy(false);
  };
  const [owners, setOwners] = useState([]);
  const [ownerBusy, setOwnerBusy] = useState(false);
  useEffect(() => { if (!isAdmin) return; api.get("/owners").then((r) => setOwners(r.data.owners || [])).catch(() => {}); }, [isAdmin]);
  const setOwnerEmail = (name, email) => setOwners((o) => o.map((x) => x.name === name ? { ...x, email } : x));
  const saveOwners = async () => {
    setOwnerBusy(true);
    try {
      const directory = {};
      owners.forEach((o) => { if (o.email) directory[o.name] = o.email; });
      const { data } = await api.put("/owners", { directory });
      toast.success(`Saved ${data.count} owner email(s)`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save directory"); }
    setOwnerBusy(false);
  };
  const [hideSocial, setHideSocial] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  useEffect(() => { if (!isAdmin) return; api.get("/settings/auth-ui").then((r) => setHideSocial(!!r.data.hide_social)).catch(() => {}); }, [isAdmin]);
  useEffect(() => { if (!isAdmin) return; api.get("/licenses").then((r) => setLicenses(r.data || [])).catch(() => {}); }, [isAdmin]);
  const saveAuthUI = async (val) => {
    setHideSocial(val); setAuthBusy(true);
    try {
      await api.put("/settings/auth-ui", { hide_social: val });
      toast.success(val ? "Google & Apple hidden on the login screen" : "Google & Apple shown on the login screen");
    } catch { toast.error("Could not update login screen"); setHideSocial(!val); }
    setAuthBusy(false);
  };
  const [pricing, setPricing] = useState([]);
  const [priceBusy, setPriceBusy] = useState(false);
  useEffect(() => { if (!isAdmin) return; api.get("/admin/pricing").then((r) => setPricing(r.data || [])).catch(() => {}); }, [isAdmin]);
  const setPrice = (id, field, val) => setPricing((ps) => ps.map((p) => p.id === id ? { ...p, [field]: val } : p));
  const savePricing = async () => {
    setPriceBusy(true);
    try {
      const prices = {};
      pricing.forEach((p) => { prices[p.id] = { monthly: Number(p.monthly), yearly: Number(p.yearly) }; });
      const { data } = await api.put("/admin/pricing", { prices });
      toast.success(`Updated pricing for ${data.count} pack(s)`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not update pricing"); }
    setPriceBusy(false);
  };

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
        enabled: brand.enabled, company_name: brand.company_name, logo: brandLogo || "", accent: brand.accent || "",
      });
      setBrand(data); setBrandLogo(""); setPreviewBust(Date.now());
      toast.success("Report branding saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save branding"); }
    setBrandBusy(false);
  };

  const removeBranding = async () => {
    setBrandBusy(true);
    try {
      const { data } = await api.put("/reports/branding", { enabled: false, company_name: "", remove_logo: true });
      setBrand(data); setBrandLogo(""); setPreviewBust(Date.now());
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
        <div className="bg-card fact-border rounded-xl p-6 space-y-3" data-testid="live-data-settings">
          <h2 className="font-head font-bold text-lg">Live data mode</h2>
          <p className="text-sm text-muted-foreground">Remove all demo/sample data from this organization and run on live data only — your endpoint self-scan and live threat feeds, benchmarked against the IBM/AI figures. This cannot be undone.</p>
          <button data-testid="reset-to-live-btn" onClick={async () => {
            if (!window.confirm("Remove all demo data and switch to live-only? This clears sample risks, vendors, assets and mock connectors.")) return;
            try { const { data } = await api.post("/admin/reset-to-live"); toast.success(`Live-only enabled — ${data.live?.risks ?? 0} live risk(s) derived. Reloading…`); setTimeout(() => window.location.reload(), 1200); }
            catch (e) { toast.error(e.response?.data?.detail || "Reset failed"); }
          }} className="px-4 py-2 rounded-md bg-crit/15 text-crit border border-crit/30 font-head font-bold text-sm hover:bg-crit/25 transition-colors">Clear demo data &amp; go live</button>
        </div>
      )}

      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="owner-directory-settings">
          <div className="flex items-center gap-2"><Users className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Owner Directory</h2></div>
          <p className="text-sm text-muted-foreground">Map each control / vendor owner name to a real email so remediation nudges reach the right person instead of falling back to all admins. Leave blank to keep the admin fallback.</p>
          {owners.length === 0 ? <p className="text-xs text-muted-foreground">No owners found yet — they appear once controls & vendors load.</p> : (
            <div className="space-y-2" data-testid="owner-directory-list">
              {owners.map((o) => (
                <div key={o.name} className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium w-40 shrink-0 truncate" title={o.name}>{o.name}</span>
                  <input data-testid={`owner-email-${o.name.replace(/[^a-zA-Z0-9]/g, "-")}`} type="email" value={o.email}
                    onChange={(e) => setOwnerEmail(o.name, e.target.value)} placeholder="owner@company.com"
                    className="flex-1 min-w-[200px] bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
                  {!o.email && o.suggestion && (
                    <button data-testid={`owner-suggest-${o.name.replace(/[^a-zA-Z0-9]/g, "-")}`} onClick={() => setOwnerEmail(o.name, o.suggestion)}
                      className="text-[11px] px-2 py-1 rounded-md bg-ai/10 border border-ai/30 text-ai hover:bg-ai/20 transition-colors shrink-0">Use {o.suggestion}</button>
                  )}
                </div>
              ))}
            </div>
          )}
          {owners.length > 0 && (
            <button data-testid="owner-directory-save" disabled={ownerBusy} onClick={saveOwners}
              className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
              {ownerBusy && <Loader2 className="w-4 h-4 animate-spin" />} Save owner directory
            </button>
          )}
        </div>
      )}

      {isAdmin && licenses.length > 0 && (
        <div className="bg-card fact-border rounded-xl p-6 space-y-3" data-testid="licenses-settings">
          <div className="flex items-center gap-2"><Package className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Add-on License Keys</h2></div>
          <p className="text-xs text-muted-foreground">Keys issued when your add-on packs were activated. Keep them confidential.</p>
          <div className="space-y-2">
            {licenses.map((l, i) => (
              <div key={i} data-testid="license-row" className="flex flex-wrap items-center justify-between gap-2 bg-secondary/40 rounded-md px-3 py-2">
                <span className="text-sm font-medium">{l.pack}</span>
                <div className="flex items-center gap-2">
                  <code className="text-xs text-ai">{l.key}</code>
                  <button data-testid="license-copy" onClick={() => { navigator.clipboard.writeText(l.key); toast.success("License key copied"); }}
                    className="text-[11px] px-2 py-1 rounded-md bg-secondary hover:bg-secondary/70 transition-colors">Copy</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {isAdmin && pricing.length > 0 && (
        <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="pricing-settings">
          <div className="flex items-center gap-2"><Package className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Add-on Pricing</h2></div>
          <p className="text-xs text-muted-foreground">Set the monthly &amp; yearly price (USD) for each add-on pack. Saving updates the live Stripe prices — new checkouts are charged the new amount immediately.</p>
          <div className="space-y-2">
            {pricing.map((p) => (
              <div key={p.id} data-testid={`pricing-row-${p.id}`} className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium w-44 shrink-0 truncate">{p.name}</span>
                <label className="text-xs text-muted-foreground">$/mo <input data-testid={`price-monthly-${p.id}`} type="number" min="0" value={p.monthly} onChange={(e) => setPrice(p.id, "monthly", e.target.value)} className="ml-1 w-24 bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>
                <label className="text-xs text-muted-foreground">$/yr <input data-testid={`price-yearly-${p.id}`} type="number" min="0" value={p.yearly} onChange={(e) => setPrice(p.id, "yearly", e.target.value)} className="ml-1 w-24 bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>
              </div>
            ))}
          </div>
          <button data-testid="save-pricing" disabled={priceBusy} onClick={savePricing}
            className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
            {priceBusy && <Loader2 className="w-4 h-4 animate-spin" />} Save pricing
          </button>
        </div>
      )}

      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="login-screen-settings">
          <div className="flex items-center gap-2"><Lock className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Login Screen</h2></div>
          <div className="flex items-center justify-between gap-4">
            <div><p className="text-sm font-medium">Hide Google &amp; Apple sign-in</p><p className="text-xs text-muted-foreground">Zero third-party logos — keep email/password, passwordless QR and Enterprise SSO only.</p></div>
            <button data-testid="toggle-hide-social" role="switch" aria-checked={hideSocial} disabled={authBusy} onClick={() => saveAuthUI(!hideSocial)}
              className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${hideSocial ? "bg-primary" : "bg-secondary"}`}>
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${hideSocial ? "translate-x-5" : ""}`} />
            </button>
          </div>
        </div>
      )}

      {isAdmin && <SsoCard />}

      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="evidence-binder-settings">
          <div className="flex items-center gap-2"><FileText className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Audit Evidence Binder</h2></div>
          <p className="text-sm text-muted-foreground">Export every control &amp; vendor remediation/evidence log into one branded PDF pack for auditors.</p>
          <button data-testid="download-evidence-binder" disabled={dlBusy === "binder"} onClick={() => downloadFile("/reports/logs-pack.pdf", "obserra-evidence-binder.pdf", "binder")}
            className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
            {dlBusy === "binder" ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />} Download evidence binder (PDF)
          </button>
        </div>
      )}

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
          <div className="flex items-center gap-3 flex-wrap">
            <div>
            <label className="text-xs text-muted-foreground">Brand accent colour — flows into the report cover, trend line &amp; risk bars</label>
            <div className="mt-1 flex items-center gap-3">
              <input type="color" data-testid="branding-accent" value={brand.accent || "#12b4d6"}
                onChange={(e) => setBrand({ ...brand, accent: e.target.value })}
                className="h-9 w-14 rounded-md bg-secondary/40 border border-border cursor-pointer p-0.5" />
              <span className="text-xs font-mono text-muted-foreground">{brand.accent || "default"}</span>
              {brand.accent && (
                <button data-testid="branding-accent-clear" onClick={() => setBrand({ ...brand, accent: "" })}
                  className="text-xs text-muted-foreground hover:text-foreground underline">Clear</button>
              )}
            </div>
          </div>
          <button data-testid="branding-save" disabled={brandBusy} onClick={saveBranding}
              className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
              {brandBusy && <Loader2 className="w-4 h-4 animate-spin" />} Save branding
            </button>
            <button data-testid="branding-reset" disabled={brandBusy} onClick={removeBranding}
              className="px-5 py-2.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/40 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              <RotateCcw className="w-4 h-4" /> Remove logo / Reset to Obserra
            </button>
          </div>

          <div className="pt-2 border-t border-border" data-testid="branding-preview">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 text-xs font-head font-bold text-muted-foreground uppercase tracking-wide">
                <ImageIcon className="w-3.5 h-3.5 text-ai" /> Live cover preview
              </div>
              <div className="inline-flex rounded-md border border-border overflow-hidden">
                {["dark", "light"].map((t) => (
                  <button key={t} data-testid={`preview-theme-${t}`} onClick={() => setPreviewTheme(t)}
                    className={`px-3 py-1 text-xs font-head font-bold capitalize transition-colors ${previewTheme === t ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-muted-foreground mb-2">Reflects the current saved branding. Save changes to update this thumbnail.</p>
            <img key={previewSrc} data-testid="branding-preview-img" src={previewSrc} alt="Board report cover preview"
              className="w-full max-w-xs rounded-lg border border-border shadow-sm bg-secondary/40" />
          </div>
        </div>
      )}

      {isAdmin && <RuntimeConnectorCard />}

      {isAdmin && <ChatAlertsCard />}

      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="deployment-docs-settings">
          <div className="flex items-center gap-2"><Server className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Deployment &amp; Documentation</h2></div>
          <p className="text-sm text-muted-foreground">Obserra — Cyber Crisis Commander installs on any device as a one-click app (PWA) — on desktop use the Install button in the address bar or the in-app banner; on mobile use "Add to Home Screen". For fully self-hosted use, download the self-contained on-premise installer below — it bundles the full app source and a one-click <span className="text-foreground">./install.sh</span>. Every guide opens with a branded cover and contents page: grab the full <span className="text-foreground">Install &amp; User Guide</span>, a short <span className="text-foreground">Executive</span> guide, or the deeper <span className="text-foreground">Admin &amp; Operator</span> guide — each with screenshots and a walkthrough of the Cyber Crisis Commander dashboards.</p>
          <div className="flex items-center gap-3 flex-wrap">
            <button data-testid="download-onprem" disabled={dlBusy} onClick={() => downloadFile("/deploy/onprem-package", "Obserra-Control-Intelligence-OnPrem.zip", "onprem")} title="Self-contained one-click installer — bundles backend + frontend source, Docker Compose, and ./install.sh"
              className="px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
              {dlBusy === "onprem" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Package className="w-4 h-4" />} On‑premise package (.zip)
            </button>
            <button data-testid="download-guide-pdf" disabled={dlBusy} onClick={() => downloadFile("/deploy/guide.pdf", "Obserra-Control-Intelligence-Install-and-User-Guide.pdf", "pdf")}
              className="px-4 py-2.5 rounded-md border border-primary/40 text-foreground hover:bg-primary/10 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              {dlBusy === "pdf" ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4 text-primary" />} Install &amp; User Guide (PDF)
            </button>
            <button data-testid="download-guide-docx" disabled={dlBusy} onClick={() => downloadFile("/deploy/guide.docx", "Obserra-Control-Intelligence-Install-and-User-Guide.docx", "docx")}
              className="px-4 py-2.5 rounded-md border border-primary/40 text-foreground hover:bg-primary/10 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              {dlBusy === "docx" ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4 text-primary" />} Install &amp; User Guide (Word)
            </button>
            <button data-testid="download-guide-exec" disabled={dlBusy} onClick={() => downloadFile("/deploy/guide-exec.pdf", "Obserra-Control-Intelligence-Executive-Guide.pdf", "exec")}
              className="px-4 py-2.5 rounded-md border border-primary/40 text-foreground hover:bg-primary/10 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              {dlBusy === "exec" ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4 text-ai" />} Executive Guide (PDF)
            </button>
            <button data-testid="download-guide-admin" disabled={dlBusy} onClick={() => downloadFile("/deploy/guide-admin.pdf", "Obserra-Control-Intelligence-Admin-Operator-Guide.pdf", "admin")}
              className="px-4 py-2.5 rounded-md border border-primary/40 text-foreground hover:bg-primary/10 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              {dlBusy === "admin" ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4 text-primary" />} Admin &amp; Operator Guide (PDF)
            </button>
            <button data-testid="regenerate-guides" disabled={regenBusy} onClick={regenGuides}
              className="px-4 py-2.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/40 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              {regenBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Regenerate guides
            </button>
            <button data-testid="regenerate-tour" disabled={tourBusy} onClick={regenTourImages} title="Recapture the in-app tour preview screenshots from the live dashboards"
              className="px-4 py-2.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/40 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              {tourBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImageIcon className="w-4 h-4" />} Regenerate tour images
            </button>
            <button data-testid="refresh-all-visuals" disabled={allVisualsBusy} onClick={refreshAllVisuals} title="Recapture every dashboard screenshot once, then rebuild the in-app tour previews and the PDF/Word guides in one pass"
              className="px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 hover:opacity-90 transition-opacity">
              {allVisualsBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Refresh all visuals
            </button>
            <button data-testid="reset-demo" disabled={resetBusy} onClick={resetDemo} title="Clear this organization's demo data and reload the realistic sample dataset (demo / trial)"
              className="px-4 py-2.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-crit/50 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              {resetBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />} Reset to demo dataset
            </button>
          </div>
          <div className="flex items-center gap-2 flex-wrap pt-1" data-testid="email-docs-row">
            <input data-testid="email-docs-input" type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="it-team@company.com"
              className="flex-1 min-w-[200px] bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
            <button data-testid="email-docs-send" disabled={emailBusy || !emailTo} onClick={emailDocs}
              className="px-4 py-2.5 rounded-md bg-ai text-background font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
              {emailBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Email to IT team
            </button>
            <button data-testid="email-docs-save" disabled={!emailTo} onClick={saveRecipient}
              className="px-3 py-2.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/40 text-sm flex items-center gap-2 disabled:opacity-50 transition-colors">
              <Bookmark className="w-4 h-4" /> Save
            </button>
          </div>
          {book.length > 0 && (
            <div className="flex flex-wrap gap-2" data-testid="recipients-book">
              {book.map((e) => (
                <span key={e} className="inline-flex items-center gap-1 text-xs bg-secondary/60 rounded-full pl-3 pr-1 py-1">
                  <button data-testid={`book-pick-${e}`} onClick={() => setEmailTo(e)} className="hover:text-foreground">{e}</button>
                  <button data-testid={`book-remove-${e}`} onClick={() => removeRecipient(e)} className="p-0.5 rounded-full hover:bg-crit/20 text-muted-foreground hover:text-crit"><X className="w-3 h-3" /></button>
                </span>
              ))}
            </div>
          )}
          {book.length > 0 && (
            <button data-testid="email-docs-all" disabled={allBusy} onClick={emailAll}
              className="w-full sm:w-auto px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-50 hover:opacity-90 transition-opacity">
              {allBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Send to whole IT list ({book.length})
            </button>
          )}
          <p className="text-xs text-muted-foreground">Emails the Install &amp; User Guide (PDF) + on-premise package (zip) to a colleague or your IT team. Prefer a guided walkthrough? Use the built-in tour via <span className="text-foreground">Guided Tour → Replay tour</span> above — it now shows each dashboard with a screenshot before you land on it.</p>
        </div>
      )}
    </div>
  );
}
