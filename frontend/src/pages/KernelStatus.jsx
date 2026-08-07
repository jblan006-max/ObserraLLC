import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PolicyModal } from "@/components/PolicyModal";
import { Layers, Loader2, ShieldCheck, GitBranch, CheckCircle2, Circle, Plus, Pencil, Activity } from "lucide-react";

const LAYER_COLOR = {
  Foundation: "225 70% 60%", Data: "280 70% 60%", Analytics: "190 90% 50%",
  Orchestration: "35 90% 55%", Intelligence: "142 70% 45%", Assurance: "15 80% 55%",
};
const SEV_COLOR = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "190 90% 50%" };
const STATUS_DOT = { operational: "142 70% 45%", idle: "215 20% 50%", degraded: "0 84% 60%" };

const fmtTs = (t) => !t ? "—" : t === "live" ? "live" : new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });

export default function KernelStatus() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [manifest, setManifest] = useState(null);
  const [health, setHealth] = useState({});
  const [policies, setPolicies] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [policyModal, setPolicyModal] = useState(null); // {policy} or {new:true}

  const loadPolicies = useCallback(() => api.get("/policies").then((r) => setPolicies(r.data)), []);
  useEffect(() => {
    api.get("/kernel/manifest").then((r) => setManifest(r.data));
    api.get("/kernel/health").then((r) => setHealth(r.data)).catch(() => {});
    loadPolicies();
    api.get("/workflows").then((r) => setWorkflows(r.data));
  }, [loadPolicies]);

  if (!manifest) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const layers = [...new Set(manifest.subsystems.map((s) => s.layer))];

  return (
    <div className="rise space-y-8">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Layers className="w-7 h-7 text-primary" /> Platform Kernel</h1>
        <p className="text-sm text-muted-foreground mt-1">The shared cybersecurity kernel — {manifest.count} subsystems with live telemetry. Every Obserra application composes on top.</p>
      </div>

      {layers.map((layer) => (
        <div key={layer}>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full" style={{ background: `hsl(${LAYER_COLOR[layer]})` }} />
            <h2 className="font-head font-bold text-sm uppercase tracking-widest text-muted-foreground">{layer}</h2>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {manifest.subsystems.filter((s) => s.layer === layer).map((s) => {
              const h = health[s.id] || {};
              const dot = STATUS_DOT[h.status] || STATUS_DOT.operational;
              return (
                <div key={s.id} data-testid={`kernel-sub-${s.id}`} className="bg-card fact-border rounded-xl p-4 hover:-translate-y-0.5 transition-transform duration-200"
                  style={{ borderTop: `2px solid hsl(${LAYER_COLOR[layer]} / 0.6)` }}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="font-head font-bold text-sm">{s.name}</div>
                    <span className="flex items-center gap-1 text-[10px] font-mono uppercase" style={{ color: `hsl(${dot})` }}>
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: `hsl(${dot})`, boxShadow: `0 0 6px hsl(${dot})` }} />{h.status || "ok"}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed min-h-[32px]">{s.desc}</p>
                  <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-border/50">
                    <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Records</div><div data-testid={`kernel-records-${s.id}`} className="font-head font-bold text-sm">{(h.records ?? 0).toLocaleString()}</div></div>
                    <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Last run</div><div className="font-head font-bold text-sm">{fmtTs(h.last_run)}</div></div>
                    <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Err rate</div><div className="font-head font-bold text-sm" style={{ color: h.error_rate > 0 ? "hsl(0 84% 60%)" : undefined }}>{((h.error_rate ?? 0) * 100).toFixed(0)}%</div></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-lg">Policy Engine · Governance Policies</h2></div>
          {isAdmin && <button data-testid="policy-new-btn" onClick={() => setPolicyModal({ new: true })}
            className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors"><Plus className="w-3.5 h-3.5" /> New policy</button>}
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          {policies.map((p) => (
            <div key={p.policy_id} data-testid={`policy-${p.policy_id}`} className="bg-card fact-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs text-ai">{p.policy_id}</span>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${SEV_COLOR[p.severity]} / 0.15)`, color: `hsl(${SEV_COLOR[p.severity]})` }}>{p.severity}</span>
                  {isAdmin && <button data-testid={`policy-edit-${p.policy_id}`} onClick={() => setPolicyModal({ policy: p })} className="text-muted-foreground hover:text-foreground"><Pencil className="w-3.5 h-3.5" /></button>}
                </div>
              </div>
              <div className="font-medium text-sm">{p.name}</div>
              <p className="text-xs text-muted-foreground mt-1">{p.statement}</p>
              <div className="text-[10px] font-mono text-muted-foreground mt-2">{p.framework} · {p.enforced ? "ENFORCED" : "MONITOR"}{p.threshold != null && ` · threshold ${p.threshold}`}</div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-3"><GitBranch className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-lg">Workflow Engine · Active Workflows</h2></div>
        {workflows.length === 0 ? (
          <div className="bg-card fact-border rounded-xl p-6 text-center text-sm text-muted-foreground">No active workflows. Remediate a control-drift alert or invite a teammate to start one.</div>
        ) : (
          <div className="space-y-3">
            {workflows.map((w) => (
              <div key={w.id} data-testid={`workflow-${w.id}`} className="bg-card fact-border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium capitalize flex items-center gap-2">
                    {w.type === "remediation" && <Activity className="w-3.5 h-3.5 text-high" />}
                    {w.type} · <span className="font-mono text-xs text-muted-foreground">{w.subject}</span>
                    {w.assignee && <span className="text-[11px] text-muted-foreground">→ {w.assignee}</span>}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-sm capitalize ${w.status === "complete" || w.status === "resolved" ? "bg-low/15 text-low" : "bg-med/15 text-med"}`}>{w.status.replace("_", " ")}</span>
                </div>
                <div className="flex flex-wrap gap-4">
                  {w.steps.map((s) => (
                    <span key={s.key} className={`flex items-center gap-1.5 text-xs ${s.done ? "text-foreground" : "text-muted-foreground"}`}>
                      {s.done ? <CheckCircle2 className="w-3.5 h-3.5 text-low" /> : <Circle className="w-3.5 h-3.5" />} {s.label}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {policyModal && <PolicyModal policy={policyModal.policy} onClose={() => setPolicyModal(null)} onSaved={loadPolicies} />}
    </div>
  );
}
