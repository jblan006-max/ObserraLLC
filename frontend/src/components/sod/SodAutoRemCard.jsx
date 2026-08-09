// Extracted from SodCommandCenter for maintainability (no behavior change).
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Bot, Mail } from "lucide-react";
import { SEV, Chip, ACTION_LABEL } from "@/components/sod/sodPrimitives";
import { useSod } from "@/context/SodContext";

export function SodAutoRemCard() {
  const { arem, aremBusy, data, digestBusy, rules, runArem, saveArem, sendDigest, sev, toggleSev } = useSod();
  return (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sod-autorem">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2"><Bot className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-base">SoD → ServiceNow Auto-Remediation</h2></div>
            <span data-testid="autorem-state" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${arem.config.enabled ? "bg-low/15 text-low" : "bg-secondary text-muted-foreground"}`}>{arem.config.enabled ? "ACTIVE" : "OFF"}</span>
            <div className="flex-1" />
            <div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">Enable engine</span><Switch data-testid="autorem-toggle" checked={arem.config.enabled} disabled={aremBusy} onCheckedChange={(v) => saveArem({ enabled: v })} /></div>
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">When enabled, the platform automatically opens a ServiceNow workflow for every account carrying an open SoD conflict of a watched severity — closing risk without a human click. A daily scheduled sweep (folded into the platform cron, 08:00 UTC) runs it unattended and emails the SAP Access Governance Digest.</p>
          <div className="flex flex-wrap items-center gap-3 mt-2">
            {arem.config.last_cron_at && (
              <span className="text-[10px] font-mono text-muted-foreground" data-testid="autorem-last-cron">Last scheduled sweep {new Date(arem.config.last_cron_at).toLocaleString()} · {arem.config.last_cron_count ?? 0} opened</span>
            )}
            <div className="flex-1" />
            <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="autorem-digest" onClick={sendDigest} disabled={digestBusy}><Mail className="w-3.5 h-3.5" />{digestBusy ? "Sending…" : "Email governance digest"}</Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Trigger severities</div>
              <div className="flex gap-1.5">{["Critical", "High", "Medium"].map((s) => {
                const on = arem.config.severities.includes(s);
                return <button key={s} data-testid={`autorem-sev-${s}`} onClick={() => toggleSev(s)} disabled={aremBusy} className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-full border transition-opacity" style={{ borderColor: `hsl(${SEV[s]} / ${on ? 0.6 : 0.25})`, background: `hsl(${SEV[s]} / ${on ? 0.15 : 0})`, color: `hsl(${SEV[s]})`, opacity: on ? 1 : 0.45 }}>{s}</button>;
              })}</div>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Remediation action</div>
              <Select value={arem.config.action} onValueChange={(v) => saveArem({ action: v })}><SelectTrigger data-testid="autorem-action" className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>{Object.entries(ACTION_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Pending candidates</div>
              <div className="flex items-center gap-3">
                <span className="font-head font-black text-2xl" style={{ color: `hsl(${arem.candidates > 0 ? "0 84% 60%" : "142 70% 45%"})` }} data-testid="autorem-candidates">{arem.candidates}</span>
                <Button size="sm" className="h-8" data-testid="autorem-run" onClick={runArem} disabled={aremBusy || arem.candidates === 0}>{aremBusy ? "Running…" : "Run now"}</Button>
              </div>
            </div>
          </div>
          {arem.log.length > 0 && (
            <div className="mt-4 border-t border-border pt-3">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Recent auto-remediations · {arem.remediated_total}</div>
              <div className="space-y-1 max-h-[160px] overflow-y-auto pr-1" data-testid="autorem-log">
                {arem.log.slice(0, 12).map((l, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <Chip v={l.severity} />
                    <span className="font-mono text-muted-foreground">{l.ticket_number}</span>
                    <span className="font-medium whitespace-nowrap">{l.sap_user}</span>
                    <span className="text-muted-foreground truncate">{l.rules.join(", ")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
  );
}
