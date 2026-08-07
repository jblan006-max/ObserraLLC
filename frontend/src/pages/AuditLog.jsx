import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, ScrollText, ShieldCheck } from "lucide-react";

export default function AuditLog() {
  const [logs, setLogs] = useState(null);
  useEffect(() => { api.get("/audit-logs").then((r) => setLogs(r.data)); }, []);

  if (!logs) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-5">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight">Immutable Audit Log</h1>
        <p className="text-sm text-muted-foreground mt-1">Every action, decision and access recorded with tenant isolation. Append-only.</p>
      </div>

      <div className="bg-card fact-border rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-border flex items-center gap-2 text-xs font-mono text-muted-foreground uppercase tracking-widest">
          <ShieldCheck className="w-3.5 h-3.5 text-low" /> {logs.length} entries · tamper-evident
        </div>
        <div className="divide-y divide-border/60">
          {logs.map((l, i) => (
            <div key={i} data-testid={`audit-${i}`} className="px-5 py-3 flex items-start gap-4 hover:bg-secondary/30 transition-colors">
              <ScrollText className="w-4 h-4 text-muted-foreground mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-ai">{l.action}</span>
                  <span className="text-[11px] text-muted-foreground">by {l.actor}</span>
                </div>
                <div className="text-sm text-foreground/90 truncate">{l.detail}</div>
              </div>
              <span className="text-[10px] font-mono text-muted-foreground whitespace-nowrap">{new Date(l.ts).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
