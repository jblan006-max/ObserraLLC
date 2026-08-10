import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Panel } from "@/components/agentic-ai/shared";
import { useDeepDive } from "@/context/DeepDiveContext";
import { drillDeepDive } from "@/lib/agenticDeepDive";
import { toast } from "sonner";
import { Gauge, ShieldCheck, XCircle, Timer, Flame, RefreshCw, Loader2, TrendingUp, FileDown, AlertTriangle, Globe, MapPin, Monitor, User } from "lucide-react";
import { BarChart, Bar, LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";
import { WorldMapThumb } from "@/components/agentic-ai/WorldMapThumb";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const fmtDTT = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const rateColor = (r) => (r == null ? "hsl(var(--muted-foreground))" : r >= 90 ? "hsl(142 70% 45%)" : r >= 60 ? "hsl(35 90% 55%)" : "hsl(0 84% 60%)");
const TT = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 };

function Tile({ label, value, sub, iconClass, Icon }) {
  return (
    <div className="rounded-xl border border-border bg-card/60 p-4" data-testid={`ca-tile-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
        {Icon && <Icon className={`w-3.5 h-3.5 ${iconClass}`} />} {label}
      </div>
      <div className="font-head font-black text-3xl mt-1">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

function AccessGlobe() {
  const [g, setG] = useState(null);
  const [busy, setBusy] = useState(true);
  const [sel, setSel] = useState(null);
  const [expBusy, setExpBusy] = useState(false);
  const [filter, setFilter] = useState("all");
  const [days, setDays] = useState(null);
  const loadG = () => {
    setBusy(true);
    api.get("/agents/runtime/access-globe", { params: days ? { days } : {} }).then(({ data }) => setG(data)).catch(() => {}).finally(() => setBusy(false));
  };
  useEffect(() => { loadG(); }, [days]);
  const exportMap = async () => {
    setExpBusy(true);
    try {
      const res = await api.get("/agents/runtime/access-globe.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = "obserra-board-access-map.pdf"; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not export the access map"); }
    setExpBusy(false);
  };
  const points = g?.points || [];
  const shown = points
    .filter((p) => (filter === "downloads" ? p.kind === "download" : filter === "suspicious" ? p.suspicious : true))
    .map((p) => ({ ...p, anomaly: p.anomaly || p.suspicious }));
  return (
    <Panel title="Evidence access globe" subtitle="Every place your shared detail-cards and auditor rooms have been opened or downloaded — geo-located live from the chain-of-custody ledger. Click any pin to see who, on what device, and which card or room."
      testid="ca-access-globe"
      actions={
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-md border border-border overflow-hidden" data-testid="ca-globe-range">
            {[[null, "All"], [7, "7d"], [30, "30d"], [90, "90d"]].map(([v, lbl]) => (
              <button key={lbl} data-testid={`ca-globe-range-${lbl.toLowerCase()}`} onClick={() => setDays(v)} className={`px-2.5 py-2 text-xs font-head font-bold transition-colors ${days === v ? "bg-ai/15 text-ai" : "text-muted-foreground hover:bg-secondary"}`}>{lbl}</button>
            ))}
          </div>
          <button data-testid="ca-globe-export" onClick={exportMap} disabled={expBusy || points.length === 0} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors disabled:opacity-50">
            {expBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />} Board Access Map
          </button>
          <button data-testid="ca-globe-refresh" onClick={loadG} disabled={busy} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-head font-bold hover:bg-secondary transition-colors disabled:opacity-50">
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />} Refresh
          </button>
        </div>
      }>
      {busy && !g ? (
        <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-ai" /></div>
      ) : points.length === 0 ? (
        <div className="py-8 text-center" data-testid="ca-globe-empty">
          <Globe className="w-9 h-9 text-muted-foreground mx-auto" />
          <p className="text-sm text-muted-foreground mt-3 max-w-md mx-auto">No geo-located evidence access yet. Once an auditor opens a shared card or evidence room from a public network, it plots here — with location, device and anomaly context.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Tile label="Total accesses" value={g.total} sub={`${g.opens} opens · ${g.downloads} downloads`} Icon={Globe} iconClass="text-ai" />
            <Tile label="Located" value={g.located} sub="geo-pinned events" Icon={ShieldCheck} iconClass="text-low" />
            <Tile label="Countries" value={(g.countries || []).length} sub={(g.countries || []).slice(0, 3).join(", ") || "—"} Icon={Gauge} iconClass="text-high" />
            <Tile label="Sources" value={`${g.cards + g.rooms}`} sub={`${g.cards} card · ${g.rooms} room`} Icon={Flame} iconClass="text-crit" />
          </div>
          <div className="flex flex-wrap items-center gap-2" data-testid="ca-globe-filters">
            {[["all", "All", points.length], ["downloads", "Downloads", g.downloads || 0], ["suspicious", "Suspicious", g.suspicious || 0]].map(([k, lbl, n]) => (
              <button key={k} data-testid={`ca-globe-filter-${k}`} onClick={() => setFilter(k)} className={`px-3 py-1.5 rounded-full text-xs font-head font-bold border transition-colors ${filter === k ? "bg-ai/15 border-ai/50 text-ai" : "border-border text-muted-foreground hover:bg-secondary"}`}>{lbl} <span className="opacity-60">({n})</span></button>
            ))}
          </div>
          <div className="flex justify-center items-center rounded-xl border border-border bg-[#0a1120] p-3 min-h-[200px]">
            {shown.length === 0 ? (
              <p className="text-sm text-muted-foreground py-10" data-testid="ca-globe-filter-empty">No {filter} accesses to plot.</p>
            ) : (
              <WorldMapThumb points={shown} width={720} height={360} onClusterClick={(c) => setSel(c)} />
            )}
          </div>
          <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: "hsl(142 70% 50%)" }} /> open</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: "hsl(190 90% 55%)" }} /> download</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: "hsl(0 84% 62%)" }} /> anomaly / outside trusted zones</span>
            <span className="ml-auto">Click any pin to inspect its access events.</span>
          </div>
        </div>
      )}
      <Dialog open={!!sel} onOpenChange={(o) => { if (!o) setSel(null); }}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto" data-testid="ca-globe-drilldown">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><MapPin className="w-4 h-4 text-ai" /> {sel?.label || "Access location"}</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">{(sel?.points || []).length} access event(s) recorded at this location.</p>
          <div className="space-y-2 mt-2">
            {(sel?.points || []).map((p, i) => (
              <div key={i} data-testid={`globe-access-${i}`} className="rounded-lg border border-border bg-secondary/20 p-3 text-xs">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-2 py-0.5 rounded-full font-mono text-[10px] ${p.kind === "download" ? "bg-ai/10 text-ai" : "bg-low/10 text-low"}`}>{p.kind}</span>
                  {p.anomaly && <span className="px-2 py-0.5 rounded-full font-mono text-[10px] bg-crit/10 text-crit">anomaly</span>}
                  <span className="font-mono text-[10px] text-muted-foreground uppercase">{p.source}</span>
                  <span className="ml-auto font-mono text-[10px] text-muted-foreground">{fmtDTT(p.at)}</span>
                </div>
                <div className="font-head font-bold mt-1.5">{p.title || "—"}</div>
                <div className="flex items-center gap-3 mt-1 text-muted-foreground flex-wrap">
                  <span className="inline-flex items-center gap-1"><User className="w-3 h-3" /> {p.who || "—"}</span>
                  <span className="inline-flex items-center gap-1"><Monitor className="w-3 h-3" /> {p.device || "—"}</span>
                  <span className="font-mono">{p.ip || "—"}</span>
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </Panel>
  );
}

export default function ControlAssurance() {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);
  const { openDeepDive } = useDeepDive();
  const load = () => {
    setLoading(true);
    api.get("/agents/runtime/control-assurance").then(({ data }) => setD(data)).catch(() => toast.error("Could not load Control Assurance")).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const [exporting, setExporting] = useState(false);
  const exportReport = async () => {
    setExporting(true);
    try {
      const res = await api.get("/agents/runtime/control-assurance-report.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = "obserra-control-assurance.pdf"; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not export report"); }
    setExporting(false);
  };
  const [sla, setSla] = useState({ enabled: false, min: 90 });
  const [slaBusy, setSlaBusy] = useState(false);
  useEffect(() => { if (d?.sla) setSla({ enabled: d.sla.enabled, min: d.sla.min }); }, [d]);
  const saveSla = async () => {
    setSlaBusy(true);
    try { await api.put("/agents/runtime/governance-settings", { control_assurance_sla_enabled: sla.enabled, control_assurance_sla_min: Number(sla.min) || 90 }); toast.success("SLA saved"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
    setSlaBusy(false);
  };

  const monthly = d?.monthly || [];
  const passRate = d?.pass_rate;

  return (
    <div className="space-y-6" data-testid="control-assurance-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Gauge className="w-6 h-6 text-ai" />
            <h1 className="font-head font-black text-2xl sm:text-3xl">Control Assurance</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">Kill-switch reliability over time — your monthly proof-of-control pass rate and enforcement response times, computed live from every fire-drill. Prove to the board that your agent kill-switches actually fire.</p>
        </div>
        <div className="flex items-center gap-2">
          <button data-testid="ca-export" onClick={exportReport} disabled={exporting || !d || d.total === 0} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors disabled:opacity-50">
            {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />} Export report
          </button>
          <button data-testid="ca-refresh" onClick={load} disabled={loading} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-head font-bold hover:bg-secondary transition-colors disabled:opacity-50">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />} Refresh
          </button>
        </div>
      </div>

      <AccessGlobe />

      {loading && !d ? (
        <div className="py-24 flex justify-center"><Loader2 className="w-7 h-7 animate-spin text-ai" /></div>
      ) : !d || d.total === 0 ? (
        <Panel title="No fire-drills yet" subtitle="Run a Kill Replay Drill to start building your kill-switch reliability record." testid="ca-empty">
          <div className="py-8 text-center">
            <Flame className="w-10 h-10 text-muted-foreground mx-auto" />
            <p className="text-sm text-muted-foreground mt-3 max-w-md mx-auto">Once you run (or schedule) a Suspend → Resume fire-drill, its timed, signed proof-of-control receipt is recorded here and this page charts your monthly pass rate over time.</p>
            <Link to="/app/agentic-ai-security" data-testid="ca-go-drill" className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold hover:opacity-90 transition-opacity">
              <Flame className="w-3.5 h-3.5" /> Go run a fire-drill
            </Link>
          </div>
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Tile label="Proof-of-control rate" value={passRate == null ? "—" : `${passRate}%`} sub={`${d.controlled}/${d.total} drills confirmed`} Icon={ShieldCheck} iconClass="text-low" />
            <Tile label="Confirmed streak" value={d.streak} sub="consecutive controlled drills" Icon={TrendingUp} iconClass="text-ai" />
            <Tile label="Avg suspend" value={d.avg_suspend_ms == null ? "—" : `${d.avg_suspend_ms}ms`} sub={d.avg_resume_ms == null ? "" : `resume ${d.avg_resume_ms}ms`} Icon={Timer} iconClass="text-high" />
            <Tile label="Total drills" value={d.total} sub={`${d.scheduled_count} scheduled · last ${fmtDTT(d.last_at)}`} Icon={Flame} iconClass="text-crit" />
          </div>

          {d.sla?.breached && (
            <div data-testid="ca-sla-breach" className="rounded-lg border border-crit/40 bg-crit/10 p-3 flex items-center gap-2 text-sm text-crit">
              <AlertTriangle className="w-4 h-4 shrink-0" /> This month's pass rate ({d.sla.current_rate}%) is below your {d.sla.min}% SLA.
            </div>
          )}
          <Panel title="Pass-rate SLA" subtitle="Get alerted (chat + email) the moment a month's kill-switch pass rate dips below your minimum." testid="ca-sla">
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex items-center gap-2 cursor-pointer"><input data-testid="ca-sla-enabled" type="checkbox" checked={sla.enabled} onChange={(e) => setSla({ ...sla, enabled: e.target.checked })} className="w-4 h-4 accent-ai" /><span className="text-sm">Enable SLA alerts</span></label>
              <label className="block"><span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Minimum pass rate (%)</span><input data-testid="ca-sla-min" type="number" min={1} max={100} value={sla.min} onChange={(e) => setSla({ ...sla, min: e.target.value })} className="mt-1.5 w-28 bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>
              <button data-testid="ca-sla-save" onClick={saveSla} disabled={slaBusy} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{slaBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />} Save SLA</button>
            </div>
          </Panel>

          <Panel title="Monthly proof-of-control pass rate" subtitle="Percentage of kill-switch fire-drills that confirmed control, per month." testid="ca-passrate">
            <div style={{ height: 260 }} data-testid="ca-passrate-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthly} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TT} formatter={(v, n, p) => [v == null ? "no drills" : `${v}% (${p.payload.controlled}/${p.payload.drills})`, "Pass rate"]} cursor={{ fill: "hsl(var(--secondary) / 0.4)" }} />
                  <Bar dataKey="pass_rate" radius={[6, 6, 0, 0]} maxBarSize={54}>
                    {monthly.map((m, i) => <Cell key={i} fill={rateColor(m.pass_rate)} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Enforcement response times" subtitle="Average time to dispatch a Suspend and a Resume to the connected runtime, per month (ms)." testid="ca-response">
            <div style={{ height: 240 }} data-testid="ca-response-chart">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={monthly} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TT} formatter={(v, n) => [v == null ? "—" : `${v}ms`, n]} />
                  <Line type="monotone" dataKey="avg_suspend_ms" name="Suspend" stroke="hsl(35 90% 55%)" strokeWidth={2.2} dot={{ r: 2 }} connectNulls />
                  <Line type="monotone" dataKey="avg_resume_ms" name="Resume" stroke="hsl(190 80% 50%)" strokeWidth={2.2} dot={{ r: 2 }} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Recent fire-drills" subtitle="The latest kill-switch replay drills and their signed receipts." testid="ca-recent">
            <div className="space-y-2" data-testid="ca-recent-list">
              {(d.recent || []).map((r, i) => (
                <button key={i} data-testid={`ca-recent-${i}`} onClick={() => openDeepDive(drillDeepDive(r))}
                  className="w-full text-left flex items-center gap-2 flex-wrap rounded-lg border border-border bg-secondary/10 px-3 py-2.5 text-xs hover:bg-secondary/30 transition-colors">
                  {r.controlled ? <ShieldCheck className="w-4 h-4 text-low shrink-0" /> : <XCircle className="w-4 h-4 text-crit shrink-0" />}
                  <span className="font-head font-bold">{r.agent_name}</span>
                  <span className="font-mono text-muted-foreground">{r.agent_ref}</span>
                  {r.scheduled && <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-ai/10 text-ai">scheduled</span>}
                  <span className="text-[10px] font-mono text-muted-foreground">suspend {r.suspend_ms}ms · resume {r.resume_ms}ms</span>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${r.signed ? "bg-low/10 text-low" : "bg-secondary/60 text-muted-foreground"}`}>{r.signed ? "signed" : "unsigned"}</span>
                  <span className="ml-auto font-mono text-[10px] text-muted-foreground">{fmtDTT(r.at)}</span>
                </button>
              ))}
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
