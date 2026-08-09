import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Spinner } from "@/components/dash";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Activity, Database, Plug, Clock, ServerCog, ArrowUpCircle, DownloadCloud, Loader2,
  HardDriveDownload, RotateCcw, ShieldCheck, AlertTriangle, RefreshCw, Building2, Terminal, CheckCircle2,
} from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const fmtBytes = (b) => (b == null ? "—" : b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`);

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

export default function SystemHealth() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [health, setHealth] = useState(null);
  const [ver, setVer] = useState(null);
  const [backups, setBackups] = useState([]);
  const [upgrade, setUpgrade] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const logRef = useRef(null);

  const loadHealth = useCallback(async () => {
    try { const { data } = await api.get("/health"); setHealth(data); } catch { setHealth((h) => h || { status: "degraded", checks: {} }); }
  }, []);
  const loadVer = useCallback(async () => {
    try { const { data } = await api.get("/deploy/version"); setVer(data); } catch { /* ignore */ }
  }, []);
  const loadBackups = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/backups"); setBackups(data.backups || []); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadUpgrade = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/upgrade/status"); setUpgrade(data); } catch { /* ignore */ }
  }, [isAdmin]);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([loadHealth(), loadVer(), loadBackups(), loadUpgrade()]);
    setRefreshing(false);
  }, [loadHealth, loadVer, loadBackups, loadUpgrade]);

  useEffect(() => { refreshAll(); }, [refreshAll]);

  // Auto-poll deep health every 20s.
  useEffect(() => {
    const t = setInterval(loadHealth, 20000);
    return () => clearInterval(t);
  }, [loadHealth]);

  // While an upgrade is running, poll its streaming status every 2.5s.
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
      toast.success("Backup created", { description: `${data.docs} document(s) across ${data.collections} collection(s) · ${fmtBytes(data.size)}` });
      await loadBackups();
    } catch (e) { toast.error(e.response?.data?.detail || "Backup failed"); }
    setBackingUp(false);
  };

  const restore = async (file) => {
    if (!window.confirm(`Restore from ${file}? This replaces this organization's current data with the snapshot.`)) return;
    try {
      const { data } = await api.post("/deploy/restore", { file });
      toast.success("Restore complete", { description: `${data.restored_docs} document(s) across ${data.collections} collection(s) restored.` });
      await loadHealth();
    } catch (e) { toast.error(e.response?.data?.detail || "Restore failed"); }
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
    try {
      await api.post("/deploy/upgrade");
      toast.success("Upgrade started — pulling the latest images and restarting.");
      await loadUpgrade();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Automatic upgrade isn't enabled on this deployment.");
    }
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

  return (
    <div className="space-y-6" data-testid="system-health-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="system-health-title">System Health</h1>
          <p className="text-sm text-muted-foreground mt-1">Live platform vitals — database, connectors and the scheduler — plus on-premise version, one-click upgrades and nightly database backups.</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-refresh" onClick={refreshAll} disabled={refreshing}>
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />{refreshing ? "Refreshing…" : "Refresh"}
          </Button>
          <span className="text-[10px] font-mono text-muted-foreground">Auto-refreshing every 20s</span>
        </div>
      </div>

      {/* Deep health tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4" data-testid="sh-health-tiles">
        <HealthTile testid="sh-service" label="Service" value={svcOk ? "Healthy" : "Degraded"} sub={health.service} accent={svcOk ? "142 70% 45%" : "0 84% 60%"} icon={svcOk ? ShieldCheck : AlertTriangle} ok={svcOk} />
        <HealthTile testid="sh-db" label="Database" value={dbOk ? "Online" : "Down"} sub={c.db?.latency_ms != null ? `${c.db.latency_ms} ms ping` : "MongoDB"} accent="210 92% 62%" icon={Database} ok={dbOk} />
        <HealthTile testid="sh-connectors" label="Connectors" value={conn.total != null ? `${conn.connected}/${conn.total}` : "—"} sub="Connected / total" accent="190 90% 50%" icon={Plug} ok={conn.total ? conn.connected > 0 : undefined} />
        <HealthTile testid="sh-scheduler" label="Scheduler" value={sched.cron_configured ? "Armed" : "Off"} sub={sched.last_activity ? `Last activity ${fmtDT(sched.last_activity)}` : "Cron secret set"} accent="152 65% 45%" icon={Clock} ok={sched.cron_configured} />
        <HealthTile testid="sh-orgs" label="Organizations" value={c.organizations ?? "—"} sub="Tenants live" accent="266 85% 66%" icon={Building2} />
      </div>

      {/* Version & Upgrade */}
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

      {/* Backups */}
      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-backups-panel">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <HardDriveDownload className="w-4 h-4 text-primary" />
              <h2 className="font-head font-bold text-lg">Database Backups</h2>
              <span className="text-[11px] text-muted-foreground">Automatic nightly snapshots · last 14 kept</span>
            </div>
            <Button size="sm" className="gap-1.5" data-testid="sh-backup-now" onClick={backupNow} disabled={backingUp}>
              {backingUp ? <Loader2 className="w-4 h-4 animate-spin" /> : <HardDriveDownload className="w-4 h-4" />}{backingUp ? "Backing up…" : "Back up now"}
            </Button>
          </div>
          {backups.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-2">Snapshot</th><th className="p-2">Size</th><th className="p-2">Created</th><th className="p-2 text-right">Actions</th></tr></thead>
                <tbody>
                  {backups.map((b) => (
                    <tr key={b.file} className="border-b border-border/50" data-testid={`sh-backup-row-${b.file}`}>
                      <td className="p-2 font-mono text-xs truncate max-w-[280px]">{b.file}</td>
                      <td className="p-2 font-mono text-xs">{fmtBytes(b.size)}</td>
                      <td className="p-2 text-xs text-muted-foreground">{fmtDT(b.created_at)}</td>
                      <td className="p-2">
                        <div className="flex items-center justify-end gap-1.5">
                          <button data-testid={`sh-backup-download-${b.file}`} onClick={() => download(b.file)} className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-secondary/60 transition-colors" title="Download"><DownloadCloud className="w-4 h-4" /></button>
                          <button data-testid={`sh-backup-restore-${b.file}`} onClick={() => restore(b.file)} className="p-1.5 rounded-md text-muted-foreground hover:text-high hover:bg-secondary/60 transition-colors" title="Restore"><RotateCcw className="w-4 h-4" /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-center gap-2 py-8 px-4 rounded-lg border border-dashed border-muted-foreground/25" data-testid="sh-backups-empty">
              <Activity className="w-6 h-6 text-muted-foreground/50" />
              <p className="text-xs text-muted-foreground max-w-xs">No backups yet — the nightly job runs with the daily maintenance cron, or click "Back up now" to create one immediately.</p>
            </div>
          )}
        </div>
      )}

      {!isAdmin && (
        <div className="bg-card fact-border rounded-xl p-5 text-sm text-muted-foreground" data-testid="sh-nonadmin-note">
          Upgrades and backups are managed by administrators. The vitals above reflect the live platform status.
        </div>
      )}
    </div>
  );
}
