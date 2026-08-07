import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { motion } from "framer-motion";
import { ScorePill, DataTypeBadge } from "@/components/badges";
import { Radar, AlertOctagon, Ban, ShieldAlert, Loader2, Activity } from "lucide-react";

export default function SituationRoom() {
  const [risks, setRisks] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [audit, setAudit] = useState([]);

  useEffect(() => {
    const load = () => {
      api.get("/risks").then((r) => setRisks(r.data));
      api.get("/ai-incidents").then((r) => setIncidents(r.data));
      api.get("/audit-logs").then((r) => setAudit(r.data.slice(0, 12)));
    };
    load(); const t = setInterval(load, 15000); return () => clearInterval(t);
  }, []);

  if (!risks) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const critical = risks.filter((r) => r.residual >= 16).sort((a, b) => b.residual - a.residual);

  return (
    <div className="rise space-y-6">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Radar className="w-7 h-7 text-ai" /> Enterprise Situation Room</h1>
        <p className="text-sm text-muted-foreground mt-1">Live command view — active incidents, critical exposures and the evidence trail as it happens.</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <div className="bg-card fact-border rounded-xl p-6">
            <h2 className="font-head font-bold text-lg mb-4 flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-crit" /> Critical Exposures</h2>
            <div className="space-y-3">
              {critical.map((r, i) => (
                <motion.div key={r.ref} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-4 p-3 rounded-lg bg-secondary/30 border border-border">
                  <ScorePill value={r.residual} />
                  <div className="flex-1 min-w-0"><div className="font-medium text-sm truncate">{r.title}</div><div className="text-[11px] text-muted-foreground">{r.ref} · {r.owner} · {r.business_impact}</div></div>
                  <span className="text-xs px-2.5 py-1 rounded-md bg-secondary/60">{r.status}</span>
                </motion.div>
              ))}
            </div>
          </div>

          <div className="bg-card fact-border rounded-xl p-6">
            <h2 className="font-head font-bold text-lg mb-4">Active AI Incidents</h2>
            <div className="space-y-3">
              {incidents.map((inc) => (
                <div key={inc.ref} className="flex items-center gap-4 p-3 rounded-lg bg-secondary/30 border border-border">
                  {inc.severity === "Critical" ? <Ban className="w-5 h-5 text-crit" /> : <AlertOctagon className="w-5 h-5 text-high" />}
                  <div className="flex-1"><div className="font-medium text-sm">{inc.title}</div><div className="text-[11px] font-mono text-muted-foreground">{inc.ref} · {inc.system} · mode: <span className="text-ai">{inc.mode}</span></div></div>
                  <span className="text-xs px-2.5 py-1 rounded-md bg-secondary/60">{inc.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-card fact-border rounded-xl p-6">
          <h2 className="font-head font-bold text-lg mb-4 flex items-center gap-2"><Activity className="w-4 h-4 text-low" /> Live Feed</h2>
          <div className="space-y-3">
            {audit.map((l, i) => (
              <div key={i} className="flex gap-3 text-xs">
                <span className="w-1.5 h-1.5 mt-1.5 rounded-full bg-ai shrink-0 animate-pulse" />
                <div className="min-w-0"><div className="font-mono text-ai text-[11px]">{l.action}</div><div className="text-foreground/80">{l.detail}</div><div className="text-[10px] text-muted-foreground">{new Date(l.ts).toLocaleTimeString()}</div></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
