import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BarChart3, Loader2 } from "lucide-react";

export default function Benchmark() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/benchmark").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6 max-w-4xl">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><BarChart3 className="w-7 h-7 text-primary" /> Peer Benchmarking</h1>
        <p className="text-sm text-muted-foreground mt-1">Your posture vs. {data.peer_set} peers in <span className="text-foreground">{data.industry}</span>.</p>
      </div>

      <div className="space-y-4">
        {data.metrics.map((m) => (
          <div key={m.name} data-testid={`benchmark-${m.name.replace(/\s+/g, "-").toLowerCase()}`} className="bg-card fact-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="font-head font-bold text-sm">{m.name}</div>
              <div className="text-xs font-mono text-muted-foreground">{m.percentile}th percentile</div>
            </div>
            <div className="relative h-8 bg-secondary/50 rounded-md overflow-hidden">
              <div className="absolute top-0 bottom-0 w-px bg-muted-foreground/60" style={{ left: `${m.peer_median}%` }} title={`Peer median ${m.peer_median}`} />
              <div className="absolute top-0 bottom-0 w-px bg-low/70" style={{ left: `${m.top_quartile}%` }} title={`Top quartile ${m.top_quartile}`} />
              <div className="h-full rounded-md flex items-center justify-end pr-2" style={{ width: `${m.you}%`, background: `linear-gradient(90deg, hsl(var(--ai) / 0.4), hsl(var(--ai) / 0.75))` }}>
                <span className="text-xs font-head font-bold text-white">{m.you}</span>
              </div>
            </div>
            <div className="flex gap-4 mt-2 text-[10px] font-mono text-muted-foreground">
              <span>You: {m.you}</span><span>Peer median: {m.peer_median}</span><span className="text-low">Top quartile: {m.top_quartile}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
