import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  Calendar, CheckCircle2, Copy, Database, Eye, Gavel, Link2, Loader2, Mail, RefreshCw, Send, ShieldCheck, Trash2, Users, X, XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { DataClassBadge, Panel } from "@/components/control-intelligence/shared";

const SOURCE_LABEL = {
  controls: "Control Monitoring",
  compliance: "Control Compliance",
  crosswalk: "Framework Crosswalk",
  connectorHealth: "Connector Health",
};

const ROLE_META = {
  board: { label: "Board", icon: Users, tone: "border-ai/40 bg-ai/10 text-ai" },
  auditor: { label: "Auditor", icon: Gavel, tone: "border-med/40 bg-med/10 text-med" },
};

function nextSendDate(sendDay, enabled, cadence) {
  if (!enabled) return null;
  const now = new Date();
  const day = Math.max(1, Math.min(28, sendDay || 1));
  const isQ = cadence === "quarterly";
  const qMonths = [0, 3, 6, 9];
  for (let i = 0; i < 16; i++) {
    const target = new Date(now.getFullYear(), now.getMonth() + i, day);
    if (isQ && !qMonths.includes(target.getMonth())) continue;
    if (i === 0 && now.getDate() > day) continue;
    return target;
  }
  return null;
}

function BriefPreviewModal({ html, loading, onClose }) {
  return createPortal(
    <div
      className="fixed inset-0 z-[9999] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      data-testid="ci-brief-preview-modal"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl max-h-[85vh] bg-card rounded-2xl border border-border overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <div className="font-head font-black text-lg flex items-center gap-2">
            <Eye className="w-4 h-4 text-ai" /> Assurance brief preview
          </div>
          <button onClick={onClose} data-testid="ci-brief-preview-close" className="text-muted-foreground hover:text-foreground">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-auto bg-white">
          {loading ? (
            <div className="py-20 flex items-center justify-center gap-2 text-sm text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin" /> Building preview…
            </div>
          ) : (
            <iframe title="brief-preview" srcDoc={html} className="w-full h-[70vh] border-0" data-testid="ci-brief-preview-frame" />
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

function BriefSettingsCard() {
  const [recipients, setRecipients] = useState([]);
  const [sendDay, setSendDay] = useState(1);
  const [enabled, setEnabled] = useState(false);
  const [cadence, setCadence] = useState("monthly");
  const [entry, setEntry] = useState("");
  const [entryRole, setEntryRole] = useState("board");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [auditorLink, setAuditorLink] = useState(null);
  const [expiryDays, setExpiryDays] = useState(90);
  const [linkBusy, setLinkBusy] = useState(false);
  const [counts, setCounts] = useState(null);

  const refreshCounts = () =>
    api.get("/control-intelligence/brief/recipients").then((r) => setCounts(r.data)).catch(() => {});

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get("/control-intelligence/settings");
        setRecipients(r.data.recipients || []);
        setSendDay(r.data.send_day || 1);
        setEnabled(Boolean(r.data.enabled));
        setCadence(r.data.cadence || "monthly");
      } catch {
        /* keep defaults */
      } finally {
        setLoading(false);
      }
      try {
        const link = await api.get("/control-intelligence/auditor-link");
        if (link.data.active) setAuditorLink(link.data);
      } catch {
        /* none yet */
      }
      refreshCounts();
    })();
  }, []);

  const addRecipient = () => {
    const value = entry.trim().toLowerCase();
    if (!value.includes("@")) {
      toast.error("Enter a valid email address.");
      return;
    }
    if (recipients.some((r) => r.email === value)) {
      setEntry("");
      return;
    }
    setRecipients((list) => [...list, { email: value, role: entryRole }]);
    setEntry("");
  };

  const removeRecipient = (email) => setRecipients((list) => list.filter((item) => item.email !== email));

  const toggleRole = (email) =>
    setRecipients((list) =>
      list.map((item) => (item.email === email ? { ...item, role: item.role === "board" ? "auditor" : "board" } : item))
    );

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put("/control-intelligence/settings", { recipients, send_day: sendDay, enabled, cadence });
      setRecipients(r.data.recipients || []);
      setSendDay(r.data.send_day || 1);
      setEnabled(Boolean(r.data.enabled));
      setCadence(r.data.cadence || "monthly");
      refreshCounts();
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

  const openPreview = async () => {
    setPreviewOpen(true);
    setPreviewLoading(true);
    try {
      const r = await api.get("/control-intelligence/brief/preview");
      setPreviewHtml(r.data.html || "<p style='font:400 14px Arial;padding:24px'>No preview content.</p>");
    } catch (e) {
      setPreviewHtml("");
      toast.error(e.response?.data?.detail || "Unable to build the preview.");
      setPreviewOpen(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  const generateLink = async (reissue) => {
    setLinkBusy(true);
    try {
      const r = await api.post("/control-intelligence/auditor-link", { days: expiryDays, reissue });
      setAuditorLink(r.data);
      toast.success(reissue ? "New auditor link issued (old one revoked)." : "Auditor verification link ready.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to generate the auditor link.");
    } finally {
      setLinkBusy(false);
    }
  };

  const revokeLink = async () => {
    setLinkBusy(true);
    try {
      await api.post("/control-intelligence/auditor-link/revoke");
      setAuditorLink(null);
      toast.success("Auditor link revoked.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to revoke the link.");
    } finally {
      setLinkBusy(false);
    }
  };

  const copyLink = async () => {
    if (!auditorLink?.url) return;
    try {
      await navigator.clipboard.writeText(auditorLink.url);
      toast.success("Auditor link copied.");
    } catch {
      toast.error("Copy failed — select and copy manually.");
    }
  };

  const next = nextSendDate(sendDay, enabled, cadence);
  const boardCount = recipients.filter((r) => r.role === "board").length;
  const auditorCount = recipients.filter((r) => r.role === "auditor").length;
  const sendLabel = counts ? `Send now → ${counts.board} Board · ${counts.auditor} Auditor` : "Send brief now";

  return (
    <Panel
      title="Executive Assurance Brief — recipients & schedule"
      subtitle="Choose who receives the board brief, assign each a Board or Auditor cover note, and pick the cadence and day it is emailed. Admins and executives always receive the Board version."
      testid="control-intel-brief-settings"
    >
      {loading ? (
        <div className="py-6 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading settings…
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Brief recipients &amp; roles</label>
            <div className="flex flex-wrap gap-2 mt-2">
              {recipients.length === 0 && (
                <span className="text-xs text-muted-foreground">No extra recipients — admins &amp; executives only (Board version).</span>
              )}
              {recipients.map(({ email, role }) => {
                const meta = ROLE_META[role] || ROLE_META.board;
                const RoleIcon = meta.icon;
                return (
                  <span
                    key={email}
                    data-testid={`ci-brief-recipient-${email}`}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-secondary/40 text-xs"
                  >
                    <Mail className="w-3 h-3 text-muted-foreground" />
                    {email}
                    <button
                      onClick={() => toggleRole(email)}
                      data-testid={`ci-brief-recipient-role-${email}`}
                      title="Toggle Board / Auditor"
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border text-[9px] font-mono font-bold ${meta.tone}`}
                    >
                      <RoleIcon className="w-2.5 h-2.5" />
                      {meta.label}
                    </button>
                    <button
                      onClick={() => removeRecipient(email)}
                      data-testid={`ci-brief-recipient-remove-${email}`}
                      className="text-muted-foreground hover:text-crit"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                );
              })}
            </div>
            <div className="text-[11px] text-muted-foreground mt-2" data-testid="ci-brief-recipient-summary">
              {boardCount} Board · {auditorCount} Auditor · admins/execs always Board
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              <input
                value={entry}
                onChange={(e) => setEntry(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRecipient())}
                placeholder="recipient@company.com"
                data-testid="ci-brief-recipient-input"
                className="flex-1 min-w-[180px] rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
              <div className="inline-flex rounded-md border border-border overflow-hidden" data-testid="ci-brief-role-select">
                {["board", "auditor"].map((r) => {
                  const meta = ROLE_META[r];
                  const RoleIcon = meta.icon;
                  const active = entryRole === r;
                  return (
                    <button
                      key={r}
                      onClick={() => setEntryRole(r)}
                      data-testid={`ci-brief-role-${r}`}
                      className={`inline-flex items-center gap-1 px-2.5 py-2 text-xs font-head font-bold transition-colors ${
                        active ? "bg-primary text-primary-foreground" : "bg-secondary/40 text-muted-foreground"
                      }`}
                    >
                      <RoleIcon className="w-3 h-3" />
                      {meta.label}
                    </button>
                  );
                })}
              </div>
              <button
                onClick={addRecipient}
                data-testid="ci-brief-recipient-add"
                className="px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"
              >
                Add
              </button>
            </div>
          </div>

          <div className="grid sm:grid-cols-3 gap-4">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Cadence</label>
              <div className="mt-2 inline-flex w-full rounded-md border border-border overflow-hidden" data-testid="ci-brief-cadence">
                {["monthly", "quarterly"].map((c) => (
                  <button
                    key={c}
                    onClick={() => setCadence(c)}
                    data-testid={`ci-brief-cadence-${c}`}
                    className={`flex-1 px-2 py-2 text-xs font-head font-bold capitalize transition-colors ${
                      cadence === c ? "bg-primary text-primary-foreground" : "bg-secondary/40 text-muted-foreground"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Send day (1–28)</label>
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
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Scheduled send</label>
              <button
                onClick={() => setEnabled((v) => !v)}
                data-testid="ci-brief-enabled-toggle"
                className={`mt-2 w-full inline-flex items-center justify-between px-3 py-2 rounded-md border text-sm font-head font-bold transition-colors ${
                  enabled ? "border-low/40 bg-low/10 text-low" : "border-border bg-secondary/40 text-muted-foreground"
                }`}
              >
                {enabled ? "On" : "Off"}
                <span className={`h-4 w-8 rounded-full relative transition-colors ${enabled ? "bg-low" : "bg-secondary"}`}>
                  <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-background transition-all ${enabled ? "left-4" : "left-0.5"}`} />
                </span>
              </button>
            </div>
          </div>

          <div
            data-testid="ci-brief-next-send"
            className="flex items-center gap-2 text-xs text-muted-foreground rounded-md border border-border bg-secondary/20 px-3 py-2"
          >
            <Calendar className="w-3.5 h-3.5 text-primary" />
            {next
              ? `Next scheduled send: ${next.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })} (08:00 UTC, ${cadence})`
              : "Scheduled send is off — enable it above to auto-email the brief."}
          </div>

          <div className="rounded-lg border border-border p-4">
            <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Gavel className="w-3 h-3" /> Auditor verification link
            </label>
            <p className="text-xs text-muted-foreground mt-1">
              A read-only Obserra link external auditors can open to verify live control evidence in-app. It is auto-included in Auditor-role briefs.
            </p>
            <div className="flex items-center gap-2 mt-3">
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Valid for</span>
              <input
                type="number"
                min={1}
                max={365}
                value={expiryDays}
                onChange={(e) => setExpiryDays(Math.max(1, Math.min(365, Number(e.target.value) || 90)))}
                data-testid="ci-auditor-link-expiry"
                className="w-20 rounded-md border border-border bg-background px-2 py-1.5 text-sm"
              />
              <span className="text-[10px] font-mono text-muted-foreground">days</span>
            </div>
            {auditorLink ? (
              <div className="mt-3 space-y-2">
                <div className="flex flex-wrap gap-2">
                  <input
                    readOnly
                    value={auditorLink.url}
                    data-testid="ci-auditor-link-url"
                    className="flex-1 min-w-[220px] rounded-md border border-border bg-background px-3 py-2 text-xs font-mono"
                  />
                  <button onClick={copyLink} data-testid="ci-auditor-link-copy" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">
                    <Copy className="w-3.5 h-3.5" /> Copy
                  </button>
                  <a href={auditorLink.url} target="_blank" rel="noreferrer" data-testid="ci-auditor-link-open" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">
                    <Link2 className="w-3.5 h-3.5" /> Open
                  </a>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {auditorLink.expires_at && (
                    <span className="text-[10px] font-mono text-muted-foreground">Expires {new Date(auditorLink.expires_at).toLocaleDateString()}</span>
                  )}
                  <button onClick={() => generateLink(true)} disabled={linkBusy} data-testid="ci-auditor-link-reissue" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border bg-secondary/40 text-[11px] font-head font-bold disabled:opacity-50">
                    {linkBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Re-issue
                  </button>
                  <button onClick={revokeLink} disabled={linkBusy} data-testid="ci-auditor-link-revoke" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-crit/40 bg-crit/10 text-crit text-[11px] font-head font-bold disabled:opacity-50">
                    <Trash2 className="w-3 h-3" /> Revoke
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => generateLink(false)}
                disabled={linkBusy}
                data-testid="ci-auditor-link-generate"
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50"
              >
                {linkBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Link2 className="w-3.5 h-3.5" />}
                Generate auditor link
              </button>
            )}
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            <button onClick={save} disabled={saving} data-testid="ci-brief-save" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              Save settings
            </button>
            <button onClick={openPreview} data-testid="ci-brief-preview" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">
              <Eye className="w-3.5 h-3.5" />
              Preview brief
            </button>
            <button onClick={sendNow} disabled={sending} data-testid="ci-brief-send-now" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">
              {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              {sendLabel}
            </button>
          </div>
        </div>
      )}

      {previewOpen && <BriefPreviewModal html={previewHtml} loading={previewLoading} onClose={() => setPreviewOpen(false)} />}
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
        <Panel title="Data source status" subtitle="Missing source data is shown as unavailable rather than replaced." testid="control-intel-source-status">
          <div className="space-y-2">
            {Object.entries(sourceStatus || {}).map(([key, status]) => (
              <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="flex items-center gap-2">
                  {status.ok ? <CheckCircle2 className="w-4 h-4 text-low" /> : <XCircle className="w-4 h-4 text-crit" />}
                  <div>
                    <div className="text-sm font-medium">{SOURCE_LABEL[key] || key}</div>
                    {!status.ok && <div className="text-[10px] text-muted-foreground">{status.error}</div>}
                  </div>
                </div>
                <span className={`text-[10px] font-mono ${status.ok ? "text-low" : "text-crit"}`}>{status.ok ? "LIVE" : "UNAVAILABLE"}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Evidence classification" subtitle="Control Intelligence separates source facts from calculations and recommendations." testid="control-intel-classification">
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
              <p className="text-xs text-muted-foreground mt-2">Obserra Advisor explanations and recommended control actions.</p>
            </div>
          </div>
        </Panel>

        <Panel title="Governance boundary" subtitle="This standalone application composes on existing services." testid="control-intel-boundary">
          <div className="space-y-3 text-sm">
            <div className="flex gap-2"><ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />No new backend service or database collection is introduced.</div>
            <div className="flex gap-2"><ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />Evidence pack and control log exports use existing report APIs.</div>
            <div className="flex gap-2"><ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />Control notes use the existing control history and notes APIs.</div>
            <div className="flex gap-2"><ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />Framework intelligence uses the existing compliance and crosswalk APIs.</div>
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
                <div className="text-[10px] font-mono mt-2">{connector.health || connector.state || "unknown"}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
