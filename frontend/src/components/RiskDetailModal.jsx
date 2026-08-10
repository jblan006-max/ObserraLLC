import { useState, useEffect } from "react";
import { X, Loader2, Wrench, ShieldX, Users, CheckCircle2, XCircle, Clock, Terminal, ShieldCheck, ListPlus, Plug, Share2, Copy, Check, ExternalLink, Eye, Download } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { AIExplain } from "@/components/AIExplain";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { toast } from "sonner";

const RATE = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
const money = (n) => n == null ? "—" : n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}k` : `$${Math.round(n || 0)}`;

// Connector status → color. Live/healthy = green, action-capable/degraded = amber, down = red, unknown = grey.
const CONN_TONE = {
  ok: "142 70% 45%", healthy: "142 70% 45%", connected: "142 70% 45%", live: "142 70% 45%", verified: "142 70% 45%",
  warn: "35 90% 55%", degraded: "35 90% 55%", "action-capable": "35 90% 55%", pending: "35 90% 55%",
  down: "0 84% 60%", unavailable: "0 84% 60%", error: "0 84% 60%", killed: "0 84% 60%", unreachable: "0 84% 60%",
};

// The connectors / data sources an item is wired to. Prefers the item's own `connectors`
// (set by agentic deep-dives with live health); otherwise derives them from whatever
// source-shaped fields the dashboard's item carries, so EVERY detail card shows connectors.
function deriveConnectors(item = {}) {
  if (Array.isArray(item.connectors) && item.connectors.length) {
    return item.connectors.filter(Boolean).map((c) =>
      typeof c === "string" ? { name: c } : { name: c.name || c.label || String(c), status: c.status, detail: c.detail }
    );
  }
  const out = [];
  const seen = new Set();
  const push = (name, detail, status) => {
    if (!name) return;
    const key = String(name).toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ name: String(name), detail, status });
  };
  if (item.provider) push(item.provider, "provider");
  (Array.isArray(item.sources) ? item.sources : item.source ? [item.source] : []).forEach((s) =>
    push(typeof s === "string" ? s : s?.name, "source", typeof s === "object" ? s?.status : undefined));
  (item.tools || []).forEach((t) => push(typeof t === "string" ? t : t?.name, "tool"));
  (item.resources || item.dataStores || item.data_flows || []).forEach((r) =>
    push(typeof r === "string" ? r : r?.name, "data store"));
  return out;
}

// Honest outcome panel — reflects the REAL backend verification (never a fake success).
// verified → green Remediated; In Progress → amber sandbox-verifying; else → red not-applied
// with the true reason + raw provider evidence (Defensibility Ledger id).
function ActionResult({ result }) {
  const [raw, setRaw] = useState(false);
  const verified = result.verified === true;
  const inProgress = result.status === "In Progress";
  const tone = verified ? "142 70% 45%" : inProgress ? "35 90% 55%" : "0 84% 60%";
  const Icon = verified ? CheckCircle2 : inProgress ? Clock : XCircle;
  const label = verified ? "Verified — remediation applied" : inProgress ? "In progress — sandbox-verifying" : "Not applied — real result";
  const evidence = result.external || result.trace;
  return (
    <div data-testid="action-result" className="rounded-xl border p-3.5 space-y-2"
      style={{ borderColor: `hsl(${tone} / 0.45)`, background: `hsl(${tone} / 0.07)` }}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className="w-4 h-4 shrink-0" style={{ color: `hsl(${tone})` }} />
          <span className="font-head font-bold text-sm" style={{ color: `hsl(${tone})` }}>{label}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {result.provider && <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full bg-secondary/70">{result.provider}</span>}
          {result.status && <span className="text-[9px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${tone} / 0.15)`, color: `hsl(${tone})` }}>{result.status}</span>}
        </div>
      </div>
      <p data-testid="action-result-message" className="text-[12px] leading-relaxed">{result.message}</p>
      {(result.risk_reduced || 0) > 0 && <p className="text-[11px] font-mono" style={{ color: "hsl(142 70% 45%)" }}>ALE reduced {money(result.risk_reduced)} — recalculated live from the fresh scan.</p>}
      {result.ledger_id && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[9px] font-mono text-muted-foreground">Ledger evidence #{String(result.ledger_id).slice(0, 8)}</span>
          {evidence && <button data-testid="action-result-raw" onClick={() => setRaw((r) => !r)} className="text-[10px] font-mono underline text-muted-foreground hover:text-foreground">{raw ? "Hide raw provider response" : "Show raw provider response"}</button>}
        </div>
      )}
      {raw && evidence && (
        <pre className="text-[10px] font-mono bg-[#0a0e17] border border-border rounded-lg p-2 overflow-x-auto max-h-56 overflow-y-auto">{JSON.stringify(evidence, null, 2)}</pre>
      )}
    </div>
  );
}

// One-click: turn any deep-dive card into a tracked remediation-plan task (grounded $ at stake).
function AddToPlanButton({ item, accent }) {
  const [state, setState] = useState("idle");
  const add = async () => {
    setState("adding");
    try {
      await api.post("/risk-engine/plan", {
        title: item.title || item.explainTitle || "Untitled item",
        ref: item.refLabel || "", source: item.explainKind || "deep-dive",
        recommendation: (item.recommendedActions && item.recommendedActions[0]) || "",
        severity: item.rating || "", context: item.explainContext || {},
      });
      setState("added");
      toast.success("Added to remediation plan — tracked in Remediations");
    } catch (e) {
      setState("idle");
      toast.error(e?.response?.data?.detail || "Could not add to plan");
    }
  };
  const added = state === "added";
  return (
    <button data-testid="deep-dive-add-plan" disabled={state !== "idle"} onClick={add}
      className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-lg border disabled:opacity-70 transition-colors"
      style={{ borderColor: `hsl(${added ? "142 70% 45%" : accent} / 0.5)`, color: added ? "hsl(142 70% 45%)" : `hsl(${accent})` }}>
      {state === "adding" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : added ? <CheckCircle2 className="w-3.5 h-3.5" /> : <ListPlus className="w-3.5 h-3.5" />}
      {added ? "Added to plan" : "Add to remediation plan"}
    </button>
  );
}

// Standard executable actions (e.g. agent Suspend/Kill/Resume, AI-system Sanction/Block). Each button
// dispatches a REAL action via /actions/run and is auto-written to the audit trail + Defensibility Ledger.
function StandardActions({ actions, accent }) {
  const [busy, setBusy] = useState(null);
  const [res, setRes] = useState(null);
  const TONE = { primary: accent, danger: "0 84% 60%", neutral: "215 15% 60%" };
  const run = async (a) => {
    if (a.confirm && !window.confirm(`${a.label} — execute this live governance action?\nIt is written to the audit trail and cannot be silently undone.`)) return;
    setBusy(a.id); setRes(null);
    try {
      const { data } = await api.post("/actions/run", { action_id: a.action_id });
      const enf = data.agent?.enforcement;
      const runtime = enf && enf.runtime === "external-webhook"
        ? (enf.external_ok ? " · dispatched to the agent runtime ✓" : " · ⚠ never reached the agent runtime")
        : "";
      setRes({ ok: true, message: data.message + runtime });
      toast.success(data.message);
      a.onDone && a.onDone(data);
    } catch (e) {
      const m = e?.response?.data?.detail || "Action failed.";
      setRes({ ok: false, message: m });
      toast.error(m);
    } finally {
      setBusy(null);
    }
  };
  return (
    <div data-testid="standard-actions">
      <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">Standard actions</div>
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => {
          const tone = TONE[a.variant] || accent;
          const Icon = a.icon || ShieldCheck;
          const primary = a.variant === "primary";
          return (
            <button
              key={a.id}
              data-testid={`std-action-${a.id}`}
              disabled={!!busy}
              onClick={() => run(a)}
              className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-lg border disabled:opacity-50 transition-colors"
              style={primary
                ? { background: `hsl(${tone})`, color: "#050810", borderColor: `hsl(${tone})` }
                : { borderColor: `hsl(${tone} / 0.5)`, color: `hsl(${tone})` }}
            >
              {busy === a.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />} {a.label}
            </button>
          );
        })}
      </div>
      {res && (
        <div
          data-testid="standard-action-result"
          className="mt-2 rounded-lg border p-2.5 text-[12px]"
          style={{ borderColor: `hsl(${res.ok ? "142 70% 45%" : "0 84% 60%"} / 0.45)`,
                   background: `hsl(${res.ok ? "142 70% 45%" : "0 84% 60%"} / 0.08)`,
                   color: `hsl(${res.ok ? "142 70% 45%" : "0 84% 60%"})` }}
        >
          {res.ok ? "✓ " : "✗ "}{res.message}
          <span className="text-muted-foreground"> · written to the audit trail + Defensibility Ledger</span>
        </div>
      )}
    </div>
  );
}

// One-click: mint an expiring, watermarked, read-only auditor link for THIS detail card (admin only).
// The public portal + signed PDF carry the card's risk/rating, connectors, recommendations and compliance,
// stamped with a "Verified by Obserra" integrity seal. Turns any card into board-ready evidence on the spot.
function ShareCardButton({ item, accent }) {
  const { user } = useAuth();
  const [state, setState] = useState("idle");
  const [link, setLink] = useState(null);
  const [copied, setCopied] = useState(false);
  const [stats, setStats] = useState(null);
  useEffect(() => {
    if (!link?.token) return;
    let ok = true;
    const poll = () => api.get(`/agents/runtime/card-share/${link.token}/stats`).then(({ data }) => { if (ok) setStats(data); }).catch(() => {});
    poll();
    const t = setInterval(poll, 15000);
    return () => { ok = false; clearInterval(t); };
  }, [link]);
  if (user?.role !== "admin") return null;

  const share = async () => {
    setState("sharing");
    try {
      const facets = (item.facets || []).map((f) => ({ label: f.label, value: f.value == null ? "" : String(f.value) }));
      const { data } = await api.post("/agents/runtime/card-share", {
        title: item.title || "Detail card",
        ref: item.refLabel || "",
        kind: item.explainKind || "deep-dive",
        rating: item.rating || null,
        score: item.score ?? null,
        ale: item.ale ?? null,
        compliance_pct: item.compliancePct ?? null,
        connectors: deriveConnectors(item),
        facets,
        recommendations: item.recommendedActions || [],
        compliance_refs: item.complianceRefs || [],
        days: 14,
      });
      setLink(data);
      setState("done");
      try { await navigator.clipboard.writeText(data.url); setCopied(true); } catch { /* clipboard blocked */ }
      toast.success("Shareable auditor link created — copied to clipboard");
    } catch (e) {
      setState("idle");
      toast.error(e?.response?.data?.detail || "Could not create share link");
    }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(link.url); setCopied(true); toast.success("Link copied"); } catch { /* blocked */ }
  };

  if (link) {
    return (
      <div data-testid="card-share-result" className="w-full rounded-xl border p-3 space-y-2"
        style={{ borderColor: `hsl(${accent} / 0.4)`, background: `hsl(${accent} / 0.06)` }}>
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider" style={{ color: `hsl(${accent})` }}>
            <Share2 className="w-3.5 h-3.5" /> Shareable auditor link · expires {new Date(link.expires_at).toLocaleDateString()}
          </div>
          <div data-testid="card-share-stats" className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1.5">
            <Eye className="w-3 h-3" /> {stats?.opens ?? 0} viewed <Download className="w-3 h-3 ml-1" /> {stats?.downloads ?? 0} downloaded
          </div>
        </div>
        <div className="flex items-start gap-3">
          <div className="bg-white p-1.5 rounded-md shrink-0"><QRCodeSVG value={link.url} size={72} level="M" /></div>
          <div className="min-w-0 flex-1 space-y-2">
            <div data-testid="card-share-url" className="text-[11px] font-mono break-all bg-secondary/50 rounded-md px-2 py-1.5">{link.url}</div>
            <div className="flex flex-wrap gap-2">
              <button data-testid="card-share-copy" onClick={copy}
                className="inline-flex items-center gap-1.5 text-[11px] font-head font-bold px-2.5 py-1.5 rounded-md border"
                style={{ borderColor: `hsl(${accent} / 0.5)`, color: `hsl(${accent})` }}>
                {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />} {copied ? "Copied" : "Copy link"}
              </button>
              <a data-testid="card-share-open" href={link.url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-[11px] font-head font-bold px-2.5 py-1.5 rounded-md border border-border text-foreground">
                <ExternalLink className="w-3.5 h-3.5" /> Open
              </a>
            </div>
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground">Read-only, expiring, watermarked with the downloader's name + a "Verified by Obserra" integrity seal. No login needed.</p>
      </div>
    );
  }

  return (
    <button data-testid="card-share-btn" disabled={state !== "idle"} onClick={share}
      className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-lg border disabled:opacity-70 transition-colors"
      style={{ borderColor: `hsl(${accent} / 0.5)`, color: `hsl(${accent})` }}>
      {state === "sharing" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Share2 className="w-3.5 h-3.5" />} Share this card
    </button>
  );
}

// Standardized universal Deep-Dive panel — Risk Score & Rating (FAIR), AI Strategic Brief,
// Recommended Actions, and an Integrated Action Hub whose buttons dispatch REAL remediations
// and surface the honest outcome inline. Reused across every engine-backed surface.
export function RiskDetailModal({ item, accent = "255 85% 66%", busy, result, onClose, onAction }) {
  if (!item) return null;
  const rc = RATE[item.rating] || accent;
  const hub = item.taskId && onAction;
  const showResult = result && result.taskId === item.taskId;
  return (
    <div data-testid="deep-dive-modal" onClick={onClose}
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/65 backdrop-blur-sm">
      <div onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={item.title || "Deep-dive"} data-testid="risk-detail-modal"
        className="bg-card border border-border rounded-2xl w-full max-w-2xl max-h-[88vh] overflow-y-auto p-6 space-y-4"
        style={{ boxShadow: `0 0 0 1px hsl(${accent} / 0.3), 0 24px 60px -20px hsl(${accent} / 0.4)` }}>
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{item.refLabel || "Deep-dive"}</div>
            <h2 className="font-head font-black text-xl tracking-tight leading-tight">{item.title}</h2>
          </div>
          <button data-testid="deep-dive-close" onClick={onClose} className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"><X className="w-5 h-5" /></button>
        </header>

        {/* Live FAIR rating + ALE + exploitability score */}
        <div className="flex flex-wrap items-center gap-2" data-testid="deep-dive-scores">
          {item.rating && <span className="text-xs font-mono font-bold px-3 py-1 rounded-full" style={{ background: `hsl(${rc} / 0.15)`, color: `hsl(${rc})` }}>{item.rating} RISK</span>}
          {item.score != null && <span className="text-xs font-mono px-3 py-1 rounded-full bg-secondary/70">Score {item.score}/100</span>}
          {item.ale != null && <span className="text-xs font-mono font-bold px-3 py-1 rounded-full" style={{ background: "hsl(15 80% 55% / 0.15)", color: "hsl(15 80% 55%)" }}>ALE {money(item.ale)}</span>}
          {item.exceedsAppetite && <span className="text-xs font-mono px-3 py-1 rounded-full bg-crit/15 text-crit">⚠ Exceeds appetite</span>}
          {item.rating == null && item.score == null && item.ale == null && <span data-testid="deep-dive-unscored" className="text-xs font-mono px-3 py-1 rounded-full bg-secondary/70 text-muted-foreground">Not yet scored</span>}
        </div>

        {/* Compliance alignment — always shown so every deep-dive maps risk → controls */}
        {(item.compliancePct != null || item.complianceRefs?.length > 0) && (
          <div data-testid="deep-dive-compliance" className="rounded-lg bg-secondary/40 p-3">
            <div className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
              <ShieldCheck className="w-3 h-3" /> Compliance alignment{item.compliancePct != null && <span className="text-foreground/70"> · {item.compliancePct}% area coverage</span>}
            </div>
            <div className="flex flex-wrap gap-1">
              {(item.complianceRefs || []).length === 0
                ? <span className="text-[11px] text-muted-foreground">Mapped controls populate as findings correlate.</span>
                : item.complianceRefs.map((c) => <span key={c} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-secondary/70">{c}</span>)}
            </div>
          </div>
        )}

        {/* Who / What / When / Where / Why */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2" data-testid="deep-dive-facets">
          {(item.facets || []).map((f, i) => (
            <div
              key={`${f.label}-${i}`}
              data-testid={`deep-dive-facet-${(f.label || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`}
              className="rounded-lg bg-secondary/40 p-3"
            >
              <div className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider text-muted-foreground">{f.icon && <f.icon className="w-3 h-3" />}{f.label}</div>
              <div className="text-sm mt-0.5 break-words">{f.value ?? "—"}</div>
            </div>
          ))}
        </div>

        {/* Connectors & data sources this item is wired to — live health where available */}
        {(() => {
          const conns = deriveConnectors(item);
          return (
            <div data-testid="deep-dive-connectors">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5"><Plug className="w-3 h-3" /> Connectors &amp; data sources</div>
              {conns.length === 0 ? (
                <p className="text-[11px] text-muted-foreground">No connected sources recorded for this item.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {conns.map((c, i) => {
                    const tone = c.status ? (CONN_TONE[String(c.status).toLowerCase()] || "215 15% 60%") : "215 15% 60%";
                    return (
                      <span key={`${c.name}-${i}`} data-testid={`deep-dive-connector-${i}`}
                        className="inline-flex items-center gap-1.5 text-[11px] font-mono px-2.5 py-1 rounded-full border"
                        style={{ borderColor: `hsl(${tone} / 0.4)`, background: `hsl(${tone} / 0.1)` }} title={c.detail || ""}>
                        {c.status && <span className="w-1.5 h-1.5 rounded-full" style={{ background: `hsl(${tone})` }} />}
                        <span className="text-foreground/90">{c.name}</span>
                        {c.detail && <span className="text-muted-foreground">· {c.detail}</span>}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })()}

        {/* AI Strategic Brief — grounded in the unified correlation model */}
        <AIExplain title={item.explainTitle || item.title} kind={item.explainKind || "deep-dive"} context={item.explainContext || {}} accent={accent} />

        {/* Recommendations & fixes — grounded guidance / fix path (always present) */}
        <div data-testid="deep-dive-recommendations">
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">Recommendations &amp; fixes</div>
          <ul className="space-y-1">
            {(item.recommendedActions && item.recommendedActions.length
              ? item.recommendedActions
              : ["Review this item's risk drivers and connectors above.",
                 "Apply a governance action below or add it to the remediation plan to track the fix."]
            ).map((s, i) => <li key={i} className="text-[12px] flex items-start gap-2"><span style={{ color: `hsl(${accent})` }}>→</span> {s}</li>)}
          </ul>
        </div>
        {item.fixScript && (
          <div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1"><Terminal className="w-3 h-3" /> Automated fix script</div>
            <pre data-testid="deep-dive-script" className="text-[11px] font-mono bg-[#0a0e17] border border-border rounded-lg p-2.5 overflow-x-auto">{item.fixScript}</pre>
          </div>
        )}

        {/* Add any card to the tracked remediation plan · Share this card as an expiring auditor link */}
        <div className="pt-1 flex flex-wrap gap-2 items-center">
          <AddToPlanButton key={`${item.refLabel || ""}|${item.title || ""}`} item={item} accent={accent} />
          <ShareCardButton item={item} accent={accent} />
        </div>

        {/* Standard executable actions (agent Suspend/Kill/Resume, AI-system Sanction/Block) */}
        {item.executableActions?.length > 0 && <StandardActions actions={item.executableActions} accent={accent} />}

        {/* Integrated Action Hub */}
        {hub ? (
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">Integrated action hub</div>
            <div className="flex flex-wrap gap-2">
              <button data-testid="action-execute-fix" disabled={busy} onClick={() => onAction("remediate")} className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-lg disabled:opacity-50" style={{ background: `hsl(${accent})`, color: "#050810" }}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wrench className="w-3.5 h-3.5" />} Execute Fix</button>
              <button data-testid="action-isolate" disabled={busy} onClick={() => onAction("isolate")} className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-lg border border-crit/40 text-crit disabled:opacity-50"><ShieldX className="w-3.5 h-3.5" /> Isolate</button>
              <button data-testid="action-assign-soc" disabled={busy} onClick={() => onAction("soc")} className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-lg border border-border text-foreground disabled:opacity-50"><Users className="w-3.5 h-3.5" /> Assign to SOC</button>
              <button data-testid="action-accept-risk" disabled={busy} onClick={() => onAction("accept")} className="flex items-center gap-1.5 text-xs font-head font-bold px-3 py-2 rounded-lg border border-border text-muted-foreground disabled:opacity-50"><CheckCircle2 className="w-3.5 h-3.5" /> Accept Risk</button>
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5">Actions dispatch a REAL external call / sandbox upgrade — the honest result (and raw provider response) appears below and is written to the Defensibility Ledger. ALE only recalculates on a verified fix.</p>
            {showResult && <div className="mt-3"><ActionResult result={result} /></div>}
          </div>
        ) : (
          <p className="text-[11px] text-muted-foreground">No open remediation task is linked to this item — resolve its underlying finding to enable one-click remediation.</p>
        )}
      </div>
    </div>
  );
}
