import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PolicyModal } from "@/components/PolicyModal";
import { ClickCard } from "@/components/dash";
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
  const [kpi, setKpi] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [policyModal, setPolicyModal] = useState(null); // {policy} or {new:true}

  const loadPolicies = useCallback(() => api.get("/policies").then((r) => setPolicies(r.data)), []);
  useEffect(() => {
    api.get("/kernel/manifest").then((r) => setManifest(r.data));
    api.get("/kernel/health").then((r) => setHealth(r.data)).catch(() => {});
    api.get("/kernel/remediation-kpi").then((r) => setKpi(r.data)).catch(() => {});
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

      {kpi && (
        <div data-testid="remediation-kpi" className="grid grid-cols-3 gap-3 sm:gap-4">
          {[["Open remediations", kpi.open, "190 90% 50%"], ["Overdue", kpi.overdue, "0 84% 60%"], ["Resolved", kpi.resolved, "142 70% 45%"]].map(([label, val, color]) => (
            <ClickCard key={label} className="bg-card fact-border rounded-xl p-4" style={{ borderLeft: `3px solid hsl(${color})` }}
              detail={{ accent: color, refLabel: "KERNEL", title: label,
                rating: label === "Overdue" && val > 0 ? "High" : "Low",
                facets: [{ label, value: String(val) }, { label: "Open", value: String(kpi.open) }, { label: "Overdue", value: String(kpi.overdue) }, { label: "Resolved", value: String(kpi.resolved) }],
                recommendedActions: [label === "Overdue" && val > 0 ? "Escalate overdue remediations to their owners now — overdue items are the primary driver of residual exposure." : "Keep remediation throughput high; resolved items retire ALE on the next scan."],
                explainTitle: `${label} — remediation KPI`, explainKind: "kernel remediation workflow kpi", explainContext: { kpi } }}>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{label}</div>
              <div className="font-head font-black text-3xl mt-1" style={{ color: val > 0 && label === "Overdue" ? `hsl(${color})` : undefined }}>{val}</div>
            </ClickCard>
          ))}
        </div>
      )}

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
                <ClickCard key={s.id} testid={`kernel-sub-${s.id}`} className="bg-card fact-border rounded-xl p-4"
                  style={{ borderTop: `2px solid hsl(${LAYER_COLOR[layer]} / 0.6)` }}
                  detail={{ accent: LAYER_COLOR[layer], refLabel: `${layer} · ${s.id}`, title: s.name,
                    rating: h.status === "degraded" ? "High" : "Low",
                    facets: [{ label: "Layer", value: layer }, { label: "Status", value: h.status || "operational" }, { label: "Records", value: (h.records ?? 0).toLocaleString() }, { label: "Last run", value: fmtTs(h.last_run) }, { label: "Error rate", value: `${((h.error_rate ?? 0) * 100).toFixed(0)}%` }],
                    recommendedActions: [h.status === "degraded" ? `${s.name} is degraded — inspect its error rate and last run; a stalled subsystem starves dependent apps of live telemetry.` : `${s.name} is healthy — it feeds live telemetry to every app composed on the kernel.`],
                    explainTitle: s.name, explainKind: "kernel subsystem telemetry health layer", explainContext: { subsystem: { id: s.id, name: s.name, layer, desc: s.desc }, health: h } }}>
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
                </ClickCard>
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
            <ClickCard key={p.policy_id} testid={`policy-${p.policy_id}`} className="bg-card fact-border rounded-lg p-4"
              detail={{ accent: SEV_COLOR[p.severity] || "215 15% 55%", refLabel: p.policy_id, title: p.name,
                rating: p.severity, facets: [{ label: "Framework", value: p.framework }, { label: "Enforcement", value: p.enforced ? "ENFORCED" : "MONITOR" }, { label: "Severity", value: p.severity }, ...(p.threshold != null ? [{ label: "Threshold", value: String(p.threshold) }] : [])],
                complianceRefs: p.framework ? [p.framework] : [],
                recommendedActions: [p.enforced ? "Policy is enforced at the request path — review matched denials periodically for false positives." : "Move this policy from MONITOR to ENFORCED once its match rate is validated, to actively block violations."],
                explainTitle: p.name, explainKind: "governance policy enforcement framework severity", explainContext: { policy: p } }}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs text-ai">{p.policy_id}</span>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${SEV_COLOR[p.severity]} / 0.15)`, color: `hsl(${SEV_COLOR[p.severity]})` }}>{p.severity}</span>
                  {isAdmin && <button data-testid={`policy-edit-${p.policy_id}`} onClick={(e) => { e.stopPropagation(); setPolicyModal({ policy: p }); }} className="text-muted-foreground hover:text-foreground"><Pencil className="w-3.5 h-3.5" /></button>}
                </div>
              </div>
              <div className="font-medium text-sm">{p.name}</div>
              <p className="text-xs text-muted-foreground mt-1">{p.statement}</p>
              <div className="text-[10px] font-mono text-muted-foreground mt-2">{p.framework} · {p.enforced ? "ENFORCED" : "MONITOR"}{p.threshold != null && ` · threshold ${p.threshold}`}</div>
            </ClickCard>
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
              <ClickCard key={w.id} testid={`workflow-${w.id}`} className="bg-card fact-border rounded-lg p-4"
                detail={{ accent: w.type === "remediation" ? "15 80% 55%" : "225 70% 60%", refLabel: `WORKFLOW · ${w.id}`, title: `${w.type} — ${w.subject}`,
                  facets: [{ label: "Type", value: w.type }, { label: "Subject", value: w.subject }, { label: "Status", value: String(w.status).replace("_", " ") }, ...(w.assignee ? [{ label: "Assignee", value: w.assignee }] : [])],
                  recommendedActions: ["Advance the open steps to completion — a stalled workflow leaves its underlying finding unremediated."],
                  explainTitle: `${w.type} workflow — ${w.subject}`, explainKind: "kernel workflow remediation steps assignee", explainContext: { workflow: w } }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium capitalize flex items-center gap-2">
                    {w.type === "remediation" && <Activity className="w-3.5 h-3.5 text-high" />}
                    {w.type} · <span className="font-mono text-xs text-muted-foreground">{w.subject}</span>
                    {w.assignee && <span className="text-[11px] text-muted-foreground">→ {w.assignee}</span>}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-sm capitalize ${w.status === "complete" || w.status === "resolved" ? "bg-low/15 text-low" : "bg-med/15 text-med"}`}>{w.status.replace("_", " ")}</span>
                </div>
                {w.type === "remediation" && w.due_at && w.status !== "resolved" && (() => {
                  const days = Math.ceil((new Date(w.due_at) - Date.now()) / 86400000);
                  return days < 0
                    ? <span data-testid={`wf-overdue-${w.id}`} className="inline-flex items-center gap-1 text-[11px] font-mono text-crit mb-2"><Activity className="w-3 h-3" />Overdue by {Math.abs(days)}d</span>
                    : <span className="inline-flex items-center gap-1 text-[11px] font-mono text-muted-foreground mb-2">Due in {days}d</span>;
                })()}
                <div className="flex flex-wrap gap-4">
                  {w.steps.map((s) => (
                    <span key={s.key} className={`flex items-center gap-1.5 text-xs ${s.done ? "text-foreground" : "text-muted-foreground"}`}>
                      {s.done ? <CheckCircle2 className="w-3.5 h-3.5 text-low" /> : <Circle className="w-3.5 h-3.5" />} {s.label}
                    </span>
                  ))}
                </div>
              </ClickCard>
            ))}
          </div>
        )}
      </div>

      {policyModal && <PolicyModal policy={policyModal.policy} onClose={() => setPolicyModal(null)} onSaved={loadPolicies} />}
    </div>
  );
}
