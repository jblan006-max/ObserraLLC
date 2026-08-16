import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function SaaSOverview() {
  const [version, setVersion] = useState(null);
  const [agents, setAgents] = useState([]);

  useEffect(() => {
    let mounted = true;
    api.get("/version").then((r) => { if (mounted) setVersion(r.data); }).catch(() => {});
    api.get("/agents").then((r) => { if (mounted) setAgents(r.data.agents || []); }).catch(() => {});
    return () => { mounted = false; };
  }, []);

  const counts = agents.reduce((acc, a) => {
    const k = a.risk_class || "Unknown";
    acc[k] = (acc[k] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="p-6">
      <h1 className="text-2xl font-head font-bold mb-4">SaaS Overview</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="p-4 bg-card rounded-md">
          <div className="text-sm text-muted-foreground">Backend</div>
          <div className="mt-2 font-mono">{version ? `${version.name} — ${version.version}` : "Loading..."}</div>
        </div>
        <div className="p-4 bg-card rounded-md">
          <div className="text-sm text-muted-foreground">Registered agents</div>
          <div className="mt-2 font-head font-bold text-xl">{agents.length}</div>
        </div>
        <div className="p-4 bg-card rounded-md">
          <div className="text-sm text-muted-foreground">Org context</div>
          <div className="mt-2">Tenant-aware: {Boolean(version).toString()}</div>
        </div>
      </div>

      <div className="bg-card p-4 rounded-md">
        <h2 className="font-bold mb-2">Agents by risk class</h2>
        {Object.keys(counts).length === 0 && <div className="text-sm text-muted-foreground">No data</div>}
        <ul className="space-y-2">
          {Object.entries(counts).map(([k, v]) => (
            <li key={k} className="flex items-center justify-between">
              <div className="text-sm">{k}</div>
              <div className="font-head font-bold">{v}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
