import { useMemo, useState } from "react";
import { Bot, Plus, Search } from "lucide-react";
import { EmptyState, Panel, StatusPill } from "@/components/agentic-ai/shared";

export default function AgentInventoryDashboard({
  agents,
  isAdmin,
  onSelectAgent,
  onRegister,
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [risk, setRisk] = useState("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (agents || []).filter((agent) => {
      if (status !== "all" && agent.status !== status) return false;
      if (risk !== "all" && agent.risk_class !== risk) return false;
      if (!q) return true;
      return `${agent.ref} ${agent.name} ${agent.owner} ${agent.model} ${(agent.tools || []).join(" ")} ${(agent.permissions || []).join(" ")}`
        .toLowerCase()
        .includes(q);
    });
  }, [agents, query, status, risk]);

  return (
    <div className="space-y-5">
      <Panel
        title="Enterprise AI agent inventory"
        subtitle="Every row is an existing backend agent record. Modeled risk and authority are client-side interpretations."
        actions={
          isAdmin ? (
            <button
              onClick={onRegister}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold"
            >
              <Plus className="w-3.5 h-3.5" />
              Register Agent
            </button>
          ) : null
        }
        testid="agentic-inventory"
      >
        <div className="flex flex-col md:flex-row gap-2 mb-4">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search agent, owner, model, tool or permission"
              className="w-full bg-secondary/60 rounded-md pl-9 pr-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
          >
            <option value="all">All statuses</option>
            <option value="sanctioned">Sanctioned</option>
            <option value="restricted">Restricted</option>
            <option value="shadow">Shadow</option>
            <option value="killed">Killed</option>
          </select>
          <select
            value={risk}
            onChange={(event) => setRisk(event.target.value)}
            className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
          >
            <option value="all">All risk classes</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>

        {filtered.length === 0 ? (
          <EmptyState
            title="No matching agents"
            text="Register an agent through the existing Obserra Agent API or adjust the current filters."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[1100px]">
              <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
                <tr>
                  <th className="text-left py-3 pr-3">Agent</th>
                  <th className="text-left py-3 px-3">Owner</th>
                  <th className="text-left py-3 px-3">Model</th>
                  <th className="text-left py-3 px-3">Risk</th>
                  <th className="text-left py-3 px-3">Modeled score</th>
                  <th className="text-left py-3 px-3">Authority</th>
                  <th className="text-left py-3 px-3">Guardrails</th>
                  <th className="text-left py-3 px-3">Action tools</th>
                  <th className="text-left py-3 pl-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((agent) => (
                  <tr
                    key={agent.ref}
                    onClick={() => onSelectAgent(agent)}
                    className="border-b border-border/60 hover:bg-secondary/35 cursor-pointer"
                  >
                    <td className="py-3 pr-3">
                      <div className="flex items-center gap-2">
                        <Bot className="w-4 h-4 text-ai" />
                        <div>
                          <div className="font-mono text-[10px] text-ai">{agent.ref}</div>
                          <div className="font-medium">{agent.name}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-muted-foreground">{agent.owner}</td>
                    <td className="py-3 px-3 font-mono text-xs">{agent.model}</td>
                    <td className="py-3 px-3"><StatusPill value={agent.risk_class} /></td>
                    <td className="py-3 px-3">
                      <span className="font-head font-black text-lg">{agent.modeledRisk}</span>
                      <span className="text-[10px] text-muted-foreground">/100</span>
                    </td>
                    <td className="py-3 px-3"><StatusPill value={agent.authority} /></td>
                    <td className="py-3 px-3">
                      <span className="font-mono text-xs">{agent.guardrailCoverage.pct}%</span>
                    </td>
                    <td className="py-3 px-3 font-mono text-xs">{agent.actionTools?.length || 0}</td>
                    <td className="py-3 pl-3"><StatusPill value={agent.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}