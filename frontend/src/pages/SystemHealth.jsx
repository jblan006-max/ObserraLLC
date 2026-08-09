import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Spinner } from "@/components/dash";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Activity, Database, Plug, Clock, ServerCog, ArrowUpCircle, DownloadCloud, Loader2,
  HardDriveDownload, RotateCcw, ShieldCheck, AlertTriangle, RefreshCw, Building2, Terminal, CheckCircle2,
  Save, Mail, MessageSquare, Slack, Zap, Archive, Lock, Send,
} from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const fmtBytes = (b) => (b == null ? "—" : b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`);
const DOT_COLOR = { ok: "142 70% 45%", degraded: "35 90% 55%", down: "0 84% 60%" };
const RANGES = [{ label: "24h", h: 24 }, { label: "7d", h: 168 }, { label: "30d", h: 720 }];

function HealthTile({ label, value, sub, accent, icon: Icon, ok, testid }) {
  return (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-4 flex items-start gap-3" style={{ borderTop: `2px solid hsl(${accent} / 0.65)` }}>
      <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: `hsl(${accent} / 0.12)` }}>
        <Icon className="w-5 h-5" style={{ color: `hsl(${accent})` }} strokeWidth={1.6} />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          {label}
          {ok !== undefined && <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-low" : "bg-crit"}`} />}
        </div>
        <div className="font-head font-black text-2xl tracking-tight mt-0.5" style={{ color: `hsl(${accent})` }}>{value}</div>
        {sub && <div className="text-[11px] text-muted-foreground mt-0.5 leading-tight truncate">{sub}</div>}
      </div>
    </div>
  );
}

function bucketize(points, hours) {
  const now = Date.now();
  const start = now - hours * 3600 * 1000;
  const cols = hours <= 24 ? 48 : hours <= 168 ? 84 : 60;
  const width = (now - start) / cols;
  const rank = { ok: 0, degraded: 1, down: 2 };
  const buckets = Array.from({ length: cols }, (_, i) => ({ status: null, count: 0, start: start + i * width }));
  (points || []).forEach((p) => {
    const t = new Date(p.at).getTime();
    if (t < start || t > now) return;
    const idx = Math.min(cols - 1, Math.max(0, Math.floor((t - start) / width)));
    const b = buckets[idx];
    b.count++;
    if (b.status === null || rank[p.status] > rank[b.status]) b.status = p.status;
  });
  return buckets;
}

function UptimeStrip({ points, range, setRange }) {
  const pts = points || [];
  const upPct = pts.length ? Math.round((pts.filter((p) => p.healthy).length / pts.length) * 100) : null;
  const buckets = bucketize(pts, range);
  return (
    <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-uptime-panel">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          <h2 className="font-head font-bold text-lg">Uptime</h2>
          {upPct != null && <span className="text-xs font-mono text-muted-foreground" data-testid="sh-uptime-pct">{upPct}% healthy · {pts.length} samples</span>}
        </div>
        <div className="flex items-center gap-1 bg-secondary/50 rounded-lg p-0.5" data-testid="sh-uptime-range">
          {RANGES.map((r) => (
            <button key={r.h} data-testid={`sh-range-${r.label}`} onClick={() => setRange(r.h)}
              className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${range === r.h ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
              {r.label}
            </button>
          ))}
        </div>
      </div>
      {pts.length ? (
        <div className="flex items-end gap-[2px] flex-wrap" data-testid="sh-uptime-dots">
          {buckets.map((b, i) => (
            <span key={i} title={`${fmtDT(new Date(b.start).toISOString())} — ${b.status || "no data"}`}
              className="w-2 h-6 rounded-sm transition-transform hover:scale-125"
              style={{ background: b.status ? `hsl(${DOT_COLOR[b.status]})` : "hsl(var(--muted-foreground) / 0.15)" }}
              data-testid={`sh-uptime-dot-${i}`} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground" data-testid="sh-uptime-empty">Collecting health samples — dots appear as the platform records status over time (auto every ~12 min and nightly).</p>
      )}
    </div>
  );
}

export default function SystemHealth() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [health, setHealth] = useState(null);
  const [detail, setDetail] = useState(null);
  const [ver, setVer] = useState(null);
  const [backups, setBackups] = useState([]);
  const [upgrade, setUpgrade] = useState(null);
  const [history, setHistory] = useState([]);
  const [range, setRange] = useState(24);
  const [bcfg, setBcfg] = useState(null);
  const [acfg, setAcfg] = useState(null);
  const [encEnabled, setEncEnabled] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [savingCfg, setSavingCfg] = useState(false);
  const [savingAlerts, setSavingAlerts] = useState(false);
  const [testingAlert, setTestingAlert] = useState(false);
  const [reprobing, setReprobing] = useState(null);
  const logRef = useRef(null);
  const [restoreTarget, setRestoreTarget] = useState(null);
  const [confirmText, setConfirmText] = useState("");
  const [restorePass, setRestorePass] = useState("");
  const [restoring, setRestoring] = useState(false);
  const [encModal, setEncModal] = useState(null); // 'enable' | 'disable'
  const [encPass, setEncPass] = useState("");
  const [encBusy, setEncBusy] = useState(false);

  const loadHealth = useCallback(async () => {
    try { const { data } = await api.get("/health"); setHealth(data); } catch { setHealth((h) => h || { status: "degraded", checks: {} }); }
  }, []);
  const loadDetail = useCallback(async () => {
    try { const { data } = await api.get("/deploy/health-detail"); setDetail(data); } catch { /* ignore */ }
  }, []);
  const loadVer = useCallback(async () => {
    try { const { data } = await api.get("/deploy/version"); setVer(data); } catch { /* ignore */ }
  }, []);
  const loadHistory = useCallback(async () => {
    try { const { data } = await api.get(`/deploy/health-history?hours=${range}`); setHistory(data.points || []); } catch { /* ignore */ }
  }, [range]);
  const loadBackups = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/backups"); setBackups(data.backups || []); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadUpgrade = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/upgrade/status"); setUpgrade(data); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadCfg = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const [b, a, e] = await Promise.all([api.get("/deploy/backup-config"), api.get("/deploy/health-config"), api.get("/deploy/backup-encryption")]);
      setBcfg(b.data); setAcfg(a.data.alerts); setEncEnabled(!!e.data.enabled);
    } catch { /* ignore */ }
  }, [isAdmin]);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([loadHealth(), loadDetail(), loadVer(), loadHistory(), loadBackups(), loadUpgrade(), loadCfg()]);
    setRefreshing(false);
  }, [loadHealth, loadDetail, loadVer, loadHistory, loadBackups, loadUpgrade, loadCfg]);

  useEffect(() => { refreshAll(); }, [refreshAll]);

  useEffect(() => {
    const t = setInterval(() => { loadHealth(); loadDetail(); }, 20000);
    return () => clearInterval(t);
  }, [loadHealth, loadDetail]);

  useEffect(() => {
    const running = upgrade && (upgrade.state === "running" || upgrade.state === "starting");
    if (!running) return;
    const t = setInterval(loadUpgrade, 2500);
    return () => clearInterval(t);
  }, [upgrade, loadUpgrade]);

  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [upgrade]);

  const backupNow = async () => {
    setBackingUp(true);
    try {
      const { data } = await api.post("/deploy/backup");
      toast.success(`Backup created${data.encrypted ? " (encrypted)" : ""}`, { description: `${data.docs} document(s) across ${data.collections} collection(s) · ${fmtBytes(data.size)}` });
      await loadBackups();
    } catch (e) { toast.error(e.response?.data?.detail || "Backup failed"); }
    setBackingUp(false);
  };

  const saveBackupCfg = async () => {
    setSavingCfg(true);
    try { const { data } = await api.put("/deploy/backup-config", bcfg); setBcfg(data); toast.success("Backup schedule saved"); }
    catch (e) { toast.error(e.response?.data?.detail || "Couldn't save schedule"); }
    setSavingCfg(false);
  };

  const submitEnc = async () => {
    setEncBusy(true);
    try {
      if (encModal === "enable") {
        await api.put("/deploy/backup-encryption", { passphrase: encPass });
        toast.success("Snapshot encryption enabled", { description: "New backups are encrypted at rest. Keep this passphrase safe — it's required to restore." });
      } else {
        await api.post("/deploy/backup-encryption/disable", { passphrase: encPass });
        toast.success("Snapshot encryption disabled");
      }
      setEncModal(null); setEncPass("");
      await loadCfg();
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't update encryption"); }
    setEncBusy(false);
  };

  const toggleAlert = (event, channel) => setAcfg((prev) => ({ ...prev, [event]: { ...prev[event], [channel]: !prev[event][channel] } }));
  const saveAlertCfg = async () => {
    setSavingAlerts(true);
    try { const { data } = await api.put("/deploy/health-config", acfg); setAcfg(data.alerts); toast.success("Alert routing saved"); }
    catch (e) { toast.error(e.response?.data?.detail || "Couldn't save routing"); }
    setSavingAlerts(false);
  };
  const testAlert = async () => {
    setTestingAlert(true);
    try {
      const { data } = await api.post("/deploy/health-alert-test");
      const parts = [];
      if (data.slack_configured) parts.push("Slack");
      if (data.teams_configured) parts.push("Teams");
      parts.push("Email (admins/execs)");
      const noChat = !data.slack_configured && !data.teams_configured;
      toast.success("Test alert dispatched", { description: `Attempted: ${parts.join(", ")}.${noChat ? " Add Slack/Teams webhooks in Settings to page chat channels." : " Check those channels now."}` });
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't send test alert"); }
    setTestingAlert(false);
  };

  const reprobe = async (cid) => {
    setReprobing(cid);
    try {
      const { data } = await api.post(`/connectors/${cid}/test`);
      if (data.state === "connected") toast.success(`${data.id || cid} reconnected`);
      else toast(`${cid}: ${data.state}`, { description: data.detail });
      await Promise.all([loadHealth(), loadDetail()]);
    } catch { toast.error("Re-probe failed"); }
    setReprobing(null);
  };

  const openRestore = (b) => { setRestoreTarget(b); setConfirmText(""); setRestorePass(""); };
  const doRestore = async () => {
    if (confirmText.trim().toUpperCase() !== "RESTORE" || !restoreTarget) return;
    if (restoreTarget.encrypted && !restorePass) return;
    setRestoring(true);
    try {
      const body = { file: restoreTarget.file, confirm: "RESTORE" };
      if (restoreTarget.encrypted) body.passphrase = restorePass;
      const { data } = await api.post("/deploy/restore", body);
      toast.success("Restore complete", { description: `${data.restored_docs} document(s) restored · current data was snapshotted to ${data.pre_restore_backup || "a pre-restore backup"}.` });
      setRestoreTarget(null);
      await Promise.all([loadHealth(), loadDetail(), loadBackups()]);
    } catch (e) { toast.error(e.response?.data?.detail || "Restore failed"); }
    setRestoring(false);
  };

  const download = async (file) => {
    try {
      const res = await api.get(`/deploy/backup/download?file=${encodeURIComponent(file)}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = file; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Download failed"); }
  };

  const doUpgrade = async () => {
    setUpgrading(true);
    try { await api.post("/deploy/upgrade"); toast.success("Upgrade started — pulling the latest images and restarting."); await loadUpgrade(); }
    catch (e) { toast.error(e.response?.data?.detail || "Automatic upgrade isn't enabled on this deployment."); }
    setUpgrading(false);
  };

  if (!health || !ver) return <Spinner />;

  const c = health.checks || {};
  const dbOk = c.db?.ok ?? health.db;
  const conn = c.connectors || {};
  const sched = c.scheduler || {};
  const svcOk = health.status === "ok";
  const upState = upgrade?.state || "idle";
  const upRunning = upState === "running" || upState === "starting";
  const degraded = detail?.degraded_detail || [];

  const ALERT_ROWS = [
    { key: "db", label: "Database", icon: Database },
    { key: "connector", label: "Connectors", icon: Plug },
    { key: "scheduler", label: "Scheduler", icon: Clock },
  ];
  const ALERT_COLS = [
    { key: "slack", label: "Slack", icon: Slack },
    { key: "teams", label: "Teams", icon: MessageSquare },
    { key: "email", label: "Email", icon: Mail },
  ];

  return (
    <div className="space-y-6" data-testid="system-health-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="system-health-title">System Health</h1>
          <p className="text-sm text-muted-foreground mt-1">Live platform vitals, uptime history, on-premise upgrades, encrypted backups and health-alert routing.</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-refresh" onClick={refreshAll} disabled={refreshing}>
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />{refreshing ? "Refreshing…" : "Refresh"}
          </Button>
          <span className="text-[10px] font-mono text-muted-foreground">Auto-refreshing every 20s</span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4" data-testid="sh-health-tiles">
        <HealthTile testid="sh-service" label="Service" value={svcOk ? "Healthy" : "Degraded"} sub={health.service} accent={svcOk ? "142 70% 45%" : "0 84% 60%"} icon={svcOk ? ShieldCheck : AlertTriangle} ok={svcOk} />
        <HealthTile testid="sh-db" label="Database" value={dbOk ? "Online" : "Down"} sub={c.db?.latency_ms != null ? `${c.db.latency_ms} ms ping` : "MongoDB"} accent="210 92% 62%" icon={Database} ok={dbOk} />
        <HealthTile testid="sh-connectors" label="Connectors" value={conn.total != null ? `${conn.connected}/${conn.total}` : "—"} sub="Connected / total" accent="190 90% 50%" icon={Plug} ok={conn.total ? conn.connected > 0 : undefined} />
        <HealthTile testid="sh-scheduler" label="Scheduler" value={sched.cron_configured ? "Armed" : "Off"} sub={sched.last_activity ? `Last activity ${fmtDT(sched.last_activity)}` : "Cron secret set"} accent="152 65% 45%" icon={Clock} ok={sched.cron_configured} />
        <HealthTile testid="sh-orgs" label="Organizations" value={c.organizations ?? "—"} sub="Tenants live" accent="266 85% 66%" icon={Building2} />
      </div>

      {degraded.length > 0 && (
        <div className="bg-card rounded-xl p-5 border border-crit/40" data-testid="sh-degraded-panel">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-crit" />
            <h2 className="font-head font-bold text-lg text-crit">Degraded connectors</h2>
            <span className="text-[11px] text-muted-foreground">Re-probe to attempt an immediate recovery</span>
          </div>
          <div className="space-y-2">
            {degraded.map((d) => (
              <div key={d.cid} className="flex flex-wrap items-center justify-between gap-2 bg-crit/5 rounded-lg px-3 py-2.5" data-testid={`sh-degraded-${d.cid}`}>
                <div className="min-w-0">
                  <div className="font-medium text-sm flex items-center gap-2">
                    {d.name}
                    <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-crit/15 text-crit">{d.state}</span>
                  </div>
                  <div className="text-[11px] text-muted-foreground truncate max-w-md">{d.detail || "No detail reported"}{d.checked_at ? ` · checked ${fmtDT(d.checked_at)}` : ""}</div>
                </div>
                <Button size="sm" variant="outline" className="gap-1.5 shrink-0" data-testid={`sh-reprobe-${d.cid}`} onClick={() => reprobe(d.cid)} disabled={reprobing === d.cid}>
                  {reprobing === d.cid ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />} Re-probe
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      <UptimeStrip points={history} range={range} setRange={setRange} />

      <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-version-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: "hsl(160 84% 45% / 0.12)" }}>
              <ServerCog className="w-5 h-5" style={{ color: "hsl(160 84% 45%)" }} />
            </div>
            <div>
              <h2 className="font-head font-bold text-lg flex items-center gap-2">
                Version <span className="font-mono text-sm px-2 py-0.5 rounded bg-secondary/60" data-testid="sh-version-current">v{ver.current}</span>
              </h2>
              {ver.update_available ? (
                <p className="text-sm text-ai flex items-center gap-1.5 mt-0.5" data-testid="sh-update-available"><ArrowUpCircle className="w-4 h-4" /> v{ver.latest} is available</p>
              ) : (
                <p className="text-sm text-muted-foreground flex items-center gap-1.5 mt-0.5" data-testid="sh-up-to-date"><CheckCircle2 className="w-4 h-4 text-low" /> You're on the latest release</p>
              )}
            </div>
          </div>
          {isAdmin && (
            <Button size="sm" className="gap-1.5" data-testid="sh-upgrade-btn" onClick={doUpgrade} disabled={upgrading || upRunning}>
              {upgrading || upRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <DownloadCloud className="w-4 h-4" />}
              {upRunning ? "Upgrading…" : "Pull latest & restart"}
            </Button>
          )}
        </div>
        {ver.notes && <p className="text-sm text-muted-foreground mt-3 border-t border-border/50 pt-3" data-testid="sh-version-notes">{ver.notes}</p>}

        {upgrade && upState !== "idle" && (
          <div className="mt-4 border-t border-border/50 pt-4" data-testid="sh-upgrade-progress">
            <div className="flex items-center gap-2 mb-2">
              <Terminal className="w-4 h-4 text-muted-foreground" />
              <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Upgrade progress</span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ml-1 ${upState === "done" ? "bg-low/15 text-low" : upState === "error" ? "bg-crit/15 text-crit" : "bg-ai/15 text-ai"}`} data-testid="sh-upgrade-state">
                {upgrade.stage || upState}
              </span>
              {upRunning && <Loader2 className="w-3.5 h-3.5 animate-spin text-ai" />}
            </div>
            <div ref={logRef} className="bg-background/70 rounded-lg border border-border p-3 max-h-56 overflow-y-auto font-mono text-[11px] leading-relaxed" data-testid="sh-upgrade-log">
              {(upgrade.lines || []).length ? (upgrade.lines || []).map((ln, i) => (
                <div key={i} className={ln.startsWith("$") ? "text-ai" : "text-muted-foreground"}>{ln}</div>
              )) : <div className="text-muted-foreground">Waiting for output…</div>}
            </div>
          </div>
        )}
      </div>

      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-backups-panel">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <HardDriveDownload className="w-4 h-4 text-primary" />
              <h2 className="font-head font-bold text-lg">Database Backups</h2>
            </div>
            <Button size="sm" className="gap-1.5" data-testid="sh-backup-now" onClick={backupNow} disabled={backingUp}>
              {backingUp ? <Loader2 className="w-4 h-4 animate-spin" /> : <HardDriveDownload className="w-4 h-4" />}{backingUp ? "Backing up…" : "Back up now"}
            </Button>
          </div>

          {bcfg && (
            <div className="flex flex-wrap items-end gap-4 mb-3 p-3 rounded-lg bg-secondary/30 border border-border/50" data-testid="sh-backup-schedule">
              <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                <input type="checkbox" data-testid="sh-schedule-enabled" checked={bcfg.enabled} onChange={(e) => setBcfg({ ...bcfg, enabled: e.target.checked })} className="w-4 h-4 accent-primary" />
                <span className="font-medium">Automatic backups</span>
              </label>
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Frequency</span>
                <select data-testid="sh-schedule-frequency" value={bcfg.frequency} disabled={!bcfg.enabled} onChange={(e) => setBcfg({ ...bcfg, frequency: e.target.value })}
                  className="bg-background rounded-md border border-border px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary disabled:opacity-50">
                  <option value="daily">Daily (nightly)</option>
                  <option value="weekly">Weekly</option>
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Snapshots to keep</span>
                <input type="number" min="1" max="90" data-testid="sh-schedule-keep" value={bcfg.keep} onChange={(e) => setBcfg({ ...bcfg, keep: Number(e.target.value) })}
                  className="bg-background rounded-md border border-border px-3 py-1.5 text-sm w-24 outline-none focus:ring-1 focus:ring-primary" />
              </div>
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-schedule-save" onClick={saveBackupCfg} disabled={savingCfg}>
                {savingCfg ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Save schedule
              </Button>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 mb-5 p-3 rounded-lg bg-secondary/30 border border-border/50" data-testid="sh-encryption-row">
            <Lock className={`w-4 h-4 ${encEnabled ? "text-low" : "text-muted-foreground"}`} />
            <span className="text-sm font-medium">Snapshot encryption</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${encEnabled ? "bg-low/15 text-low" : "bg-secondary text-muted-foreground"}`} data-testid="sh-encryption-status">
              {encEnabled ? "On — AES at rest" : "Off"}
            </span>
            <span className="text-[11px] text-muted-foreground flex-1 min-w-[180px]">Encrypts every snapshot at rest; a passphrase is required to restore.</span>
            {encEnabled ? (
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-encryption-disable" onClick={() => { setEncModal("disable"); setEncPass(""); }}>Disable</Button>
            ) : (
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-encryption-enable" onClick={() => { setEncModal("enable"); setEncPass(""); }}><Lock className="w-3.5 h-3.5" /> Enable encryption</Button>
            )}
          </div>

          {backups.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-2">Snapshot</th><th className="p-2">Organization</th><th className="p-2">Contents</th><th className="p-2">Size</th><th className="p-2">Created</th><th className="p-2 text-right">Actions</th></tr></thead>
                <tbody>
                  {backups.map((b) => (
                    <tr key={b.file} className="border-b border-border/50" data-testid={`sh-backup-row-${b.file}`}>
                      <td className="p-2 font-mono text-xs">
                        <div className="flex items-center gap-2">
                          {b.encrypted && <Lock className="w-3 h-3 text-low shrink-0" data-testid={`sh-backup-lock-${b.file}`} />}
                          <span className="truncate max-w-[175px]">{b.file}</span>
                          {b.tag && <span className={`shrink-0 text-[9px] font-mono px-1.5 py-0.5 rounded ${b.tag === "pre-restore" ? "bg-high/15 text-high" : b.tag === "nightly" ? "bg-ai/15 text-ai" : "bg-secondary text-muted-foreground"}`} data-testid={`sh-backup-tag-${b.file}`}>{b.tag}</span>}
                        </div>
                      </td>
                      <td className="p-2 text-xs" data-testid={`sh-backup-org-${b.file}`}>{b.org_name || "—"}</td>
                      <td className="p-2 text-xs text-muted-foreground font-mono" data-testid={`sh-backup-contents-${b.file}`}>{b.docs != null ? `${b.docs} docs · ${b.collections} cols` : "—"}</td>
                      <td className="p-2 font-mono text-xs">{fmtBytes(b.size)}</td>
                      <td className="p-2 text-xs text-muted-foreground">{fmtDT(b.created_at)}</td>
                      <td className="p-2">
                        <div className="flex items-center justify-end gap-1.5">
                          <button data-testid={`sh-backup-download-${b.file}`} onClick={() => download(b.file)} className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-secondary/60 transition-colors" title={`Download ${b.org_name || ""}${b.docs != null ? ` · ${b.docs} docs` : ""}${b.encrypted ? " (encrypted)" : ""}`}><DownloadCloud className="w-4 h-4" /></button>
                          <button data-testid={`sh-backup-restore-${b.file}`} onClick={() => openRestore(b)} className="p-1.5 rounded-md text-muted-foreground hover:text-high hover:bg-secondary/60 transition-colors" title="Restore"><RotateCcw className="w-4 h-4" /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-center gap-2 py-8 px-4 rounded-lg border border-dashed border-muted-foreground/25" data-testid="sh-backups-empty">
              <Archive className="w-6 h-6 text-muted-foreground/50" />
              <p className="text-xs text-muted-foreground max-w-xs">No backups yet — the scheduled job runs with the daily maintenance cron, or click "Back up now" to create one immediately.</p>
            </div>
          )}
        </div>
      )}

      {isAdmin && acfg && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-alert-routing-panel">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-primary" />
              <h2 className="font-head font-bold text-lg">Health Alert Routing</h2>
              <span className="text-[11px] text-muted-foreground">Choose where each degraded event pages</span>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-alerts-test" onClick={testAlert} disabled={testingAlert}>
                {testingAlert ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Send test alert
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-alerts-save" onClick={saveAlertCfg} disabled={savingAlerts}>
                {savingAlerts ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Save routing
              </Button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
                  <th className="p-2">Event</th>
                  {ALERT_COLS.map((col) => (
                    <th key={col.key} className="p-2 text-center"><span className="inline-flex items-center gap-1"><col.icon className="w-3.5 h-3.5" />{col.label}</span></th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ALERT_ROWS.map((row) => (
                  <tr key={row.key} className="border-b border-border/50" data-testid={`sh-alert-row-${row.key}`}>
                    <td className="p-2 font-medium"><span className="inline-flex items-center gap-2"><row.icon className="w-4 h-4 text-muted-foreground" />{row.label}</span></td>
                    {ALERT_COLS.map((col) => (
                      <td key={col.key} className="p-2 text-center">
                        <input type="checkbox" data-testid={`sh-alert-${row.key}-${col.key}`} checked={!!acfg[row.key]?.[col.key]} onChange={() => toggleAlert(row.key, col.key)} className="w-4 h-4 accent-primary cursor-pointer" />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-muted-foreground mt-3">Slack/Teams use this org's configured webhooks; email notifies admins &amp; executives. In-app notifications are always recorded.</p>
        </div>
      )}

      {/* Encryption modal */}
      {encModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="sh-encryption-modal" onClick={() => !encBusy && setEncModal(null)}>
          <div className="bg-card fact-border rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-2">
              <Lock className="w-5 h-5 text-primary" />
              <h3 className="font-head font-bold text-lg">{encModal === "enable" ? "Enable snapshot encryption" : "Disable snapshot encryption"}</h3>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              {encModal === "enable"
                ? "Set a passphrase. Every new backup will be encrypted at rest, and this passphrase will be required to restore. Store it somewhere safe — it cannot be recovered."
                : "Enter the current passphrase to turn off encryption for future backups."}
            </p>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Passphrase{encModal === "enable" ? " (min 8 characters)" : ""}</label>
            <input type="password" data-testid="sh-encryption-passphrase" autoFocus value={encPass} onChange={(e) => setEncPass(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") submitEnc(); }}
              className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary transition-shadow mb-4" placeholder="••••••••" />
            <div className="flex items-center justify-end gap-2">
              <button data-testid="sh-encryption-cancel" onClick={() => setEncModal(null)} disabled={encBusy} className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50">Cancel</button>
              <button data-testid="sh-encryption-submit" onClick={submitEnc} disabled={encBusy || (encModal === "enable" ? encPass.trim().length < 8 : !encPass)}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-40">
                {encBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}{encModal === "enable" ? "Enable" : "Disable"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Restore modal */}
      {restoreTarget && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="sh-restore-modal" onClick={() => !restoring && setRestoreTarget(null)}>
          <div className="bg-card fact-border rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-5 h-5 text-high" />
              <h3 className="font-head font-bold text-lg">Restore this snapshot?</h3>
            </div>
            <p className="text-sm text-muted-foreground mb-3">
              This replaces the current data for <b className="text-foreground">{restoreTarget.org_name || "this organization"}</b> with
              <span className="font-mono text-xs"> {restoreTarget.file}</span>
              {restoreTarget.docs != null && <> ({restoreTarget.docs} docs · {restoreTarget.collections} collections)</>}.
            </p>
            <div className="rounded-md border border-ai/30 bg-ai/5 px-3 py-2 text-xs text-ai mb-4 flex items-start gap-2" data-testid="sh-restore-autobackup-note">
              <HardDriveDownload className="w-4 h-4 mt-0.5 shrink-0" />
              <span>A <b>pre-restore backup</b> of the current data is taken automatically first, so you can always roll back.</span>
            </div>
            {restoreTarget.encrypted && (
              <div className="mb-4">
                <label className="block text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1.5"><Lock className="w-3.5 h-3.5 text-low" /> This backup is encrypted — enter its passphrase</label>
                <input type="password" data-testid="sh-restore-passphrase" value={restorePass} onChange={(e) => setRestorePass(e.target.value)}
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary transition-shadow" placeholder="Backup passphrase" />
              </div>
            )}
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Type <span className="font-mono text-foreground">RESTORE</span> to confirm</label>
            <input data-testid="sh-restore-confirm-input" autoFocus value={confirmText} onChange={(e) => setConfirmText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") doRestore(); }}
              className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-high transition-shadow mb-4" placeholder="RESTORE" />
            <div className="flex items-center justify-end gap-2">
              <button data-testid="sh-restore-cancel" onClick={() => setRestoreTarget(null)} disabled={restoring} className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50">Cancel</button>
              <button data-testid="sh-restore-confirm" onClick={doRestore} disabled={restoring || confirmText.trim().toUpperCase() !== "RESTORE" || (restoreTarget.encrypted && !restorePass)}
                className="px-4 py-2 rounded-md bg-high text-white font-head font-bold text-sm flex items-center gap-2 disabled:opacity-40">
                {restoring ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />} Restore now
              </button>
            </div>
          </div>
        </div>
      )}

      {!isAdmin && (
        <div className="bg-card fact-border rounded-xl p-5 text-sm text-muted-foreground" data-testid="sh-nonadmin-note">
          Upgrades, backups, encryption and alert routing are managed by administrators. The vitals and uptime above reflect the live platform status.
        </div>
      )}
    </div>
  );
}
