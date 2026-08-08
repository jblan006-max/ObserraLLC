import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { useDeepDive } from "@/context/DeepDiveContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { GitCompare, ShieldAlert, ShieldCheck, FlaskConical, ScrollText, Wrench } from "lucide-react";

const SEV = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "190 90% 50%", Low: "142 70% 45%" };
const Chip = ({ v, map = SEV }) => <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${map[v] || "220 10% 55%"} / 0.15)`, color: `hsl(${map[v] || "220 10% 55%"})` }}>{v}</span>;

export default function SodCommandCenter() {
  const { openDeepDive } = useDeepDive();
  const [data, setData] = useState(null);
  const [rules, setRules] = useState([]);
  const [people, setPeople] = useState([]);
  const [roles, setRoles] = useState([]);
  const [sev, setSev] = useState("all");
  const [area, setArea] = useState("all");
  const [status, setStatus] = useState("all");
  const [mit, setMit] = useState(null);
  const [control, setControl] = useState("");
  const [mitStatus, setMitStatus] = useState("Mitigated");
  const [busy, setBusy] = useState(false);
  // simulator
  const [simPerson, setSimPerson] = useState("");
  const [simRole, setSimRole] = useState("");
  const [simRoles, setSimRoles] = useState([]);
  const [simResult, setSimResult] = useState(null);

  const loadConflicts = useCallback(async () => {
    const p = new URLSearchParams();
    if (sev !== "all") p.set("severity", sev);
    if (area !== "all") p.set("area", area);
    if (status !== "all") p.set("status", status);
    const { data } = await api.get(`/sap/sod/conflicts?${p.toString()}`);
    setData(data);
  }, [sev, area, status]);
  useEffect(() => { loadConflicts(); }, [loadConflicts]);
  useEffect(() => {
    api.get("/sap/sod/rules").then((r) => setRules(r.data.rules));
    api.get("/sap/identities").then((r) => setPeople(r.data.identities));
    api.get("/sap/roles").then((r) => setRoles(r.data.roles));
  }, []);

  if (!data) return <Spinner />;

  const openRule = async (r) => {
    try {
      const { data } = await api.get(`/sap/sod/rules/${r.ref}`);
      const ru = data.rule;
      openDeepDive({
        accent: SEV[ru.severity], refLabel: ru.ref, title: ru.name, rating: ru.severity,
        facets: [
          { label: "Risk area", value: ru.area },
          { label: "Business risk", value: ru.business_risk },
          { label: "Violations", value: `${data.counts.total} total · ${data.counts.open} open · ${data.counts.mitigated} mitigated` },
          { label: data.function_a.label, value: `T-codes: ${data.function_a.tcodes.join(", ") || "—"}` },
          { label: data.function_b.label, value: `T-codes: ${data.function_b.tcodes.join(", ") || "—"}` },
          { label: "Current holders", value: data.holders.slice(0, 8).map((h) => h.person_name).join(", ") || "None currently" },
        ],
        recommendedActions: [
          `Prevent any single identity from holding both “${data.function_a.label}” and “${data.function_b.label}”.`,
          data.counts.open > 0 ? `Remediate ${data.counts.open} open violation(s): remove one conflicting role or attach a mitigating control with evidence.` : "No open violations — keep this rule under continuous monitoring.",
        ],
        complianceRefs: ["SOX ITGC", "NIST AC-5", "ISO 27001 A.5.3"],
        explainTitle: `${ru.name} — SoD rule`, explainKind: "SAP segregation of duties rule and its toxic function combination",
        explainContext: { rule: data },
      });
    } catch (e) { toast.error("Could not load rule detail"); }
  };

  const openConflict = (c) => openDeepDive({
    accent: SEV[c.severity], refLabel: c.conflict_ref, title: c.rule_name, rating: c.severity,
    facets: [
      { label: "User", value: c.person_name }, { label: "System", value: c.system },
      { label: "Risk area", value: c.area }, { label: "Status", value: c.status },
      { label: c.function_a, value: `via ${c.a_via_roles.join(", ")}` },
      { label: c.function_b, value: `via ${c.b_via_roles.join(", ")}` },
    ],
    recommendedActions: [
      `Remove one conflicting role (${c.a_via_roles[0]} or ${c.b_via_roles[0]}) to break the toxic combination.`,
      "If the access is required, attach a mitigating control with evidence and an expiry date.",
    ],
    complianceRefs: ["SOX ITGC", "NIST AC-5", "ISO 27001 A.5.3"],
    explainTitle: `${c.rule_name} — SoD conflict`, explainKind: "SAP segregation of duties conflict remediation",
    explainContext: { conflict: c },
  });

  const runMitigate = async () => {
    setBusy(true);
    try {
      await api.post("/sap/sod/conflicts/mitigate", { conflict_ref: mit.conflict_ref, control, status: mitStatus });
      toast.success(`Conflict ${mitStatus.toLowerCase()}`); setMit(null); setControl(""); await loadConflicts();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const addSimRole = () => { if (simRole && !simRoles.includes(simRole)) setSimRoles([...simRoles, simRole]); setSimRole(""); };
  const runSim = async () => {
    if (!simPerson || simRoles.length === 0) { toast.error("Pick an identity and at least one role"); return; }
    try {
      const { data } = await api.post("/sap/sod/simulate", { person_ref: simPerson, add_roles: simRoles });
      setSimResult(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Simulation failed"); }
  };

  return (
    <div className="space-y-6" data-testid="sod-command-center">
      <div>
        <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="sod-title">SoD Command Center</h1>
        <p className="text-sm text-muted-foreground mt-1">Live Segregation-of-Duties detection across users and roles, mitigating controls, and pre-assignment risk simulation.</p>
      </div>

      <SapInsight dashboard="SoD Command Center" focus="segregation-of-duties toxic combinations and mitigation" accent="0 84% 60%" auto slug="sod-command" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Critical conflicts" value={data.summary.Critical} accent="0 84% 60%" icon={ShieldAlert} testid="sod-critical" />
        <StatCard label="High conflicts" value={data.summary.High} accent="35 90% 55%" icon={ShieldAlert} testid="sod-high" />
        <StatCard label="Medium conflicts" value={data.summary.Medium} accent="190 90% 50%" icon={GitCompare} testid="sod-medium" />
        <StatCard label="Total rows" value={data.total} sub={`${rules.length} rules in library`} accent="142 70% 45%" icon={ShieldCheck} testid="sod-total" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Simulator */}
        <div className="lg:col-span-5 bg-card fact-border rounded-xl p-5" data-testid="sod-simulator">
          <div className="flex items-center gap-2 mb-1"><FlaskConical className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-base">Pre-Assignment Risk Simulation</h2></div>
          <p className="text-[11px] text-muted-foreground mb-3">Check which SoD conflicts a role assignment would introduce before approving it.</p>
          <div className="space-y-2">
            <Select value={simPerson} onValueChange={setSimPerson}><SelectTrigger data-testid="sim-person" className="h-9"><SelectValue placeholder="Select identity…" /></SelectTrigger>
              <SelectContent>{people.slice(0, 60).map((p) => <SelectItem key={p.ref} value={p.ref}>{p.name} · {p.department}</SelectItem>)}</SelectContent></Select>
            <div className="flex gap-2">
              <Select value={simRole} onValueChange={setSimRole}><SelectTrigger data-testid="sim-role" className="h-9 flex-1"><SelectValue placeholder="Add role…" /></SelectTrigger>
                <SelectContent>{roles.map((r) => <SelectItem key={r.ref} value={r.ref}>{r.name}</SelectItem>)}</SelectContent></Select>
              <Button data-testid="sim-add-role" variant="outline" className="h-9" onClick={addSimRole}>Add</Button>
            </div>
            {simRoles.length > 0 && <div className="flex flex-wrap gap-1.5">{simRoles.map((r) => <span key={r} className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary">{r}</span>)}</div>}
            <Button data-testid="sim-run" className="w-full" onClick={runSim}>Simulate</Button>
          </div>
          {simResult && (
            <div className="mt-4 border-t border-border pt-3" data-testid="sim-result">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs">Decision:</span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full" style={{ background: `hsl(${simResult.decision === "BLOCK" ? "0 84% 60%" : simResult.decision === "REVIEW" ? "35 90% 55%" : "142 70% 45%"} / 0.15)`, color: `hsl(${simResult.decision === "BLOCK" ? "0 84% 60%" : simResult.decision === "REVIEW" ? "35 90% 55%" : "142 70% 45%"})` }}>{simResult.decision}</span>
              </div>
              {simResult.introduced_conflicts.length === 0 ? <p className="text-xs text-low">No new conflicts introduced.</p> : (
                <div className="space-y-1.5">{simResult.introduced_conflicts.map((c) => (
                  <div key={c.conflict_ref} className="text-xs flex items-center gap-2"><Chip v={c.severity} /> {c.rule_name}</div>
                ))}</div>
              )}
            </div>
          )}
        </div>

        {/* Rule library */}
        <div className="lg:col-span-7 bg-card fact-border rounded-xl p-5" data-testid="sod-rules">
          <div className="flex items-center gap-2 mb-3"><ScrollText className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-base">SoD Rule Library</h2></div>
          <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
            {rules.map((r) => (
              <button key={r.ref} onClick={() => openRule(r)} data-testid={`sod-rule-${r.ref}`} className="w-full text-left flex items-start gap-3 p-2.5 rounded-lg bg-secondary/30 hover:bg-secondary/60 transition-colors">
                <Chip v={r.severity} />
                <div className="min-w-0">
                  <div className="text-sm font-medium">{r.name} <span className="text-[10px] font-mono text-muted-foreground">· {r.ref} · {r.area}</span></div>
                  <div className="text-[11px] text-muted-foreground">{r.function_a_label} ✕ {r.function_b_label}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Conflicts table */}
      <div className="bg-card fact-border rounded-xl">
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
          <h2 className="font-head font-bold text-base flex-1">Detected Conflicts</h2>
          <Select value={sev} onValueChange={setSev}><SelectTrigger data-testid="sod-filter-sev" className="w-[130px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All severity</SelectItem><SelectItem value="Critical">Critical</SelectItem><SelectItem value="High">High</SelectItem><SelectItem value="Medium">Medium</SelectItem></SelectContent></Select>
          <Select value={area} onValueChange={setArea}><SelectTrigger data-testid="sod-filter-area" className="w-[150px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All areas</SelectItem>{data.areas.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent></Select>
          <Select value={status} onValueChange={setStatus}><SelectTrigger data-testid="sod-filter-status" className="w-[140px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All statuses</SelectItem><SelectItem value="Open">Open</SelectItem><SelectItem value="Mitigated">Mitigated</SelectItem><SelectItem value="Accepted">Accepted</SelectItem></SelectContent></Select>
        </div>
        <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
          <table className="w-full text-sm" data-testid="sod-table">
            <thead className="sticky top-0 bg-card"><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
              <th className="p-3">Severity</th><th className="p-3">Rule</th><th className="p-3">User</th><th className="p-3">System</th><th className="p-3">Area</th><th className="p-3">Status</th><th className="p-3 text-right">Action</th>
            </tr></thead>
            <tbody>
              {data.conflicts.map((c) => (
                <tr key={c.conflict_ref} className="border-b border-border/50 hover:bg-secondary/30" data-testid={`sod-row-${c.conflict_ref}`}>
                  <td className="p-3"><Chip v={c.severity} /></td>
                  <td className="p-3"><button onClick={() => openConflict(c)} className="text-left hover:text-primary font-medium" data-testid={`sod-open-${c.conflict_ref}`}>{c.rule_name}</button></td>
                  <td className="p-3 whitespace-nowrap">{c.person_name}</td>
                  <td className="p-3 font-mono text-xs">{c.system}</td>
                  <td className="p-3 text-xs">{c.area}</td>
                  <td className="p-3"><Chip v={c.status} map={{ Open: "0 84% 60%", Mitigated: "142 70% 45%", Accepted: "35 90% 55%" }} /></td>
                  <td className="p-3 text-right"><button data-testid={`sod-mitigate-${c.conflict_ref}`} onClick={() => { setMit(c); setControl(c.mitigating_control || ""); setMitStatus(c.status === "Open" ? "Mitigated" : c.status); }} className="inline-flex items-center gap-1 text-xs text-ai hover:underline"><Wrench className="w-3.5 h-3.5" /> Mitigate</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={!!mit} onOpenChange={(o) => !o && setMit(null)}>
        <DialogContent data-testid="sod-mitigate-dialog">
          <DialogHeader><DialogTitle>Mitigate — {mit?.rule_name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">{mit?.business_risk}</p>
            <Textarea data-testid="mit-control" value={control} onChange={(e) => setControl(e.target.value)} placeholder="Describe the mitigating control (e.g. monthly detective review of payment runs by Controller)…" rows={3} />
            <Select value={mitStatus} onValueChange={setMitStatus}><SelectTrigger data-testid="mit-status" className="h-9"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="Mitigated">Mitigated (control in place)</SelectItem><SelectItem value="Accepted">Risk Accepted</SelectItem><SelectItem value="Open">Re-open (remove control)</SelectItem></SelectContent></Select>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setMit(null)}>Cancel</Button><Button data-testid="mit-save" disabled={busy} onClick={runMitigate}>{busy ? "Saving…" : "Save"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
