import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SourceBadge, FreshnessBadge } from "@/components/badges";
import { AIInsight } from "@/components/AIInsight";
import { StatCard, CardShell, EmptyState, Spinner } from "@/components/dash";
import { RiskDetailModal } from "@/components/RiskDetailModal";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { AutoActions } from "@/components/AutoActions";
import { ConnectorHealth } from "@/components/ConnectorHealth";
import { Boxes, Server, ShieldCheck, Network, Laptop, Radio, Lock, X, Loader2, RefreshCw, Wrench, Fingerprint, ShieldAlert, Check, MapPin, DollarSign, User } from "lucide-react";

const ACCENT = "35 92% 55%"; // Asset Intelligence → amber
const critColor = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
const money = (n) => (n == null ? "—" : n >= 1e6 ? "$" + (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? "$" + Math.round(n / 1e3) + "k" : "$" + Math.round(n || 0));
const worst = (list) => ["Critical", "High", "Medium", "Low"].find((r) => list.includes(r)) || "Low";

export default function AssetIntelligence() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [d, setD] = useState(null);
  const [conn, setConn] = useState(null);
  const [deep, setDeep] = useState(null);
  const [deviceBusy, setDeviceBusy] = useState("");
  const [disc, setDisc] = useState(null);
  const [actions, setActions] = useState(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [actionResult, setActionResult] = useState(null);

  const loadConn = () => api.get("/self-scan/assets").then((r) => setConn(r.data)).catch(() => setConn(null));
  const loadActions = () => api.get("/connectors/discovery-actions").then((r) => setActions(r.data)).catch(() => setActions({ actions: [], open: 0 }));
  const loadDisc = () => api.get("/risk-engine/discovered").then((r) => setDisc(r.data)).catch(() => setDisc({ assets: [], total_ale: 0, count: 0 }));

  useEffect(() => {
    api.get("/dash/assets").then((r) => setD(r.data)).catch(() => setD({ assets: [], summary: {} }));
    loadDisc();
    loadConn();
    loadActions();
  }, []);
  useEffect(() => { setActionResult(null); }, [deep?.taskId]);

  const resolveAction = async (id) => {
    try { await api.post(`/connectors/discovery-actions/${id}/resolve`); toast.success("Action resolved"); loadActions(); }
    catch { toast.error("Could not resolve action"); }
  };

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

  // No-Mock action hub inside the deep-dive — dispatches a REAL call to the asset's live source
  // (Intune via Microsoft Graph, or the live self-scan autofix), then reflects the honest result.
  const assetAction = async (kind) => {
    const act = deep?.action;
    if (!act) return;
    setDetailBusy(true);
    try {
      if (act.type === "device") {
        const ep = kind === "soc" ? "sync" : "remediate";
        const { data } = await api.post(`/self-scan/device/${encodeURIComponent(act.id)}/${ep}`);
        const verified = kind === "accept" ? false : (data?.verified ?? true);
        setActionResult({ taskId: deep.taskId, verified, status: data?.status || (kind === "accept" ? "Accepted" : "Applied"), provider: "Microsoft Intune (Graph)", message: data?.message || (kind === "soc" ? "Device sync requested via Microsoft Graph." : "Compliance policy pushed to device via Microsoft Graph, then re-synced to verify."), external: data });
        toast.success("Real Intune action dispatched");
        await loadConn();
      } else if (act.type === "scan") {
        const { data } = await api.post(`/self-scan/autofix`);
        setActionResult({ taskId: deep.taskId, verified: data?.verified ?? false, status: data?.status || "In Progress", provider: "Live Self-Scan", message: data?.message || "AI autofix launched against live findings.", external: data });
        toast.success(data?.message || "AI Autofix launched");
      } else {
        setActionResult({ taskId: deep.taskId, verified: false, status: "Not applied", provider: act.source || "provider", message: `Connect ${act.source || "this asset's source"} in Available Connectors with a live write-scoped key to enable real remediation — no status is flipped without a verified provider call.` });
      }
    } catch (e) {
      setActionResult({ taskId: deep.taskId, verified: false, status: "Not applied", provider: "provider", message: e.response?.data?.detail || "The live provider call failed — raw error recorded to the Defensibility Ledger." });
    }
    setDetailBusy(false);
  };

  // ---- Universal deep-dive builders (rating + live score + AI brief + metadata-aware fixes) ----
  const openAsset = (a) => {
    const det = a.detail || {};
    const ip = (det.ips || [])[0] || det.host;
    const recs = [];
    if ((det.cves || 0) > 0) recs.push(`Patch ${det.cves} open CVE(s)${det.kev_matches ? ` incl. ${det.kev_matches} CISA-KEV (actively exploited)` : ""} on ${a.name}${ip ? ` (${ip})` : ""}, then re-run the live scan — this retires its contribution to the Strategic Risk Score.`);
    const missing = det.security_headers?.missing || [];
    if (missing.length) recs.push(`Add the missing security headers on ${ip || a.name}: ${missing.join(", ")}.`);
    if (a.exposure >= 45) recs.push(`Reduce internet exposure on ${ip || a.name} — restrict inbound access and close unused open ports.`);
    if (!recs.length) recs.push("Maintain current hardening; keep dependencies pinned and re-scan on change.");
    setDeep({
      refLabel: a.ref, title: a.name, rating: a.criticality,
      score: det.security_score != null ? det.security_score : a.exposure, ale: a.residual_ale,
      complianceRefs: ["NIST RA-5", "NIST SI-2", "ISO A.8.8", "CIS 7.4"],
      recommendedActions: recs,
      taskId: (det.cves || 0) > 0 ? `scan:${a.ref}` : undefined,
      action: { type: "scan", source: a.source },
      facets: [
        { icon: Server, label: "Type / Source", value: `${a.type} · ${a.source}` },
        { icon: Network, label: "IP / Host", value: ip || "not resolved" },
        { icon: Radio, label: "MAC address", value: a.network?.mac || det.mac || "not provided by source" },
        { icon: MapPin, label: "Site / location", value: a.network?.site || det.site || "—" },
        { icon: Lock, label: "TLS", value: det.tls?.ok ? `${det.tls.protocol} · ${det.tls.issuer}` : "not verified" },
        { icon: Boxes, label: "Open CVEs / KEV", value: `${det.cves ?? 0} CVE · ${det.kev_matches ?? 0} KEV` },
      ],
      explainTitle: a.name, explainKind: "asset network exposure compliance cve remediation ip mac site strategic-risk-score",
      explainContext: { asset: { ref: a.ref, name: a.name, type: a.type, criticality: a.criticality, exposure: a.exposure, ip, detail: det } },
    });
  };

  const openDiscovered = (a) => {
    const net = a.network || {};
    const high = a.rating === "High" || a.rating === "Critical";
    setDeep({
      refLabel: a.ref, title: a.name, rating: a.rating, score: a.exposure ?? a.score, ale: a.residual_ale,
      complianceRefs: ["NIST RA-5", "NIST AC-2", "ISO A.8.1"],
      recommendedActions: [
        `${a.name} (${a.type}) is mapped live from ${a.source}. Its metadata — IP ${net.ip || "n/a"}, MAC ${net.mac || "n/a"}, site ${net.site || "n/a"} — feeds the Unified Risk Correlation Engine and contributes ${money(a.residual_ale)} to the Strategic Risk Score.`,
        high ? "Prioritise: bring the asset to compliance / least-privilege at the source, then let the daily zero-touch re-probe retire its ALE contribution." : "Sustain posture — the daily zero-touch health check re-probes and re-prices this asset automatically.",
      ],
      facets: [
        { icon: Server, label: "Type / Source", value: `${a.type} · ${a.source}` },
        { icon: Network, label: "IP address", value: net.ip || "not provided by source" },
        { icon: Radio, label: "MAC address", value: net.mac || "not provided by source" },
        { icon: MapPin, label: "Site / location", value: net.site || "—" },
        { icon: DollarSign, label: "Strategic Risk Score (ALE)", value: money(a.residual_ale) },
        { icon: ShieldCheck, label: "Rating", value: a.rating },
      ],
      explainTitle: a.name, explainKind: "discovered asset metadata ip mac site strategic-risk-score remediation",
      explainContext: { asset: a },
    });
  };

  const openDevice = (dv) => {
    const nc = dv.compliance === "noncompliant";
    setDeep({
      refLabel: (dv.id || "device").slice(0, 14), title: dv.name, rating: nc ? "High" : "Medium", score: nc ? 70 : 30,
      complianceRefs: ["NIST CM-2", "NIST SI-2", "CIS 4.1"],
      taskId: `dev:${dv.id}`, action: { type: "device", id: dv.id },
      recommendedActions: [
        `${dv.name} — owner ${dv.owner || "—"}, ${dv.os || ""} ${dv.os_version || ""}. IP ${dv.ip || "n/a"} · MAC ${dv.mac || "n/a"} · site ${dv.site || "n/a"}. Current state: ${dv.compliance || "unknown"}.`,
        nc ? "Execute Fix pushes the Intune compliance policy via Microsoft Graph, then re-syncs to verify — retiring this device's Strategic Risk Score contribution." : "Device compliant — keep policy synced; the daily check re-verifies automatically.",
      ],
      facets: [
        { icon: Laptop, label: "Device / OS", value: `${dv.name} · ${dv.os || "—"} ${dv.os_version || ""}` },
        { icon: User, label: "Owner", value: dv.owner || "—" },
        { icon: Network, label: "IP address", value: dv.ip || "not provided by Intune" },
        { icon: Radio, label: "MAC address", value: dv.mac || "not provided by Intune" },
        { icon: MapPin, label: "Site / location", value: dv.site || "—" },
        { icon: ShieldCheck, label: "Compliance", value: dv.compliance || "unknown" },
      ],
      explainTitle: dv.name, explainKind: "managed device intune compliance ip mac site remediation strategic-risk-score",
      explainContext: { device: dv },
    });
  };

  const openCard = ({ title, refLabel, rating, facets, recs, kind, ctx }) => setDeep({
    refLabel, title, rating, facets, recommendedActions: recs,
    explainTitle: title, explainKind: kind, explainContext: ctx,
  });

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
        <p className="text-sm text-muted-foreground mt-1">Live asset inventory hydrated with connection metadata — IP, MAC &amp; site — from every connected source. Click any card for the AI deep-dive: risk rating, live score, grounded recommendation &amp; a metadata-aware fix wired to the real SaaS connector.</p>
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

      <ConnectorHealth accent={ACCENT} />

      {actions?.actions?.length > 0 && (
        <CardShell testid="discovery-actions" title="Discovery actions — auto-opened" icon={ShieldAlert} accent="0 84% 60%"
          right={<span className="text-[10px] font-mono text-muted-foreground">{actions.open} open · {actions.total} total</span>}>
          <p className="text-[11px] text-muted-foreground mb-2">Opened automatically the moment discovery finds a non-compliant device, a privileged/guest identity, or a degraded connector — so exposure is actioned as it appears.</p>
          <div className="space-y-2">
            {actions.actions.slice(0, 20).map((ac) => (
              <div key={ac.id} data-testid={`disc-action-${ac.id}`} className="flex items-start gap-3 bg-secondary/30 rounded-lg px-3 py-2.5">
                <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full shrink-0 ${ac.status === "open" ? "bg-crit/15 text-crit" : "bg-low/15 text-low"}`}>{ac.status}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{ac.reason}</div>
                  <div className="text-[10px] font-mono text-muted-foreground">{ac.kind} · {ac.asset_name} · {new Date(ac.created_at).toLocaleString()}</div>
                </div>
                {isAdmin && ac.status === "open" && (
                  <button data-testid={`resolve-action-${ac.id}`} onClick={() => resolveAction(ac.id)}
                    className="shrink-0 text-[11px] flex items-center gap-1 px-2.5 py-1 rounded-md bg-low/10 border border-low/30 text-low hover:bg-low/20 transition-colors"><Check className="w-3 h-3" /> Resolve</button>
                )}
              </div>
            ))}
          </div>
        </CardShell>
      )}

      {disc?.assets?.length > 0 && (
        <CardShell testid="discovered-assets" title="Discovered live assets" icon={Fingerprint} accent={ACCENT}
          right={<span className="text-[10px] font-mono text-muted-foreground">{disc.count} assets · {money(disc.total_ale)} ALE contributed</span>}>
          <p className="text-[11px] text-muted-foreground mb-2">Connected-SaaS devices, users, connectors, repos &amp; CMDB CIs mapped live into the Risk Engine — IP/MAC/site + posture priced into the Strategic Risk Score. Click any row for the deep-dive.</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[760px]">
              <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
                <tr>
                  <th className="text-left px-3 py-2">Ref / Asset</th><th className="text-left px-3 py-2">Type</th>
                  <th className="text-left px-3 py-2">Source</th><th className="text-left px-3 py-2">IP</th>
                  <th className="text-left px-3 py-2">MAC</th><th className="text-left px-3 py-2">Site</th>
                  <th className="text-left px-3 py-2">Rating</th><th className="text-right px-3 py-2">ALE contrib.</th>
                </tr>
              </thead>
              <tbody>
                {disc.assets.map((a) => (
                  <tr key={a.ref} data-testid={`discovered-${a.ref}`} onClick={() => openDiscovered(a)}
                    className="border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer">
                    <td className="px-3 py-2"><div className="font-mono text-[11px]" style={{ color: `hsl(${ACCENT})` }}>{a.ref}</div><div className="font-medium truncate max-w-[180px]">{a.name}</div></td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{a.type}</td>
                    <td className="px-3 py-2 text-xs">{a.source}</td>
                    <td className="px-3 py-2 font-mono text-[11px]">{a.network?.ip || <span className="text-muted-foreground/60">—</span>}</td>
                    <td className="px-3 py-2 font-mono text-[11px]">{a.network?.mac || <span className="text-muted-foreground/60">—</span>}</td>
                    <td className="px-3 py-2 text-[11px] truncate max-w-[160px]">{a.network?.site || <span className="text-muted-foreground/60">—</span>}</td>
                    <td className="px-3 py-2"><span className="text-[10px] font-mono px-1.5 py-0.5 rounded-sm" style={{ background: `hsl(${critColor[a.rating] || critColor.Low} / 0.15)`, color: `hsl(${critColor[a.rating] || critColor.Low})` }}>{a.rating}</span></td>
                    <td className="px-3 py-2 text-right font-mono text-xs" style={{ color: `hsl(${ACCENT})` }}>{money(a.residual_ale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardShell>
      )}

      {/* Secondary card grid — every card clickable → deep-dive */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <CardShell testid="asset-criticality" title="Assets by criticality" icon={Boxes} accent={ACCENT}
          right={<span className="text-[10px] font-mono text-ai">Deep-dive →</span>}>
          <div className="grid grid-cols-2 gap-3 cursor-pointer" onClick={() => openCard({
            title: "Assets by criticality", refLabel: "PORTFOLIO", rating: worst(["Critical", "High", "Medium", "Low"].filter((t) => (byCrit[t] || 0) > 0)),
            facets: ["Critical", "High", "Medium", "Low"].map((t) => ({ icon: Boxes, label: t, value: `${byCrit[t] ?? 0} asset(s)` })),
            recs: [`${byCrit.Critical || 0} Critical / ${byCrit.High || 0} High assets drive most of the Strategic Risk Score — remediate these first for the biggest ALE reduction.`, "Re-run the live scan after fixes to re-rate the portfolio."],
            kind: "asset criticality distribution strategic-risk-score", ctx: { by_criticality: byCrit, summary: s },
          })}>
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
            <div className="space-y-1.5 cursor-pointer" onClick={() => openCard({
              title: "Endpoint security headers", refLabel: "HEADERS", rating: hdr.score >= 70 ? "Low" : hdr.score >= 40 ? "Medium" : "High", 
              facets: [{ icon: ShieldCheck, label: "Header score", value: `${hdr.score}%` }, { icon: Lock, label: "Present", value: (hdr.present || []).join(", ") || "—" }, { icon: X, label: "Missing", value: (hdr.missing || []).join(", ") || "none" }],
              recs: (hdr.missing || []).length ? [`Add the missing headers: ${(hdr.missing || []).join(", ")} — each closes a specific web-exposure vector and raises the endpoint score.`] : ["All key headers present — sustain and re-scan on deploy."],
              kind: "security headers hardening web exposure", ctx: { headers: hdr },
            })}>
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
                <div key={i} data-testid={`asset-source-${i}`} onClick={() => openCard({
                  title: `Source — ${src.name}`, refLabel: "SOURCE", rating: src.status === "live" ? "Low" : "Medium",
                  facets: [{ icon: Radio, label: "Source", value: src.name }, { icon: ShieldCheck, label: "Status", value: src.status }],
                  recs: [src.status === "live" ? `${src.name} is live — its inventory feeds asset metadata (IP/MAC/site) into the Risk Engine.` : `Reconnect ${src.name} in Available Connectors to resume live metadata ingestion.`],
                  kind: "connector source health metadata ingestion", ctx: { source: src },
                })}
                  className="flex items-center justify-between text-xs bg-secondary/30 hover:bg-secondary/60 rounded-md px-3 py-2 cursor-pointer transition-colors">
                  <span className="font-medium truncate">{src.name}</span>
                  <span className={`font-mono text-[10px] px-2 py-0.5 rounded-full ${src.status === "live" ? "bg-low/15 text-low" : "bg-secondary/60 text-muted-foreground"}`}>{src.status}</span>
                </div>
              ))}
            </div>
          )}
        </CardShell>
      </div>

      {/* Managed devices (Intune) — every device card opens a real-action deep-dive */}
      <CardShell testid="asset-devices" title="Managed devices (Microsoft Intune)" icon={Laptop} accent={ACCENT}
        right={devices?.available && <span className="text-[10px] font-mono text-muted-foreground">{devices.total} devices · <span className="text-low">{devices.compliant} compliant</span> · <span className="text-crit">{devices.noncompliant} non-compliant</span></span>}>
        {!devices?.available ? (
          <EmptyState icon={Laptop} text={devices?.note || "Connect Microsoft 365 (Intune) to inventory managed devices, their OS, owner, IP/MAC/site and compliance state."}
            cta={<a href="/app/connectors" className="text-xs font-head font-bold px-3 py-1.5 rounded-full" style={{ background: `hsl(${ACCENT})`, color: "#050810" }}>Connect Microsoft 365</a>} />
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {(devices.items || []).map((dv) => (
              <div key={dv.id} data-testid={`device-${dv.id}`} onClick={() => openDevice(dv)} className="bg-secondary/30 hover:bg-secondary/60 rounded-md p-3 text-xs cursor-pointer transition-colors">
                <div className="font-medium truncate">{dv.name}</div>
                <div className="text-muted-foreground truncate">{dv.owner || "—"} · {dv.os || "—"} {dv.os_version || ""}</div>
                <div className="text-[10px] font-mono text-muted-foreground/80 truncate">IP {dv.ip || "n/a"} · MAC {dv.mac || "n/a"}</div>
                <span className={`inline-block mt-1 font-mono text-[9px] px-1.5 py-0.5 rounded-sm ${dv.compliance === "compliant" ? "bg-low/15 text-low" : "bg-crit/15 text-crit"}`}>{dv.compliance || "unknown"}</span>
                {isAdmin && (
                  <div className="flex gap-1.5 mt-2" onClick={(e) => e.stopPropagation()}>
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

      <RiskDetailModal item={deep} accent={ACCENT} busy={detailBusy} result={actionResult} onClose={() => setDeep(null)} onAction={assetAction} />
    </div>
  );
}
