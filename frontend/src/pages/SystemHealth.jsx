import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Spinner } from "@/components/dash";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Activity, Database, Plug, Clock, ServerCog, ArrowUpCircle, DownloadCloud, Loader2,
  HardDriveDownload, RotateCcw, ShieldCheck, AlertTriangle, RefreshCw, Building2, Terminal, CheckCircle2,
  Save, Mail, MessageSquare, Slack, Zap, Archive, Lock, Send, FileText, KeyRound, Eye, History, FileCheck2,
  Share2, Copy, X, Trash2, DoorOpen, Link2, Palette, MessageCircle, Ban, Download, Pencil, Plus,
} from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const slaAge = (s) => {
  if (!s) return null;
  const h = Math.max(0, (Date.now() - new Date(s).getTime()) / 3.6e6);
  const label = h < 24 ? `${Math.max(1, Math.round(h))}h` : `${Math.round(h / 24)}d`;
  const color = h >= 72 ? "bg-crit/15 text-crit" : h >= 24 ? "bg-high/15 text-high" : "bg-low/15 text-low";
  return { label, color };
};
const REPLY_TEMPLATES = [
  { label: "Evidence attached", text: "The requested evidence is attached in the latest signed evidence pack — see the download on your portal." },
  { label: "Under review", text: "Thanks — the governance team is reviewing this request and will follow up shortly." },
  { label: "Please clarify", text: "Could you clarify the specific system, control or period this request relates to so we can provide the right evidence?" },
  { label: "Resolved", text: "This has been addressed. Please let us know if you need anything further for your audit." },
];
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
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [reprobing, setReprobing] = useState(null);
  const logRef = useRef(null);
  const [restoreTarget, setRestoreTarget] = useState(null);
  const [confirmText, setConfirmText] = useState("");
  const [restorePass, setRestorePass] = useState("");
  const [restoring, setRestoring] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [encModal, setEncModal] = useState(null); // 'enable' | 'disable' | 'rotate'
  const [encPass, setEncPass] = useState("");
  const [encNewPass, setEncNewPass] = useState("");
  const [encBusy, setEncBusy] = useState(false);
  const [evidence, setEvidence] = useState([]);
  const [genEvidence, setGenEvidence] = useState(false);
  const [evCfg, setEvCfg] = useState(null);
  const [previews, setPreviews] = useState([]);
  const [digest, setDigest] = useState(null);
  const [digesting, setDigesting] = useState(false);
  const [period, setPeriod] = useState("current");
  const [shareModal, setShareModal] = useState(null);
  const [sharingFile, setSharingFile] = useState(null);
  const [sendingDigest, setSendingDigest] = useState(false);
  const [shares, setShares] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [creatingRoom, setCreatingRoom] = useState(false);
  const [digestTestEmail, setDigestTestEmail] = useState("");
  const [sendingTestEmail, setSendingTestEmail] = useState(false);
  const [comments, setComments] = useState([]);
  const [brandModal, setBrandModal] = useState(false);
  const [brand, setBrand] = useState({ welcome: "", use_org_logo: true, has_logo: false, org_logo_available: false });
  const [brandLogo, setBrandLogo] = useState(null);
  const [savingBrand, setSavingBrand] = useState(false);
  const [revokingAll, setRevokingAll] = useState(false);
  const [replyDrafts, setReplyDrafts] = useState({});
  const [inboxStatus, setInboxStatus] = useState("all");
  const [inboxRoom, setInboxRoom] = useState("all");
  const [savedTemplates, setSavedTemplates] = useState([]);
  const [templateModal, setTemplateModal] = useState(false);
  const [tplDraft, setTplDraft] = useState([]);
  const [savingTpl, setSavingTpl] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkStatus, setBulkStatus] = useState("Resolved");
  const [exporting, setExporting] = useState(false);

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
  const loadEvidence = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/evidence/list"); setEvidence(data.evidence || []); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadPreviews = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/restore-previews"); setPreviews(data.previews || []); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadShares = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/evidence/shares"); setShares(data.shares || []); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadRooms = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/audit-rooms"); setRooms(data.rooms || []); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadComments = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/audit-room-comments"); setComments(data.comments || []); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadTemplates = useCallback(async () => {
    if (!isAdmin) return;
    try { const { data } = await api.get("/deploy/reply-templates"); setSavedTemplates(data.templates || []); } catch { /* ignore */ }
  }, [isAdmin]);
  const loadCfg = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const [b, a, e, ev] = await Promise.all([api.get("/deploy/backup-config"), api.get("/deploy/health-config"), api.get("/deploy/backup-encryption"), api.get("/deploy/evidence-config")]);
      setBcfg(b.data); setAcfg(a.data.alerts); setEncEnabled(!!e.data.enabled); setEvCfg(ev.data);
    } catch { /* ignore */ }
  }, [isAdmin]);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([loadHealth(), loadDetail(), loadVer(), loadHistory(), loadBackups(), loadUpgrade(), loadCfg(), loadEvidence(), loadPreviews(), loadShares(), loadRooms(), loadComments(), loadTemplates()]);
    setRefreshing(false);
  }, [loadHealth, loadDetail, loadVer, loadHistory, loadBackups, loadUpgrade, loadCfg, loadEvidence, loadPreviews, loadShares, loadRooms, loadComments, loadTemplates]);

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

  const blobDownload = (data, name) => {
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  };

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
      } else if (encModal === "disable") {
        await api.post("/deploy/backup-encryption/disable", { passphrase: encPass });
        toast.success("Snapshot encryption disabled");
      } else {
        const { data } = await api.post("/deploy/backup-encryption/rotate", { old_passphrase: encPass, new_passphrase: encNewPass });
        toast.success("Passphrase rotated", { description: `${data.reencrypted} existing snapshot(s) re-encrypted with the new passphrase.` });
      }
      setEncModal(null); setEncPass(""); setEncNewPass("");
      await Promise.all([loadCfg(), loadBackups()]);
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

  const downloadCompliance = async () => {
    setDownloadingPdf(true);
    try {
      const res = await api.get("/deploy/compliance-evidence", { responseType: "blob" });
      blobDownload(res.data, `Obserra-Compliance-Evidence-${new Date().toISOString().slice(0, 10)}.pdf`);
      toast.success("Compliance evidence PDF downloaded");
    } catch { toast.error("Couldn't generate the evidence PDF"); }
    setDownloadingPdf(false);
  };

  const periodOpts = () => {
    const opts = [{ v: "current", label: "Current snapshot" }];
    const now = new Date();
    for (let i = 0; i < 6; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      opts.push({ v: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`, label: d.toLocaleString(undefined, { month: "long", year: "numeric" }) });
    }
    const seen = new Set();
    for (let i = 0; i < 4; i++) {
      const qd = new Date(now.getFullYear(), now.getMonth() - i * 3, 1);
      const q = Math.floor(qd.getMonth() / 3) + 1;
      const v = `${qd.getFullYear()}-Q${q}`;
      if (!seen.has(v)) { seen.add(v); opts.push({ v, label: `Q${q} ${qd.getFullYear()}` }); }
    }
    return opts;
  };
  const periodBody = () => {
    if (period === "current") return null;
    if (period.includes("-Q")) return { kind: "quarter", value: period };
    return { kind: "month", value: period };
  };
  const generateEvidence = async () => {
    setGenEvidence(true);
    try {
      const { data } = await api.post("/deploy/evidence/generate", { period: periodBody() });
      toast.success("Evidence archived to locker", { description: `${data.period_label} · ${fmtBytes(data.size)}` });
      await loadEvidence();
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't archive evidence"); }
    setGenEvidence(false);
  };
  const downloadEvidence = async (file) => {
    try {
      const res = await api.get(`/deploy/evidence/download?file=${encodeURIComponent(file)}`, { responseType: "blob" });
      blobDownload(res.data, file);
    } catch { toast.error("Download failed"); }
  };
  const saveEvidenceCfg = async (patch) => {
    const next = { monthly_email: !!evCfg?.monthly_email, keep: parseInt(evCfg?.keep || 60, 10), quarterly_pack: evCfg?.quarterly_pack !== false, ...patch };
    try {
      const { data } = await api.put("/deploy/evidence-config", next);
      setEvCfg(data);
      if (patch.monthly_email !== undefined) toast.success(data.monthly_email ? "Monthly evidence email on" : "Monthly evidence email paused", { description: data.monthly_email ? "Auditors & admins receive the signed PDF on the 1st of each month." : "The scheduled evidence email is paused." });
      else if (patch.quarterly_pack !== undefined) toast.success(data.quarterly_pack ? "Quarter-end pack on" : "Quarter-end pack paused", { description: data.quarterly_pack ? "A signed quarter-end evidence pack is emailed at each quarter start." : "The quarterly pack is paused." });
      else toast.success("Retention updated", { description: `Keeping the latest ${data.keep} report(s); older ones roll off.` });
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't update"); }
  };
  const shareEvidence = async (file) => {
    setSharingFile(file);
    try {
      const { data } = await api.post("/deploy/evidence/share", { file, ttl_days: 7 });
      setShareModal({ file, url: data.url, expires_at: data.expires_at });
      await loadShares();
      try { await navigator.clipboard.writeText(data.url); toast.success("Share link copied", { description: `Read-only, expires ${new Date(data.expires_at).toLocaleDateString()}.` }); }
      catch { toast.success("Share link created"); }
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't create link"); }
    setSharingFile(null);
  };
  const createAuditRoom = async () => {
    setCreatingRoom(true);
    try {
      const { data } = await api.post("/deploy/audit-room", { ttl_days: 14 });
      setShareModal({ title: "Audit Room link", url: data.url, expires_at: data.expires_at });
      await loadRooms();
      try { await navigator.clipboard.writeText(data.url); toast.success("Audit Room created", { description: `Link copied · expires ${new Date(data.expires_at).toLocaleDateString()}.` }); }
      catch { toast.success("Audit Room created"); }
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't create audit room"); }
    setCreatingRoom(false);
  };
  const revokeShare = async (token) => {
    try { await api.post("/deploy/evidence/share/revoke", { token }); toast.success("Share link revoked"); await loadShares(); }
    catch (e) { toast.error(e.response?.data?.detail || "Couldn't revoke"); }
  };
  const revokeRoom = async (token) => {
    try { await api.post("/deploy/audit-room/revoke", { token }); toast.success("Audit room revoked"); await loadRooms(); }
    catch (e) { toast.error(e.response?.data?.detail || "Couldn't revoke"); }
  };
  const renewRoom = async (token) => {
    try {
      const { data } = await api.post("/deploy/audit-room/renew", { token, ttl_days: 14 });
      toast.success("Audit Room renewed", { description: `Now expires ${fmtDT(data.expires_at)}.` });
      await loadRooms();
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't renew"); }
  };
  const revokeAllShares = async () => {
    if (!window.confirm("Revoke ALL auditor share links and audit rooms? External auditors will immediately lose access.")) return;
    setRevokingAll(true);
    try {
      const { data } = await api.post("/deploy/shares/revoke-all");
      toast.success("All access revoked", { description: `${data.shares_revoked} link(s) and ${data.rooms_revoked} room(s) revoked.` });
      await Promise.all([loadShares(), loadRooms()]);
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't revoke all"); }
    setRevokingAll(false);
  };
  const openBrandModal = async () => {
    try { const { data } = await api.get("/deploy/audit-room-branding"); setBrand(data); } catch { /* ignore */ }
    setBrandLogo(null);
    setBrandModal(true);
  };
  const onBrandLogo = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 1400000) { toast.error("Logo too large (max ~1.4MB)"); return; }
    const reader = new FileReader();
    reader.onload = () => setBrandLogo(reader.result);
    reader.readAsDataURL(file);
  };
  const saveRoomBranding = async () => {
    setSavingBrand(true);
    try {
      const payload = { welcome: brand.welcome || "", use_org_logo: !!brand.use_org_logo };
      if (brandLogo !== null) payload.logo = brandLogo;
      await api.put("/deploy/audit-room-branding", payload);
      toast.success("Audit Room branding saved");
      setBrandModal(false);
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't save branding"); }
    setSavingBrand(false);
  };
  const replyComment = async (id) => {
    const reply = (replyDrafts[id] || "").trim();
    if (!reply) { toast.error("Enter a reply"); return; }
    try {
      await api.post(`/deploy/audit-room-comments/${id}/reply`, { reply });
      toast.success("Reply sent", { description: "Marked as resolved and now visible on the auditor's portal." });
      setReplyDrafts((d) => ({ ...d, [id]: "" }));
      await loadComments();
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't send reply"); }
  };
  const setCommentStatus = async (id, status) => {
    try {
      await api.post(`/deploy/audit-room-comments/${id}/status`, { status });
      await loadComments();
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't update status"); }
  };
  const toggleSelect = (id) => setSelectedIds((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const bulkSetStatus = async () => {
    const ids = [...selectedIds];
    if (!ids.length) return;
    try {
      const { data } = await api.post("/deploy/audit-room-comments/bulk-status", { ids, status: bulkStatus });
      toast.success(`${data.updated} request(s) set to ${bulkStatus}`);
      setSelectedIds(new Set());
      await loadComments();
    } catch (e) { toast.error(e.response?.data?.detail || "Bulk update failed"); }
  };
  const exportComments = async () => {
    setExporting(true);
    try {
      const res = await api.get("/deploy/audit-room-comments/export.csv", { responseType: "blob" });
      blobDownload(res.data, `audit-requests-${new Date().toISOString().slice(0, 10)}.csv`);
    } catch { toast.error("Export failed"); }
    setExporting(false);
  };
  const openTemplateEditor = () => {
    setTplDraft((savedTemplates.length ? savedTemplates : REPLY_TEMPLATES).map((t) => ({ ...t })));
    setTemplateModal(true);
  };
  const saveTemplates = async () => {
    setSavingTpl(true);
    try {
      const clean = tplDraft.filter((t) => (t.label || "").trim() && (t.text || "").trim());
      const { data } = await api.put("/deploy/reply-templates", { templates: clean });
      setSavedTemplates(data.templates || clean);
      toast.success("Reply templates saved");
      setTemplateModal(false);
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't save templates"); }
    setSavingTpl(false);
  };
  const sendTestDigest = async () => {
    const email = digestTestEmail.trim();
    if (!email.includes("@")) { toast.error("Enter a valid email address"); return; }
    setSendingTestEmail(true);
    try { await api.post("/deploy/health-digest-test-email", { email }); toast.success("Test digest sent", { description: `Emailed to ${email}.` }); setDigestTestEmail(""); }
    catch (e) { toast.error(e.response?.data?.detail || "Couldn't send test digest"); }
    setSendingTestEmail(false);
  };
  const sendDigestNow = async () => {
    setSendingDigest(true);
    try {
      const { data } = await api.post("/deploy/health-digest-send");
      if (data.sent) toast.success("Digest sent", { description: `Routed to: ${data.channels?.join(", ") || "in-app only"}.` });
      else toast("Nothing to send", { description: "All systems healthy — no degraded events today." });
      await previewDigest();
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't send digest"); }
    setSendingDigest(false);
  };
  const previewDigest = async () => {
    setDigesting(true);
    try { const { data } = await api.get("/deploy/health-digest-preview"); setDigest(data); }
    catch (e) { toast.error(e.response?.data?.detail || "Couldn't build digest preview"); }
    setDigesting(false);
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

  const openRestore = (b) => { setRestoreTarget(b); setConfirmText(""); setRestorePass(""); setPreview(null); };
  const runPreview = async () => {
    if (!restoreTarget) return;
    if (restoreTarget.encrypted && !restorePass) { toast.error("Enter the passphrase to preview an encrypted backup."); return; }
    setPreviewing(true);
    try {
      const body = { file: restoreTarget.file };
      if (restoreTarget.encrypted) body.passphrase = restorePass;
      const { data } = await api.post("/deploy/restore-preview", body);
      setPreview(data);
      loadPreviews();
    } catch (e) { toast.error(e.response?.data?.detail || "Couldn't build preview"); }
    setPreviewing(false);
  };
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
      blobDownload(res.data, file);
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

  const roomLabel = {};
  rooms.forEach((r, idx) => { roomLabel[r.token] = `Room ${idx + 1}`; });
  const roomOptions = [];
  const seenRooms = new Set();
  comments.forEach((c) => {
    if (c.token && !seenRooms.has(c.token)) { seenRooms.add(c.token); roomOptions.push({ token: c.token, label: roomLabel[c.token] || "Archived room" }); }
  });
  const filteredComments = comments.filter((c) => {
    const st = c.status || "Open";
    if (inboxStatus !== "all" && st !== inboxStatus) return false;
    if (inboxRoom !== "all" && c.token !== inboxRoom) return false;
    return true;
  });
  const openComments = comments.filter((c) => (c.status || "Open") !== "Resolved");
  const oldestOpen = openComments.length ? openComments.reduce((a, b) => (new Date(a.at) <= new Date(b.at) ? a : b)) : null;
  const oldestOpenBreach = oldestOpen && (Date.now() - new Date(oldestOpen.at).getTime()) / 3.6e6 >= 24;
  const activeTemplates = savedTemplates.length ? savedTemplates : REPLY_TEMPLATES;

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
          <p className="text-sm text-muted-foreground mt-1">Live platform vitals, uptime history, on-premise upgrades, encrypted backups, alert routing and auditor evidence.</p>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-compliance-pdf" onClick={downloadCompliance} disabled={downloadingPdf}>
              {downloadingPdf ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />} Compliance PDF
            </Button>
          )}
          <div className="flex flex-col items-end gap-1">
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-refresh" onClick={refreshAll} disabled={refreshing}>
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />{refreshing ? "Refreshing…" : "Refresh"}
            </Button>
            <span className="text-[10px] font-mono text-muted-foreground">Auto-refreshing every 20s</span>
          </div>
        </div>
      </div>

      {isAdmin && oldestOpen && oldestOpenBreach && (
        <button data-testid="sh-oldest-open-banner" onClick={() => document.querySelector('[data-testid="sh-comments-panel"]')?.scrollIntoView({ behavior: "smooth" })}
          className="w-full flex items-center gap-3 bg-high/10 border border-high/40 rounded-xl px-4 py-3 text-left hover:bg-high/15 transition-colors">
          <AlertTriangle className="w-5 h-5 text-high shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-high">Oldest open audit request has been waiting {slaAge(oldestOpen.at)?.label}</div>
            <div className="text-xs text-muted-foreground truncate">{oldestOpen.author}: {oldestOpen.comment}</div>
          </div>
          <span className="text-xs font-mono text-high shrink-0">Review →</span>
        </button>
      )}

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
            <span className="text-[11px] text-muted-foreground flex-1 min-w-[160px]">Encrypts every snapshot at rest; a passphrase is required to restore.</span>
            {encEnabled ? (
              <>
                <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-encryption-rotate" onClick={() => { setEncModal("rotate"); setEncPass(""); setEncNewPass(""); }}><KeyRound className="w-3.5 h-3.5" /> Rotate passphrase</Button>
                <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-encryption-disable" onClick={() => { setEncModal("disable"); setEncPass(""); }}>Disable</Button>
              </>
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

      {isAdmin && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-evidence-panel">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-primary" />
              <h2 className="font-head font-bold text-lg">Evidence Locker</h2>
              <span className="text-[11px] text-muted-foreground">Signed compliance PDFs, archived by date for auditor self-serve</span>
            </div>
            <div className="flex items-center gap-2">
              <select data-testid="sh-evidence-period" value={period} onChange={(e) => setPeriod(e.target.value)} className="h-9 rounded-md border border-border bg-secondary/40 px-2 text-xs" title="Reporting period">
                {periodOpts().map((o) => <option key={o.v} value={o.v}>{o.label}</option>)}
              </select>
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-audit-room-create" onClick={createAuditRoom} disabled={creatingRoom}>
                {creatingRoom ? <Loader2 className="w-4 h-4 animate-spin" /> : <DoorOpen className="w-4 h-4" />} Audit Room
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-room-branding-btn" onClick={openBrandModal}>
                <Palette className="w-4 h-4" /> Room Branding
              </Button>
              <Button size="sm" className="gap-1.5" data-testid="sh-evidence-generate" onClick={generateEvidence} disabled={genEvidence}>
                {genEvidence ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}{genEvidence ? "Generating…" : "Generate & archive"}
              </Button>
            </div>
          </div>

          {evCfg && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4 p-3 rounded-lg bg-secondary/30 border border-border/50" data-testid="sh-evidence-monthly-row">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input type="checkbox" data-testid="sh-evidence-monthly" checked={!!evCfg.monthly_email} onChange={(e) => saveEvidenceCfg({ monthly_email: e.target.checked })} className="w-4 h-4 accent-primary" />
                <span className="text-sm font-medium">Email monthly evidence</span>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input type="checkbox" data-testid="sh-evidence-quarterly" checked={!!evCfg.quarterly_pack} onChange={(e) => saveEvidenceCfg({ quarterly_pack: e.target.checked })} className="w-4 h-4 accent-primary" />
                <span className="text-sm font-medium">Quarter-end pack</span>
              </label>
              <span className="text-[11px] text-muted-foreground flex-1 min-w-[160px]">On the 1st of each month the signed PDF is archived here and emailed to admins, executives and your saved IT/audit recipients.</span>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                Keep latest
                <input type="number" min="1" max="365" data-testid="sh-evidence-keep" value={evCfg.keep ?? 60}
                  onChange={(e) => setEvCfg({ ...evCfg, keep: e.target.value })}
                  onBlur={(e) => saveEvidenceCfg({ keep: Math.max(1, Math.min(365, parseInt(e.target.value || "60", 10))) })}
                  className="w-16 h-8 rounded-md border border-border bg-background px-2 text-foreground" />
                report(s)
              </label>
            </div>
          )}

          {evidence.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-2">Report</th><th className="p-2">Generated by</th><th className="p-2">Source</th><th className="p-2">Size</th><th className="p-2">Created</th><th className="p-2 text-right">Actions</th></tr></thead>
                <tbody>
                  {evidence.map((ev) => (
                    <tr key={ev.file} className="border-b border-border/50" data-testid={`sh-evidence-row-${ev.file}`}>
                      <td className="p-2 font-mono text-xs"><span className="truncate max-w-[190px] inline-block align-middle">{ev.file}</span><div className="text-[10px] text-muted-foreground font-sans">{ev.period_label || "—"}</div></td>
                      <td className="p-2 text-xs text-muted-foreground">{ev.generated_by || "—"}</td>
                      <td className="p-2"><span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded ${ev.source === "monthly-cron" ? "bg-ai/15 text-ai" : "bg-secondary text-muted-foreground"}`}>{ev.source === "monthly-cron" ? "monthly" : "manual"}</span></td>
                      <td className="p-2 font-mono text-xs">{fmtBytes(ev.size)}</td>
                      <td className="p-2 text-xs text-muted-foreground">{fmtDT(ev.created_at)}</td>
                      <td className="p-2">
                        <div className="flex items-center justify-end gap-1">
                          {ev.verify_token && <a data-testid={`sh-evidence-verify-${ev.file}`} href={`${process.env.REACT_APP_BACKEND_URL}/api/deploy/evidence/verify/${ev.verify_token}`} target="_blank" rel="noreferrer" className="p-1.5 rounded-md text-muted-foreground hover:text-ai hover:bg-secondary/60 transition-colors" title="Open public verification page"><ShieldCheck className="w-4 h-4" /></a>}
                          <button data-testid={`sh-evidence-share-${ev.file}`} onClick={() => shareEvidence(ev.file)} disabled={sharingFile === ev.file} className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-secondary/60 transition-colors disabled:opacity-50" title="Create read-only share link">{sharingFile === ev.file ? <Loader2 className="w-4 h-4 animate-spin" /> : <Share2 className="w-4 h-4" />}</button>
                          <button data-testid={`sh-evidence-download-${ev.file}`} onClick={() => downloadEvidence(ev.file)} className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-secondary/60 transition-colors" title="Download signed PDF"><DownloadCloud className="w-4 h-4" /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-center gap-2 py-8 px-4 rounded-lg border border-dashed border-muted-foreground/25" data-testid="sh-evidence-empty">
              <Archive className="w-6 h-6 text-muted-foreground/50" />
              <p className="text-xs text-muted-foreground max-w-xs">No archived evidence yet — click "Generate &amp; archive" to capture a signed snapshot, or leave the monthly email on for automatic records.</p>
            </div>
          )}
        </div>
      )}

      {isAdmin && (shares.length > 0 || rooms.length > 0) && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-links-panel">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <Link2 className="w-4 h-4 text-primary" />
              <h2 className="font-head font-bold text-lg">Shared Access Links</h2>
              <span className="text-[11px] text-muted-foreground">Active auditor links &amp; rooms — open counts and one-tap revoke</span>
            </div>
            <Button size="sm" variant="outline" className="gap-1.5 text-crit border-crit/40 hover:bg-crit/10" data-testid="sh-revoke-all" onClick={revokeAllShares} disabled={revokingAll}>
              {revokingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <Ban className="w-4 h-4" />} Revoke all
            </Button>
          </div>
          <div className="space-y-2">
            {rooms.map((r) => (
              <div key={r.token} className="flex flex-wrap items-center justify-between gap-2 bg-secondary/25 rounded-lg px-3 py-2" data-testid={`sh-room-row-${r.token}`}>
                <div className="min-w-0 flex items-center gap-2">
                  <DoorOpen className="w-4 h-4 text-ai shrink-0" />
                  <div className="min-w-0">
                    <div className="text-xs font-medium flex items-center gap-2">Audit Room{r.expired && <span className="text-[9px] uppercase text-crit font-mono">expired</span>}</div>
                    <div className="text-[11px] text-muted-foreground">by {r.created_by} · expires {fmtDT(r.expires_at)}</div>
                    <div className="text-[11px] text-muted-foreground flex flex-wrap gap-x-2" data-testid={`sh-room-analytics-${r.token}`}>
                      <span>{r.opens || 0} open(s)</span>
                      <span>· last viewed {r.last_opened_at ? fmtDT(r.last_opened_at) : "—"}</span>
                      <span>· {r.downloads || 0} download(s)</span>
                      {r.last_downloaded_by && <span>· by {r.last_downloaded_by}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button data-testid={`sh-room-renew-${r.token}`} onClick={() => renewRoom(r.token)} className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-secondary/60" title="Renew (extend 14 days)"><RefreshCw className="w-4 h-4" /></button>
                  <a href={r.url} target="_blank" rel="noreferrer" className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-secondary/60" title="Open portal"><DoorOpen className="w-4 h-4" /></a>
                  <button data-testid={`sh-room-revoke-${r.token}`} onClick={() => revokeRoom(r.token)} className="p-1.5 rounded-md text-muted-foreground hover:text-crit hover:bg-secondary/60" title="Revoke room"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
            {shares.map((s) => (
              <div key={s.token} className="flex flex-wrap items-center justify-between gap-2 bg-secondary/25 rounded-lg px-3 py-2" data-testid={`sh-share-row-${s.token}`}>
                <div className="min-w-0 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                  <div className="min-w-0">
                    <div className="text-xs font-mono truncate max-w-[280px] flex items-center gap-2">{s.file}{s.expired && <span className="text-[9px] uppercase text-crit font-mono">expired</span>}</div>
                    <div className="text-[11px] text-muted-foreground">by {s.created_by} · expires {fmtDT(s.expires_at)} · {s.opens} open(s)</div>
                  </div>
                </div>
                <button data-testid={`sh-share-revoke-${s.token}`} onClick={() => revokeShare(s.token)} className="p-1.5 rounded-md text-muted-foreground hover:text-crit hover:bg-secondary/60 shrink-0" title="Revoke link"><Trash2 className="w-4 h-4" /></button>
              </div>
            ))}
          </div>
        </div>
      )}

      {isAdmin && comments.length > 0 && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-comments-panel">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <MessageCircle className="w-4 h-4 text-primary" />
            <h2 className="font-head font-bold text-lg">Audit Requests</h2>
            <span className="text-[11px] text-muted-foreground">Auditor comments — reply and track each through to resolved</span>
            <div className="flex items-center gap-2 ml-auto">
              <select data-testid="sh-inbox-status-filter" value={inboxStatus} onChange={(e) => setInboxStatus(e.target.value)} className="h-7 rounded-md border border-border bg-secondary/40 px-2 text-[11px]">
                <option value="all">All statuses</option>
                <option value="Open">Open</option>
                <option value="In Progress">In Progress</option>
                <option value="Resolved">Resolved</option>
              </select>
              {roomOptions.length > 1 && (
                <select data-testid="sh-inbox-room-filter" value={inboxRoom} onChange={(e) => setInboxRoom(e.target.value)} className="h-7 rounded-md border border-border bg-secondary/40 px-2 text-[11px]">
                  <option value="all">All rooms</option>
                  {roomOptions.map((r) => (<option key={r.token} value={r.token}>{r.label}</option>))}
                </select>
              )}
              <span className="text-[11px] font-mono text-muted-foreground" data-testid="sh-comments-open-count">{comments.filter((c) => (c.status || "Open") !== "Resolved").length} open</span>
              <Button size="sm" variant="outline" className="gap-1.5 h-7 px-2 text-[11px]" data-testid="sh-inbox-templates" onClick={openTemplateEditor}>
                <Pencil className="w-3.5 h-3.5" /> Templates
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5 h-7 px-2 text-[11px]" data-testid="sh-inbox-export" onClick={exportComments} disabled={exporting}>
                {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Export CSV
              </Button>
            </div>
          </div>
          {selectedIds.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 mb-2 bg-primary/10 border border-primary/30 rounded-lg px-3 py-2" data-testid="sh-bulk-bar">
              <span className="text-xs font-semibold">{selectedIds.size} selected</span>
              <select value={bulkStatus} onChange={(e) => setBulkStatus(e.target.value)} data-testid="sh-bulk-status" className="h-7 rounded-md border border-border bg-secondary/40 px-2 text-[11px] ml-auto">
                <option value="Open">Open</option>
                <option value="In Progress">In Progress</option>
                <option value="Resolved">Resolved</option>
              </select>
              <Button size="sm" className="h-7 px-3 text-[11px]" data-testid="sh-bulk-apply" onClick={bulkSetStatus}>Apply</Button>
              <Button size="sm" variant="outline" className="h-7 px-3 text-[11px]" data-testid="sh-bulk-clear" onClick={() => setSelectedIds(new Set())}>Clear</Button>
            </div>
          )}
          <div className="space-y-3">
            {filteredComments.length === 0 && (
              <p className="text-xs text-muted-foreground" data-testid="sh-inbox-empty">No requests match the current filter.</p>
            )}
            {filteredComments.map((c, i) => {
              const st = c.status || "Open";
              const stColor = st === "Resolved" ? "text-low" : st === "In Progress" ? "text-primary" : "text-high";
              return (
                <div key={c.id || i} className="bg-secondary/25 rounded-lg px-3 py-2.5" data-testid={`sh-comment-${i}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <input type="checkbox" data-testid={`sh-comment-select-${i}`} checked={selectedIds.has(c.id)} onChange={() => toggleSelect(c.id)} className="w-3.5 h-3.5 accent-primary" />
                      <span className="text-xs font-semibold">{c.author}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {st !== "Resolved" && slaAge(c.at) && (
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${slaAge(c.at).color}`} data-testid={`sh-comment-sla-${i}`}>waiting {slaAge(c.at).label}</span>
                      )}
                      <span className="text-[11px] text-muted-foreground">{fmtDT(c.at)}</span>
                    </div>
                  </div>
                  <p className="text-sm text-foreground/90 mt-1 whitespace-pre-wrap break-words">{c.comment}</p>
                  {c.reply && (
                    <div className="mt-2 pl-3 border-l-2 border-primary/40" data-testid={`sh-comment-reply-${i}`}>
                      <div className="text-[10px] font-mono uppercase tracking-wider text-primary">Your reply · {c.reply_by} · {fmtDT(c.reply_at)}</div>
                      <p className="text-sm text-foreground/80 mt-0.5 whitespace-pre-wrap break-words">{c.reply}</p>
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <span className={`text-[10px] font-mono uppercase tracking-wider ${stColor}`}>{st}</span>
                    <select value={st} data-testid={`sh-comment-status-${i}`} onChange={(e) => setCommentStatus(c.id, e.target.value)}
                      className="h-7 rounded-md border border-border bg-secondary/40 px-2 text-[11px]">
                      <option value="Open">Open</option>
                      <option value="In Progress">In Progress</option>
                      <option value="Resolved">Resolved</option>
                    </select>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-2" data-testid={`sh-reply-templates-${i}`}>
                    {activeTemplates.map((tpl) => (
                      <button key={tpl.label} type="button" onClick={() => setReplyDrafts((d) => ({ ...d, [c.id]: tpl.text }))}
                        className="text-[10px] px-2 py-0.5 rounded-full border border-border text-muted-foreground hover:bg-secondary/60 hover:text-foreground transition-colors">{tpl.label}</button>
                    ))}
                  </div>
                  <div className="flex items-end gap-2 mt-2">
                    <textarea rows={1} data-testid={`sh-comment-reply-input-${i}`} value={replyDrafts[c.id] || ""}
                      onChange={(e) => setReplyDrafts((d) => ({ ...d, [c.id]: e.target.value }))}
                      placeholder={c.reply ? "Reply again…" : "Reply to this auditor…"}
                      className="flex-1 rounded-md border border-border bg-secondary/40 px-2.5 py-1.5 text-sm resize-y min-h-[34px]" />
                    <Button size="sm" className="gap-1.5 shrink-0" data-testid={`sh-comment-reply-send-${i}`} onClick={() => replyComment(c.id)}>
                      <Send className="w-3.5 h-3.5" /> Reply
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {isAdmin && previews.length > 0 && (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sh-restore-log-panel">
          <div className="flex items-center gap-2 mb-3">
            <History className="w-4 h-4 text-primary" />
            <h2 className="font-head font-bold text-lg">Restore Preview Log</h2>
            <span className="text-[11px] text-muted-foreground">Dry-run checks admins ran before restoring — an audit trail</span>
          </div>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {previews.map((p, i) => (
              <div key={i} className="flex flex-wrap items-center justify-between gap-2 bg-secondary/25 rounded-lg px-3 py-2" data-testid={`sh-restore-log-${i}`}>
                <div className="min-w-0">
                  <div className="text-xs font-mono truncate max-w-[280px] flex items-center gap-1.5">{p.encrypted && <Lock className="w-3 h-3 text-low shrink-0" />}{p.file}</div>
                  <div className="text-[11px] text-muted-foreground">{p.by || "admin"} · {fmtDT(p.at)} · {p.collections} collection(s)</div>
                </div>
                <div className="text-xs font-mono shrink-0" title="Current → Backup record count">
                  {p.total_current} → {p.total_backup}
                  <span className={`ml-2 ${p.net_delta > 0 ? "text-low" : p.net_delta < 0 ? "text-crit" : "text-muted-foreground"}`}>{p.net_delta > 0 ? `+${p.net_delta}` : p.net_delta}</span>
                </div>
              </div>
            ))}
          </div>
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
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-digest-preview" onClick={previewDigest} disabled={digesting}>
                {digesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5" />} Preview digest
              </Button>
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
          <p className="text-[11px] text-muted-foreground mt-3">Degraded events are bundled into <b>one daily digest per channel</b> (no repeat pings). Slack/Teams use this org's webhooks; email notifies admins &amp; executives; in-app is always recorded.</p>
          <div className="mt-3 flex flex-wrap items-center gap-2" data-testid="sh-digest-test-row">
            <span className="text-xs text-muted-foreground">Preview it — send a one-off test digest to:</span>
            <input type="email" data-testid="sh-digest-test-email" value={digestTestEmail} onChange={(e) => setDigestTestEmail(e.target.value)} placeholder="auditor@company.com" className="h-8 w-56 rounded-md border border-border bg-background px-2 text-xs text-foreground" />
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-digest-test-send" onClick={sendTestDigest} disabled={sendingTestEmail}>
              {sendingTestEmail ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />} Send test
            </Button>
          </div>
          {digest && (
            <div className="mt-3 rounded-lg border border-border bg-secondary/25 p-3" data-testid="sh-digest-preview-result">
              {digest.healthy ? (
                <div className="text-sm text-low flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4" /> All systems healthy — no digest would be sent today.</div>
              ) : (
                <>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                    {digest.already_sent_today ? "Today's digest already sent — preview of its contents" : digest.would_send ? "This digest would be sent today" : "Degraded, but nothing routed to a channel yet"}
                  </div>
                  <div className="space-y-1.5">
                    {["slack", "teams", "email"].map((ch) => (
                      <div key={ch} data-testid={`sh-digest-${ch}`} className="text-xs flex gap-2">
                        <span className="inline-block w-14 font-mono uppercase text-muted-foreground shrink-0">{ch}</span>
                        {digest.per_channel[ch]?.length ? (
                          <span className="text-foreground">{digest.per_channel[ch].join(" · ")}</span>
                        ) : (
                          <span className="text-muted-foreground/60">— not routed here</span>
                        )}
                      </div>
                    ))}
                  </div>
                  <Button size="sm" className="gap-1.5 mt-3" data-testid="sh-digest-send" onClick={sendDigestNow} disabled={sendingDigest}>
                    {sendingDigest ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Send digest now
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {shareModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="sh-share-modal" onClick={() => setShareModal(null)}>
          <div className="bg-card border border-border rounded-xl p-5 w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-head font-bold text-lg flex items-center gap-2"><Share2 className="w-4 h-4 text-primary" /> {shareModal.title || "Share evidence"}</h3>
              <button data-testid="sh-share-close" onClick={() => setShareModal(null)} className="p-1 rounded-md text-muted-foreground hover:bg-secondary/60"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-xs text-muted-foreground mb-3">Read-only link — no Obserra account required. Expires {new Date(shareModal.expires_at).toLocaleDateString()}.</p>
            <div className="flex items-center gap-2">
              <input readOnly data-testid="sh-share-url" value={shareModal.url} className="flex-1 h-9 rounded-md border border-border bg-secondary/40 px-2 text-xs font-mono" onFocus={(e) => e.target.select()} />
              <Button size="sm" variant="outline" className="gap-1.5" data-testid="sh-share-copy" onClick={async () => { try { await navigator.clipboard.writeText(shareModal.url); toast.success("Copied"); } catch { toast.error("Copy failed"); } }}><Copy className="w-3.5 h-3.5" /> Copy</Button>
            </div>
          </div>
        </div>
      )}

      {brandModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="sh-brand-modal" onClick={() => !savingBrand && setBrandModal(false)}>
          <div className="bg-card fact-border rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-head font-bold text-lg flex items-center gap-2"><Palette className="w-5 h-5 text-primary" /> Audit Room branding</h3>
              <button data-testid="sh-brand-close" onClick={() => setBrandModal(false)} className="p-1 rounded-md text-muted-foreground hover:bg-secondary/60"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-sm text-muted-foreground mb-4">Personalize the public auditor portal with your logo and a welcome note.</p>
            <label className="text-xs font-medium">Logo</label>
            <div className="flex items-center gap-2 mt-1 mb-3">
              <input type="file" accept="image/png,image/jpeg,image/svg+xml" onChange={onBrandLogo} data-testid="sh-brand-logo-input" className="text-xs" />
              {(brandLogo || (brand.has_logo && brandLogo === null)) && (
                <button data-testid="sh-brand-logo-clear" onClick={() => setBrandLogo("")} className="text-[11px] text-crit hover:underline">Remove</button>
              )}
            </div>
            {brandLogo && brandLogo !== "" && <img src={brandLogo} alt="preview" className="max-h-12 mb-3 rounded" />}
            <label className="flex items-center gap-2 text-sm mb-3 cursor-pointer select-none">
              <input type="checkbox" data-testid="sh-brand-use-org" checked={!!brand.use_org_logo} onChange={(e) => setBrand({ ...brand, use_org_logo: e.target.checked })} className="w-4 h-4 accent-primary" />
              <span>Fall back to my report-branding logo {!brand.org_logo_available && <span className="text-[11px] text-muted-foreground">(none set)</span>}</span>
            </label>
            <label className="text-xs font-medium">Welcome note</label>
            <textarea data-testid="sh-brand-welcome" rows={3} value={brand.welcome || ""} onChange={(e) => setBrand({ ...brand, welcome: e.target.value })} placeholder="e.g. Welcome — this portal contains our latest SAP access governance evidence for your audit." className="w-full mt-1 mb-4 rounded-md border border-border bg-secondary/40 px-3 py-2 text-sm" />
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="outline" onClick={() => setBrandModal(false)} disabled={savingBrand}>Cancel</Button>
              <Button size="sm" className="gap-1.5" data-testid="sh-brand-save" onClick={saveRoomBranding} disabled={savingBrand}>
                {savingBrand ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
              </Button>
            </div>
          </div>
        </div>
      )}

      {templateModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="sh-template-modal" onClick={() => !savingTpl && setTemplateModal(false)}>
          <div className="bg-card fact-border rounded-2xl shadow-2xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-head font-bold text-lg flex items-center gap-2"><Pencil className="w-5 h-5 text-primary" /> Reply templates</h3>
              <button data-testid="sh-template-close" onClick={() => setTemplateModal(false)} className="p-1 rounded-md text-muted-foreground hover:bg-secondary/60"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-sm text-muted-foreground mb-4">Your own one-tap canned replies for the Audit Requests inbox.</p>
            <div className="space-y-3">
              {tplDraft.map((t, idx) => (
                <div key={idx} className="bg-secondary/25 rounded-lg p-3 space-y-2" data-testid={`sh-template-row-${idx}`}>
                  <div className="flex items-center gap-2">
                    <input value={t.label} data-testid={`sh-template-label-${idx}`} onChange={(e) => setTplDraft((d) => d.map((x, j) => (j === idx ? { ...x, label: e.target.value } : x)))}
                      placeholder="Chip label (e.g. Evidence attached)" className="flex-1 rounded-md border border-border bg-secondary/40 px-2.5 py-1.5 text-sm" />
                    <button data-testid={`sh-template-remove-${idx}`} onClick={() => setTplDraft((d) => d.filter((_, j) => j !== idx))} className="p-1.5 rounded-md text-muted-foreground hover:text-crit hover:bg-secondary/60"><Trash2 className="w-4 h-4" /></button>
                  </div>
                  <textarea rows={2} value={t.text} data-testid={`sh-template-text-${idx}`} onChange={(e) => setTplDraft((d) => d.map((x, j) => (j === idx ? { ...x, text: e.target.value } : x)))}
                    placeholder="Reply text inserted when the chip is tapped" className="w-full rounded-md border border-border bg-secondary/40 px-2.5 py-1.5 text-sm resize-y" />
                </div>
              ))}
            </div>
            <Button size="sm" variant="outline" className="gap-1.5 mt-3" data-testid="sh-template-add" onClick={() => setTplDraft((d) => [...d, { label: "", text: "" }])}>
              <Plus className="w-4 h-4" /> Add template
            </Button>
            <div className="flex justify-end gap-2 mt-5">
              <Button size="sm" variant="outline" onClick={() => setTemplateModal(false)} disabled={savingTpl}>Cancel</Button>
              <Button size="sm" className="gap-1.5" data-testid="sh-template-save" onClick={saveTemplates} disabled={savingTpl}>
                {savingTpl ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Encryption / rotate modal */}
      {encModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="sh-encryption-modal" onClick={() => !encBusy && setEncModal(null)}>
          <div className="bg-card fact-border rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-2">
              {encModal === "rotate" ? <KeyRound className="w-5 h-5 text-primary" /> : <Lock className="w-5 h-5 text-primary" />}
              <h3 className="font-head font-bold text-lg">{encModal === "enable" ? "Enable snapshot encryption" : encModal === "disable" ? "Disable snapshot encryption" : "Rotate backup passphrase"}</h3>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              {encModal === "enable"
                ? "Set a passphrase. Every new backup will be encrypted at rest, and this passphrase will be required to restore. Store it somewhere safe — it cannot be recovered."
                : encModal === "disable"
                  ? "Enter the current passphrase to turn off encryption for future backups."
                  : "Enter the current passphrase and a new one. All existing encrypted snapshots will be re-encrypted with the new passphrase in one step."}
            </p>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">{encModal === "rotate" ? "Current passphrase" : `Passphrase${encModal === "enable" ? " (min 8 characters)" : ""}`}</label>
            <input type="password" data-testid="sh-encryption-passphrase" autoFocus value={encPass} onChange={(e) => setEncPass(e.target.value)}
              className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary transition-shadow mb-4" placeholder="••••••••" />
            {encModal === "rotate" && (
              <>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">New passphrase (min 8 characters)</label>
                <input type="password" data-testid="sh-encryption-newpassphrase" value={encNewPass} onChange={(e) => setEncNewPass(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") submitEnc(); }}
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary transition-shadow mb-4" placeholder="••••••••" />
              </>
            )}
            <div className="flex items-center justify-end gap-2">
              <button data-testid="sh-encryption-cancel" onClick={() => setEncModal(null)} disabled={encBusy} className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50">Cancel</button>
              <button data-testid="sh-encryption-submit" onClick={submitEnc}
                disabled={encBusy || (encModal === "enable" ? encPass.trim().length < 8 : encModal === "disable" ? !encPass : (!encPass || encNewPass.trim().length < 8))}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-40">
                {encBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}{encModal === "enable" ? "Enable" : encModal === "disable" ? "Disable" : "Rotate"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Restore modal */}
      {restoreTarget && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" data-testid="sh-restore-modal" onClick={() => !restoring && setRestoreTarget(null)}>
          <div className="bg-card fact-border rounded-2xl shadow-2xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
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
                <label className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1.5"><Lock className="w-3.5 h-3.5 text-low" /> This backup is encrypted — enter its passphrase</label>
                <input type="password" data-testid="sh-restore-passphrase" value={restorePass} onChange={(e) => setRestorePass(e.target.value)}
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary transition-shadow" placeholder="Backup passphrase" />
              </div>
            )}
            <div className="mb-4">
              <Button size="sm" variant="outline" className="gap-1.5 w-full justify-center" data-testid="sh-restore-preview-btn" onClick={runPreview} disabled={previewing}>
                {previewing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5" />} Preview changes
              </Button>
              {preview && (
                <div className="mt-3 border border-border rounded-lg overflow-hidden" data-testid="sh-restore-preview">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground px-3 py-2 bg-secondary/40 flex justify-between">
                    <span>Collection</span><span>Current → Backup (Δ)</span>
                  </div>
                  <div className="max-h-48 overflow-y-auto">
                    {preview.rows.map((r) => (
                      <div key={r.collection} className="flex items-center justify-between px-3 py-1.5 text-xs border-t border-border/40" data-testid={`sh-preview-${r.collection}`}>
                        <span className="font-mono truncate max-w-[220px]">{r.collection}</span>
                        <span className="font-mono">
                          {r.current} → {r.backup}
                          <span className={`ml-2 ${r.delta > 0 ? "text-low" : r.delta < 0 ? "text-crit" : "text-muted-foreground"}`}>{r.delta > 0 ? `+${r.delta}` : r.delta}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="text-[11px] text-muted-foreground px-3 py-2 bg-secondary/30 border-t border-border/40">
                    {preview.collections} collection(s) · backup has {preview.total_backup} docs vs {preview.total_current} current. Collections not in the backup are left untouched.
                  </div>
                </div>
              )}
            </div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Type <span className="font-mono text-foreground">RESTORE</span> to confirm</label>
            <input data-testid="sh-restore-confirm-input" value={confirmText} onChange={(e) => setConfirmText(e.target.value)}
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
          Upgrades, backups, encryption, alert routing and compliance evidence are managed by administrators. The vitals and uptime above reflect the live platform status.
        </div>
      )}
    </div>
  );
}
