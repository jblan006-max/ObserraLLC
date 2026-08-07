import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { X, Loader2, CheckCircle2, Circle, UserCheck, ShieldCheck, Clock, AlertTriangle } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STATUS_COLOR = { open: "35 90% 55%", in_progress: "190 90% 50%", resolved: "142 70% 45%" };

function slaInfo(wf) {
  if (!wf.due_at) return null;
  const due = new Date(wf.due_at);
  const days = Math.ceil((due - Date.now()) / 86400000);
  const overdue = wf.status !== "resolved" && days < 0;
  return { due, days, overdue };
}

export function RemediationModal({ workflow, onChanged, onClose }) {
  const [wf, setWf] = useState(workflow);
  const [assignee, setAssignee] = useState(workflow?.assignee || "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [members, setMembers] = useState([]);

  useEffect(() => { api.get("/members").then((r) => setMembers(r.data)).catch(() => {}); }, []);
  if (!wf) return null;
  const sla = slaInfo(wf);

  const act = async (action) => {
    setBusy(action);
    try {
      const { data } = await api.post(`/workflows/${wf.id}/action`, {
        action, assignee: assignee || undefined, note: note || undefined,
      });
      setWf(data); setNote("");
      toast.success(`Remediation ${data.status.replace("_", " ")}`);
      onChanged?.();
      if (action === "resolve") setTimeout(onClose, 700);
    } catch { toast.error("Action failed"); }
    setBusy("");
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" data-testid="remediation-modal">
      <div className="w-full max-w-md bg-card fact-border rounded-xl p-6 rise">
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-primary" /><h2 className="font-head font-black text-xl">Remediation · {wf.subject}</h2></div>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-xs px-2 py-0.5 rounded-sm font-mono inline-block capitalize" style={{ background: `hsl(${STATUS_COLOR[wf.status]} / 0.15)`, color: `hsl(${STATUS_COLOR[wf.status]})` }}>{wf.status.replace("_", " ")}</span>
              {sla && (sla.overdue
                ? <span data-testid="sla-overdue" className="text-xs px-2 py-0.5 rounded-sm font-mono bg-crit/15 text-crit flex items-center gap-1"><AlertTriangle className="w-3 h-3" />Overdue {Math.abs(sla.days)}d</span>
                : wf.status !== "resolved" && <span data-testid="sla-due" className="text-xs px-2 py-0.5 rounded-sm font-mono bg-secondary/60 text-muted-foreground flex items-center gap-1"><Clock className="w-3 h-3" />Due in {sla.days}d</span>)}
            </div>
          </div>
          <button data-testid="remediation-close" onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>

        <div className="space-y-2 mb-5">
          {wf.steps.map((s) => (
            <div key={s.key} className={`flex items-center gap-2 text-sm ${s.done ? "text-foreground" : "text-muted-foreground"}`}>
              {s.done ? <CheckCircle2 className="w-4 h-4 text-low" /> : <Circle className="w-4 h-4" />} {s.label}
            </div>
          ))}
        </div>

        {wf.assignee && <div className="text-xs text-muted-foreground mb-3 flex items-center gap-1"><UserCheck className="w-3.5 h-3.5" /> Assigned to <span className="text-foreground">{wf.assignee}</span></div>}

        {wf.status !== "resolved" && (
          <div className="space-y-3">
            <div>
              <span className="text-xs font-medium text-muted-foreground mb-1.5 block">Assign to teammate</span>
              <Select value={assignee} onValueChange={setAssignee}>
                <SelectTrigger data-testid="remediation-assignee" className="bg-secondary/60"><SelectValue placeholder="Select an owner…" /></SelectTrigger>
                <SelectContent>
                  {members.map((m) => <SelectItem key={m.email} value={m.name}>{m.name} · {m.role}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <textarea data-testid="remediation-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2}
              placeholder="Add a note…" className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
            <div className="flex gap-2">
              <button data-testid="remediation-accept" disabled={!!busy} onClick={() => act("accept")}
                className="flex-1 py-2 rounded-md bg-secondary/60 hover:bg-secondary text-sm font-medium disabled:opacity-50">Accept</button>
              <button data-testid="remediation-assign" disabled={!!busy || !assignee} onClick={() => act("assign")}
                className="flex-1 py-2 rounded-md bg-ai/15 border border-ai/40 text-ai text-sm font-medium disabled:opacity-50">Assign</button>
              <button data-testid="remediation-resolve" disabled={!!busy} onClick={() => act("resolve")}
                className="flex-1 py-2 rounded-md bg-primary text-primary-foreground text-sm font-head font-bold disabled:opacity-50">
                {busy === "resolve" ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Resolve"}
              </button>
            </div>
          </div>
        )}

        {wf.notes?.length > 0 && (
          <div className="mt-4 space-y-1 max-h-28 overflow-y-auto border-t border-border/60 pt-3">
            {wf.notes.map((n, i) => <div key={i} className="text-[11px] text-muted-foreground">• {n.note}</div>)}
          </div>
        )}
      </div>
    </div>
  );
}
