import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SourceBadge, FreshnessBadge } from "@/components/badges";
import { AIInsight } from "@/components/AIInsight";
import { StatCard, CardShell, EmptyState, Spinner } from "@/components/dash";
import { RiskDetailModal } from "@/components/RiskDetailModal";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { AutoActions } from "@/components/AutoActions";
import { Boxes, Server, ShieldCheck, Network, Laptop, Radio, Lock, X, Loader2, RefreshCw, Wrench } from "lucide-react";

const ACCENT = "35 92% 55%"; // Asset Intelligence → amber
const critColor = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };

export default function AssetIntelligence() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [d, setD] = useState(null);
  const [conn, setConn] = useState(null);
  const [deep, setDeep] = useState(null);
  const [deviceBusy, setDeviceBusy] = useState("");

  const loadConn = () => api.get("/self-scan/assets").then((r) => setConn(r.data)).catch(() => setConn(null));

  useEffect(() => {
    api.get("/dash/assets").then((r) => setD(r.data)).catch(() => setD({ assets: [], summary: {} }));
    loadConn();
  }, []);

  const deviceAction = async (id, action) => {
    setDeviceBusy(id + action);
    try {
      await api.post(`/self-scan/device/${encodeURIComponent(id)}/${action}`);
      toast.success(action === "sync" ? "Device sync requested" : "Compliance policy pushed");
      await loadConn();
    } catch {
      toast.error(action === "sync" ? "Sync failed" : "Auto-remediate failed");
    }
    setDeviceBusy("");
  };

  // Universal Deep-Dive — every asset row opens the same AI-native detail (risk score,
  // compliance alignment, grounded AI recommendation + fixes) as the rest of the platform.
  const openAsset = (a) => {
    const det = a.detail || {};
    const recs = [];
    if ((det.cves || 0) > 0) recs.push(`Patch ${det.cves} open CVE(s)${det.kev_matches ? ` incl. ${det.kev_matches} CISA-KEV (actively exploited)` : ""} on this asset, then re-run the live scan.`);
    const missing = det.security_headers?.missing || [];
    if (missing.length) recs.push(`Add the missing security headers: ${missing.join(", ")}.`);
    if (a.exposure >= 45) recs.push("Reduce internet exposure — restrict inbound access and close unused open ports.");
    if (!recs.length) recs.push("Maintain current hardening; keep dependencies pinned and re-scan on change.");
    setDeep({
      refLabel: a.ref, title: a.name, rating: a.criticality,
      score: det.security_score != null ? det.security_score : a.exposure,
      complianceRefs: ["NIST RA-5", "NIST SI-2", "ISO A.8.8", "CIS 7.4"],
      recommendedActions: recs,
      facets: [
        { icon: Server, label: "Type", value: a.type },
        { icon: Network, label: "IP / Host", value: (det.ips || [])[0] || det.host || "not resolved" },
        { icon: Lock, label: "TLS", value: det.tls?.ok ? `${det.tls.protocol} · ${det.tls.issuer}` : "not verified" },
        { icon: ShieldCheck, label: "Security score", value: det.security_score != null ? `${det.security_score}/100` : "—" },
        { icon: Boxes, label: "Open CVEs / KEV", value: `${det.cves ?? 0} CVE · ${det.kev_matches ?? 0} KEV` },
        { icon: Radio, label: "Exposure", value: `${a.exposure}/100${a.exposure >= 45 ? " · internet-facing" : ""}` },
      ],
      explainTitle: a.name, explainKind: "asset network exposure compliance cve remediation",
      explainContext: { asset: { ref: a.ref, name: a.name, type: a.type, criticality: a.criticality, exposure: a.exposure, detail: det } },
    });
  };

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
        <p className="text-sm text-muted-foreground mt-1">Live asset inventory enriched with network metadata — IPs, DNS, TLS, open ports, security headers &amp; exposure. Click any asset for an AI deep-dive with risk score, compliance alignment &amp; fixes.</p>
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

      {/* Inventory table — every row opens the universal AI deep-dive */}
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
                <th className="text-left px-4 py-3">Source</th><th className="text-right px-4 py-3">Detail</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => {
                const open = (a.detail?.open_ports || []).filter((p) => p.open);
                return (
                  <tr key={a.ref} data-testid={`asset-${a.ref}`} onClick={() => openAsset(a)}
                    className="border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer">
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
                    <td className="px-4 py-3 text-right"><span className="text-[10px] font-mono" style={{ color: `hsl(${ACCENT})` }}>Deep-dive →</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <RiskDetailModal item={deep} accent={ACCENT} onClose={() => setDeep(null)} />
    </div>
  );
}
