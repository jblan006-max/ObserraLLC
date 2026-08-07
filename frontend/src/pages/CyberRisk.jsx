import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ShieldAlert, Loader2, Layers, PlayCircle, Gauge, ShieldCheck, TrendingDown } from "lucide-react";

const TIER = (residual) => residual >= 16 ? "0 84% 60%" : residual >= 9 ? "35 90% 55%" : "142 70% 45%";

function Stat({ label, value, unit, icon: Icon, accent }) {
  return (
    <div className="bg-card fact-border rounded-xl p-4" style={accent ? { borderLeft: `3px solid hsl(${accent})` } : {}}>
      <div className="text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1.5">
        {Icon && <Icon className="w-3.5 h-3.5" />} {label}
      </div>
      <div className="font-head font-black text-3xl mt-1">{value}{unit}</div>
    </div>
  );
}

export default function CyberRisk() {
  const { user, mode } = useAuth();
  const isAdmin = user?.role === "admin";
  const isExec = mode === "executive";
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");

  const load = () => api.get("/cyber/overview").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);

  const treat = async (ref) => {
    setBusy(ref);
    try { await api.post(`/cyber/risks/${ref}/treat`); toast.success(`Treatment workflow opened for ${ref}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Treat failed"); }
    setBusy("");
  };

  if (!data) return <div className="flex items-center justify-center h-96" data-testid="cyber-loading"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6" data-testid="cyber-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><ShieldAlert className="w-7 h-7 text-primary" /> Cyber Risk</h1>
        <p className="text-sm text-muted-foreground mt-1">{isExec ? "Strategic cyber risk posture — business exposure and mitigation at a glance." : "Control-centric cyber risk posture — a kernel-native app composed on the Obserra kernel."}</p>
        <div data-testid="cyber-composition" className="flex flex-wrap items-center gap-2 mt-3">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Layers className="w-3.5 h-3.5" /> Composed on:</span>
          {data.composition.map((c) => <span key={c} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{c}</span>)}
          {data.live_m365_users != null && <span data-testid="cyber-m365-live" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/15 text-low border border-low/30">M365 LIVE · {data.live_m365_users} users{data.live_m365_risky != null ? ` · ${data.live_m365_risky} risky` : ""}</span>}
          {data.live_risk_penalty > 0 && <span data-testid="cyber-risk-penalty" className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-high/15 text-high border border-high/30">−{data.live_risk_penalty} posture (live signal)</span>}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Posture score" value={data.posture_score} unit="" icon={Gauge} accent="142 70% 45%" />
        <Stat label="Risk mitigation" value={data.mitigation_pct} unit="%" icon={TrendingDown} />
        <Stat label="Control coverage" value={data.control_coverage} unit="%" icon={ShieldCheck} />
        <Stat label="Open risks" value={`${data.open_risks}/${data.total_risks}`} unit="" icon={ShieldAlert} accent="0 84% 60%" />
      </div>

      <div className="bg-card fact-border rounded-xl overflow-x-auto" data-testid="cyber-top-risks">
        <div className="px-4 py-3 border-b border-border text-xs font-mono uppercase tracking-wider text-muted-foreground">Top residual cyber risks</div>
        <table className="w-full text-sm min-w-[720px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3">Risk</th><th className="text-left px-4 py-3">Owner</th><th className="text-left px-4 py-3">Status</th><th className="text-left px-4 py-3">Residual</th><th className="text-right px-4 py-3">Action</th></tr>
          </thead>
          <tbody>
            {data.risks.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No cyber risks recorded.</td></tr>
            ) : data.risks.map((r) => (
              <tr key={r.ref} data-testid={`cyber-risk-${r.ref}`} className="border-b border-border/60 hover:bg-secondary/40 transition-colors">
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{r.ref}</div><div className="font-medium">{r.title}</div></td>
                <td className="px-4 py-3 text-muted-foreground">{r.owner || "—"}</td>
                <td className="px-4 py-3">{r.status}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${TIER(r.residual)} / 0.15)`, color: `hsl(${TIER(r.residual)})` }}>{r.residual}/25</span></td>
                <td className="px-4 py-3 text-right">
                  {isAdmin && <button data-testid={`treat-${r.ref}`} disabled={!!busy} onClick={() => treat(r.ref)} className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 disabled:opacity-50">{busy === r.ref ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />} Treat</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">Treating a risk opens a remediation workflow and alerts owners — proving the kernel loop.</p>
    </div>
  );
}
