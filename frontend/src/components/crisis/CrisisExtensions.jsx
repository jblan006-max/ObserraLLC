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
  const load = useCallback(async () => {
    try {
      const r = await api.get("/crisis/connectors/native");
      setData(r.data);
    } catch {
      /* operator-only / not permitted — stay hidden */
    }
  }, []);
  useEffect(() => { load(); }, [load]);
  const copy = (text, label) => { navigator.clipboard?.writeText(text); toast.success(`${label} copied.`); };
  if (!data) return null;
  const mask = (url) => (reveal ? url : url.replace(/secret=[^&]+/, "secret=••••••••••••"));
  return (
    <Section
      testid="crisis-native-connectors"
      title="Native SIEM / EDR Connectors"
      subtitle="One paste to onboard a tool — each URL already carries the vendor field-mapping and your per-org secret. No transformation needed on the tool's side."
      actions={
        <button
          onClick={() => setReveal((v) => !v)}
          data-testid="crisis-native-reveal"
          className="px-2.5 py-1.5 rounded-md border border-border bg-secondary/40 text-[10px] font-mono"
        >
          {reveal ? "Hide secrets" : "Show secrets"}
        </button>
      }
    >
      <div className="grid gap-3 md:grid-cols-2">
        {(data.connectors || []).map((c) => {
          const url = `${BASE}${c.path}`;
          return (
            <div key={c.vendor} data-testid={`crisis-native-${c.vendor}`} className="rounded-lg border border-border bg-secondary/30 p-3">
              <div className="flex items-center gap-2">
                <Radio className="w-3.5 h-3.5 text-ai" />
                <span className="font-head font-bold text-sm">{c.label}</span>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1 leading-snug">{c.note}</p>
              <div className="flex items-center gap-2 mt-2">
                <code data-testid={`crisis-native-url-${c.vendor}`} className="text-[10px] font-mono break-all flex-1 bg-background border border-border rounded-md px-2 py-1.5">{mask(url)}</code>
                <button
                  onClick={() => copy(url, `${c.label} URL`)}
                  data-testid={`crisis-native-copy-${c.vendor}`}
                  className="shrink-0 p-1.5 rounded-md border border-border hover:bg-secondary"
                  title="Copy push URL"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="text-[9px] font-mono text-muted-foreground mt-1.5">or send the secret in the <span className="text-foreground">{c.header}</span> header</div>
            </div>
          );
        })}
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
