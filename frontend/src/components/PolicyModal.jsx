import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { X, Loader2, Activity } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const SEVERITIES = ["Low", "Medium", "High", "Critical"];
const THRESHOLD_POLICIES = ["POL-EVID-FRESH", "POL-CTRL-EFFECT", "POL-CTRL-DRIFT"];

export function PolicyModal({ policy, onClose, onSaved }) {
  const editing = !!policy;
  const canSimulate = editing && THRESHOLD_POLICIES.includes(policy.policy_id);
  const [form, setForm] = useState({
    name: policy?.name || "", statement: policy?.statement || "",
    framework: policy?.framework || "Custom", severity: policy?.severity || "Medium",
    enforced: policy?.enforced ?? true, threshold: policy?.threshold ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [sim, setSim] = useState(null);
  const timer = useRef(null);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  useEffect(() => {
    if (!canSimulate || form.threshold === "") { setSim(null); return; }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api.post("/policies/simulate", { policy_id: policy.policy_id, threshold: Number(form.threshold) })
        .then((r) => setSim(r.data)).catch(() => setSim(null));
    }, 400);
    return () => clearTimeout(timer.current);
  }, [form.threshold, canSimulate, policy]);

  const save = async () => {
    if (!form.name.trim() || !form.statement.trim()) { toast.error("Name and statement are required"); return; }
    setBusy(true);
    const payload = { ...form, threshold: form.threshold === "" ? null : Number(form.threshold) };
    try {
      if (editing) await api.patch(`/policies/${policy.policy_id}`, payload);
      else await api.post("/policies", payload);
      toast.success(editing ? "Policy updated" : "Policy created");
      onSaved(); onClose();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" data-testid="policy-modal">
      <div className="w-full max-w-md bg-card fact-border rounded-xl p-6 rise">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-head font-black text-xl">{editing ? `Edit ${policy.policy_id}` : "New Policy"}</h2>
          <button data-testid="policy-close" onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>
        <div className="space-y-3">
          <Field label="Name" testid="policy-name" value={form.name} onChange={set("name")} />
          <label className="block">
            <span className="text-xs font-medium text-muted-foreground mb-1.5 block">Statement</span>
            <textarea data-testid="policy-statement" value={form.statement} onChange={set("statement")} rows={3}
              className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
          </label>
          <Field label="Framework" testid="policy-framework" value={form.framework} onChange={set("framework")} />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="text-xs font-medium text-muted-foreground mb-1.5 block">Severity</span>
              <Select value={form.severity} onValueChange={(v) => setForm((f) => ({ ...f, severity: v }))}>
                <SelectTrigger data-testid="policy-severity" className="bg-secondary/60"><SelectValue /></SelectTrigger>
                <SelectContent>{SEVERITIES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Field label="Threshold" testid="policy-threshold" type="number" value={form.threshold} onChange={set("threshold")} />
          </div>
          {canSimulate && sim && sim.applies && (
            <div data-testid="policy-simulation" className="ai-border rounded-md p-3 bg-ai/5 flex items-center gap-2 text-sm">
              <Activity className="w-4 h-4 text-ai" />
              <span>This threshold would flag <b data-testid="sim-flagged">{sim.flagged}</b> of {sim.total} controls{sim.flagged > 0 ? `: ${sim.controls.join(", ")}` : ""}.</span>
            </div>
          )}
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input data-testid="policy-enforced" type="checkbox" checked={form.enforced} onChange={(e) => setForm((f) => ({ ...f, enforced: e.target.checked }))} />
            Enforced (actively evaluated)
          </label>
        </div>
        <button data-testid="policy-save" disabled={busy} onClick={save}
          className="w-full mt-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-50">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />} {editing ? "Save changes" : "Create policy"}
        </button>
      </div>
    </div>
  );
}

function Field({ label, testid, type = "text", ...props }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted-foreground mb-1.5 block">{label}</span>
      <input data-testid={testid} type={type} {...props}
        className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
    </label>
  );
}
