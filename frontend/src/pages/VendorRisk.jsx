import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Building, Loader2, Layers, ShieldAlert, PlayCircle } from "lucide-react";

const TIER = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };

export default function VendorRisk() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");

  const load = () => api.get("/vendors").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);

  const assess = async (ref) => {
    setBusy(ref);
    try { const { data: r } = await api.post(`/vendors/${ref}/assess`); toast.success(`${ref}: ${r.risk_tier} (${r.risk_score})`); load(); }
    catch { toast.error("Assess failed"); }
    setBusy("");
  };

  if (!data) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Building className="w-7 h-7 text-primary" /> Third-Party Risk</h1>
        <p className="text-sm text-muted-foreground mt-1">Vendor risk management — the second standalone app composed on the Obserra kernel.</p>
        <div data-testid="tpr-composition" className="flex flex-wrap items-center gap-2 mt-3">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Layers className="w-3.5 h-3.5" /> Composed on:</span>
          {data.composition.map((c) => <span key={c} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{c}</span>)}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 max-w-md">
        <div className="bg-card fact-border rounded-xl p-4"><div className="text-[10px] font-mono uppercase text-muted-foreground">Portfolio risk</div><div className="font-head font-black text-3xl">{data.portfolio_risk}</div></div>
        <div className="bg-card fact-border rounded-xl p-4" style={{ borderLeft: "3px solid hsl(0 84% 60%)" }}><div className="text-[10px] font-mono uppercase text-muted-foreground">High / Critical</div><div className="font-head font-black text-3xl text-crit">{data.high_risk}</div></div>
      </div>

      <div className="bg-card fact-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3">Vendor</th><th className="text-left px-4 py-3">Category</th><th className="text-left px-4 py-3">Data access</th><th className="text-left px-4 py-3">Attested</th><th className="text-left px-4 py-3">Incidents</th><th className="text-left px-4 py-3">Risk</th><th className="text-right px-4 py-3">Action</th></tr>
          </thead>
          <tbody>
            {data.vendors.map((v) => (
              <tr key={v.ref} data-testid={`vendor-row-${v.ref}`} className="border-b border-border/60 hover:bg-secondary/40 transition-colors">
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{v.ref}</div><div className="font-medium">{v.name}</div></td>
                <td className="px-4 py-3 text-muted-foreground">{v.category}</td>
                <td className="px-4 py-3">{v.data_access}</td>
                <td className="px-4 py-3">{v.attestation}%</td>
                <td className="px-4 py-3">{v.incidents > 0 ? <span className="text-crit flex items-center gap-1"><ShieldAlert className="w-3.5 h-3.5" />{v.incidents}</span> : "0"}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${TIER[v.risk_tier]} / 0.15)`, color: `hsl(${TIER[v.risk_tier]})` }}>{v.risk_tier} · {v.risk_score}</span></td>
                <td className="px-4 py-3 text-right">
                  {isAdmin && <button data-testid={`assess-${v.ref}`} disabled={!!busy} onClick={() => assess(v.ref)} className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 disabled:opacity-50">{busy === v.ref ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />} Assess</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">Assessing a High/Critical vendor opens a remediation workflow and alerts owners — proving the kernel loop.</p>
    </div>
  );
}
