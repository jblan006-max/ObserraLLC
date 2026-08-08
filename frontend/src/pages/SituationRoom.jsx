import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { motion } from "framer-motion";
import { ScorePill } from "@/components/badges";
import { AIInsight } from "@/components/AIInsight";
import { AIFix } from "@/components/AIFix";
import { StatCard } from "@/components/dash";
import { useDeepDive } from "@/context/DeepDiveContext";
import { Radar, AlertOctagon, Ban, ShieldAlert, Loader2, Activity, X, ChevronRight } from "lucide-react";

const ACCENT = "190 90% 50%"; // Situation Room → cyan

function RiskModal({ risk, onClose }) {
  if (!risk) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div data-testid="situation-risk-modal" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl max-h-[86vh] overflow-y-auto bg-card border rounded-2xl p-6 space-y-4 rise"
        style={{ borderColor: `hsl(${ACCENT} / 0.4)`, boxShadow: `inset 0 1px 0 hsl(${ACCENT} / 0.3)` }}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[11px]" style={{ color: `hsl(${ACCENT})` }}>{risk.ref}</div>
            <div className="font-head font-black text-xl tracking-tight break-words">{risk.title}</div>
            <div className="text-xs text-muted-foreground">{risk.owner} · {risk.business_impact} · {risk.status}</div>
          </div>
          <button data-testid="situation-risk-close" onClick={onClose} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>
        <div className="flex items-center gap-3">
          <ScorePill value={risk.residual} />
          <div className="text-xs text-muted-foreground">Residual {risk.residual} · inherent {risk.inherent} · source {risk.source} · confidence {risk.confidence}</div>
        </div>
        <AIFix entity="risk" refId={risk.ref} accent={ACCENT} />
      </div>
    </div>
  );
}

export default function SituationRoom() {
  const [risks, setRisks] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [audit, setAudit] = useState([]);
  const [sel, setSel] = useState(null);
  const { openDeepDive } = useDeepDive();

  useEffect(() => {
    const load = () => {
      api.get("/risks").then((r) => setRisks(r.data));
      api.get("/ai-incidents").then((r) => setIncidents(r.data));
      api.get("/audit-logs").then((r) => setAudit(r.data.slice(0, 14)));
    };
    load(); const t = setInterval(load, 15000); return () => clearInterval(t);
  }, []);

  if (!risks) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const critical = risks.filter((r) => r.residual >= 16).sort((a, b) => b.residual - a.residual);
  const high = risks.filter((r) => r.residual >= 8 && r.residual < 16).length;
  const openInc = incidents.filter((i) => i.status !== "Resolved").length;
  const critInc = incidents.filter((i) => i.severity === "Critical").length;

  return (
    <div className="rise space-y-6" data-testid="situation-room-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2" style={{ color: `hsl(${ACCENT})` }}><Radar className="w-7 h-7" strokeWidth={1.5} /> Enterprise Situation Room</h1>
        <p className="text-sm text-muted-foreground mt-1">Live command view — active incidents, critical exposures and the evidence trail as it happens. Click any exposure for its AI risk rating &amp; fix.</p>
      </div>

      <AIInsight dashboard="Situation Room" accent={ACCENT} auto slug="situation-room" />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard testid="sr-kpi-critical" label="Critical exposures" value={critical.length} accent="0 84% 60%" sub="residual ≥ 16" />
        <StatCard testid="sr-kpi-high" label="High exposures" value={high} accent="15 80% 55%" sub="residual 8–15" />
        <StatCard testid="sr-kpi-risks" label="Tracked risks" value={risks.length} accent={ACCENT} sub="in register" />
        <StatCard testid="sr-kpi-incidents" label="Open incidents" value={openInc} accent="35 90% 55%" sub={`${critInc} critical`} />
        <StatCard testid="sr-kpi-events" label="Live events" value={audit.length} accent="142 70% 45%" sub="last 14 shown" />
        <StatCard testid="sr-kpi-mode" label="Command mode" value="LIVE" accent={ACCENT} sub="auto-refresh 15s" />
      </div>

      <div className="grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <div className="bg-card fact-border rounded-xl p-6">
            <h2 className="font-head font-bold text-lg mb-4 flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-crit" /> Critical Exposures</h2>
            {critical.length === 0 ? (
              <div className="text-sm text-low py-8 text-center rounded-lg border border-dashed border-muted-foreground/25">✓ No critical exposures (residual ≥ 16) right now.</div>
            ) : (
              <div className="space-y-3">
                {critical.map((r, i) => (
                  <motion.button key={r.ref} type="button" onClick={() => setSel(r)} data-testid={`sr-exposure-${r.ref}`}
                    initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                    className="w-full text-left flex items-center gap-4 p-3 rounded-lg bg-secondary/30 border border-border hover:bg-secondary/50 transition-colors">
                    <ScorePill value={r.residual} />
                    <div className="flex-1 min-w-0"><div className="font-medium text-sm truncate">{r.title}</div><div className="text-[11px] text-muted-foreground truncate">{r.ref} · {r.owner} · {r.business_impact}</div></div>
                    <span className="text-xs px-2.5 py-1 rounded-md bg-secondary/60 shrink-0">{r.status}</span>
                    <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
                  </motion.button>
                ))}
              </div>
            )}
          </div>

          <div className="bg-card fact-border rounded-xl p-6">
            <h2 className="font-head font-bold text-lg mb-4 flex items-center gap-2"><AlertOctagon className="w-4 h-4 text-high" /> Active AI Incidents</h2>
            {incidents.length === 0 ? (
              <div className="text-sm text-low py-8 text-center rounded-lg border border-dashed border-muted-foreground/25">No active AI incidents reported.</div>
            ) : (
              <div className="space-y-3">
                {incidents.map((inc) => (
                  <button key={inc.ref} type="button" data-testid={`sr-incident-${inc.ref}`}
                    onClick={() => openDeepDive({ accent: ACCENT, refLabel: inc.ref, title: inc.title,
                      rating: inc.severity === "Critical" ? "Critical" : "High",
                      facets: [{ label: "System", value: inc.system }, { label: "Mode", value: inc.mode }, { label: "Severity", value: inc.severity }, { label: "Status", value: inc.status }],
                      recommendedActions: [`Triage ${inc.ref} on ${inc.system} — confirm containment mode “${inc.mode}”, then drive to Resolved and log the evidence.`],
                      explainTitle: inc.title, explainKind: "ai incident containment severity system mode",
                      explainContext: { incident: inc } })}
                    className="w-full text-left flex items-center gap-4 p-3 rounded-lg bg-secondary/30 border border-border hover:bg-secondary/50 transition-colors">
                    {inc.severity === "Critical" ? <Ban className="w-5 h-5 text-crit shrink-0" /> : <AlertOctagon className="w-5 h-5 text-high shrink-0" />}
                    <div className="flex-1 min-w-0"><div className="font-medium text-sm truncate">{inc.title}</div><div className="text-[11px] font-mono text-muted-foreground truncate">{inc.ref} · {inc.system} · mode: <span className="text-ai">{inc.mode}</span></div></div>
                    <span className="text-xs px-2.5 py-1 rounded-md bg-secondary/60 shrink-0">{inc.status}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="bg-card fact-border rounded-xl p-6">
          <h2 className="font-head font-bold text-lg mb-4 flex items-center gap-2"><Activity className="w-4 h-4 text-low" /> Live Feed</h2>
          {audit.length === 0 ? (
            <div className="text-sm text-muted-foreground py-8 text-center rounded-lg border border-dashed border-muted-foreground/25">No audit events yet.</div>
          ) : (
            <div className="space-y-3">
              {audit.map((l, i) => (
                <div key={i} className="flex gap-3 text-xs">
                  <span className="w-1.5 h-1.5 mt-1.5 rounded-full bg-ai shrink-0 animate-pulse" />
                  <div className="min-w-0"><div className="font-mono text-ai text-[11px]">{l.action}</div><div className="text-foreground/80">{l.detail}</div><div className="text-[10px] text-muted-foreground">{new Date(l.ts).toLocaleTimeString()}</div></div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <RiskModal risk={sel} onClose={() => setSel(null)} />
    </div>
  );
}
