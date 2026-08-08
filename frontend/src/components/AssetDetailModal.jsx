import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { X, Loader2, Network, Cpu, ShieldCheck, Lock, AlertTriangle, Wrench } from "lucide-react";

// Full asset drill-down: live network metadata + vulnerability data + fix recommendations.
export function AssetDetailModal({ assetRef, findings = [], accent = "35 92% 55%", onClose }) {
  const [asset, setAsset] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!assetRef) { setAsset(null); return; }
    setLoading(true);
    api.get("/dash/assets")
      .then((r) => setAsset((r.data.assets || []).find((a) => a.ref === assetRef) || { ref: assetRef, detail: {} }))
      .catch(() => setAsset({ ref: assetRef, detail: {} }))
      .finally(() => setLoading(false));
  }, [assetRef]);

  if (!assetRef) return null;
  const d = asset?.detail || {};
  const recs = [];
  (d.security_headers?.missing || []).forEach((h) => recs.push(`Enable missing security header: ${h}`));
  if ((d.cves || 0) > 0) recs.push(`Patch ${d.cves} dependency CVE(s) detected on this endpoint`);
  if ((d.kev_matches || 0) > 0) recs.push(`Prioritise ${d.kev_matches} CISA KEV-listed vulnerabilit(ies) — actively exploited in the wild`);
  findings.filter((f) => f.status !== "pass" && f.remediation).slice(0, 4).forEach((f) => recs.push(f.remediation));
  if (!recs.length) recs.push("No open remediation — maintain current hardening, headers and monitoring.");

  const Kv = ({ k, v }) => (
    <div className="flex items-start justify-between gap-3 text-xs py-1 border-b border-border/40 last:border-0">
      <span className="text-muted-foreground shrink-0">{k}</span><span className="text-right break-all font-mono">{v ?? "—"}</span>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div data-testid="asset-detail-modal" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl max-h-[85vh] overflow-y-auto bg-card border rounded-2xl p-6 space-y-4 rise"
        style={{ borderColor: `hsl(${accent} / 0.4)`, boxShadow: `inset 0 1px 0 hsl(${accent} / 0.3)` }}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[11px]" style={{ color: `hsl(${accent})` }}>{asset?.ref || assetRef}</div>
            <div className="font-head font-black text-xl tracking-tight truncate">{asset?.name || "Asset"}</div>
            <div className="text-xs text-muted-foreground">{asset?.type} · {asset?.criticality} criticality · exposure {asset?.exposure ?? "—"}</div>
          </div>
          <button data-testid="asset-modal-close" onClick={onClose} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-1 bg-secondary/20 rounded-lg p-3">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><Network className="w-3 h-3" /> Network metadata</div>
              <Kv k="Host" v={d.host} />
              <Kv k="IP addresses" v={(d.ips || []).join(", ") || "not resolved"} />
              <Kv k="DNS aliases" v={(d.dns_aliases || []).join(", ") || "—"} />
              <Kv k="Server" v={d.server} />
              <Kv k="TLS" v={d.tls?.ok ? `${d.tls.protocol} · ${d.tls.issuer}` : "not verified"} />
              <Kv k="Cert expires" v={d.tls?.not_after} />
              <Kv k="Security score" v={d.security_score != null ? `${d.security_score}/100` : null} />
            </div>
            <div className="space-y-3">
              <div className="bg-secondary/20 rounded-lg p-3">
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Vulnerability data</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-crit/10 rounded-md p-2"><div className="text-[10px] text-muted-foreground">Open CVEs</div><div className="font-head font-black text-lg text-crit">{d.cves ?? 0}</div></div>
                  <div className="bg-crit/10 rounded-md p-2"><div className="text-[10px] text-muted-foreground">KEV matches</div><div className="font-head font-black text-lg text-crit">{d.kev_matches ?? 0}</div></div>
                  <div className="bg-secondary/40 rounded-md p-2"><div className="text-[10px] text-muted-foreground">MITRE techniques</div><div className="font-head font-black text-lg">{d.mitre_techniques ?? 0}</div></div>
                  <div className="bg-secondary/40 rounded-md p-2"><div className="text-[10px] text-muted-foreground">CWE weaknesses</div><div className="font-head font-black text-lg">{d.cwe_ids ?? 0}</div></div>
                </div>
              </div>
              <div className="bg-secondary/20 rounded-lg p-3">
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1"><Cpu className="w-3 h-3" /> Open ports</div>
                <div className="flex flex-wrap gap-1.5">
                  {(d.open_ports || []).length === 0 ? <span className="text-xs text-muted-foreground">No port data.</span> :
                    d.open_ports.map((p) => <span key={p.port} className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${p.open ? "bg-low/10 text-low border-low/20" : "bg-secondary/40 text-muted-foreground border-border"}`}>{p.port} {p.service}</span>)}
                </div>
              </div>
            </div>

            <div className="sm:col-span-2 space-y-1 bg-secondary/20 rounded-lg p-3">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><Lock className="w-3 h-3" /> Security headers</div>
              {!d.security_headers ? <span className="text-xs text-muted-foreground">Run a live scan to populate header posture.</span> : (
                <div className="flex flex-wrap gap-1.5">
                  {(d.security_headers.present || []).map((h) => <span key={h} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/10 text-low border border-low/20">{h}</span>)}
                  {(d.security_headers.missing || []).map((h) => <span key={h} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-crit/10 text-crit border border-crit/20 line-through">{h}</span>)}
                </div>
              )}
            </div>

            <div className="sm:col-span-2 rounded-lg p-3 border" style={{ borderColor: `hsl(${accent} / 0.35)`, background: `hsl(${accent} / 0.06)` }}>
              <div className="text-[10px] font-mono uppercase tracking-wider mb-1.5 flex items-center gap-1" style={{ color: `hsl(${accent})` }}><Wrench className="w-3 h-3" /> Recommendations to fix</div>
              <ul className="space-y-1.5" data-testid="asset-modal-recs">
                {recs.map((r, i) => (
                  <li key={i} className="text-sm flex items-start gap-2"><span style={{ color: `hsl(${accent})` }}>→</span> {r}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
