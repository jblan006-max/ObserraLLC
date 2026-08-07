import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { RefreshCw, Radio } from "lucide-react";

const PHASES = [
  "Ingesting Entra ID sign-in logs…",
  "Evaluating conditional access policies…",
  "Correlating privileged role assignments…",
  "Scanning Defender for Cloud Apps telemetry…",
  "Refreshing Tenable vulnerability findings…",
];

export function SyncTicker() {
  const [records, setRecords] = useState(null);
  const [phase, setPhase] = useState(0);
  const [pulse, setPulse] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    const sync = async () => {
      try {
        const { data } = await api.post("/connectors/sync");
        if (!mounted.current) return;
        setRecords(data.records_ingested);
        setPulse(true);
        setTimeout(() => { if (mounted.current) setPulse(false); }, 900);
      } catch { /* silent — mocked live sync */ }
    };
    sync();
    const s = setInterval(sync, 9000);
    const p = setInterval(() => setPhase((x) => (x + 1) % PHASES.length), 3000);
    return () => { mounted.current = false; clearInterval(s); clearInterval(p); };
  }, []);

  return (
    <div data-testid="connector-sync-ticker"
      className="flex items-center gap-3 flex-wrap text-xs font-mono bg-card fact-border rounded-lg px-4 py-2.5 mb-3">
      <span className="flex items-center gap-1.5 text-low">
        <span className={`w-2 h-2 rounded-full bg-low ${pulse ? "animate-ping" : ""}`}
          style={{ boxShadow: "0 0 8px hsl(142 70% 45%)" }} />
        <Radio className="w-3.5 h-3.5" /> LIVE
      </span>
      <span className="text-muted-foreground hidden sm:inline">Entra ID · Tenable · Defender CASB</span>
      <span key={phase} className="text-ai fade-phase flex items-center gap-1.5">
        <RefreshCw className="w-3 h-3 animate-spin" style={{ animationDuration: "2.5s" }} />
        {PHASES[phase]}
      </span>
      {records != null && (
        <span data-testid="sync-records" className="ml-auto text-foreground">
          {records.toLocaleString()} records ingested
        </span>
      )}
    </div>
  );
}
