import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { MoonStar, Ghost, Cpu } from "lucide-react";

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—");

const Table = ({ rows, cols, testid, empty }) => (
  <div className="bg-card fact-border rounded-xl overflow-x-auto" data-testid={testid}>
    <table className="w-full text-sm">
      <thead><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
        {cols.map((c) => <th key={c.k} className="p-3">{c.label}</th>)}
      </tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.ref || i} className="border-b border-border/50 hover:bg-secondary/30">
            {cols.map((c) => <td key={c.k} className="p-3 text-xs">{c.render ? c.render(r) : r[c.k]}</td>)}
          </tr>
        ))}
        {rows.length === 0 && <tr><td colSpan={cols.length} className="p-6 text-center text-muted-foreground">{empty}</td></tr>}
      </tbody>
    </table>
  </div>
);

export default function AccessMonitoring() {
  const [d, setD] = useState(null);
  const [tab, setTab] = useState("dormant");
  const load = useCallback(async () => { const { data } = await api.get("/sap/access-monitoring"); setD(data); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;

  const flag = (r) => (
    <>
      {r.privileged && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple/15 text-purple mr-1">PRIV</span>}
      {r.lock_state === "locked" && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">LOCKED</span>}
    </>
  );
  const tabs = [
    { k: "dormant", label: `Dormant (${d.counts.dormant})`, icon: MoonStar },
    { k: "orphan", label: `Orphan (${d.counts.orphan})`, icon: Ghost },
    { k: "service", label: `Service / Technical (${d.counts.service})`, icon: Cpu },
  ];

  return (
    <div className="space-y-6" data-testid="monitoring-page">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="monitoring-title">Access Monitoring</h1>
        <p className="text-sm text-muted-foreground mt-1">Continuous detection of dormant, orphan and ownerless service/technical accounts.</p>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Dormant accounts" value={d.counts.dormant} sub="Unused >90 days" accent="168 76% 46%" icon={MoonStar} testid="mon-dormant" />
        <StatCard label="Orphan accounts" value={d.counts.orphan} sub="No active owner" accent="38 92% 55%" icon={Ghost} testid="mon-orphan" />
        <StatCard label="Service / technical" value={d.counts.service} sub="RFC / batch / firefighter" accent="266 85% 66%" icon={Cpu} testid="mon-service" />
      </div>
      <div className="flex gap-2">
        {tabs.map((t) => (
          <button key={t.k} data-testid={`mon-tab-${t.k}`} onClick={() => setTab(t.k)} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${tab === t.k ? "bg-primary text-primary-foreground" : "bg-secondary/50 hover:bg-secondary"}`}><t.icon className="w-3.5 h-3.5" />{t.label}</button>
        ))}
      </div>
      {tab === "dormant" && <Table testid="mon-dormant-table" rows={d.dormant} empty="No dormant accounts." cols={[
        { k: "sap_user", label: "SAP User" }, { k: "person_name", label: "Person" }, { k: "system", label: "System" },
        { k: "last_login", label: "Last Login", render: (r) => fmtDate(r.last_login) }, { k: "flags", label: "Flags", render: flag },
      ]} />}
      {tab === "orphan" && <Table testid="mon-orphan-table" rows={d.orphan} empty="No orphan accounts." cols={[
        { k: "sap_user", label: "SAP User" }, { k: "person_name", label: "Person" }, { k: "system", label: "System" },
        { k: "reason", label: "Reason" }, { k: "flags", label: "Flags", render: flag },
      ]} />}
      {tab === "service" && <Table testid="mon-service-table" rows={d.service_accounts} empty="No service accounts." cols={[
        { k: "sap_user", label: "SAP User" }, { k: "account_type", label: "Type" }, { k: "system", label: "System" },
        { k: "owner", label: "Owner", render: (r) => r.owner || <span className="text-crit">unassigned</span> }, { k: "last_login", label: "Last Login", render: (r) => fmtDate(r.last_login) },
      ]} />}
    </div>
  );
}
