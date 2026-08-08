import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ShieldCheck, Loader2, AlertTriangle, CheckCircle2, XCircle, Bug, RefreshCw, Bot, Play, Pause, Zap, Clock, ThumbsUp, ThumbsDown, Globe, MonitorSmartphone, Server, Activity } from "lucide-react";

const SEV = {
  critical: { c: "0 84% 60%", label: "Critical" },
  high: { c: "15 80% 55%", label: "High" },
  medium: { c: "35 90% 55%", label: "Medium" },
  low: { c: "48 90% 55%", label: "Low" },
  info: { c: "199 70% 50%", label: "Info" },
};
const scoreCol = (v) => (v >= 85 ? "142 70% 45%" : v >= 65 ? "35 90% 55%" : "0 84% 60%");
const rel = (iso) => (iso ? new Date(iso).toLocaleString() : "never");

// ECG / heartbeat trace — hospital-monitor style vitals for endpoint health.
const _BEAT = [[0, 20], [10, 20], [14, 17], [18, 20], [24, 20], [26, 23], [30, 4], [33, 33], [36, 20], [44, 20], [48, 15], [54, 20], [60, 20]];
function ecgPoints(flat) {
  const out = [];
  for (let i = 0; i < 9; i++) {
    if (flat) { out.push(`${i * 60},20`, `${i * 60 + 60},20`); }
    else { for (const [x, y] of _BEAT) out.push(`${x + i * 60},${y}`); }
  }
  return out.join(" ");
}
const _PTS = ecgPoints(false);
const _FLAT = ecgPoints(true);

function HeartbeatTrace({ mode = "pulse", color, height = 46 }) {
  const flat = mode === "flat";
  const dur = mode === "slow" ? "3.4s" : "1.4s";
  const stroke = color || (mode === "slow" ? "35 90% 55%" : flat ? "0 0% 45%" : "142 70% 45%");
  return (
    <div className="relative overflow-hidden rounded-md ecg-box w-full" style={{ height }} data-testid={`ecg-${mode}`}>
      <div className="ecg-grid" />
      <div style={{ width: 1080, height, animation: flat ? "none" : `ecgScroll ${dur} linear infinite` }}>
        <svg width="1080" height={height} viewBox="0 0 540 40" preserveAspectRatio="none">
          <polyline points={flat ? _FLAT : _PTS} fill="none" stroke={`hsl(${stroke})`} strokeWidth="1.4"
            strokeLinejoin="round" strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 3px hsl(${stroke} / 0.9))`, animation: mode === "slow" ? "ecgWarn 1.6s ease-in-out infinite" : "none" }} />
        </svg>
      </div>
    </div>
  );
}

const ECG_CSS = `
@keyframes ecgScroll{from{transform:translateX(0)}to{transform:translateX(-120px)}}
@keyframes ecgWarn{0%,100%{opacity:1}50%{opacity:.4}}
.ecg-box{background:radial-gradient(circle at 50% 50%, hsl(220 45% 8%), hsl(222 47% 5%));}
.ecg-grid{position:absolute;inset:0;background-image:linear-gradient(hsl(160 60% 40% / .07) 1px,transparent 1px),linear-gradient(90deg,hsl(160 60% 40% / .07) 1px,transparent 1px);background-size:16px 12px;pointer-events:none;}
`;


export default function SecurityScanner() {
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [engine, setEngine] = useState(null);
  const [pending, setPending] = useState([]);
  const [endpoint, setEndpoint] = useState("");
  const [autoRunning, setAutoRunning] = useState(false);
  const [assets, setAssets] = useState(null);

  const loadScan = () => api.get("/self-scan/latest").then((r) => setScan(r.data && r.data.id ? r.data : null)).catch(() => setScan(null));
  const loadEngine = () => api.get("/self-scan/engine").then((r) => { setEngine(r.data.engine); setPending(r.data.pending || []); setEndpoint(r.data.endpoint || ""); }).catch(() => {});
  const loadAssets = () => api.get("/self-scan/assets").then((r) => setAssets(r.data)).catch(() => {});
  useEffect(() => { Promise.all([loadScan(), loadEngine(), loadAssets()]).finally(() => setLoading(false)); }, []);

  // Auto-detect: poll so newly connected sources/devices stream into the monitor live.
  useEffect(() => {
    const id = setInterval(() => { loadAssets(); loadEngine(); }, 20000);
    const onVis = () => { if (!document.hidden) { loadAssets(); loadEngine(); } };
    document.addEventListener("visibilitychange", onVis);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", onVis); };
  }, []);

  const run = async () => {
    setRunning(true);
    toast.info("Running live self-scan (headers, CORS, OSV CVEs, CISA KEV, MITRE ATT&CK)…");
    try {
      const { data } = await api.post("/self-scan/run");
      setScan(data);
      toast.success(`Scan complete — score ${data.score}/100 · compliance auto-updated`);
    } catch (e) {
      toast.error("Scan failed. Check backend logs.");
    }
    setRunning(false);
  };

  const toggleRemediate = async (fid, done) => {
    try {
      const { data } = await api.post("/self-scan/remediate", { finding_id: fid, done });
      setScan((s) => ({ ...s, remediated: data.remediated }));
      toast.success(done ? "Marked remediated — compliance controls updated" : "Reopened finding");
    } catch (e) {
      toast.error("Could not update remediation state");
    }
  };

  const patchEngine = async (patch) => {
    try {
      const { data } = await api.put("/self-scan/engine", patch);
      setEngine(data);
      toast.success("Autonomous engine updated");
    } catch (e) {
      toast.error("Could not update engine");
    }
  };

  const runEngine = async () => {
    setAutoRunning(true);
    toast.info("Running autonomous cycle — AI review, auto-fix safe config, queue upgrades…");
    try {
      const { data } = await api.post("/self-scan/engine/run");
      await Promise.all([loadScan(), loadEngine()]);
      toast.success(`Autonomous cycle done — ${data.applied?.length || 0} auto-fixed · ${data.queued?.length || 0} awaiting approval`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Autonomous run failed");
    }
    setAutoRunning(false);
  };

  const decide = async (approval_id, approve) => {
    try {
      await api.post("/self-scan/upgrade/approve", { approval_id, approve });
      await Promise.all([loadScan(), loadEngine()]);
      toast.success(approve ? "Approved & applied — compliance updated" : "Declined — accepted as risk");
    } catch (e) {
      toast.error("Could not record decision");
    }
  };

  const s = scan?.summary || {};
  const findings = scan?.findings || [];
  const fails = findings.filter((f) => f.status === "fail");
  const passes = findings.filter((f) => f.status === "pass");
  const engStatus = !engine?.enabled ? "off" : engine?.paused ? "paused" : "active";
  const ov = assets?.overview || {};
  const scoreVital = (v) => v == null ? { mode: "flat", c: "0 0% 45%", label: "no data" } : v >= 85 ? { mode: "pulse", c: "142 70% 45%", label: "● stable" } : v >= 65 ? { mode: "pulse", c: "35 90% 55%", label: "▲ caution" } : { mode: "slow", c: "0 84% 60%", label: "▼ critical" };
  const STALE_MS = 24 * 3600 * 1000;
  const vitals = (src) => {
    const stale = src.synced_at && (Date.now() - new Date(src.synced_at).getTime() > STALE_MS);
    if (src.status === "live") return stale
      ? { mode: "slow", c: "35 90% 55%", label: "Stale", health: 62, bpm: 48 }
      : { mode: "pulse", c: "142 70% 45%", label: "Live", health: Math.max(60, 99 - (src.metrics?.risky_users || 0) * 2), bpm: 72 };
    if (src.status === "degraded") return { mode: "slow", c: "35 90% 55%", label: "Degraded", health: 45, bpm: 40 };
    if (src.status === "available") return { mode: "flat", c: "199 65% 50%", label: "Standby", health: null, bpm: 0 };
    return { mode: "flat", c: "0 0% 45%", label: "Disconnected", health: null, bpm: 0 };
  };

  return (
    <div className="rise space-y-6" data-testid="security-scanner-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Bug className="w-7 h-7 text-crit" /> Self Vulnerability Scanner</h1>
          <p className="text-sm text-muted-foreground mt-1">Live, evidence-based security test of this platform — hardening headers, CORS, dependency CVEs (OSV.dev), CISA KEV cross-reference and MITRE ATT&CK mapping. Results auto-update the compliance crosswalk.</p>
          <div className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1.5" data-testid="scan-endpoint"><Globe className="w-3.5 h-3.5" /> Scanning live endpoint: <span className="font-mono">{endpoint || "localhost"}</span></div>
        </div>
        <button data-testid="run-scan-btn" onClick={run} disabled={running} className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50 flex items-center gap-2">
          {running ? <><Loader2 className="w-4 h-4 animate-spin" /> Scanning…</> : <><RefreshCw className="w-4 h-4" /> Run live scan</>}
        </button>
      </div>

      {/* Autonomous AI remediation engine */}
      <div className="bg-card fact-border rounded-xl p-6" data-testid="auto-engine">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="font-head font-bold text-lg flex items-center gap-2"><Bot className="w-5 h-5 text-ai" /> Autonomous Remediation Engine</h2>
            <p className="text-xs text-muted-foreground mt-1 max-w-2xl">AI (Obserrian Advisor) scans daily, auto-applies safe, non-breaking config hardening, and always notifies + waits for your approval before applying dependency upgrades. Pause or resume anytime.</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span data-testid="engine-status" className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-full font-bold"
              style={{ background: engStatus === "active" ? "hsl(142 70% 45% / 0.15)" : engStatus === "paused" ? "hsl(35 90% 55% / 0.15)" : "hsl(0 0% 50% / 0.12)", color: engStatus === "active" ? "hsl(142 70% 40%)" : engStatus === "paused" ? "hsl(35 90% 45%)" : "hsl(0 0% 45%)" }}>
              {engStatus === "active" ? "● Active · daily" : engStatus === "paused" ? "❙❙ Paused" : "Off"}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-4">
          {!engine?.enabled ? (
            <button data-testid="engine-enable" onClick={() => patchEngine({ enabled: true, paused: false })} className="px-4 py-2 rounded-md bg-ai text-white font-head font-bold text-sm flex items-center gap-2"><Zap className="w-4 h-4" /> Enable engine</button>
          ) : (
            <>
              {engine?.paused ? (
                <button data-testid="engine-resume" onClick={() => patchEngine({ paused: false })} className="px-4 py-2 rounded-md bg-low text-white font-head font-bold text-sm flex items-center gap-2"><Play className="w-4 h-4" /> Resume</button>
              ) : (
                <button data-testid="engine-pause" onClick={() => patchEngine({ paused: true })} className="px-4 py-2 rounded-md bg-secondary font-head font-bold text-sm flex items-center gap-2"><Pause className="w-4 h-4" /> Pause</button>
              )}
              <button data-testid="engine-run" onClick={runEngine} disabled={autoRunning || engine?.paused} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50 flex items-center gap-2">
                {autoRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Running…</> : <><Bot className="w-4 h-4" /> Run cycle now</>}
              </button>
              <button data-testid="engine-disable" onClick={() => patchEngine({ enabled: false })} className="px-3 py-2 rounded-md text-xs text-muted-foreground hover:text-foreground">Turn off</button>
              <label className="flex items-center gap-2 text-[11px] cursor-pointer ml-1" data-testid="engine-autoapply">
                <input type="checkbox" checked={!!engine?.auto_apply_config} onChange={(e) => patchEngine({ auto_apply_config: e.target.checked })} />
                Auto-apply safe config fixes
              </label>
            </>
          )}
        </div>

        {engine?.last_summary && (
          <div className="text-[11px] text-muted-foreground mt-3 flex items-center gap-1.5" data-testid="engine-lastrun">
            <Clock className="w-3.5 h-3.5" /> Last cycle {rel(engine.last_summary.ts)} ({engine.last_summary.trigger}) — {engine.last_summary.applied?.length || 0} auto-fixed, {engine.last_summary.queued?.length || 0} queued, score {engine.last_summary.score}/100
          </div>
        )}

        {pending.length > 0 && (
          <div className="mt-4 border-t border-border pt-4" data-testid="pending-approvals">
            <div className="flex items-center gap-2 mb-3"><AlertTriangle className="w-4 h-4 text-high" /><h3 className="font-head font-bold text-sm">Awaiting your approval before applying ({pending.length})</h3></div>
            <div className="space-y-2">
              {pending.map((p) => (
                <div key={p.id} data-testid={`approval-${p.finding_id}`} className="p-3 rounded-lg bg-secondary/40 flex flex-wrap items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{p.title}</span>
                      <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${SEV[p.severity]?.c || SEV.info.c} / 0.15)`, color: `hsl(${SEV[p.severity]?.c || SEV.info.c})` }}>{p.severity}</span>
                      {p.kev && <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full bg-crit/15 text-crit">KEV</span>}
                      <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full bg-ai/10 text-ai">{p.kind}</span>
                    </div>
                    {p.package && <div className="text-[11px] font-mono text-muted-foreground mt-1">{p.package} {p.current_version} → {p.fixed_version || "patched"}</div>}
                    <div className="text-xs text-muted-foreground mt-1">{p.rationale || p.detail}</div>
                    <div className="text-xs mt-1"><b>Fix:</b> {p.remediation}</div>
                    {p.cve_ids?.length > 0 && <div className="flex flex-wrap gap-1 mt-1.5">{p.cve_ids.slice(0, 10).map((c) => <span key={c} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-crit/10 text-crit border border-crit/20">{c}</span>)}</div>}                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button data-testid={`approve-${p.finding_id}`} onClick={() => decide(p.id, true)} className="px-3 py-1.5 rounded-md bg-low text-white text-xs font-bold flex items-center gap-1"><ThumbsUp className="w-3.5 h-3.5" /> Approve</button>
                    <button data-testid={`reject-${p.finding_id}`} onClick={() => decide(p.id, false)} className="px-3 py-1.5 rounded-md bg-secondary text-xs font-bold flex items-center gap-1"><ThumbsDown className="w-3.5 h-3.5" /> Decline</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Connected devices & health */}
      <div className="bg-card fact-border rounded-xl p-6" data-testid="connected-assets">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="font-head font-bold text-lg flex items-center gap-2"><Server className="w-5 h-5 text-ai" /> Connected devices &amp; health</h2>
          {assets && <span className="text-[11px] text-muted-foreground flex items-center gap-1.5"><Activity className="w-3.5 h-3.5" /> {assets.healthy}/{assets.total_sources} sources live</span>}
        </div>
        <style>{ECG_CSS}</style>
        {!assets || assets.total_sources === 0 ? (
          <div className="text-sm text-muted-foreground" data-testid="assets-empty">No connected sources yet. Connect Microsoft 365, Copilot, ChatGPT or an enterprise connector to inventory devices and monitor their health here.</div>
        ) : (
          <>
            {/* Primary vitals — app health, compliance, endpoint security */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4" data-testid="primary-vitals">
              {[
                { key: "app", label: "App health", value: ov.app_health },
                { key: "compliance", label: "Compliance", value: ov.compliance_pct, suffix: "%" },
                { key: "endpoint", label: "Endpoint security", value: ov.security_score },
              ].map((m) => {
                const vt = scoreVital(m.value);
                return (
                  <div key={m.key} data-testid={`vital-${m.key}`} className="rounded-xl border border-border overflow-hidden">
                    <HeartbeatTrace mode={vt.mode} color={vt.c} height={64} />
                    <div className="flex items-center justify-between px-3 py-2" style={{ background: "hsl(222 47% 6%)" }}>
                      <div>
                        <div className="text-[9px] uppercase tracking-widest text-muted-foreground">{m.label}</div>
                        <div className="text-[9px] font-mono uppercase" style={{ color: `hsl(${vt.c})` }}>{vt.label}</div>
                      </div>
                      <div data-testid={`vital-${m.key}-value`} className="font-head font-black text-3xl leading-none" style={{ color: `hsl(${vt.c})` }}>{m.value ?? "—"}{m.value != null && m.suffix ? m.suffix : ""}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mb-4 px-1 text-[10px] text-muted-foreground flex items-center gap-1.5" data-testid="endpoint-line"><Globe className="w-3 h-3" /> {endpoint || "localhost"} · {scan?.ts ? `verified ${rel(scan.ts)}` : "awaiting first scan"} · auto-refreshing every 20s</div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {assets.sources.map((src, i) => {
                const v = vitals(src);
                const mparts = Object.entries(src.metrics || {}).filter(([, val]) => val !== null && val !== undefined && val !== "").map(([k, val]) => `${val} ${k}`);
                return (
                  <div key={i} data-testid={`asset-${src.kind}-${i}`} className="rounded-lg border border-border overflow-hidden bg-card">
                    <div className="flex items-center justify-between gap-2 px-3 pt-2">
                      <span className="font-medium text-sm truncate">{src.name}</span>
                      <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full shrink-0" style={{ background: `hsl(${v.c} / 0.15)`, color: `hsl(${v.c})` }}>{v.label}</span>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-2">
                      <div className="flex-1 min-w-0"><HeartbeatTrace mode={v.mode} color={v.c} height={34} /></div>
                      <div className="w-11 text-right shrink-0">
                        <div className="font-head font-black text-lg leading-none" style={{ color: `hsl(${v.c})` }}>{v.health ?? "—"}</div>
                        <div className="text-[8px] uppercase text-muted-foreground">{v.bpm ? `${v.bpm} bpm` : "flatline"}</div>
                      </div>
                    </div>
                    <div className="px-3 pb-2 text-[10px] text-muted-foreground truncate">{[mparts.join(" · "), src.synced_at ? `synced ${rel(src.synced_at)}` : null].filter(Boolean).join(" · ")}</div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* Managed device inventory (Intune) */}
        <div className="mt-5 border-t border-border pt-4" data-testid="device-inventory">
          <div className="flex items-center gap-2 mb-2"><MonitorSmartphone className="w-4 h-4 text-primary" /><h3 className="font-head font-bold text-sm">Managed device health</h3></div>
          {assets?.devices?.available ? (
            <>
              <div className="flex flex-wrap gap-3 mb-3">
                {[["Total", assets.devices.total, "199 70% 50%"], ["Compliant", assets.devices.compliant, "142 70% 45%"], ["Non-compliant", assets.devices.noncompliant, "0 84% 60%"], ["Unknown", assets.devices.unknown, "35 90% 55%"]].map(([l, n, c]) => (
                  <div key={l} className="rounded-lg px-4 py-2 border text-center" style={{ borderColor: `hsl(${c} / 0.3)`, background: `hsl(${c} / 0.06)` }}>
                    <div className="font-head font-black text-xl" style={{ color: `hsl(${c})` }}>{n}</div>
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{l}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-1 max-h-56 overflow-auto">
                {assets.devices.items.map((d, i) => {
                  const c = d.compliance === "compliant" ? "142 70% 45%" : d.compliance === "noncompliant" ? "0 84% 60%" : "35 90% 55%";
                  return (
                    <div key={i} className="flex items-center justify-between gap-2 text-xs py-1 border-b border-border/50">
                      <span className="truncate"><span className="font-medium">{d.name || "device"}</span>{d.owner ? <span className="text-muted-foreground"> · {d.owner}</span> : null}<span className="text-muted-foreground"> · {[d.os, d.os_version, d.model].filter(Boolean).join(" ")}</span></span>
                      <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full shrink-0" style={{ background: `hsl(${c} / 0.15)`, color: `hsl(${c})` }}>{d.compliance || "unknown"}</span>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="text-xs text-muted-foreground" data-testid="device-note">{assets?.devices?.note || "Connect Microsoft 365 (Intune) to inventory managed devices and their health."}</div>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
      ) : !scan ? (
        <div className="bg-card fact-border rounded-xl p-10 text-center" data-testid="no-scan">
          <ShieldCheck className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No scan yet. Run a live scan to test this platform and populate evidence-based compliance.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            <div className="lg:col-span-4 bg-card fact-border rounded-xl p-6 flex flex-col items-center justify-center text-center">
              <div className="text-xs text-muted-foreground mb-1">Security score</div>
              <div data-testid="scan-score" className="font-head font-black text-6xl tracking-tight" style={{ color: `hsl(${scoreCol(scan.score)})` }}>{scan.score}</div>
              <div className="text-[11px] text-muted-foreground mt-2">Last scan {rel(scan.ts)} · {scan.duration_ms}ms</div>
              <div className="text-[11px] text-muted-foreground">{s.dependencies_scanned} deps scanned · {s.vulnerable_dependencies || 0} vulnerable</div>
              {scan.mitre_techniques?.length > 0 && <div className="text-[10px] text-muted-foreground mt-1">{scan.mitre_techniques.length} MITRE ATT&CK · {scan.cwe_ids?.length || 0} MITRE CWE mapped</div>}
            </div>
            <div className="lg:col-span-8 bg-card fact-border rounded-xl p-6">
              <h2 className="font-head font-bold text-lg mb-4">Findings by severity</h2>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {["critical", "high", "medium", "low", "info"].map((k) => (
                  <div key={k} data-testid={`sev-${k}`} className="rounded-lg p-3 border text-center" style={{ borderColor: `hsl(${SEV[k].c} / 0.3)`, background: `hsl(${SEV[k].c} / 0.06)` }}>
                    <div className="font-head font-black text-2xl" style={{ color: `hsl(${SEV[k].c})` }}>{s[k] || 0}</div>
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{SEV[k].label}</div>
                  </div>
                ))}
              </div>
              {scan.kev_matches?.length > 0 && (
                <div className="mt-4 p-3 rounded-lg bg-crit/10 border border-crit/30 text-sm text-crit flex items-start gap-2" data-testid="kev-alert">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> <span><b>{scan.kev_matches.length} actively-exploited (CISA KEV)</b>: {scan.kev_matches.join(", ")}</span>
                </div>
              )}
              <div className="text-[11px] text-muted-foreground mt-3">{s.passed} checks passing · {fails.length} to remediate · {s.total_checks} total</div>
            </div>
          </div>

          {fails.length > 0 && (
            <div className="bg-card fact-border rounded-xl p-6" data-testid="findings-remediate">
              <div className="flex items-center gap-2 mb-4"><AlertTriangle className="w-4 h-4 text-high" /><h2 className="font-head font-bold text-lg">Findings & remediation</h2></div>
              <div className="space-y-3">
                {fails.map((f) => (
                  <div key={f.id} data-testid={`finding-${f.id}`} className="p-4 rounded-lg bg-secondary/30">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <XCircle className="w-4 h-4" style={{ color: `hsl(${SEV[f.severity].c})` }} />
                      <span className="font-medium text-sm">{f.title}</span>
                      <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${SEV[f.severity].c} / 0.15)`, color: `hsl(${SEV[f.severity].c})` }}>{f.severity}</span>
                      {f.kev && <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full bg-crit/15 text-crit">KEV</span>}
                      <span className="text-[10px] text-muted-foreground">{f.category}</span>
                    </div>
                    <div className="text-xs text-muted-foreground mb-2">{f.evidence}</div>
                    {f.cve_ids?.length > 0 && <div className="flex flex-wrap gap-1 mb-2">{f.cve_ids.slice(0, 12).map((c) => <span key={c} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-crit/10 text-crit border border-crit/20">{c}</span>)}</div>}
                    <div className="text-xs flex items-start gap-1.5"><ShieldCheck className="w-3.5 h-3.5 mt-0.5 text-low shrink-0" /><span><b>Fix:</b> {f.remediation}</span></div>
                    <div className="flex flex-wrap gap-1 mt-2">{f.control_refs?.map((r) => <span key={r} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{r}</span>)}</div>
                    {f.mitre?.length > 0 && <div className="flex flex-wrap gap-1 mt-1.5">{f.mitre.map((m) => <span key={m.id} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-crit/5 text-crit/80 border border-crit/15" title={m.tactic}>ATT&CK {m.id} · {m.name}</span>)}</div>}
                    {f.cwe?.length > 0 && <div className="flex flex-wrap gap-1 mt-1.5">{f.cwe.map((w) => <span key={w.id} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-high/5 text-high/90 border border-high/20" title={w.name}>{w.id} · {w.name}</span>)}</div>}
                    <label className="flex items-center gap-2 mt-3 text-[11px] cursor-pointer text-low font-medium" data-testid={`remediate-${f.id}`}>
                      <input type="checkbox" checked={(scan.remediated || []).includes(f.id)} onChange={(e) => toggleRemediate(f.id, e.target.checked)} />
                      Mark remediation complete — update compliance controls
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-card fact-border rounded-xl p-6" data-testid="findings-passing">
            <div className="flex items-center gap-2 mb-4"><CheckCircle2 className="w-4 h-4 text-low" /><h2 className="font-head font-bold text-lg">Passing controls ({passes.length})</h2></div>
            <div className="space-y-2">
              {passes.map((f) => (
                <div key={f.id} data-testid={`finding-${f.id}`} className="flex items-start gap-2 text-sm">
                  <CheckCircle2 className="w-4 h-4 mt-0.5 text-low shrink-0" />
                  <div><span className="font-medium">{f.title}</span> <span className="text-[11px] text-muted-foreground">— {f.evidence}</span>
                    <div className="flex flex-wrap gap-1 mt-1">{f.control_refs?.map((r) => <span key={r} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-low/10 text-low border border-low/20">{r}</span>)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
