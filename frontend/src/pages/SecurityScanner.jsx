import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ShieldCheck, Loader2, AlertTriangle, CheckCircle2, XCircle, Bug, RefreshCw } from "lucide-react";

const SEV = {
  critical: { c: "0 84% 60%", label: "Critical" },
  high: { c: "15 80% 55%", label: "High" },
  medium: { c: "35 90% 55%", label: "Medium" },
  low: { c: "48 90% 55%", label: "Low" },
  info: { c: "199 70% 50%", label: "Info" },
};
const scoreCol = (v) => (v >= 85 ? "142 70% 45%" : v >= 65 ? "35 90% 55%" : "0 84% 60%");
const rel = (iso) => (iso ? new Date(iso).toLocaleString() : "never");

export default function SecurityScanner() {
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const load = () => api.get("/self-scan/latest").then((r) => setScan(r.data && r.data.id ? r.data : null)).catch(() => setScan(null)).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const run = async () => {
    setRunning(true);
    toast.info("Running live self-scan (headers, CORS, OSV CVEs, CISA KEV)…");
    try {
      const { data } = await api.post("/self-scan/run");
      setScan(data);
      toast.success(`Scan complete — score ${data.score}/100 · compliance auto-updated`);
    } catch (e) {
      toast.error("Scan failed. Check backend logs.");
    }
    setRunning(false);
  };

  const s = scan?.summary || {};
  const findings = scan?.findings || [];
  const fails = findings.filter((f) => f.status === "fail");
  const passes = findings.filter((f) => f.status === "pass");

  return (
    <div className="rise space-y-6" data-testid="security-scanner-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Bug className="w-7 h-7 text-crit" /> Self Vulnerability Scanner</h1>
          <p className="text-sm text-muted-foreground mt-1">Live, evidence-based security test of this platform — hardening headers, CORS, dependency CVEs (OSV.dev) and CISA KEV cross-reference. Results auto-update the compliance crosswalk.</p>
        </div>
        <button data-testid="run-scan-btn" onClick={run} disabled={running} className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50 flex items-center gap-2">
          {running ? <><Loader2 className="w-4 h-4 animate-spin" /> Scanning…</> : <><RefreshCw className="w-4 h-4" /> Run live scan</>}
        </button>
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
