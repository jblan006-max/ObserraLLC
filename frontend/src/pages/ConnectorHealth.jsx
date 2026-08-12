import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { AIInsight } from "@/components/AIInsight";
import { ConnectorCatalog } from "@/components/ConnectorCatalog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Plug, Server, Clock, CheckCircle2, AlertTriangle, RefreshCw, Activity, XCircle, Rocket, BookOpen, FileDown } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, ReferenceLine } from "recharts";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const HEALTH = {
  healthy: { c: "142 70% 45%", label: "Healthy", Icon: CheckCircle2 },
  stale: { c: "35 90% 55%", label: "Stale", Icon: Clock },
  degraded: { c: "0 84% 60%", label: "Degraded", Icon: AlertTriangle },
};
const fmtAge = (m) => (m == null ? "—" : m < 60 ? `${m}m ago` : `${Math.floor(m / 60)}h ${m % 60}m ago`);

const GL_STATUS = {
  pass: { c: "142 70% 45%", Icon: CheckCircle2, label: "Ready" },
  warn: { c: "35 90% 55%", Icon: AlertTriangle, label: "Attention" },
  fail: { c: "0 84% 60%", Icon: XCircle, label: "Blocker" },
};

function GoLiveChecklist() {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { const { data } = await api.get("/sap/go-live-checklist"); setD(data); }
    catch (e) { toast.error("Could not run readiness check"); }
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);
  const dRef = useRef(null);
  useEffect(() => { dRef.current = d; }, [d]);
  const lastProbeRef = useRef(0);
  useEffect(() => {
    const tick = async () => {
      const cur = dRef.current;
      if (cur && cur.items.some((i) => i.id === "freshness" && i.status !== "pass") && Date.now() - lastProbeRef.current > 180000) {
        lastProbeRef.current = Date.now();
        try { await api.post("/sap/systems/reprobe"); } catch (e) { /* silent — re-check will surface state */ }
      }
      load();
    };
    const t = setInterval(tick, 30000);
    return () => clearInterval(t);
  }, [load]);
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [guideBusy, setGuideBusy] = useState(false);
  const openGuide = async () => {
    setGuideBusy(true);
    try {
      const res = await api.get("/deploy/guide.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not open the guide"); }
    setGuideBusy(false);
  };
  const [reportBusy, setReportBusy] = useState(false);
  const exportReport = async () => {
    setReportBusy(true);
    try {
      const res = await api.get("/sap/go-live-report.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = "obserra-go-live-report.pdf"; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not export report"); }
    setReportBusy(false);
  };
  const [fixing, setFixing] = useState("");
  const [webhookOpen, setWebhookOpen] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [savingWebhook, setSavingWebhook] = useState(false);
  const saveWebhook = async () => {
    const url = webhookUrl.trim();
    if (!url.toLowerCase().startsWith("http")) { toast.error("Enter a valid http(s) webhook URL"); return; }
    setSavingWebhook(true);
    try {
      await api.put("/agents/runtime/webhook", { webhook: url, secret: webhookSecret.trim() || undefined });
      toast.success("Agent-runtime webhook registered — re-checking readiness");
      setWebhookOpen(false); setWebhookUrl(""); setWebhookSecret("");
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not register webhook"); }
    setSavingWebhook(false);
  };
  const fixItem = async (it) => {
    if (it.id === "freshness" || it.id === "connectors") {
      setFixing(it.id);
      try { await api.post("/sap/systems/reprobe"); toast.success("Connectors re-probed — data refreshed"); await load(); }
      catch (e) { toast.error("Re-probe failed"); }
      setFixing("");
      return;
    }
    if (it.id === "runtime") { setWebhookOpen(true); return; }
    navigate("/app/settings");
  };
  const tone = d?.ready ? "142 70% 45%" : (d?.failed ? "0 84% 60%" : "35 90% 55%");

  return (
    <div className="bg-card fact-border rounded-xl p-5" data-testid="go-live-checklist">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{ background: `hsl(${tone} / 0.14)` }}>
            <Rocket className="w-5 h-5" style={{ color: `hsl(${tone})` }} />
          </div>
          <div>
            <h2 className="font-head font-bold text-lg leading-tight">Go-Live Readiness</h2>
            <p className="text-xs text-muted-foreground">Live production-readiness — every check runs against real state · auto-refreshes every 30s.</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {d && (
            <div className="text-right">
              <div className="font-head font-black text-2xl leading-none" style={{ color: `hsl(${tone})` }} data-testid="go-live-score">{d.score}%</div>
              <div className="text-[10px] font-mono uppercase tracking-wider" style={{ color: `hsl(${tone})` }} data-testid="go-live-status">{d.ready ? "Production ready" : `${d.failed} blocker(s)`}</div>
            </div>
          )}
          {isAdmin && (
            <Button size="sm" variant="ghost" className="gap-1.5" data-testid="go-live-guide-link" onClick={openGuide} disabled={guideBusy}>
              <BookOpen className="w-3.5 h-3.5" />{guideBusy ? "Opening…" : "Read the Go-Live guide"}
            </Button>
          )}
          {isAdmin && (
            <Button size="sm" variant="ghost" className="gap-1.5" data-testid="go-live-export-report" onClick={exportReport} disabled={reportBusy}>
              <FileDown className="w-3.5 h-3.5" />{reportBusy ? "Exporting…" : "Export report"}
            </Button>
          )}
          <Button size="sm" variant="outline" className="gap-1.5" data-testid="go-live-recheck" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />{loading ? "Checking…" : "Re-check"}
          </Button>
        </div>
      </div>
      {!d ? <Spinner /> : (
        <>
          <div className="h-2 rounded-full bg-secondary overflow-hidden mb-4">
            <div className="h-full rounded-full transition-all" style={{ width: `${d.score}%`, background: `hsl(${tone})` }} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {d.items.map((it) => { const S = GL_STATUS[it.status] || GL_STATUS.warn; const I = S.Icon; return (
              <div key={it.id} className="flex items-start gap-2.5 rounded-lg p-3 bg-secondary/30" data-testid={`go-live-item-${it.id}`}>
                <I className="w-4 h-4 mt-0.5 shrink-0" style={{ color: `hsl(${S.c})` }} />
                <div className="min-w-0">
                  <div className="text-sm font-medium flex items-center gap-2">{it.label}
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-full shrink-0" style={{ background: `hsl(${S.c} / 0.15)`, color: `hsl(${S.c})` }}>{S.label}</span>
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{it.detail}</div>
                  {it.status !== "pass" && it.fix && (
                    <button data-testid={`go-live-fix-${it.id}`} onClick={() => fixItem(it)} disabled={fixing === it.id}
                      className="text-[11px] mt-1 inline-flex items-center gap-1 font-medium underline decoration-dotted underline-offset-2 hover:no-underline disabled:opacity-60" style={{ color: `hsl(${S.c})` }}>
                      {fixing === it.id ? "Fixing…" : `Fix → ${it.fix}`}
                    </button>
                  )}
                </div>
              </div>
            ); })}
          </div>
          {d.trend && d.trend.length >= 2 ? (
            <div className="mt-4 pt-4 border-t border-border" data-testid="go-live-history">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Readiness history</h3>
                <span className="text-[10px] text-muted-foreground">{d.trend.length} day(s) · target 100%</span>
              </div>
              <ResponsiveContainer width="100%" height={120}>
                <AreaChart data={d.trend} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
                  <defs><linearGradient id="glGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={`hsl(${tone})`} stopOpacity={0.35} /><stop offset="100%" stopColor={`hsl(${tone})`} stopOpacity={0} /></linearGradient></defs>
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} tickFormatter={(v) => (v ? v.slice(5) : v)} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} width={30} />
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} formatter={(v) => [`${v}%`, "Readiness"]} />
                  <ReferenceLine y={100} stroke="hsl(142 70% 45%)" strokeDasharray="3 3" />
                  <Area type="monotone" dataKey="score" stroke={`hsl(${tone})`} strokeWidth={2} fill="url(#glGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="mt-4 pt-4 border-t border-border text-[11px] text-muted-foreground" data-testid="go-live-history-empty">
              Readiness history builds one point per day — the trend chart appears once there are at least two days of checks. Today: {d.score}%.
            </div>
          )}
        </>
      )}
      <Dialog open={webhookOpen} onOpenChange={setWebhookOpen}>
        <DialogContent data-testid="webhook-dialog">
          <DialogHeader>
            <DialogTitle>Wire the agent-runtime enforcement webhook</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">Register the signed HTTPS endpoint your agent runtime listens on. Obserra dispatches Kill / Suspend / Resume events (HMAC-SHA256 signed) here. Once saved, this check turns green and readiness reaches 100%.</p>
            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Webhook URL</label>
              <Input data-testid="webhook-url-input" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://runtime.example.com/obserra/enforce" className="mt-1" />
            </div>
            <div>
              <label className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Signing secret <span className="opacity-60">(optional)</span></label>
              <Input data-testid="webhook-secret-input" type="password" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} placeholder="Signs the X-Obserra-Signature header" className="mt-1" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => navigate("/app/settings")}>Open full settings</Button>
            <Button size="sm" data-testid="webhook-save" onClick={saveWebhook} disabled={savingWebhook}>{savingWebhook ? "Registering…" : "Register & re-check"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function ConnectorHealth() {
  const [d, setD] = useState(null);
  const [probing, setProbing] = useState(false);
  const load = useCallback(async () => { const { data } = await api.get("/sap/systems"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  const reprobe = async () => {
    setProbing(true);
    try {
      const { data } = await api.post("/sap/systems/reprobe");
      setD(data);
      const h = data.connector_health || {};
      toast.success(`Re-probed ${data.connectors.length} connector(s)`, { description: `${h.healthy || 0} healthy · ${h.stale || 0} stale · ${h.degraded || 0} degraded` });
    } catch (e) { toast.error("Re-probe failed"); }
    setProbing(false);
  };
  if (!d) return <Spinner />;
  const connected = d.connectors.filter((c) => c.status === "connected").length;
  const health = d.connector_health || { healthy: 0, stale: 0, degraded: 0 };

  return (
    <div className="space-y-6" data-testid="systems-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="systems-title">Connector Health</h1>
          <p className="text-sm text-muted-foreground mt-1">SAP landscape, source connectors and data freshness. Live API connection is enabled by supplying per-connector credentials; the current access model was ingested as a discovered snapshot with provenance.</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button size="sm" className="gap-1.5" data-testid="sys-reprobe" onClick={reprobe} disabled={probing}>
            <RefreshCw className={`w-3.5 h-3.5 ${probing ? "animate-spin" : ""}`} />{probing ? "Re-probing…" : "Re-probe all connectors"}
          </Button>
          {d.last_probe_at && <span className="text-[10px] font-mono text-muted-foreground" data-testid="sys-last-probe">Last probe {fmtDT(d.last_probe_at)}</span>}
        </div>
      </div>

      <GoLiveChecklist />

      <AIInsight dashboard="Connector Health" focus="connector coverage, credential readiness and data freshness" accent="190 90% 50%" auto slug="sap-systems" />

      <div className="bg-card fact-border rounded-xl p-5" data-testid="all-connectors-panel">
        <h2 className="font-head font-bold text-lg mb-1">Enterprise Connectors — SAP, AI &amp; Obserra</h2>
        <p className="text-xs text-muted-foreground mb-4">Every source system across the platform, live with real connectivity health. Connect any SAP, AI, identity, SIEM, ITSM or collaboration system to feed Control Intelligence and Cyber Crisis Commander.</p>
        <ConnectorCatalog />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="SAP systems" value={d.systems.length} accent="210 92% 62%" icon={Server} testid="sys-count" />
        <StatCard label="Connectors" value={d.connectors.length} sub={`${connected} ingesting`} accent="190 90% 50%" icon={Plug} testid="sys-connectors" />
        <StatCard label="Production systems" value={d.systems.filter((s) => s.prod).length} accent="0 84% 60%" icon={Server} testid="sys-prod" />
        <StatCard label="Legal entities" value={d.legal_entities.length} accent="266 85% 66%" icon={Server} testid="sys-le" />
      </div>

      <div className="grid grid-cols-3 gap-4" data-testid="sys-health-summary">
        {["healthy", "stale", "degraded"].map((k) => { const H = HEALTH[k]; const I = H.Icon; return (
          <div key={k} className="bg-card fact-border rounded-xl p-4 flex items-center gap-3" data-testid={`sys-health-${k}`}>
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: `hsl(${H.c} / 0.12)` }}><I className="w-5 h-5" style={{ color: `hsl(${H.c})` }} /></div>
            <div><div className="font-head font-black text-2xl" style={{ color: `hsl(${H.c})` }}>{health[k] || 0}</div><div className="text-[11px] text-muted-foreground">{H.label} connector(s)</div></div>
          </div>
        ); })}
      </div>

      <div className="bg-card fact-border rounded-xl p-5" data-testid="sys-systems-panel">
        <h2 className="font-head font-bold text-lg mb-3">SAP Landscape</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-2">System</th><th className="p-2">Product</th><th className="p-2">Client</th><th className="p-2">Tier</th><th className="p-2">Accounts</th><th className="p-2">Dialog</th><th className="p-2">Technical</th></tr></thead>
            <tbody>
              {d.systems.map((s) => (
                <tr key={s.ref} className="border-b border-border/50" data-testid={`sys-row-${s.ref}`}>
                  <td className="p-2 font-mono font-semibold">{s.ref}</td><td className="p-2 text-xs">{s.name}</td><td className="p-2 text-xs">{s.client}</td>
                  <td className="p-2"><span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${s.prod ? "bg-crit/15 text-crit" : "bg-secondary text-muted-foreground"}`}>{s.tier}</span></td>
                  <td className="p-2 text-xs">{s.accounts}</td><td className="p-2 text-xs">{s.dialog_users}</td><td className="p-2 text-xs">{s.technical_users}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="sys-connectors-panel">
        {d.connectors.map((c) => (
          <div key={c.id} className="bg-card fact-border rounded-xl p-4" data-testid={`sys-connector-${c.id}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2"><Plug className="w-4 h-4 text-primary" /><span className="font-medium">{c.name}</span></div>
              {(() => { const H = HEALTH[c.health] || HEALTH.healthy; const I = H.Icon; return (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1" style={{ background: `hsl(${H.c} / 0.15)`, color: `hsl(${H.c})` }} data-testid={`sys-conn-health-${c.id}`}><I className="w-3 h-3" />{H.label}</span>
              ); })()}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
              <div>Category<div className="text-foreground">{c.category}</div></div>
              <div>Mode<div className="text-foreground">{c.mode}</div></div>
              <div>Records<div className="text-foreground font-mono">{c.records}</div></div>
              <div>Data freshness<div style={{ color: `hsl(${(HEALTH[c.health] || HEALTH.healthy).c})` }} className="font-mono">{fmtAge(c.age_min)}</div></div>
              <div className="col-span-2 flex items-center gap-1"><Clock className="w-3 h-3" /> Last sync {fmtDT(c.last_sync)} · Live API: {c.auth_ready ? "ready" : "pending credentials"}</div>
              {c.drift_note && <div className="col-span-2 flex items-start gap-1 text-[10px]" style={{ color: c.health === "healthy" ? undefined : `hsl(${(HEALTH[c.health] || HEALTH.healthy).c})` }} data-testid={`sys-conn-drift-${c.id}`}><Activity className="w-3 h-3 mt-0.5 shrink-0" /> {c.drift_note}</div>}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-card fact-border rounded-xl p-5" data-testid="sys-authority-panel">
        <h2 className="font-head font-bold text-lg mb-3">HR Authority Matrix (ADP / IZ8)</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
          {d.legal_entities.map((le) => (
            <div key={le.code} className="flex items-center justify-between text-sm p-2.5 rounded-lg bg-secondary/30">
              <span>{le.name} <span className="font-mono text-[10px] text-muted-foreground">· {le.code} · {le.country}</span></span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-ai/15 text-ai">{le.hr} authoritative</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
