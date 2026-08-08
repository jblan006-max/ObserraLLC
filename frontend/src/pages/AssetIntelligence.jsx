import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SourceBadge, FreshnessBadge } from "@/components/badges";
import { AIInsight } from "@/components/AIInsight";
import { StatCard, CardShell, EmptyState, Spinner } from "@/components/dash";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { AutoActions } from "@/components/AutoActions";
import { Boxes, Server, ShieldCheck, Network, Laptop, Radio, Lock, X, Cpu, Loader2, RefreshCw, Wrench } from "lucide-react";

const ACCENT = "35 92% 55%"; // Asset Intelligence → amber
const critColor = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };

function Kv({ k, v, mono }) {
  return (
    <div className="flex items-start justify-between gap-3 text-xs py-1 border-b border-border/40 last:border-0">
      <span className="text-muted-foreground shrink-0">{k}</span>
      <span className={`text-right break-all ${mono ? "font-mono" : ""}`}>{v ?? "—"}</span>
    </div>
  );
}

export default function AssetIntelligence() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [d, setD] = useState(null);
  const [conn, setConn] = useState(null);
  const [sel, setSel] = useState(null);
  const [deviceBusy, setDeviceBusy] = useState("");

  useEffect(() => {
    api.get("/dash/assets").then((r) => setD(r.data)).catch(() => setD({ assets: [], summary: {} }));
    api.get("/self-scan/assets").then((r) => setConn(r.data)).catch(() => setConn(null));
  }, []);

  if (!d) return <Spinner />;
  const s = d.summary || {};
  const assets = d.assets || [];
  const rep = assets.find((a) => a.detail?.security_headers) || assets[0];
  const hdr = rep?.detail?.security_headers;
  const devices = conn?.devices;
  const sources = conn?.sources || [];
  const byCrit = s.by_criticality || {};

  return (
    <div className="rise space-y-5" data-testid="asset-intelligence-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2" style={{ color: `hsl(${ACCENT})` }}>
          <Boxes className="w-7 h-7" strokeWidth={1.5} /> Asset Intelligence
        </h1>
        <p className="text-sm text-muted-foreground mt-1">Live asset inventory enriched with network metadata — IPs, DNS, TLS, open ports, security headers &amp; exposure — from your endpoint scan and connected sources.</p>
      </div>

      {/* KPI row — always present */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard testid="asset-kpi-total" label="Assets" value={s.total ?? 0} accent={ACCENT} sub="in inventory" />
        <StatCard testid="asset-kpi-exposed" label="Internet-facing" value={s.internet_facing ?? 0} accent="0 84% 60%" sub="resolvable / reachable" />
        <StatCard testid="asset-kpi-tls" label="TLS valid" value={s.tls_ok ?? 0} accent="142 70% 45%" sub="certs verified" />
        <StatCard testid="asset-kpi-exposure" label="Avg exposure" value={s.avg_exposure ?? 0} accent={ACCENT} sub="0–100 score" />
        <StatCard testid="asset-kpi-kev" label="KEV matches" value={s.kev_matches ?? 0} accent="0 84% 60%" sub="CISA known-exploited" />
        <StatCard testid="asset-kpi-cves" label="Open CVEs" value={s.open_cves ?? 0} accent="15 80% 55%" sub="dependency findings" />
      </div>

      <AIInsight dashboard="Asset Intelligence" accent={ACCENT} auto />

      <AutoActions accent={ACCENT} />

      {/* Secondary card grid — always present */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <CardShell testid="asset-criticality" title="Assets by criticality" icon={Boxes} accent={ACCENT}>
          <div className="grid grid-cols-2 gap-3">
            {["Critical", "High", "Medium", "Low"].map((t) => (
              <div key={t} data-testid={`asset-crit-${t}`} className="rounded-lg p-3 border" style={{ borderColor: `hsl(${critColor[t]} / 0.35)`, background: `hsl(${critColor[t]} / 0.06)` }}>
                <div className="text-[10px] font-mono uppercase" style={{ color: `hsl(${critColor[t]})` }}>{t}</div>
                <div className="font-head font-black text-2xl tracking-tight">{byCrit[t] ?? 0}</div>
              </div>
            ))}
          </div>
        </CardShell>

        <CardShell testid="asset-headers" title="Endpoint security headers" icon={ShieldCheck} accent={ACCENT}
          right={hdr && <span className="font-mono text-xs" style={{ color: `hsl(${hdr.score >= 70 ? "142 70% 45%" : hdr.score >= 40 ? "35 90% 55%" : "0 84% 60%"})` }}>{hdr.score}%</span>}>
          {!hdr ? (
            <EmptyState icon={ShieldCheck} text="Run a live self-scan on Security Scanner to populate header posture for your endpoint." />
          ) : (
            <div className="space-y-1.5">
              {(hdr.present || []).map((h) => <div key={h} className="flex items-center gap-2 text-xs"><Lock className="w-3 h-3 text-low" /> <span className="font-mono">{h}</span></div>)}
              {(hdr.missing || []).map((h) => <div key={h} className="flex items-center gap-2 text-xs text-muted-foreground"><X className="w-3 h-3 text-crit" /> <span className="font-mono line-through opacity-70">{h}</span></div>)}
            </div>
          )}
        </CardShell>

        <CardShell testid="asset-sources" title="Connected sources" icon={Radio} accent={ACCENT}
          right={<span className="text-[10px] font-mono text-muted-foreground">{conn?.healthy ?? 0}/{conn?.total_sources ?? 0} live</span>}>
          {sources.length === 0 ? (
            <EmptyState icon={Radio} text="No sources connected yet. Connect Microsoft 365, SSO, Tenable or CASB in Available Connectors."
              cta={<a href="/app/connectors" className="text-xs font-head font-bold px-3 py-1.5 rounded-full" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}>Connect a source</a>} />
          ) : (
            <div className="space-y-2">
              {sources.map((src, i) => (
                <div key={i} data-testid={`asset-source-${i}`} className="flex items-center justify-between text-xs bg-secondary/30 rounded-md px-3 py-2">
                  <span className="font-medium truncate">{src.name}</span>
                  <span className={`font-mono text-[10px] px-2 py-0.5 rounded-full ${src.status === "live" ? "bg-low/15 text-low" : "bg-secondary/60 text-muted-foreground"}`}>{src.status}</span>
                </div>
              ))}
            </div>
          )}
        </CardShell>
      </div>

      {/* Managed devices (Intune) — always present, connect state if absent */}
      <CardShell testid="asset-devices" title="Managed devices (Microsoft Intune)" icon={Laptop} accent={ACCENT}
        right={devices?.available && <span className="text-[10px] font-mono text-muted-foreground">{devices.total} devices · <span className="text-low">{devices.compliant} compliant</span> · <span className="text-crit">{devices.noncompliant} non-compliant</span></span>}>
        {!devices?.available ? (
          <EmptyState icon={Laptop} text={devices?.note || "Connect Microsoft 365 (Intune) to inventory managed devices, their OS, owner and compliance state."}
            cta={<a href="/app/connectors" className="text-xs font-head font-bold px-3 py-1.5 rounded-full" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}>Connect Microsoft 365</a>} />
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {(devices.items || []).map((dv) => (
              <div key={dv.id} data-testid={`device-${dv.id}`} className="bg-secondary/30 rounded-md p-3 text-xs">
                <div className="font-medium truncate">{dv.name}</div>
                <div className="text-muted-foreground truncate">{dv.owner || "—"} · {dv.os || "—"} {dv.os_version || ""}</div>
                <span className={`inline-block mt-1 font-mono text-[9px] px-1.5 py-0.5 rounded-sm ${dv.compliance === "compliant" ? "bg-low/15 text-low" : "bg-crit/15 text-crit"}`}>{dv.compliance || "unknown"}</span>
                {isAdmin && (
                  <div className="flex gap-1.5 mt-2">
                    <button data-testid={`device-sync-${dv.id}`} disabled={!!deviceBusy} onClick={() => deviceAction(dv.id, "sync")} className="flex items-center gap-1 text-[10px] px-2 py-1 rounded-md bg-secondary/60 hover:bg-secondary disabled:opacity-50">{deviceBusy === dv.id + "sync" ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Sync</button>
                    <button data-testid={`device-fix-${dv.id}`} disabled={!!deviceBusy} onClick={() => deviceAction(dv.id, "remediate")} className="flex items-center gap-1 text-[10px] px-2 py-1 rounded-md disabled:opacity-50" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}>{deviceBusy === dv.id + "remediate" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wrench className="w-3 h-3" />} Auto-remediate</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardShell>

      {/* Inventory table + detail pane */}
      <div className="md:flex md:gap-5 md:items-start">
        <div className="min-w-0 flex-1">
          {assets.length === 0 ? (
            <CardShell testid="asset-inventory" title="Asset inventory" icon={Server} accent={ACCENT}>
              <EmptyState icon={Server} text="No assets yet — run a live scan or connect a source to populate your inventory." />
            </CardShell>
          ) : (
            <div className="bg-card fact-border rounded-xl overflow-x-auto" data-testid="asset-inventory">
              <table className="w-full text-sm min-w-[860px]">
                <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
                  <tr>
                    <th className="text-left px-4 py-3">Ref / Asset</th><th className="text-left px-4 py-3">Type</th>
                    <th className="text-left px-4 py-3">Crit</th><th className="text-left px-4 py-3">Exposure</th>
                    <th className="text-left px-4 py-3">IP / Host</th><th className="text-left px-4 py-3">Ports</th>
                    <th className="text-left px-4 py-3">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {assets.map((a) => {
                    const open = (a.detail?.open_ports || []).filter((p) => p.open);
                    return (
                      <tr key={a.ref} data-testid={`asset-${a.ref}`} onClick={() => setSel(a)}
                        className={`border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer ${sel?.ref === a.ref ? "bg-secondary/50" : ""}`}>
                        <td className="px-4 py-3"><div className="font-mono text-xs" style={{ color: `hsl(${ACCENT})` }}>{a.ref}</div><div className="font-medium">{a.name}</div></td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{a.type}</td>
                        <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${critColor[a.criticality]} / 0.15)`, color: `hsl(${critColor[a.criticality]})` }}>{a.criticality}</span></td>
                        <td className="px-4 py-3 w-32">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${a.exposure}%`, background: a.exposure >= 70 ? "hsl(0 84% 60%)" : a.exposure >= 45 ? "hsl(35 90% 55%)" : "hsl(142 70% 45%)" }} /></div>
                            <span className="font-mono text-xs w-6">{a.exposure}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono text-[11px]">{(a.detail?.ips || [])[0] || <span className="text-muted-foreground/60">not resolved</span>}</td>
                        <td className="px-4 py-3">{open.length ? <span className="font-mono text-[11px]">{open.map((p) => p.port).join(", ")}</span> : <span className="text-muted-foreground/60 text-xs">—</span>}</td>
                        <td className="px-4 py-3"><div className="flex flex-col gap-1"><SourceBadge source={a.source} /><FreshnessBadge freshness={a.freshness} /></div></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {sel && (
          <aside data-testid="asset-detail-pane" className="hidden md:block md:w-80 shrink-0 md:sticky md:top-28 bg-card fact-border rounded-xl p-4 space-y-3" style={{ borderTop: `2px solid hsl(${ACCENT})` }}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0"><div className="font-mono text-[11px]" style={{ color: `hsl(${ACCENT})` }}>{sel.ref}</div><div className="font-head font-bold text-sm truncate">{sel.name}</div></div>
              <button data-testid="asset-detail-close" onClick={() => setSel(null)} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-0.5">
              <Kv k="Host" v={sel.detail?.host} mono />
              <Kv k="IP addresses" v={(sel.detail?.ips || []).join(", ") || "not resolved"} mono />
              <Kv k="Server" v={sel.detail?.server} />
              <Kv k="TLS" v={sel.detail?.tls?.ok ? `${sel.detail.tls.protocol} · ${sel.detail.tls.issuer}` : "not verified"} />
              <Kv k="Cert expires" v={sel.detail?.tls?.not_after} mono />
              <Kv k="Security score" v={sel.detail?.security_score != null ? `${sel.detail.security_score}/100` : null} mono />
              <Kv k="Open CVEs" v={sel.detail?.cves} mono />
              <Kv k="KEV matches" v={sel.detail?.kev_matches} mono />
              <Kv k="MITRE techniques" v={sel.detail?.mitre_techniques} mono />
              <Kv k="CWE weaknesses" v={sel.detail?.cwe_ids} mono />
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1"><Network className="w-3 h-3" /> Open ports</div>
              <div className="flex flex-wrap gap-1.5">
                {(sel.detail?.open_ports || []).length === 0 ? <span className="text-xs text-muted-foreground">No port data.</span> :
                  sel.detail.open_ports.map((p) => (
                    <span key={p.port} className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${p.open ? "bg-low/10 text-low border-low/20" : "bg-secondary/40 text-muted-foreground border-border"}`}>{p.port} {p.service}{p.open ? "" : " ·closed"}</span>
                  ))}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1"><Cpu className="w-3 h-3" /> Technologies</div>
              <div className="flex flex-wrap gap-1.5">
                {(sel.detail?.technologies || []).length === 0 ? <span className="text-xs text-muted-foreground">—</span> :
                  sel.detail.technologies.map((t, i) => <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-secondary/40">{t}</span>)}
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
