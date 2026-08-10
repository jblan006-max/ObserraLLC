import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, ScrollText, ShieldCheck, Download, FileText } from "lucide-react";
import { toast } from "sonner";
import { AIInsight } from "@/components/AIInsight";

export default function AuditLog() {
  const [logs, setLogs] = useState(null);
  const [actor, setActor] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [trustedOnly, setTrustedOnly] = useState(false);
  const [exporting, setExporting] = useState("");
  useEffect(() => { api.get("/audit-logs").then((r) => setLogs(r.data)); }, []);

  if (!logs) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  const actors = [...new Set(logs.map((l) => l.actor).filter(Boolean))].sort();
  const shown = logs.filter((l) => (!actor || l.actor === actor)
    && (!since || (l.ts || "").slice(0, 10) >= since)
    && (!until || (l.ts || "").slice(0, 10) <= until)
    && (!trustedOnly || (l.action || "").toLowerCase().includes("trusted")));

  const exportFile = async (fmt) => {
    setExporting(fmt);
    try {
      const { data } = await api.get(`/agents/runtime/audit-log.${fmt}${trustedOnly ? "?trusted=true" : ""}`, { responseType: "blob" });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url; a.download = `obserra-audit-log.${fmt}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Audit log exported (${fmt.toUpperCase()})`);
    } catch (e) {
      toast.error(e.response?.status === 403 ? "Export is admin-only." : "Export failed.");
    } finally { setExporting(""); }
  };

  return (
    <div className="rise space-y-5">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight">Immutable Audit Log</h1>
        <p className="text-sm text-muted-foreground mt-1">Every action, decision and access change recorded with tenant isolation. Append-only.</p>
      </div>

      <AIInsight dashboard="Audit Log" focus="who changed SAP access, remediation and de-provisioning actions, and any unusual privileged activity in the audit trail" accent="168 76% 46%" auto slug="audit-log" />

      <div className="flex flex-wrap items-center gap-2" data-testid="audit-filters">
        <select data-testid="audit-actor" value={actor} onChange={(e) => setActor(e.target.value)} className="bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary">
          <option value="">All actors</option>
          {actors.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <input data-testid="audit-since" type="date" value={since} onChange={(e) => setSince(e.target.value)} className="bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
        <input data-testid="audit-until" type="date" value={until} onChange={(e) => setUntil(e.target.value)} className="bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
        <button data-testid="audit-trusted-filter" onClick={() => setTrustedOnly((v) => !v)}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm border transition-colors ${trustedOnly ? "bg-ai/15 border-ai text-ai" : "bg-secondary/60 border-transparent text-muted-foreground hover:text-foreground"}`}>
          <ShieldCheck className="w-3.5 h-3.5" /> Trusted rule changes
        </button>
        {(actor || since || until || trustedOnly) && <button data-testid="audit-clear" onClick={() => { setActor(""); setSince(""); setUntil(""); setTrustedOnly(false); }} className="text-sm text-muted-foreground hover:text-foreground px-2">Clear</button>}
        <div className="ml-auto flex items-center gap-2">
          <button data-testid="audit-export-csv" onClick={() => exportFile("csv")} disabled={!!exporting} className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm bg-secondary/60 border border-border hover:bg-secondary disabled:opacity-50">
            {exporting === "csv" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} CSV
          </button>
          <button data-testid="audit-export-pdf" onClick={() => exportFile("pdf")} disabled={!!exporting} className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm bg-primary text-primary-foreground font-head font-bold disabled:opacity-50">
            {exporting === "pdf" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />} PDF
          </button>
        </div>
      </div>

      <div className="bg-card fact-border rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-border flex items-center gap-2 text-xs font-mono text-muted-foreground uppercase tracking-widest">
          <ShieldCheck className="w-3.5 h-3.5 text-low" /> {shown.length} of {logs.length} entries · tamper-evident{trustedOnly ? " · trusted rule changes" : ""}
        </div>
        <div className="divide-y divide-border/60">
          {shown.map((l, i) => (
            <div key={i} data-testid={`audit-${i}`} className="px-5 py-3 flex items-start gap-4 hover:bg-secondary/30 transition-colors">
              <ScrollText className="w-4 h-4 text-muted-foreground mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs text-ai">{l.action}</span>
                  <span className="text-[11px] text-muted-foreground">by {l.actor}</span>
                  {l.target && <span className="text-[11px] text-muted-foreground">→ {l.target}</span>}
                </div>
                <div className="text-sm text-foreground/90 truncate">{l.detail}</div>
              </div>
              <span className="text-[10px] font-mono text-muted-foreground whitespace-nowrap">{new Date(l.ts).toLocaleString()}</span>
            </div>
          ))}
          {shown.length === 0 && <div className="px-5 py-8 text-sm text-muted-foreground text-center">No entries match these filters.</div>}
        </div>
      </div>
    </div>
  );
}
