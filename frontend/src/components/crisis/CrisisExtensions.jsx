import { useCallback, useEffect, useState } from "react";
import {
  Radio,
  Copy,
  Loader2,
  Send,
  MessageSquare,
  Presentation,
  Link2,
  Download,
  Banknote,
  Gavel,
  Scale,
  ShieldCheck,
  Timer,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { money, obligationCountdown } from "@/lib/crisisCommanderModels";

const BASE = process.env.REACT_APP_BACKEND_URL || "";

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function Section({ title, subtitle, actions, children, testid }) {
  return (
    <section data-testid={testid} className="bg-card fact-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="font-head font-black text-lg tracking-tight">{title}</h2>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function Empty({ title, text }) {
  return (
    <div className="py-10 text-center">
      <AlertTriangle className="w-8 h-8 text-muted-foreground mx-auto" />
      <div className="font-head font-bold mt-3">{title}</div>
      <p className="text-sm text-muted-foreground max-w-lg mx-auto mt-2">{text}</p>
    </div>
  );
}

function Countdown({ due }) {
  if (!due) return <span className="text-[10px] font-mono text-muted-foreground">no deadline</span>;
  const cd = obligationCountdown(due);
  const cls = cd.overdue ? "bg-crit/15 text-crit" : cd.urgent ? "bg-med/15 text-med" : "bg-secondary/60 text-muted-foreground";
  return (
    <span className={`inline-flex items-center gap-1 text-[9px] font-mono px-2 py-0.5 rounded-full ${cls}`}>
      <Timer className="w-3 h-3" />{cd.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Native SIEM / EDR / SOAR connectors — one-paste push URLs per vendor.
// ---------------------------------------------------------------------------
export function NativeConnectors() {
  const [data, setData] = useState(null);
  const [reveal, setReveal] = useState(false);
  const [testing, setTesting] = useState("");
  const [quiet, setQuiet] = useState(null);
  const [quietBusy, setQuietBusy] = useState(false);
  const load = useCallback(async () => {
    try { const r = await api.get("/crisis/connectors/native"); setData(r.data); } catch { /* operator-only */ }
    try { const q = await api.get("/crisis/connectors/quiet-check"); setQuiet(q.data); } catch { /* ignore */ }
  }, []);
  useEffect(() => { load(); }, [load]);
  const copy = (text, label) => { navigator.clipboard?.writeText(text); toast.success(`${label} copied.`); };
  const testPing = async (vendor) => {
    setTesting(vendor);
    try {
      await api.post(`/crisis/connectors/${vendor}/test`, {});
      toast.success(`Test event sent through the ${vendor} connector — health updated.`);
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || "Test failed."); }
    finally { setTesting(""); }
  };
  const toggleQuiet = async () => {
    setQuietBusy(true);
    try {
      const { data: s } = await api.post("/crisis/settings", { connector_quiet: !(quiet?.enabled) });
      toast.success(s.connector_quiet ? "Quiet-connector alerts enabled." : "Quiet-connector alerts disabled.");
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || "Unable to update."); }
    finally { setQuietBusy(false); }
  };
  if (!data) return null;
  const mask = (url) => (reveal ? url : url.replace(/secret=[^&]+/, "secret=••••••••••••"));
  return (
    <Section testid="crisis-native-connectors" title="Native SIEM / EDR Connectors"
      subtitle="One paste to onboard a tool — each URL already carries the vendor field-mapping and your per-org secret. No transformation needed on the tool's side."
      actions={<div className="flex items-center gap-2"><ConnectorWizard /><button onClick={() => setReveal((v) => !v)} data-testid="crisis-native-reveal" className="px-2.5 py-1.5 rounded-md border border-border bg-secondary/40 text-[10px] font-mono">{reveal ? "Hide secrets" : "Show secrets"}</button></div>}>
      <div className="grid gap-3 md:grid-cols-2">
        {(data.connectors || []).map((c) => {
          const url = `${BASE}${c.path}`;
          return (
            <div key={c.vendor} data-testid={`crisis-native-${c.vendor}`} className="rounded-lg border border-border bg-secondary/30 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2"><Radio className="w-3.5 h-3.5 text-ai" /><span className="font-head font-bold text-sm">{c.label}</span></div>
                <button onClick={() => testPing(c.vendor)} disabled={testing === c.vendor} data-testid={`crisis-native-test-${c.vendor}`} title="Send a synthetic test event to confirm wiring" className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded-md border border-ai/40 bg-ai/10 text-ai text-[10px] font-head font-bold disabled:opacity-50">{testing === c.vendor ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}Test</button>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1 leading-snug">{c.note}</p>
              <div className="flex items-center gap-1.5 mt-1.5" data-testid={`crisis-native-health-${c.vendor}`}>
                <span className={`w-2 h-2 rounded-full ${c.last_received ? "bg-low animate-pulse" : "bg-muted-foreground/40"}`} />
                <span className="text-[9px] font-mono text-muted-foreground">{c.last_received ? `Live · last received ${new Date(c.last_received).toLocaleString()} · ${c.count || 0} event(s)` : "No events received yet"}</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <code data-testid={`crisis-native-url-${c.vendor}`} className="text-[10px] font-mono break-all flex-1 bg-background border border-border rounded-md px-2 py-1.5">{mask(url)}</code>
                <button onClick={() => copy(url, `${c.label} URL`)} data-testid={`crisis-native-copy-${c.vendor}`} className="shrink-0 p-1.5 rounded-md border border-border hover:bg-secondary" title="Copy push URL"><Copy className="w-3.5 h-3.5" /></button>
              </div>
              <div className="text-[9px] font-mono text-muted-foreground mt-1.5">or send the secret in the <span className="text-foreground">{c.header}</span> header</div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 rounded-lg border border-border bg-secondary/20 p-3 flex items-center gap-3 flex-wrap" data-testid="crisis-connector-quiet">
        <span className="text-xs font-head font-bold">Quiet-connector alerts</span>
        <button onClick={toggleQuiet} disabled={quietBusy} data-testid="crisis-quiet-toggle" className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-[11px] font-head font-bold disabled:opacity-50 ${quiet?.enabled ? "border-low/40 bg-low/15 text-low" : "border-border bg-secondary/40"}`}>{quietBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5" />}{quiet?.enabled ? "On" : "Off"}</button>
        <span className="text-[11px] text-muted-foreground">Pings the security channel if a wired connector goes silent for {quiet?.threshold_hours || 6}h+ during business hours.{quiet?.quiet?.length ? ` Currently quiet: ${quiet.quiet.map((x) => x.vendor).join(", ")}.` : ""}</span>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Digital War Room — broadcast a SITREP to Teams / Slack.
// ---------------------------------------------------------------------------
export function WarRoomBroadcast({ selectedCase, changed }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [channels, setChannels] = useState({ teams: false, slack: false });
  useEffect(() => {
    api.get("/crisis/broadcast/status").then((r) => setChannels(r.data || {})).catch(() => {});
  }, []);
  const any = channels.teams || channels.slack;
  const send = async () => {
    if (!selectedCase) { toast.error("Select a crisis case first."); return; }
    setBusy(true);
    try {
      const { data } = await api.post(`/crisis/cases/${selectedCase.ref}/broadcast`, { message: msg.trim() });
      if (data.posted) {
        const where = [data.teams && "Teams", data.slack && "Slack"].filter(Boolean).join(" & ");
        toast.success(`SITREP broadcast to ${where}.`);
      } else {
        toast.message("SITREP logged to the timeline. Connect a Teams/Slack webhook to push it to leadership chat.");
      }
      setMsg("");
      await changed?.(selectedCase.ref);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Broadcast failed.");
    } finally {
      setBusy(false);
    }
  };
  const Pill = ({ on, label, testid }) => (
    <span data-testid={testid} className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full border ${on ? "border-low/30 bg-low/10 text-low" : "border-border bg-secondary/50 text-muted-foreground"}`}>
      <MessageSquare className="w-3 h-3" />{label} {on ? "connected" : "not set"}
    </span>
  );
  return (
    <Section
      testid="crisis-warroom-broadcast"
      title="Broadcast to Teams / Slack"
      subtitle="Push a live situation report to leadership chat and record it on the crisis timeline — coordinate responders wherever they are."
      actions={<div className="flex items-center gap-1.5"><Pill on={channels.teams} label="Teams" testid="crisis-broadcast-teams" /><Pill on={channels.slack} label="Slack" testid="crisis-broadcast-slack" /></div>}
    >
      <div className="space-y-3">
        <textarea
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          data-testid="crisis-broadcast-message"
          rows={3}
          placeholder="Optional update to add to the SITREP (severity, phase, containment % and pending decisions are added automatically)…"
          className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary resize-y"
        />
        <div className="flex items-center justify-between gap-3 flex-wrap">
          {!any && <span className="text-[11px] text-med">No chat channel wired — the SITREP will still be recorded on the timeline. Add a Teams/Slack webhook in Settings to push it live.</span>}
          <button
            onClick={send}
            disabled={busy || !selectedCase}
            data-testid="crisis-broadcast-send"
            className="ml-auto inline-flex items-center gap-1.5 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}Broadcast SITREP
          </button>
        </div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Present to Board — one-tap shareable snapshot link + one-page board PDF.
// ---------------------------------------------------------------------------
export function PresentToBoard({ selectedCase, variant = "panel", auto = false }) {
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dl, setDl] = useState(false);
  const ref = selectedCase?.ref;
  const present = useCallback(async () => {
    if (!ref) { toast.error("Select a crisis case first."); return; }
    setBusy(true);
    try {
      const { data } = await api.post(`/crisis/cases/${ref}/present-board`, {});
      setInfo(data);
      try { await navigator.clipboard?.writeText(`${window.location.origin}${data.snapshot_path}`); } catch { /* clipboard blocked */ }
      toast.success("Board pack ready — snapshot link copied.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to prepare the board pack.");
    } finally {
      setBusy(false);
    }
  }, [ref]);
  useEffect(() => { setInfo(null); }, [ref]);
  useEffect(() => { if (auto && ref) present(); }, [auto, ref, present]);

  const downloadPdf = async () => {
    if (!ref) return;
    setDl(true);
    try {
      const res = await api.get(`/crisis/cases/${ref}/board-onepager.pdf`, { responseType: "blob" });
      downloadBlob(res.data, `obserra-board-snapshot-${ref}.pdf`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "PDF download failed.");
    } finally {
      setDl(false);
    }
  };

  const snapUrl = info ? `${window.location.origin}${info.snapshot_path}` : "";

  const Actions = () => (
    <div className="flex items-center gap-2 flex-wrap" data-testid="crisis-present-actions">
      {!info ? (
        <button onClick={present} disabled={busy || !ref} data-testid="crisis-present-board-btn" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Presentation className="w-3.5 h-3.5" />}Prepare board pack
        </button>
      ) : (
        <>
          <input readOnly value={snapUrl} data-testid="crisis-present-link" onFocus={(e) => e.target.select()} className="flex-1 min-w-[200px] bg-secondary/60 rounded-md px-3 py-1.5 text-xs font-mono" />
          <button onClick={() => { navigator.clipboard?.writeText(snapUrl); toast.success("Link copied."); }} data-testid="crisis-present-copy" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><Copy className="w-3.5 h-3.5" />Copy</button>
          <a href={snapUrl} target="_blank" rel="noreferrer" data-testid="crisis-present-open" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><Link2 className="w-3.5 h-3.5" />Open</a>
          <button onClick={downloadPdf} disabled={dl} data-testid="crisis-present-pdf" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{dl ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}One-page PDF</button>
        </>
      )}
    </div>
  );

  if (variant === "banner") {
    return (
      <div data-testid="crisis-present-banner" className="rounded-xl border border-ai/40 bg-ai/10 p-4 flex flex-col lg:flex-row lg:items-center gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <CheckCircle2 className="w-5 h-5 text-ai shrink-0" />
          <div>
            <div className="font-head font-bold text-sm">Storyline complete — present it to the board</div>
            <div className="text-xs text-muted-foreground">Turn this incident into a shareable snapshot link and a one-page board PDF in one tap.</div>
          </div>
        </div>
        <div className="lg:ml-auto w-full lg:w-auto"><Actions /></div>
      </div>
    );
  }

  return (
    <Section
      testid="crisis-present-panel"
      title="Present to Board"
      subtitle="Hand directors a live, read-only snapshot link and a one-page board PDF of this crisis — both branded and audit-logged."
    >
      <Actions />
      {info && <div className="text-[10px] font-mono text-muted-foreground mt-3">Snapshot link expires {info.expires_at ? new Date(info.expires_at).toLocaleDateString() : "—"}.</div>}
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Board Crisis Dashboard — director-focused read-only crisis view.
// ---------------------------------------------------------------------------
export function BoardCrisisDashboard({ selectedCase }) {
  const [board, setBoard] = useState(null);
  const [loading, setLoading] = useState(false);
  const ref = selectedCase?.ref;
  const load = useCallback(async () => {
    if (!ref) { setBoard(null); return; }
    setLoading(true);
    try {
      const r = await api.get(`/crisis/cases/${ref}/board`);
      setBoard(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to load the board view.");
    } finally {
      setLoading(false);
    }
  }, [ref]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!ref) return undefined;
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [ref, load]);

  if (!ref) {
    return <Empty title="No crisis case selected" text="Select a crisis case to open the director-facing board view." />;
  }
  if (!board && loading) {
    return (
      <div className="min-h-[35vh] flex items-center justify-center" data-testid="crisis-board-loading">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }
  if (!board) return null;
  const c = board.case || {};
  const fin = c.financial_exposure;
  const pending = board.pending_decisions || [];
  const regs = board.regulatory || [];
  const tl = board.timeline || [];

  const KPI = ({ label, value, sub, icon: Icon, accent = "0 84% 60%", testid }) => (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-4" style={{ borderLeft: `3px solid hsl(${accent})` }}>
      <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">{Icon && <Icon className="w-3.5 h-3.5" />}{label}</div>
      <div className="font-head font-black text-2xl lg:text-3xl mt-2 break-words">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );

  return (
    <div className="space-y-5" data-testid="crisis-board-dashboard">
      <div className="rounded-xl border border-border bg-secondary/30 px-4 py-2.5 flex items-center gap-2" data-testid="crisis-board-readonly">
        <ShieldCheck className="w-4 h-4 text-ai" />
        <span className="text-xs text-muted-foreground">Read-only board view of <span className="text-foreground font-bold">{c.ref}</span> · {c.title} · auto-refreshes every 20s.</span>
      </div>

      <div className="grid md:grid-cols-3 xl:grid-cols-5 gap-4">
        <KPI testid="crisis-board-kpi-severity" label="Severity / Phase" value={c.severity || "None"} sub={c.phase || "-"} icon={AlertTriangle} accent="0 84% 60%" />
        <KPI testid="crisis-board-kpi-contained" label="Contained" value={`${board.contained_pct ?? 0}%`} sub={`Recovery ${board.recovery_overall ?? 0}%`} icon={ShieldCheck} accent="142 70% 45%" />
        <KPI testid="crisis-board-kpi-decisions" label="Decisions pending" value={board.counts?.pending_decisions ?? 0} sub={`${board.counts?.open_actions ?? 0} open actions`} icon={Gavel} accent="266 85% 66%" />
        <KPI testid="crisis-board-kpi-exposure" label="Financial exposure" value={typeof fin === "number" ? money(fin) : "—"} sub={typeof fin === "number" ? "Residual ALE" : "Not quantified"} icon={Banknote} accent="35 90% 55%" />
        <KPI testid="crisis-board-kpi-regulatory" label="Regulatory clocks" value={regs.length} sub="tracked obligations" icon={Scale} accent="199 89% 55%" />
      </div>

      <PresentToBoard selectedCase={selectedCase} variant="panel" />

      <DirectorDigest />

      <div className="grid xl:grid-cols-2 gap-5">
        <Section testid="crisis-board-decisions" title="Decisions Awaiting the Board" subtitle="Executive approvals mirrored from the Decision Room, with SLA countdowns.">
          {pending.length === 0 ? <Empty title="No decisions pending" text="No executive decisions are currently awaiting approval." /> : (
            <div className="space-y-2">{pending.map((d, i) => (
              <div key={i} data-testid={`crisis-board-decision-${i}`} className="rounded-lg border border-high/25 bg-high/5 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-head font-bold text-sm min-w-0 truncate">{d.title}</div>
                  <Countdown due={d.due_at} />
                </div>
                <div className="text-xs text-muted-foreground mt-1">Owner: {d.owner || "Unassigned"}{d.priority ? ` · ${d.priority}` : ""}{d.business_impact ? ` · ${d.business_impact}` : ""}</div>
              </div>
            ))}</div>
          )}
        </Section>

        <Section testid="crisis-board-regulatory" title="Regulatory Clocks" subtitle="Statutory and contractual notification deadlines for this incident.">
          {regs.length === 0 ? <Empty title="No obligations tracked" text="No regulatory obligations have been recorded for this crisis." /> : (
            <div className="space-y-2">{regs.map((o, i) => (
              <div key={i} data-testid={`crisis-board-reg-${i}`} className="rounded-lg border border-border bg-secondary/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-head font-bold text-sm min-w-0 truncate">{o.regulation} <span className="text-muted-foreground font-normal">· {o.jurisdiction}</span></div>
                  <Countdown due={o.deadline_at} />
                </div>
                <div className="text-xs text-muted-foreground mt-1">Status: {o.status || "-"}</div>
              </div>
            ))}</div>
          )}
        </Section>
      </div>

      <Section testid="crisis-board-timeline" title="Latest Timeline" subtitle="Most recent crisis events, newest first.">
        {tl.length === 0 ? <Empty title="No timeline events" text="No events have been recorded for this crisis yet." /> : (
          <div className="space-y-1.5">{tl.map((e, i) => (
            <div key={i} data-testid={`crisis-board-tl-${i}`} className="flex items-center justify-between gap-3 bg-secondary/30 border border-border rounded-md px-3 py-2">
              <div className="min-w-0"><div className="text-sm font-medium truncate">{e.title}</div><div className="text-[10px] font-mono text-muted-foreground">{e.kind} · {e.source || "manual"} · {e.severity}</div></div>
              <span className="shrink-0 text-[9px] font-mono text-muted-foreground">{e.occurred_at ? new Date(e.occurred_at).toLocaleString() : ""}</span>
            </div>
          ))}</div>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Auto-SITREP Console — preview & tweak the scheduled SITREP wording, or send
// a test SITREP to leadership chat right now.
// ---------------------------------------------------------------------------
export function SitrepConsole({ selectedCase, changed }) {
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState(null);
  const [cadence, setCadence] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [templates, setTemplates] = useState([]);
  const ref = selectedCase?.ref;
  useEffect(() => {
    api.get("/crisis/sitrep/templates").then((r) => setTemplates(r.data.templates || [])).catch(() => {});
  }, []);
  const saveAsTemplate = async () => {
    const text = note.trim();
    if (!text) { toast.error("Write a note first, then save it as a template."); return; }
    const label = (window.prompt("Template name?", text.slice(0, 40)) || "").trim();
    if (!label) return;
    try {
      const { data } = await api.post("/crisis/sitrep/templates", { label, text });
      setTemplates(data.templates || []);
      toast.success(`Saved template "${label}".`);
    } catch (e) { toast.error(e.response?.data?.detail || "Unable to save template."); }
  };
  const load = useCallback(async () => {
    if (!ref) { setPreview(null); return; }
    setLoading(true);
    try {
      const { data } = await api.get(`/crisis/cases/${ref}/sitrep/preview`);
      setPreview(data.text); setNote(data.note || ""); setCadence(data.cadence_hours || 0);
    } catch { /* operator-only */ }
    finally { setLoading(false); }
  }, [ref]);
  useEffect(() => { load(); }, [load]);
  const save = async () => {
    if (!ref) return;
    setSaving(true);
    try {
      await api.patch(`/crisis/cases/${ref}`, { sitrep_note: note });
      toast.success("SITREP note saved — it will be included in scheduled posts.");
      await changed?.(ref); await load();
    } catch (e) { toast.error(e.response?.data?.detail || "Unable to save note."); }
    finally { setSaving(false); }
  };
  const sendNow = async () => {
    if (!ref) return;
    setSending(true);
    try {
      const { data } = await api.post(`/crisis/cases/${ref}/sitrep/send-now`, {});
      if (data.posted) toast.success("Test SITREP posted to leadership chat.");
      else toast.message("No chat channel wired — connect Teams/Slack to post live. (Logged to timeline.)");
      await changed?.(ref);
    } catch (e) { toast.error(e.response?.data?.detail || "Send failed."); }
    finally { setSending(false); }
  };
  if (!ref) return null;
  return (
    <Section testid="crisis-sitrep-console" title="Auto-SITREP Console"
      subtitle={cadence > 0 ? `Scheduled every ${cadence}h while this crisis is active — preview and tweak the wording before it goes out.` : "Auto-SITREP is off — set a cadence from the header 'More' menu. You can still preview and send a test now."}>
      <div className="space-y-3">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">Preview (auto-composed + your note)</div>
          <pre data-testid="crisis-sitrep-preview" className="whitespace-pre-wrap text-xs bg-background border border-border rounded-md p-3 font-mono leading-relaxed">{loading ? "Loading…" : (preview || "—")}</pre>
        </div>
        <div>
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Custom note (added to every SITREP)</div>
            <button onClick={saveAsTemplate} data-testid="crisis-sitrep-save-template" className="text-[10px] font-head font-bold text-ai hover:underline">Save as template</button>
          </div>
          {templates.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2" data-testid="crisis-sitrep-templates">
              {templates.map((t) => (
                <button key={t.id} onClick={() => setNote((n) => (n ? n + " · " : "") + t.text)} data-testid={`crisis-sitrep-tpl-${t.id}`} title={t.text} className="px-2 py-1 rounded-full border border-border bg-secondary/50 text-[10px] font-head font-bold hover:bg-secondary">+ {t.label}</button>
              ))}
            </div>
          )}
          <textarea value={note} onChange={(e) => setNote(e.target.value)} data-testid="crisis-sitrep-note" rows={2}
            placeholder="e.g. Bridge line open +1-555-0100 · Legal engaged · Next exec sync 14:00 UTC"
            className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary resize-y" />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={save} disabled={saving} data-testid="crisis-sitrep-save" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <MessageSquare className="w-3.5 h-3.5" />}Save note &amp; preview</button>
          <button onClick={sendNow} disabled={sending} data-testid="crisis-sitrep-send-now" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}Send test SITREP now</button>
        </div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Weekly Director Digest — opt-in weekly board rollup of all open crises.
// ---------------------------------------------------------------------------
export function DirectorDigest() {
  const [s, setS] = useState({ director_digest: false, director_digest_weekday: 0, director_digest_hour: 8 });
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [preview, setPreview] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const load = useCallback(async () => {
    try { const r = await api.get("/crisis/settings"); setS(r.data); } catch { /* operator-only */ }
  }, []);
  useEffect(() => { load(); }, [load]);
  const patch = async (partial, msg) => {
    setBusy(true);
    try { const { data } = await api.post("/crisis/settings", partial); setS(data); if (msg) toast.success(msg); }
    catch (e) { toast.error(e.response?.data?.detail || "Unable to update."); }
    finally { setBusy(false); }
  };
  const openPreview = async () => {
    try {
      const { data } = await api.get("/crisis/director-digest/preview");
      if (!data.crises) { toast.message("No open crises to include right now."); return; }
      setPreview(data.html); setShowPreview(true);
    } catch (e) { toast.error(e.response?.data?.detail || "Preview failed."); }
  };
  const sendNow = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/crisis/director-digest/send-now", {});
      if (data.sent) toast.success(`Digest sent to ${data.sent} director(s) covering ${data.crises} open crisis(es).`);
      else toast.message(data.message || "No open crises to report.");
    } catch (e) { toast.error(e.response?.data?.detail || "Send failed."); }
    finally { setSending(false); }
  };
  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  return (
    <Section testid="crisis-director-digest" title="Weekly Director Digest"
      subtitle="Email board members a weekly rollup of every open crisis — pick the day &amp; time, preview it, then switch it on.">
      <div className="space-y-3">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-[11px] font-mono text-muted-foreground">Send every</span>
          <select value={s.director_digest_weekday} onChange={(e) => patch({ director_digest_weekday: Number(e.target.value) })} data-testid="crisis-digest-weekday" className="px-2 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">{DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}</select>
          <span className="text-[11px] font-mono text-muted-foreground">at</span>
          <select value={s.director_digest_hour} onChange={(e) => patch({ director_digest_hour: Number(e.target.value) })} data-testid="crisis-digest-hour" className="px-2 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00 UTC</option>)}</select>
        </div>
        <div className="flex items-center gap-2.5 flex-wrap">
          <button onClick={() => patch({ director_digest: !s.director_digest }, !s.director_digest ? "Weekly director digest enabled." : "Weekly director digest disabled.")} disabled={busy} data-testid="crisis-digest-toggle" className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-md border text-xs font-head font-bold disabled:opacity-50 ${s.director_digest ? "border-low/40 bg-low/15 text-low" : "border-border bg-secondary/40"}`}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}{s.director_digest ? "Weekly digest: On" : "Weekly digest: Off"}</button>
          <button onClick={openPreview} data-testid="crisis-digest-preview" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><Presentation className="w-3.5 h-3.5" />Preview</button>
          <button onClick={sendNow} disabled={sending} data-testid="crisis-digest-send-now" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}Send now</button>
          <span className="text-[11px] text-muted-foreground">To admins, executives &amp; owners.</span>
        </div>
      </div>
      {showPreview && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="crisis-digest-preview-modal" onClick={() => setShowPreview(false)}>
          <div className="bg-white rounded-xl w-full max-w-2xl max-h-[85vh] overflow-auto p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-end mb-2"><button onClick={() => setShowPreview(false)} data-testid="crisis-digest-preview-close" className="text-slate-500 text-sm">✕ Close</button></div>
            <div dangerouslySetInnerHTML={{ __html: preview }} />
          </div>
        </div>
      )}
    </Section>
  );
}


// ---------------------------------------------------------------------------
// Connector Health tile — compact green/amber status row for Mission Control.
// ---------------------------------------------------------------------------
export function ConnectorHealthTile({ openTab }) {
  const [conns, setConns] = useState([]);
  const load = useCallback(async () => {
    try {
      const [n, q] = await Promise.all([
        api.get("/crisis/connectors/native"),
        api.get("/crisis/connectors/quiet-check").catch(() => ({ data: { quiet: [] } })),
      ]);
      const quietSet = new Set((q.data.quiet || []).map((x) => x.vendor));
      setConns((n.data.connectors || []).map((c) => ({ ...c, quiet: quietSet.has(c.vendor) })));
    } catch { /* operator-only */ }
  }, []);
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);
  if (!conns.length) return null;
  const wired = conns.filter((c) => c.last_received);
  return (
    <Section testid="crisis-connector-health-tile" title="Connector Health"
      subtitle="Live status of your wired security tools — green = flowing, amber = gone quiet."
      actions={<button onClick={() => openTab?.("command")} data-testid="crisis-health-tile-manage" className="px-2.5 py-1.5 rounded-md border border-border bg-secondary/40 text-[10px] font-mono">Manage</button>}>
      {wired.length === 0 ? (
        <div className="text-sm text-muted-foreground" data-testid="crisis-health-tile-empty">No connectors have delivered events yet. Open Incident Command → Native Connectors to wire and test a tool.</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {wired.map((c) => (
            <div key={c.vendor} data-testid={`crisis-health-chip-${c.vendor}`} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-head font-bold ${c.quiet ? "border-med/40 bg-med/10 text-med" : "border-low/40 bg-low/10 text-low"}`}>
              <span className={`w-2 h-2 rounded-full ${c.quiet ? "bg-med" : "bg-low animate-pulse"}`} />
              {c.label}
              <span className="text-[9px] font-mono text-muted-foreground">{c.quiet ? "quiet" : `${c.count || 0} evt`}</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Connector Onboarding Wizard — guided paste URL → send test → turn green.
// ---------------------------------------------------------------------------
export function ConnectorWizard() {
  const [open, setOpen] = useState(false);
  const [conns, setConns] = useState([]);
  const [vendor, setVendor] = useState(null);
  const [testing, setTesting] = useState(false);
  const load = useCallback(async () => {
    try { const r = await api.get("/crisis/connectors/native"); setConns(r.data.connectors || []); } catch { /* */ }
  }, []);
  useEffect(() => { if (open) load(); }, [open, load]);
  const sel = conns.find((c) => c.vendor === vendor);
  const url = sel ? `${BASE}${sel.path}` : "";
  const done = !!(sel && sel.last_received);
  const runTest = async () => {
    if (!vendor) return;
    setTesting(true);
    try { await api.post(`/crisis/connectors/${vendor}/test`, {}); toast.success("Test event received — connector is wired."); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Test failed."); }
    finally { setTesting(false); }
  };
  return (
    <>
      <button onClick={() => { setOpen(true); setVendor(null); }} data-testid="crisis-wizard-open" className="px-2.5 py-1.5 rounded-md border border-ai/40 bg-ai/10 text-ai text-[10px] font-head font-bold inline-flex items-center gap-1"><Radio className="w-3 h-3" />Setup wizard</button>
      {open && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="crisis-wizard-modal" onClick={() => setOpen(false)}>
          <div className="bg-card border border-border rounded-xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-head font-black text-lg">Connector Setup Wizard</h3>
              <button onClick={() => setOpen(false)} data-testid="crisis-wizard-close" className="text-muted-foreground hover:text-foreground text-sm">✕</button>
            </div>
            {!vendor ? (
              <>
                <div className="text-xs text-muted-foreground mb-3">Step 1 — pick the tool you're wiring:</div>
                <div className="grid grid-cols-2 gap-2">
                  {conns.map((c) => (
                    <button key={c.vendor} onClick={() => setVendor(c.vendor)} data-testid={`crisis-wizard-pick-${c.vendor}`} className="text-left px-3 py-2 rounded-md border border-border bg-secondary/40 hover:bg-secondary text-xs font-head font-bold">{c.label}</button>
                  ))}
                </div>
              </>
            ) : (
              <div className="space-y-3">
                <div className="text-sm font-head font-bold">{sel?.label}</div>
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Step 2 — paste this push URL into the tool's webhook action</div>
                  <div className="flex items-center gap-2">
                    <code data-testid="crisis-wizard-url" className="text-[10px] font-mono break-all flex-1 bg-background border border-border rounded-md px-2 py-1.5">{url}</code>
                    <button onClick={() => { navigator.clipboard?.writeText(url); toast.success("URL copied."); }} data-testid="crisis-wizard-copy" className="shrink-0 p-1.5 rounded-md border border-border hover:bg-secondary"><Copy className="w-3.5 h-3.5" /></button>
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-1">{sel?.note}</div>
                </div>
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Step 3 — send a test event and watch it turn green</div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <button onClick={runTest} disabled={testing} data-testid="crisis-wizard-test" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}Send test event</button>
                    <span data-testid="crisis-wizard-status" className={`inline-flex items-center gap-1.5 text-xs font-head font-bold ${done ? "text-low" : "text-muted-foreground"}`}><span className={`w-2.5 h-2.5 rounded-full ${done ? "bg-low animate-pulse" : "bg-muted-foreground/40"}`} />{done ? "Connected — event received" : "Waiting for first event"}</span>
                  </div>
                </div>
                <div className="flex justify-between pt-2">
                  <button onClick={() => setVendor(null)} data-testid="crisis-wizard-back" className="text-xs text-muted-foreground hover:text-foreground">← Pick another</button>
                  <button onClick={() => setOpen(false)} data-testid="crisis-wizard-done" className="px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">Done</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}