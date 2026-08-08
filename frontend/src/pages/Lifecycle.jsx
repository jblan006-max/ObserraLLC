import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { useDeepDive } from "@/context/DeepDiveContext";
import { UserPlus, UserX, GitBranch } from "lucide-react";

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—");

export default function Lifecycle() {
  const { openDeepDive } = useDeepDive();
  const [d, setD] = useState(null);
  const load = useCallback(async () => { const { data } = await api.get("/sap/jml"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;

  const openLeaver = (l) => openDeepDive({
    accent: "0 84% 60%", refLabel: l.ref, title: `${l.name} — residual access`, rating: "Critical", score: l.score,
    facets: [
      { label: "Department", value: l.department }, { label: "Terminated", value: fmtDate(l.termination_date) },
      { label: "Residual SAP accounts", value: l.residual_accounts }, { label: "AD/Entra enabled", value: l.ad_enabled ? "Yes" : "No" },
    ],
    recommendedActions: [
      "Immediately lock all residual SAP accounts and revoke roles for this terminated worker.",
      "Disable the linked AD/Entra identity and open a ServiceNow leaver ticket to verify closure.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-2", "ISO 27001 A.5.11"],
    explainTitle: `${l.name} — terminated worker residual SAP access`, explainKind: "SAP leaver residual access remediation",
    explainContext: { leaver: l },
  });

  return (
    <div className="space-y-6" data-testid="lifecycle-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="lifecycle-title">Joiner / Mover / Leaver</h1>
        <p className="text-sm text-muted-foreground mt-1">Workforce lifecycle correlated with SAP access — recent joiners, transfers and terminated workers still holding access.</p>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Joiners (21d)" value={d.counts.joiners} accent="142 70% 45%" icon={UserPlus} testid="jml-joiners" />
        <StatCard label="Movers" value={d.counts.movers} accent="260 85% 66%" icon={GitBranch} testid="jml-movers" />
        <StatCard label="Leavers w/ residual access" value={d.counts.leavers} accent="0 84% 60%" icon={UserX} testid="jml-leavers" />
      </div>

      <div className="bg-card fact-border rounded-xl p-5" data-testid="jml-leavers-panel">
        <div className="flex items-center gap-2 mb-3"><UserX className="w-4 h-4 text-crit" /><h2 className="font-head font-bold text-lg">Terminated — Residual Access (Critical)</h2></div>
        <div className="space-y-2">
          {d.leavers.map((l) => (
            <button key={l.ref} data-testid={`jml-leaver-${l.ref}`} onClick={() => openLeaver(l)} className="w-full text-left flex items-center gap-3 p-3 rounded-lg bg-crit/5 hover:bg-crit/10 border border-crit/20 transition-colors">
              <span className="font-head font-black text-xl text-crit w-10">{l.score}</span>
              <div className="flex-1 min-w-0"><div className="text-sm font-medium">{l.name}</div><div className="text-[11px] text-muted-foreground">{l.department} · terminated {fmtDate(l.termination_date)} · {l.residual_accounts} active account(s){l.ad_enabled ? " · AD still enabled" : ""}</div></div>
              <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full bg-crit/15 text-crit">Critical</span>
            </button>
          ))}
          {d.leavers.length === 0 && <p className="text-sm text-low py-3">No terminated workers with residual SAP access. ✓</p>}
        </div>
      </div>

      <div className="bg-card fact-border rounded-xl p-5" data-testid="jml-joiners-panel">
        <div className="flex items-center gap-2 mb-3"><UserPlus className="w-4 h-4 text-low" /><h2 className="font-head font-bold text-lg">Recent Joiners</h2></div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-2">Name</th><th className="p-2">Dept</th><th className="p-2">Hire Date</th><th className="p-2">HR Source</th><th className="p-2">Provisioned</th></tr></thead>
            <tbody>
              {d.joiners.map((j) => (
                <tr key={j.ref} className="border-b border-border/50"><td className="p-2 font-medium">{j.name}</td><td className="p-2 text-xs">{j.department}</td><td className="p-2 text-xs">{fmtDate(j.hire_date)}</td><td className="p-2 text-xs font-mono">{j.hr_authority}</td><td className="p-2 text-xs">{j.provisioned ? <span className="text-low">✓ {j.accounts} account(s)</span> : <span className="text-amber">Pending</span>}</td></tr>
              ))}
              {d.joiners.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-muted-foreground">No recent joiners.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
