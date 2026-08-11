import { useEffect, useState } from "react";
import { CheckCircle2, Database, Loader2, Mail, Send, ShieldCheck, X, XCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { DataClassBadge, Panel } from "@/components/control-intelligence/shared";

const SOURCE_LABEL = {
  controls: "Control Monitoring",
  compliance: "Control Compliance",
  crosswalk: "Framework Crosswalk",
  connectorHealth: "Connector Health",
};

function BriefSettingsCard() {
  const [recipients, setRecipients] = useState([]);
  const [sendDay, setSendDay] = useState(1);
  const [enabled, setEnabled] = useState(false);
  const [entry, setEntry] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get("/control-intelligence/settings");
        setRecipients(r.data.recipients || []);
        setSendDay(r.data.send_day || 1);
        setEnabled(Boolean(r.data.enabled));
      } catch {
        /* keep defaults */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const addRecipient = () => {
    const value = entry.trim().toLowerCase();
    if (!value.includes("@")) {
      toast.error("Enter a valid email address.");
      return;
    }
    if (recipients.includes(value)) {
      setEntry("");
      return;
    }
    setRecipients((list) => [...list, value]);
    setEntry("");
  };

  const removeRecipient = (email) =>
    setRecipients((list) => list.filter((item) => item !== email));

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put("/control-intelligence/settings", {
        recipients,
        send_day: sendDay,
        enabled,
      });
      setRecipients(r.data.recipients || []);
      setSendDay(r.data.send_day || 1);
      setEnabled(Boolean(r.data.enabled));
      toast.success("Board brief settings saved.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to save settings.");
    } finally {
      setSaving(false);
    }
  };

  const sendNow = async () => {
    setSending(true);
    try {
      const r = await api.post("/control-intelligence/email-brief");
      toast.success(`Assurance brief emailed to ${r.data.sent} recipient(s).`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to email the brief.");
    } finally {
      setSending(false);
    }
  };

  return (
    <Panel
      title="Executive Assurance Brief — recipients & schedule"
      subtitle="Choose exactly who receives the board brief and on which day of the month it is emailed. Admins and executives always receive it in addition to these recipients."
      testid="control-intel-brief-settings"
    >
      {loading ? (
        <div className="py-6 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading settings…
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
              Board recipients
            </label>
            <div className="flex flex-wrap gap-2 mt-2">
              {recipients.length === 0 && (
                <span className="text-xs text-muted-foreground">
                  No extra recipients — admins &amp; executives only.
                </span>
              )}
              {recipients.map((email) => (
                <span
                  key={email}
                  data-testid={`ci-brief-recipient-${email}`}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-secondary/40 text-xs"
                >
                  <Mail className="w-3 h-3 text-muted-foreground" />
                  {email}
                  <button
                    onClick={() => removeRecipient(email)}
                    data-testid={`ci-brief-recipient-remove-${email}`}
                    className="text-muted-foreground hover:text-crit"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2 mt-3">
              <input
                value={entry}
                onChange={(e) => setEntry(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRecipient())}
                placeholder="board.member@company.com"
                data-testid="ci-brief-recipient-input"
                className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
              <button
                onClick={addRecipient}
                data-testid="ci-brief-recipient-add"
                className="px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"
              >
                Add
              </button>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                Send day of month (1–28)
              </label>
              <input
                type="number"
                min={1}
                max={28}
                value={sendDay}
                onChange={(e) => setSendDay(Math.max(1, Math.min(28, Number(e.target.value) || 1)))}
                data-testid="ci-brief-send-day"
                className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                Scheduled monthly send
              </label>
              <button
                onClick={() => setEnabled((v) => !v)}
                data-testid="ci-brief-enabled-toggle"
                className={`mt-2 w-full inline-flex items-center justify-between px-3 py-2 rounded-md border text-sm font-head font-bold transition-colors ${
                  enabled ? "border-low/40 bg-low/10 text-low" : "border-border bg-secondary/40 text-muted-foreground"
                }`}
              >
                {enabled ? "Enabled" : "Disabled"}
                <span
                  className={`h-4 w-8 rounded-full relative transition-colors ${enabled ? "bg-low" : "bg-secondary"}`}
                >
                  <span
                    className={`absolute top-0.5 h-3 w-3 rounded-full bg-background transition-all ${enabled ? "left-4" : "left-0.5"}`}
                  />
                </span>
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            <button
              onClick={save}
              disabled={saving}
              data-testid="ci-brief-save"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              Save settings
            </button>
            <button
              onClick={sendNow}
              disabled={sending}
              data-testid="ci-brief-send-now"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50"
            >
              {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              Send brief now
            </button>
          </div>
        </div>
      )}
    </Panel>
  );
}

export default function DefensibilityDashboard({ data, sourceStatus, isAdmin }) {
  const connectors = data?.connectorHealth?.connectors || [];
  const summary = data?.connectorHealth?.summary || {};

  return (
    <div className="space-y-5">
      {isAdmin && <BriefSettingsCard />}
      <div className="grid xl:grid-cols-3 gap-5">
        <Panel
          title="Data source status"
          subtitle="Missing source data is shown as unavailable rather than replaced."
          testid="control-intel-source-status"
        >
          <div className="space-y-2">
            {Object.entries(sourceStatus || {}).map(([key, status]) => (
              <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="flex items-center gap-2">
                  {status.ok ? (
                    <CheckCircle2 className="w-4 h-4 text-low" />
                  ) : (
                    <XCircle className="w-4 h-4 text-crit" />
                  )}
                  <div>
                    <div className="text-sm font-medium">{SOURCE_LABEL[key] || key}</div>
                    {!status.ok && <div className="text-[10px] text-muted-foreground">{status.error}</div>}
                  </div>
                </div>
                <span className={`text-[10px] font-mono ${status.ok ? "text-low" : "text-crit"}`}>
                  {status.ok ? "LIVE" : "UNAVAILABLE"}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Evidence classification"
          subtitle="Control Intelligence separates source facts from calculations and recommendations."
          testid="control-intel-classification"
        >
          <div className="space-y-4">
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="FACT" />
              <p className="text-xs text-muted-foreground mt-2">
                Control status, effectiveness, maturity, owner, evidence expiry, framework coverage, crosswalk mappings and history records returned by the current backend.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="MODELLED" />
              <p className="text-xs text-muted-foreground mt-2">
                Control health score, priority score, evidence state grouping and cross-framework convergence ranking calculated in the browser.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="AI RECOMMENDATION" />
              <p className="text-xs text-muted-foreground mt-2">
                Obserra Advisor explanations and recommended control actions.
              </p>
            </div>
          </div>
        </Panel>

        <Panel
          title="Governance boundary"
          subtitle="This standalone application composes on existing services."
          testid="control-intel-boundary"
        >
          <div className="space-y-3 text-sm">
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              No new backend service or database collection is introduced.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Evidence pack and control log exports use existing report APIs.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Control notes use the existing control history and notes APIs.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Framework intelligence uses the existing compliance and crosswalk APIs.
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        title="Connector health context"
        subtitle={`${summary.healthy || 0} healthy · ${summary.degraded || 0} degraded. Existing connector health only.`}
        testid="control-intel-connectors"
      >
        {connectors.length === 0 ? (
          <div className="py-8 text-center">
            <Database className="w-8 h-8 text-muted-foreground mx-auto" />
            <div className="text-sm text-muted-foreground mt-2">No connector health records are available.</div>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {connectors.map((connector) => (
              <div key={`${connector.id}:${connector.name}`} className="rounded-lg border border-border p-3">
                <div className="font-head font-bold text-sm">{connector.name}</div>
                <div className="text-[10px] text-muted-foreground mt-1">{connector.category}</div>
                <div className="text-[10px] font-mono mt-2">
                  {connector.health || connector.state || "unknown"}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
