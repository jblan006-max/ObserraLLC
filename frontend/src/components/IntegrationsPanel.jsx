import { useState } from "react";
import { KeyRound, ShieldAlert, Radar, Plug, RefreshCw, Loader2, Zap } from "lucide-react";
import { FreshnessBadge } from "@/components/badges";

const ICONS = { identity: KeyRound, vuln: ShieldAlert, shadow: Radar };

export function IntegrationsPanel({ integrations, onAction, running }) {
  return (
    <div className="grid md:grid-cols-3 gap-4" data-testid="integrations-panel">
      {integrations.map((intg) => {
        const Icon = ICONS[intg.icon] || Plug;
        return (
          <div key={intg.id} data-testid={`integration-${intg.id}`}
            className="relative bg-card fact-border rounded-lg p-4 overflow-hidden group hover:border-primary/40 transition-colors duration-200">
            <div className="absolute -right-6 -top-6 w-24 h-24 rounded-full bg-primary/5 group-hover:bg-primary/10 transition-colors" />
            <div className="relative flex items-start justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <span className="w-9 h-9 rounded-md bg-primary/15 border border-primary/30 flex items-center justify-center">
                  <Icon className="w-4.5 h-4.5 text-primary" style={{ width: 18, height: 18 }} />
                </span>
                <div>
                  <div className="font-head font-bold text-sm leading-tight">{intg.name}</div>
                  <div className="text-[10px] font-mono text-muted-foreground uppercase">{intg.category}</div>
                </div>
              </div>
              <FreshnessBadge freshness="live" />
            </div>
            <div className="relative flex items-center gap-3 text-[10px] font-mono text-muted-foreground mb-3">
              <span className="px-1.5 py-0.5 rounded-sm bg-low/15 text-low">CONNECTED</span>
              <span>{intg.records?.toLocaleString()} recs</span>
              <span className="px-1.5 py-0.5 rounded-sm border border-med/40 text-med">{intg.sync_mode}</span>
            </div>
            <div className="relative space-y-1.5">
              {intg.actions.map((a) => {
                const isRun = running === a.id;
                const isSync = a.id.endsWith("_sync");
                return (
                  <button key={a.id} data-testid={`action-${a.id}`} disabled={!!running}
                    onClick={() => onAction(a.id)}
                    className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-md text-xs font-medium transition-all duration-200 disabled:opacity-50 ${
                      isSync ? "bg-secondary/60 hover:bg-secondary text-foreground"
                             : "bg-primary/10 hover:bg-primary/20 border border-primary/30 text-foreground"}`}>
                    <span className="flex items-center gap-1.5">
                      {isRun ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : isSync ? <RefreshCw className="w-3.5 h-3.5" /> : <Zap className="w-3.5 h-3.5 text-primary" />}
                      {a.label}
                    </span>
                    {a.impact && <span className="text-[10px] font-mono text-muted-foreground">{a.impact}</span>}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
