import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  Calendar, CheckCircle2, Copy, Database, Download, Eye, FileText, Gavel, Link2, Loader2, Mail, RefreshCw, Send, ShieldCheck, Trash2, Users, X, XCircle,
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

function BriefPreviewModal({ html, src, loading, onClose }) {
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
            {src ? <FileText className="w-4 h-4 text-ai" /> : <Eye className="w-4 h-4 text-ai" />}
            {src ? "Branded PDF preview" : "Assurance brief preview"}
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
          ) : src ? (
            <iframe title="brief-pdf-preview" src={src} className="w-full h-[70vh] border-0" data-testid="ci-brief-preview-frame" />
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
  const [previewSrc, setPreviewSrc] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [auditorLink, setAuditorLink] = useState(null);
  const [expiryDays, setExpiryDays] = useState(90);
  const [linkBusy, setLinkBusy] = useState(false);
  const [counts, setCounts] = useState(null);
  const [accessLog, setAccessLog] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [dropDays, setDropDays] = useState(2);
  const [askName, setAskName] = useState(false);
  const [recap, setRecap] = useState(null);
  const [recapBusy, setRecapBusy] = useState(false);
  const [recapEnabled, setRecapEnabled] = useState(false);
  const [recapWeekday, setRecapWeekday] = useState(0);
  const [timeline, setTimeline] = useState(null);

  const refreshCounts = () =>
    api.get("/control-intelligence/brief/recipients").then((r) => setCounts(r.data)).catch(() => {});
  const refreshAccess = () =>
    api.get("/control-intelligence/auditor-link/access?limit=12").then((r) => setAccessLog(r.data.events || [])).catch(() => {});
  const refreshAnalytics = () =>
    api.get("/control-intelligence/auditor-link/analytics").then((r) => setAnalytics(r.data)).catch(() => {});
  const refreshTimeline = () =>
    api.get("/control-intelligence/auditor-link/timeline").then((r) => setTimeline(r.data.people || [])).catch(() => {});

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get("/control-intelligence/settings");
        setRecipients(r.data.recipients || []);
        setSendDay(r.data.send_day || 1);
        setEnabled(Boolean(r.data.enabled));
        setCadence(r.data.cadence || "monthly");
        setDropDays(r.data.drop_days === 3 ? 3 : 2);
        setAskName(Boolean(r.data.ask_name));
        setRecapEnabled(Boolean(r.data.recap_enabled));
        setRecapWeekday(Math.max(0, Math.min(6, Number(r.data.recap_weekday) || 0)));
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
      refreshAccess();
      refreshAnalytics();
      refreshTimeline();
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
      const r = await api.put("/control-intelligence/settings", { recipients, send_day: sendDay, enabled, cadence, drop_days: dropDays, ask_name: askName, recap_enabled: recapEnabled, recap_weekday: recapWeekday });
      setRecipients(r.data.recipients || []);
      setSendDay(r.data.send_day || 1);
      setEnabled(Boolean(r.data.enabled));
      setCadence(r.data.cadence || "monthly");
      setDropDays(r.data.drop_days === 3 ? 3 : 2);
      setAskName(Boolean(r.data.ask_name));
      setRecapEnabled(Boolean(r.data.recap_enabled));
      setRecapWeekday(Math.max(0, Math.min(6, Number(r.data.recap_weekday) || 0)));
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
    setPreviewSrc(null);
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

  const openPdfPreview = () => {
    setPreviewHtml("");
    setPreviewLoading(false);
    setPreviewSrc(`${process.env.REACT_APP_BACKEND_URL}/api/control-intelligence/brief.pdf`);
    setPreviewOpen(true);
  };

  const closePreview = () => {
    setPreviewOpen(false);
    setPreviewSrc(null);
  };

  const generateLink = async (reissue) => {
    setLinkBusy(true);
    try {
      const r = await api.post("/control-intelligence/auditor-link", { days: expiryDays, reissue });
      setAuditorLink(r.data);
      refreshAccess();
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
      refreshAccess();
      toast.success("Auditor link revoked.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to revoke the link.");
    } finally {
      setLinkBusy(false);
    }
  };

  const followUp = async (token) => {
    try {
      const r = await api.post("/control-intelligence/auditor-link/follow-up", { token });
      if (r.data.sent > 0) toast.success(`Follow-up sent to ${r.data.sent} auditor recipient(s).`);
      else toast.message(r.data.note || "No auditor recipients configured.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to send the follow-up.");
    }
  };

  const previewRecap = () =>
    api.get("/control-intelligence/auditor-link/recap/preview?days=7").then((r) => setRecap(r.data))
      .catch(() => toast.error("Unable to load the recap preview."));

  const sendRecap = async () => {
    setRecapBusy(true);
    try {
      const r = await api.post("/control-intelligence/auditor-link/recap/send?days=7");
      setRecap(r.data.recap);
      toast.success(`Weekly recap sent to ${r.data.sent} recipient(s).`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to send the recap.");
    } finally {
      setRecapBusy(false);
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

          <div className="grid sm:grid-cols-2 gap-4" data-testid="ci-engagement-settings">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Owner nudge after</label>
              <div className="mt-2 inline-flex w-full rounded-md border border-border overflow-hidden" data-testid="ci-drop-days">
                {[2, 3].map((d) => (
                  <button
                    key={d}
                    onClick={() => setDropDays(d)}
                    data-testid={`ci-drop-days-${d}`}
                    className={`flex-1 px-2 py-2 text-xs font-head font-bold transition-colors ${
                      dropDays === d ? "bg-primary text-primary-foreground" : "bg-secondary/40 text-muted-foreground"
                    }`}
                  >
                    {d} declining days
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground mt-1.5">Email an owner when their effectiveness falls this many days in a row.</p>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Ask auditor name</label>
              <button
                onClick={() => setAskName((v) => !v)}
                data-testid="ci-ask-name-toggle"
                className={`mt-2 w-full inline-flex items-center justify-between px-3 py-2 rounded-md border text-sm font-head font-bold transition-colors ${
                  askName ? "border-ai/40 bg-ai/10 text-ai" : "border-border bg-secondary/40 text-muted-foreground"
                }`}
              >
                {askName ? "On" : "Off"}
                <span className={`h-4 w-8 rounded-full relative transition-colors ${askName ? "bg-ai" : "bg-secondary"}`}>
                  <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-background transition-all ${askName ? "left-4" : "left-0.5"}`} />
                </span>
              </button>
              <p className="text-[10px] text-muted-foreground mt-1.5">Prompt auditors for their name when they open the portal, so views are attributed.</p>
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

            {accessLog.length > 0 && (
              <div className="mt-4 border-t border-border pt-3" data-testid="ci-auditor-access-log">
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">Auditor access log</div>
                <div className="space-y-1.5 max-h-40 overflow-auto">
                  {accessLog.map((ev, i) => (
                    <div key={`${ev.at}-${i}`} data-testid={`ci-auditor-access-row-${i}`} className="flex items-center justify-between text-[11px]">
                      <span className="flex items-center gap-1.5">
                        {ev.kind === "download" ? <Download className="w-3 h-3 text-ai" /> : <Eye className="w-3 h-3 text-muted-foreground" />}
                        <span className="font-head font-bold capitalize">{ev.kind}</span>
                        <span className="text-muted-foreground">{ev.who || "anonymous"}</span>
                      </span>
                      <span className="font-mono text-muted-foreground">
                        {new Date(ev.at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {analytics && analytics.totals.views + analytics.totals.downloads > 0 && (
              <div className="mt-4 border-t border-border pt-3" data-testid="ci-auditor-analytics">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Reviewer engagement</div>
                  <button onClick={refreshAnalytics} data-testid="ci-auditor-analytics-refresh" className="text-[10px] font-mono text-muted-foreground hover:text-foreground">
                    Refresh
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-2 mb-3">
                  <div className="rounded-lg border border-border bg-secondary/30 p-2 text-center">
                    <div className="font-head font-black text-lg" data-testid="ci-analytics-views">{analytics.totals.views}</div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Views</div>
                  </div>
                  <div className="rounded-lg border border-border bg-secondary/30 p-2 text-center">
                    <div className="font-head font-black text-lg" data-testid="ci-analytics-downloads">{analytics.totals.downloads}</div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Downloads</div>
                  </div>
                  <div className="rounded-lg border border-border bg-secondary/30 p-2 text-center">
                    <div className="font-head font-black text-lg" data-testid="ci-analytics-reviewers">{analytics.totals.reviewers}</div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground">Reviewers</div>
                  </div>
                </div>
                {analytics.reviewers.length > 0 && (
                  <div className="space-y-1">
                    {analytics.reviewers.map((rv, i) => (
                      <div key={rv.who} data-testid={`ci-analytics-reviewer-${i}`} className="flex items-center justify-between text-[11px]">
                        <span className="flex items-center gap-1.5">
                          <Download className="w-3 h-3 text-ai" />
                          <span className="font-head font-bold">{rv.who}</span>
                        </span>
                        <span className="font-mono text-muted-foreground">
                          {rv.downloads} download(s) · {new Date(rv.last_at).toLocaleDateString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {analytics.links.length > 0 && (
                  <div className="mt-3 space-y-1.5">
                    <div className="text-[9px] font-mono uppercase text-muted-foreground mb-1">
                      Per-link engagement
                      {analytics.totals.awaiting_download > 0 && (
                        <span data-testid="ci-analytics-awaiting" className="ml-2 text-med normal-case">· {analytics.totals.awaiting_download} awaiting download</span>
                      )}
                    </div>
                    {analytics.links.map((lk, i) => (
                      <div key={lk.token} data-testid={`ci-analytics-link-${i}`} className="flex items-center justify-between gap-2 text-[11px]">
                        <span className="font-mono text-muted-foreground flex items-center gap-1.5 min-w-0">
                          …{lk.short} · <span className="capitalize">{lk.status}</span>
                          {lk.awaiting_download && (
                            <span data-testid={`ci-analytics-awaiting-${i}`} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border border-med/40 bg-med/10 text-med text-[9px] font-head font-bold normal-case">
                              <Eye className="w-2.5 h-2.5" /> viewed{lk.viewers && lk.viewers.length > 0 ? ` by ${lk.viewers.join(", ")}` : ""} · not downloaded
                            </span>
                          )}
                        </span>
                        <span className="flex items-center gap-2 shrink-0">
                          <span className="font-mono text-muted-foreground">{lk.views} view(s) · {lk.downloads} download(s)</span>
                          {lk.awaiting_download && lk.status === "active" && (
                            <button onClick={() => followUp(lk.token)} data-testid={`ci-analytics-nudge-${i}`} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-ai/40 bg-ai/10 text-ai text-[10px] font-head font-bold">
                              <Send className="w-2.5 h-2.5" /> Nudge
                            </button>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="mt-4 border-t border-border pt-3" data-testid="ci-recap-panel">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Weekly assurance recap</div>
                <div className="flex items-center gap-2">
                  <button onClick={previewRecap} data-testid="ci-recap-preview" className="text-[10px] font-mono text-muted-foreground hover:text-foreground">Preview</button>
                  <button onClick={sendRecap} disabled={recapBusy} data-testid="ci-recap-send" className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-ai/40 bg-ai/10 text-ai text-[10px] font-head font-bold disabled:opacity-50">
                    {recapBusy ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Send className="w-2.5 h-2.5" />} Send now
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <button
                  onClick={() => setRecapEnabled((v) => !v)}
                  data-testid="ci-recap-enabled-toggle"
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[10px] font-head font-bold transition-colors ${
                    recapEnabled ? "border-low/40 bg-low/10 text-low" : "border-border bg-secondary/40 text-muted-foreground"
                  }`}
                >
                  Auto-send {recapEnabled ? "On" : "Off"}
                </button>
                <select
                  value={recapWeekday}
                  onChange={(e) => setRecapWeekday(Number(e.target.value))}
                  disabled={!recapEnabled}
                  data-testid="ci-recap-weekday"
                  className="rounded-md border border-border bg-background px-2 py-1 text-[11px] disabled:opacity-50"
                >
                  {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((d, i) => (
                    <option key={d} value={i}>{d}</option>
                  ))}
                </select>
                <span className="text-[10px] text-muted-foreground">Save settings to apply</span>
              </div>
              {recap ? (
                <div data-testid="ci-recap-body" className="text-[11px] text-muted-foreground font-mono space-y-0.5">
                  <div>Last {recap.days}d · {recap.views} view(s) · {recap.downloads} download(s) · {recap.reviewers.length} reviewer(s){recap.reviewers.length > 0 ? ` · ${recap.reviewers.join(", ")}` : ""}</div>
                  {recap.awaiting && recap.awaiting.length > 0 && (
                    <div data-testid="ci-recap-awaiting" className="text-med">{recap.awaiting.length} link(s) viewed but not downloaded</div>
                  )}
                  {recap.nudged_owners && recap.nudged_owners.length > 0 && (
                    <div data-testid="ci-recap-nudged">Readiness nudges this week: {recap.nudged_owners.join(", ")}</div>
                  )}
                </div>
              ) : (
                <div className="text-[11px] text-muted-foreground">Preview the 7-day recap (auditor engagement, chase list &amp; readiness nudges), or send it to admins &amp; execs now.</div>
              )}
            </div>

            {timeline && timeline.length > 0 && (
              <div className="mt-4 border-t border-border pt-3" data-testid="ci-reviewer-timeline">
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">Reviewer timeline</div>
                <div className="space-y-2">
                  {timeline.map((p, i) => (
                    <div key={p.who} data-testid={`ci-timeline-person-${i}`} className="rounded-lg border border-border bg-secondary/20 p-2">
                      <div className="flex items-center justify-between text-[11px] mb-1">
                        <span className="font-head font-bold">{p.who}</span>
                        {p.review_seconds != null ? (
                          <span data-testid={`ci-timeline-duration-${i}`} className="font-mono text-low">
                            view→download in {p.review_seconds >= 3600
                              ? `${Math.floor(p.review_seconds / 3600)}h ${Math.floor((p.review_seconds % 3600) / 60)}m`
                              : p.review_seconds >= 60
                                ? `${Math.floor(p.review_seconds / 60)}m ${p.review_seconds % 60}s`
                                : `${p.review_seconds}s`}
                          </span>
                        ) : (
                          <span className="font-mono text-muted-foreground">{p.first_download ? "downloaded" : "not downloaded"}</span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {p.events.map((ev, j) => (
                          <span key={j} className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-mono ${ev.kind === "download" ? "bg-ai/10 text-ai" : "bg-secondary/60 text-muted-foreground"}`}>
                            {ev.kind === "download" ? <Download className="w-2.5 h-2.5" /> : <Eye className="w-2.5 h-2.5" />}
                            {new Date(ev.at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
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
            <button onClick={openPdfPreview} data-testid="ci-brief-pdf-preview" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">
              <FileText className="w-3.5 h-3.5" />
              Preview branded PDF
            </button>
            <button onClick={sendNow} disabled={sending} data-testid="ci-brief-send-now" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">
              {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              {sendLabel}
            </button>
          </div>
        </div>
      )}

      {previewOpen && <BriefPreviewModal html={previewHtml} src={previewSrc} loading={previewLoading} onClose={closePreview} />}
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
