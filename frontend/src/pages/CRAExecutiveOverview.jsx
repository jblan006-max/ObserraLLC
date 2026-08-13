import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { APP_VERSION_LABEL } from "@/version";
import { useAuth } from "@/context/AuthContext";
import { useCRAData } from "@/hooks/useCRAData";
import { CraTabAnalyst } from "@/components/cra/CraAI";
import { toast } from "sonner";
import {
  Boxes, BadgeCheck, ShieldCheck, TriangleAlert, FileCheck2, Fingerprint,
  Building2, Download, RefreshCw, ArrowRight, Clock3, Loader2,
  Camera, Trash2, Mail, ArrowUpRight, ArrowDownRight, Share2, Eye, X, Copy, Check, GitCompareArrows,
} from "lucide-react";

const pct = (n, d) => (d ? Math.round((n / d) * 100) : 0);
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const GOOD_DOWN = new Set(["article14_overdue", "ce_blockers"]);
const PCT_KEYS = new Set(["classification_approved_pct", "ce_ready_pct", "control_compliance_pct", "nist_alignment_pct", "average_readiness_pct", "ai_grounding_score"]);

// Every board KPI stored on a snapshot, in board reading order.
const CMP_ROWS = [
  ["Products under CRA", "products"],
  ["Classification approved", "classification_approved_pct"],
  ["CE market-ready", "ce_ready_pct"],
  ["Article 14 overdue", "article14_overdue"],
  ["Control compliance", "control_compliance_pct"],
  ["NIST CSF alignment", "nist_alignment_pct"],
  ["CE blockers", "ce_blockers"],
  ["Average readiness", "average_readiness_pct"],
  ["AI grounding score", "ai_grounding_score"],
];

function toneFor(score) {
  if (score == null) return "text-muted-foreground border-border";
  if (score >= 80) return "text-low border-low/30";
  if (score >= 50) return "text-high border-high/30";
  return "text-crit border-crit/30";
}

const fmtVal = (k, v) => (v == null ? "—" : PCT_KEYS.has(k) ? `${v}%` : `${v}`);

function DeltaChip({ k, v }) {
  if (v == null || v === 0) return <span className="text-[10px] font-mono text-muted-foreground">±0</span>;
  const up = v > 0;
  const good = GOOD_DOWN.has(k) ? !up : up;
  const Arrow = up ? ArrowUpRight : ArrowDownRight;
  return <span className={`inline-flex items-center gap-0.5 text-[10px] font-mono font-bold ${good ? "text-low" : "text-crit"}`}><Arrow className="w-3 h-3" />{up ? "+" : ""}{v}</span>;
}

function KpiCard({ label, value, sub, Icon, tone = "text-primary border-primary/25", onClick, testid }) {
  return (
    <button onClick={onClick} data-testid={testid} className={`text-left rounded-xl border bg-card p-4 hover:bg-secondary/30 transition-colors ${tone}`}>
      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider opacity-80"><Icon className="w-3.5 h-3.5" /> {label}</div>
      <div className="font-head font-black text-3xl mt-1 text-foreground">{value}</div>
      {sub && <div className="text-[11px] font-mono text-muted-foreground mt-0.5">{sub}</div>}
    </button>
  );
}

function Panel({ title, subtitle, children, testid, action }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5" data-testid={testid}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-head font-bold text-sm">{title}</div>
          {subtitle && <div className="text-[11px] font-mono text-muted-foreground">{subtitle}</div>}
        </div>
        {action}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Bar({ label, value, total, tone = "bg-primary" }) {
  const p = total ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-foreground/90">{label}</span>
        <span className="font-mono text-muted-foreground">{value}{total ? ` / ${total}` : ""}</span>
      </div>
      <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className={`h-full ${tone}`} style={{ width: `${p}%` }} /></div>
    </div>
  );
}

// Live board-facing countdown to the nearest statutory CRA deadline.
function Seg({ n, label, urgent }) {
  return (
    <div className="text-center">
      <div className={`font-head font-black text-3xl lg:text-4xl tabular-nums ${urgent ? "text-crit" : "text-high"}`}>{String(n).padStart(2, "0")}</div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground">{label}</div>
    </div>
  );
}
function DeadlineCountdown({ nd }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!nd) return null;
  const target = new Date(`${nd.date}T00:00:00Z`).getTime();
  const diff = Math.max(0, target - now);
  const d = Math.floor(diff / 86400000);
  const h = Math.floor((diff % 86400000) / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  const urgent = d <= 120;
  return (
    <div data-testid="cra-exec-deadline" className={`rounded-xl border p-4 lg:p-5 flex flex-col sm:flex-row sm:items-center gap-4 ${urgent ? "border-crit/30 bg-crit/5" : "border-high/25 bg-high/5"}`}>
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <Clock3 className={`w-5 h-5 shrink-0 mt-0.5 ${urgent ? "text-crit" : "text-high"}`} />
        <div className="min-w-0">
          <div className="font-head font-bold text-sm">Countdown to the next CRA statutory deadline</div>
          <div className="text-[11px] font-mono text-muted-foreground truncate">{nd.label} · {nd.date}</div>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-4 sm:gap-6 shrink-0" data-testid="cra-exec-countdown">
        <Seg n={d} label="Days" urgent={urgent} />
        <Seg n={h} label="Hrs" urgent={urgent} />
        <Seg n={m} label="Min" urgent={urgent} />
        <Seg n={s} label="Sec" urgent={urgent} />
      </div>
    </div>
  );
}

// Lightweight centered modal (avoids pulling in a dialog dependency for these panels).
function Modal({ title, subtitle, onClose, children, testid, wide }) {
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm" data-testid={testid} onClick={onClose}>
      <div className={`w-full ${wide ? "max-w-3xl" : "max-w-lg"} max-h-[88vh] overflow-hidden rounded-xl border border-border bg-card shadow-2xl flex flex-col`} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border">
          <div>
            <div className="font-head font-black text-lg">{title}</div>
            {subtitle && <div className="text-[11px] font-mono text-muted-foreground mt-0.5">{subtitle}</div>}
          </div>
          <button onClick={onClose} data-testid={`${testid}-close`} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

const NIST_TONE = { Low: "bg-low", Medium: "bg-high", High: "bg-crit", Unknown: "bg-secondary" };
const SNAP_KPIS = [["Class.", "classification_approved_pct"], ["CE", "ce_ready_pct"], ["Control", "control_compliance_pct"], ["NIST", "nist_alignment_pct"], ["AI", "ai_grounding_score"]];
const fld = "mt-1 w-full bg-background border border-border rounded-md px-2 py-1.5 text-xs font-mono outline-none focus:border-ai";

export default function CRAExecutiveOverview() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const { data, loading, error, reload, refreshing } = useCRAData();
  const [assurance, setAssurance] = useState(null);
  const [briefBusy, setBriefBusy] = useState(false);
  const [snap, setSnap] = useState(null);
  const [savingSnap, setSavingSnap] = useState(false);
  const [emailCfg, setEmailCfg] = useState(null);
  const [sched, setSched] = useState({ enabled: false, day_of_week: 0, hour_utc: 8 });
  const [emailBusy, setEmailBusy] = useState(false);
  // Compare
  const [cmpA, setCmpA] = useState("");
  const [cmpB, setCmpB] = useState("current");
  // Email preview
  const [preview, setPreview] = useState(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  // Share link
  const [share, setShare] = useState(null); // {url, expires_at}
  const [shareBusy, setShareBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadSnapshots = () => api.get("/cra/exec-snapshots").then((r) => {
    setSnap(r.data);
    setCmpA((prev) => prev || (r.data.snapshots?.length ? r.data.snapshots[r.data.snapshots.length - 1].id : "current"));
  }).catch(() => {});
  const loadEmailCfg = () => api.get("/cra/exec-email/settings").then((r) => { setEmailCfg(r.data); setSched(r.data.schedule); }).catch(() => {});

  useEffect(() => {
    api.get("/cra/ai-monitor?days=30").then((r) => setAssurance(r.data)).catch(() => {});
    loadSnapshots();
    loadEmailCfg();
  }, []);

  const goTab = (tab) => {
    localStorage.setItem("cra-governance-tab", tab);
    localStorage.setItem("cra-governance-tab-pulse", tab);
    navigate("/app/cra-governance");
  };

  const downloadBrief = async () => {
    setBriefBusy(true);
    try {
      const r = await api.get("/cra/executive-overview.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = "obserra-eu-cra-executive-overview.pdf";
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    } catch { toast.error("Could not generate the executive overview PDF"); }
    setBriefBusy(false);
  };

  const saveSnapshot = async () => {
    setSavingSnap(true);
    try { await api.post("/cra/exec-snapshot", { label: "" }); await loadSnapshots(); toast.success("Snapshot saved"); }
    catch { toast.error("Could not save snapshot"); }
    setSavingSnap(false);
  };
  const deleteSnapshot = async (id) => {
    try { await api.delete(`/cra/exec-snapshot/${id}`); await loadSnapshots(); } catch { toast.error("Could not delete snapshot"); }
  };
  const saveEmailCfg = async () => {
    try { await api.put("/cra/exec-email/settings", sched); toast.success("Board email schedule saved"); loadEmailCfg(); }
    catch { toast.error("Could not save schedule"); }
  };
  const sendEmailNow = async () => {
    setEmailBusy(true);
    try { const r = await api.post("/cra/exec-email/send-now"); toast.success(`Sent to ${r.data.sent_to}`); }
    catch (e) { toast.error(e?.response?.data?.detail || "Could not send"); }
    setEmailBusy(false);
  };
  const openPreview = async () => {
    setPreviewBusy(true);
    try { const r = await api.get("/cra/exec-email/preview"); setPreview(r.data.html); }
    catch { toast.error("Could not load the email preview"); }
    setPreviewBusy(false);
  };
  const createShareLink = async () => {
    setShareBusy(true);
    try {
      const r = await api.post("/cra/exec-overview-link");
      setShare({ url: `${window.location.origin}${r.data.path}`, expires_at: r.data.expires_at });
      setCopied(false);
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not create a share link"); }
    setShareBusy(false);
  };
  const copyShare = async () => {
    try { await navigator.clipboard.writeText(share.url); setCopied(true); toast.success("Link copied"); setTimeout(() => setCopied(false), 2000); }
    catch { toast.error("Copy failed — select and copy the link manually"); }
  };
  const revokeShare = async () => {
    try { const r = await api.post("/cra/exec-overview-link/revoke"); toast.success(`Revoked ${r.data.revoked} link(s)`); setShare(null); }
    catch { toast.error("Could not revoke links"); }
  };

  if (loading && !data) {
    return <div className="flex items-center gap-2 text-sm text-muted-foreground p-8"><Loader2 className="w-4 h-4 animate-spin" /> Loading the EU CRA executive posture…</div>;
  }

  const dash = data?.dashboard || {};
  const controls = data?.controls?.overall || {};
  const nist = data?.nist?.overall || {};
  const nistFns = data?.nist?.functions || [];
  const cls = dash.classifications || {};
  const products = dash.products || 0;
  const nd = dash.next_deadline;

  const kpis = [
    { label: "Products under CRA", value: products, sub: `${cls["Critical"] || 0} critical · ${cls["Class II"] || 0} Class II`, Icon: Boxes, tone: "text-primary border-primary/25", tab: "products" },
    { label: "Classification approved", value: `${pct(dash.classification_approved || 0, products)}%`, sub: `${dash.classification_approved || 0} / ${products} approved`, Icon: BadgeCheck, tone: toneFor(pct(dash.classification_approved || 0, products)), tab: "products" },
    { label: "CE market-ready", value: `${pct(dash.ce_ready || 0, products)}%`, sub: `${dash.ce_ready || 0} / ${products} ready`, Icon: ShieldCheck, tone: toneFor(pct(dash.ce_ready || 0, products)), tab: "declaration" },
    { label: "Article 14 overdue", value: dash.reporting_overdue ?? 0, sub: "24h / 72h / final clocks", Icon: TriangleAlert, tone: (dash.reporting_overdue || 0) > 0 ? "text-crit border-crit/30" : "text-low border-low/30", tab: "vulnerability" },
    { label: "Control compliance", value: `${controls.percentage ?? 0}%`, sub: `${controls.implemented ?? 0} implemented · ${controls.partial ?? 0} partial`, Icon: FileCheck2, tone: toneFor(controls.percentage), tab: "controls" },
    { label: "NIST CSF alignment", value: `${nist.alignment_percentage ?? 0}%`, sub: `${nist.functions_aligned ?? 0} / ${nist.functions_total ?? 6} functions aligned`, Icon: ShieldCheck, tone: toneFor(nist.alignment_percentage), tab: "nist" },
    { label: "External assessments", value: dash.open_external_assessments ?? 0, sub: "open notified-body reviews", Icon: Building2, tone: "text-primary border-primary/25", tab: "conformity" },
    { label: "AI grounding score", value: assurance?.avg_score == null ? "—" : `${assurance.avg_score}%`, sub: assurance ? `${assurance.total_checks} answers checked · ${assurance.flagged_total} flagged` : "hallucination monitor", Icon: Fingerprint, tone: toneFor(assurance?.avg_score), tab: "assurance" },
  ];

  const cmpOptions = [{ id: "current", label: "Live now" }, ...(snap?.snapshots || []).map((s) => ({ id: s.id, label: `${s.label} · ${new Date(s.at).toLocaleDateString()}` }))];
  const getKpis = (sel) => (sel === "current" ? (snap?.current || {}) : (snap?.snapshots.find((s) => s.id === sel)?.kpis || {}));
  const aK = getKpis(cmpA);
  const bK = getKpis(cmpB);
  const canCompare = snap && (snap.snapshots?.length || 0) >= 1;

  return (
    <div className="rise space-y-6" data-testid="cra-executive-overview">
      <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-head font-black text-3xl tracking-tight">EU CRA Executive Overview</h1>
            <span className="px-2 py-1 rounded-full border border-primary/25 bg-primary/10 text-primary text-[10px] font-mono font-bold">REGULATION (EU) 2024/2847</span>
            <span data-testid="cra-exec-version" className="px-2 py-1 rounded-full border border-border bg-secondary/60 text-muted-foreground text-[10px] font-mono font-bold">Obserra CRA {APP_VERSION_LABEL}</span>
          </div>
          <p className="text-sm text-muted-foreground mt-2 max-w-3xl">
            A board-ready rollup of the whole EU Cyber Resilience Act posture. Every KPI opens the exact governance tab it
            summarizes; save dated snapshots to compare month over month, share a read-only board link and schedule the board email to directors.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={reload} disabled={refreshing} data-testid="cra-exec-refresh" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh</button>
          {isAdmin && <button onClick={createShareLink} disabled={shareBusy} data-testid="cra-exec-share" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 bg-ai/10 text-ai text-xs font-head font-bold">{shareBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Share2 className="w-3.5 h-3.5" />} Share read-only link</button>}
          <button onClick={saveSnapshot} disabled={savingSnap} data-testid="cra-exec-snapshot-save" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">{savingSnap ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />} Save snapshot</button>
          <button onClick={downloadBrief} disabled={briefBusy} data-testid="cra-exec-brief" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">{briefBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Executive Brief PDF</button>
          <button onClick={() => goTab("mission")} data-testid="cra-exec-open-governance" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Open Governance <ArrowRight className="w-3.5 h-3.5" /></button>
        </div>
      </div>

      {error && <div className="rounded-xl border border-crit/25 bg-crit/5 p-4 text-sm">{error}</div>}

      <DeadlineCountdown nd={nd} />

      <CraTabAnalyst tab="mission" />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {kpis.map((k) => (
          <KpiCard key={k.label} {...k} onClick={() => goTab(k.tab)} testid={`cra-exec-kpi-${k.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel title="Product classification split" subtitle="EU CRA risk categories across the registered portfolio" testid="cra-exec-classification">
          <div className="space-y-3">
            <Bar label="Default" value={cls["Default"] || 0} total={products} tone="bg-primary" />
            <Bar label="Class I (important)" value={cls["Class I"] || 0} total={products} tone="bg-high" />
            <Bar label="Class II (important)" value={cls["Class II"] || 0} total={products} tone="bg-high" />
            <Bar label="Critical" value={cls["Critical"] || 0} total={products} tone="bg-crit" />
          </div>
          <div className="mt-4 pt-3 border-t border-border grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-[10px] font-mono uppercase text-muted-foreground">Avg readiness</div><div className="font-head font-bold text-lg">{dash.average_readiness ?? 0}%</div></div>
            <div><div className="text-[10px] font-mono uppercase text-muted-foreground">Products assessed</div><div className="font-head font-bold text-lg">{controls.products_assessed ?? 0} / {controls.products_total ?? products}</div></div>
          </div>
        </Panel>

        <Panel title="NIST CSF 2.0 alignment" subtitle={nist.framework || "NIST CSF 2.0 · SP 800-218 (SSDF)"} testid="cra-exec-nist">
          <div className="space-y-2.5">
            {nistFns.map((f) => (
              <div key={f.code}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-foreground/90"><span className="font-mono text-muted-foreground">{f.code}</span> {f.name}</span>
                  <span className="font-mono text-muted-foreground">{f.compliance_rate}%</span>
                </div>
                <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className={`h-full ${NIST_TONE[f.risk] || "bg-primary"}`} style={{ width: `${f.compliance_rate}%` }} /></div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Essential-requirement control posture" subtitle={`${controls.requirements_total ?? 0} CRA requirements assessed`} testid="cra-exec-controls">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-low/25 bg-low/5 p-3"><div className="font-head font-black text-2xl text-low">{controls.implemented ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Implemented</div></div>
            <div className="rounded-lg border border-high/25 bg-high/5 p-3"><div className="font-head font-black text-2xl text-high">{controls.partial ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Partial</div></div>
            <div className="rounded-lg border border-crit/25 bg-crit/5 p-3"><div className="font-head font-black text-2xl text-crit">{(controls.gaps ?? 0) + (controls.not_started ?? 0)}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Gap / not started</div></div>
          </div>
          <div className="mt-4"><Bar label="Overall control compliance" value={controls.percentage ?? 0} total={100} tone={(controls.percentage ?? 0) >= 80 ? "bg-low" : (controls.percentage ?? 0) >= 50 ? "bg-high" : "bg-crit"} /></div>
        </Panel>

        <Panel title="AI assurance & grounding" subtitle="Hallucination monitor across every Obserrian CRA AI answer" testid="cra-exec-assurance">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className={`rounded-lg border p-3 ${toneFor(assurance?.avg_score)}`}><div className="font-head font-black text-2xl">{assurance?.avg_score == null ? "—" : `${assurance.avg_score}%`}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Avg score</div></div>
            <div className="rounded-lg border border-border p-3"><div className="font-head font-black text-2xl text-foreground">{assurance?.total_checks ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Checked</div></div>
            <div className={`rounded-lg border p-3 ${(assurance?.flagged_total || 0) > 0 ? "border-crit/25 text-crit" : "border-low/25 text-low"}`}><div className="font-head font-black text-2xl">{assurance?.flagged_total ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Flagged</div></div>
          </div>
          <button onClick={() => goTab("assurance")} className="mt-4 inline-flex items-center gap-1.5 text-[11px] font-head font-bold text-ai hover:underline" data-testid="cra-exec-open-assurance">Open the AI Assurance monitor <ArrowRight className="w-3 h-3" /></button>
        </Panel>
      </div>

      {/* Snapshot compare — side-by-side board movement */}
      <Panel title="Compare snapshots" subtitle="See exactly what moved between two dated snapshots (or against the live posture)" testid="cra-exec-compare">
        {!canCompare ? (
          <div className="text-sm text-muted-foreground">Save at least one snapshot to compare it against the live posture or another snapshot.</div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <label className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Baseline (A)
                <select data-testid="cra-exec-compare-a" value={cmpA} onChange={(e) => setCmpA(e.target.value)} className={fld}>
                  {cmpOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                </select>
              </label>
              <label className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Compare to (B)
                <select data-testid="cra-exec-compare-b" value={cmpB} onChange={(e) => setCmpB(e.target.value)} className={fld}>
                  {cmpOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                </select>
              </label>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="cra-exec-compare-table">
                <thead className="font-mono uppercase text-[9px] text-muted-foreground border-b border-border">
                  <tr><th className="text-left py-2">KPI</th><th className="text-right py-2">A</th><th className="text-right py-2">B</th><th className="text-right py-2 flex items-center justify-end gap-1"><GitCompareArrows className="w-3 h-3" /> Change</th></tr>
                </thead>
                <tbody>
                  {CMP_ROWS.map(([label, key]) => {
                    const a = aK[key]; const b = bK[key];
                    const delta = (typeof a === "number" && typeof b === "number") ? b - a : null;
                    return (
                      <tr key={key} className="border-b border-border/60" data-testid={`cra-exec-compare-row-${key}`}>
                        <td className="py-2 pr-3 text-foreground/90">{label}</td>
                        <td className="py-2 text-right font-mono">{fmtVal(key, a)}</td>
                        <td className="py-2 text-right font-mono font-bold">{fmtVal(key, b)}</td>
                        <td className="py-2 text-right"><DeltaChip k={key} v={delta} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel title="Executive Overview board email" subtitle="Schedule this rollup to directors — separate from the analyst digest" testid="cra-exec-email">
          {emailCfg ? (
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" data-testid="cra-exec-email-enabled" checked={!!sched.enabled} disabled={!emailCfg.is_admin} onChange={(e) => setSched({ ...sched, enabled: e.target.checked })} />
                Email the Executive Overview to directors weekly
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Day
                  <select data-testid="cra-exec-email-day" value={sched.day_of_week} disabled={!emailCfg.is_admin} onChange={(e) => setSched({ ...sched, day_of_week: +e.target.value })} className={fld}>
                    {DAYS.map((dd, i) => <option key={i} value={i}>{dd}</option>)}
                  </select>
                </label>
                <label className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Hour (UTC)
                  <select data-testid="cra-exec-email-hour" value={sched.hour_utc} disabled={!emailCfg.is_admin} onChange={(e) => setSched({ ...sched, hour_utc: +e.target.value })} className={fld}>
                    {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}
                  </select>
                </label>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {emailCfg.is_admin && <button onClick={saveEmailCfg} data-testid="cra-exec-email-save" className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Save schedule</button>}
                <button onClick={openPreview} disabled={previewBusy} data-testid="cra-exec-email-preview" className="px-3 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold inline-flex items-center gap-1.5">{previewBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5" />} Preview email</button>
                <button onClick={sendEmailNow} disabled={emailBusy} data-testid="cra-exec-email-sendnow" className="px-3 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold inline-flex items-center gap-1.5">{emailBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />} Send me one now</button>
              </div>
              {!emailCfg.is_admin && <div className="text-[11px] font-mono text-muted-foreground">Only admins can change the schedule.</div>}
            </div>
          ) : <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading schedule…</div>}
        </Panel>

        <Panel title="Executive Overview snapshots" subtitle="Save a dated snapshot to compare CRA posture month over month" testid="cra-exec-snapshots"
          action={<button onClick={saveSnapshot} disabled={savingSnap} data-testid="cra-exec-snapshots-save" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold shrink-0">{savingSnap ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />} Save</button>}>
          {(!snap || snap.snapshots.length === 0) && <div className="text-sm text-muted-foreground">No snapshots yet — save one to start tracking CRA posture over time. Deltas appear on the next snapshot.</div>}
          <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
            {snap?.snapshots.map((s) => (
              <div key={s.id} data-testid={`cra-exec-snapshot-${s.id}`} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div><span className="font-head font-bold text-sm">{s.label}</span> <span className="text-[10px] font-mono text-muted-foreground">{new Date(s.at).toLocaleDateString()}</span></div>
                  <button onClick={() => deleteSnapshot(s.id)} data-testid={`cra-exec-snapshot-del-${s.id}`} className="text-muted-foreground hover:text-crit"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
                <div className="grid grid-cols-5 gap-2 mt-2 text-center">
                  {SNAP_KPIS.map(([lbl, key]) => (
                    <div key={key}>
                      <div className="text-[9px] font-mono uppercase text-muted-foreground">{lbl}</div>
                      <div className="font-head font-bold text-sm">{s.kpis[key] == null ? "—" : `${s.kpis[key]}%`}</div>
                      {s.delta && <DeltaChip k={key} v={s.delta[key]} />}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="text-[10px] font-mono text-muted-foreground">
        Article 14 reporting applies {dash.reporting_effective_date} · General CRA application {dash.general_application_date} · Live figures — Obserra never substitutes synthetic regulatory data.
      </div>

      {preview !== null && (
        <Modal title="Board email preview" subtitle="Exactly what directors receive" testid="cra-exec-email-preview-modal" onClose={() => setPreview(null)} wide>
          <div className="rounded-lg border border-border overflow-hidden bg-white">
            <iframe title="email-preview" srcDoc={preview} className="w-full h-[60vh]" data-testid="cra-exec-email-preview-frame" sandbox="" />
          </div>
        </Modal>
      )}

      {share && (
        <Modal title="Read-only Executive Overview link" subtitle="Directors can view the live board posture without logging in" testid="cra-exec-share-modal" onClose={() => setShare(null)}>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <input readOnly value={share.url} data-testid="cra-exec-share-url" className="flex-1 bg-background border border-border rounded-md px-3 py-2 text-xs font-mono outline-none" onFocus={(e) => e.target.select()} />
              <button onClick={copyShare} data-testid="cra-exec-share-copy" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold shrink-0">{copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />} {copied ? "Copied" : "Copy"}</button>
            </div>
            <div className="text-[11px] font-mono text-muted-foreground">Expires {new Date(share.expires_at).toLocaleString()} · product names & internal records are never exposed · up to 5 active links.</div>
            <div className="flex items-center gap-2 pt-2 border-t border-border">
              <a href={share.url} target="_blank" rel="noreferrer" data-testid="cra-exec-share-open" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">Open <ArrowRight className="w-3.5 h-3.5" /></a>
              <button onClick={revokeShare} data-testid="cra-exec-share-revoke" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-crit/40 bg-crit/10 text-crit text-xs font-head font-bold">Revoke all links</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
