import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, FileDown, Link2, Loader2, Plus, ShieldAlert, X } from "lucide-react";
import { toast } from "sonner";
import { AIExplain } from "@/components/AIExplain";
import { api } from "@/lib/api";
import { DataClassBadge, PALETTE, StatusPill } from "@/components/control-intelligence/shared";

const pal = (i) => PALETTE[i % PALETTE.length];

export default function ControlDetailModal({
  control,
  isAdmin,
  onClose,
  onEvidencePack,
  onExportLog,
}) {
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [kind, setKind] = useState("remediation");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await api.get(`/controls/${control.control_id}/history`);
      setHistory(Array.isArray(response.data) ? response.data : []);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [control.control_id]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const addNote = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api.post(`/controls/${control.control_id}/notes`, { kind, text: text.trim() });
      setText("");
      toast.success("Control log updated.");
      await loadHistory();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to update control log.");
    } finally {
      setBusy(false);
    }
  };

  const frameworkEntries = Object.entries(control.frameworks || {}).filter(([, v]) => (Array.isArray(v) ? v.length : v));
  const criticality = control.criticality || "—";
  const critAccent =
    /crit/i.test(criticality) ? "0 84% 60%" : /high/i.test(criticality) ? "24 90% 55%" :
    /med/i.test(criticality) ? "35 90% 55%" : "142 70% 45%";
  const riskLevel = control.status === "Failing"
    ? "Critical"
    : control.drift || control.evidence_state === "Expired"
    ? "High"
    : control.evidence_state === "Expiring" || control.status !== "Passing"
    ? "Medium"
    : "Low";
  const riskAccent = riskLevel === "Critical" ? "0 84% 60%" : riskLevel === "High" ? "24 90% 55%" : riskLevel === "Medium" ? "35 90% 55%" : "142 70% 45%";

  const explainContext = {
    control_id: control.control_id,
    name: control.name,
    category: control.category,
    owner: control.owner,
    status: control.status,
    effectiveness: control.effectiveness,
    maturity: control.maturity,
    drift: control.drift,
    drift_delta: control.drift_delta,
    evidence_state: control.evidence_state,
    days_to_expiry: control.days_to_expiry,
    modeled_priority_score: control.priority_score,
    modeled_risk_level: riskLevel,
    criticality: control.criticality,
    related_risk: control.related_risk,
    frameworks: control.frameworks,
  };

  return createPortal((
    <div className="fixed inset-0 z-[70] bg-black/65 backdrop-blur-sm flex items-center justify-center p-4" data-testid="control-intel-detail-modal">
      <div className="w-full max-w-5xl max-h-[92vh] overflow-y-auto bg-card fact-border rounded-xl">
        <div className="sticky top-0 z-10 bg-card border-b border-border px-5 py-4 flex items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[10px] text-ai">{control.control_id}</div>
            <h2 className="font-head font-black text-2xl mt-1">{control.name}</h2>
            <div className="text-xs text-muted-foreground mt-1">{control.owner || "Unassigned"} · {control.category}</div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              <StatusPill value={control.status} />
              <StatusPill value={control.evidence_state} />
              <DataClassBadge kind="MODELLED" />
            </div>
          </div>
          <button onClick={onClose} data-testid="control-intel-detail-close" className="p-2 rounded-md hover:bg-secondary"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-5 space-y-5">
          {/* SCORING */}
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">Scoring</div>
            <div className="grid md:grid-cols-5 gap-3">
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Effectiveness</div><div className="font-head font-black text-2xl mt-1">{control.effectiveness}%</div></div>
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Maturity</div><div className="font-head font-black text-2xl mt-1">{control.maturity || 0}/5</div></div>
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Priority</div><div className="font-head font-black text-2xl mt-1">{control.priority_score}/100</div></div>
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Evidence</div><div className="font-head font-black text-xl mt-1">{control.evidence_state}</div></div>
              <div className="rounded-lg bg-secondary/30 p-3"><div className="text-[9px] font-mono uppercase text-muted-foreground">Expiry</div><div className="font-head font-black text-xl mt-1">{control.days_to_expiry != null ? `${control.days_to_expiry}d` : "—"}</div></div>
            </div>
          </div>

          {/* RISK + CONTROL ALIGNMENT */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-border p-4">
              <div className="font-head font-bold flex items-center gap-2"><ShieldAlert className="w-4 h-4" style={{ color: `hsl(${riskAccent})` }} /> Risk & criticality</div>
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Risk level</div><div className="font-head font-black text-xl mt-1" style={{ color: `hsl(${riskAccent})` }}>{riskLevel}</div></div>
                <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Criticality</div><div className="font-head font-black text-xl mt-1" style={{ color: `hsl(${critAccent})` }}>{criticality}</div></div>
              </div>
              <div className="mt-3 space-y-1.5 text-xs text-muted-foreground">
                <div className="flex items-center gap-2"><AlertTriangle className="w-3.5 h-3.5 text-med" /> Drift: {control.drift ? `Detected (Δ ${control.drift_delta ?? "?"})` : "Stable"}</div>
                {control.related_risk && <div>Related risk: <span className="font-mono text-foreground">{control.related_risk}</span></div>}
                {control.baseline != null && <div>Baseline effectiveness: <span className="font-mono text-foreground">{control.baseline}%</span></div>}
              </div>
            </div>

            <div className="rounded-xl border border-border p-4">
              <div className="font-head font-bold flex items-center gap-2"><Link2 className="w-4 h-4 text-ai" /> Control alignment</div>
              <div className="text-xs text-muted-foreground mt-1">Frameworks this control maps to (live feed).</div>
              {frameworkEntries.length === 0 ? (
                <div className="text-sm text-muted-foreground mt-3">No framework mappings returned for this control.</div>
              ) : (
                <div className="mt-3 space-y-2 max-h-40 overflow-y-auto">
                  {frameworkEntries.map(([fw, refs], i) => (
                    <div key={fw} className="flex items-start justify-between gap-2 rounded-lg border border-border px-3 py-2">
                      <span className="text-sm font-medium flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: `hsl(${pal(i)})` }} />{fw}</span>
                      <span className="font-mono text-[10px] text-muted-foreground text-right">{Array.isArray(refs) ? refs.join(", ") : String(refs)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* RECOMMENDATIONS & FIXES */}
          <AIExplain
            title={`${control.control_id} ${control.name}`}
            kind="control effectiveness maturity evidence drift framework compliance remediation fixes"
            context={explainContext}
            accent="168 76% 46%"
          />

          {/* HISTORY + ACTIONS */}
          <div className="grid xl:grid-cols-2 gap-5">
            <div>
              <div className="font-head font-bold">Control history</div>
              <div className="text-xs text-muted-foreground mt-1">Existing control notes, evidence and remediation history.</div>
              <div className="mt-3 max-h-80 overflow-y-auto space-y-2">
                {historyLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading history</div>
                ) : history.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No history records returned.</div>
                ) : (
                  history.map((entry, index) => (
                    <div key={`${entry.ts}:${index}`} className="rounded-lg border border-border p-3">
                      <div className="flex items-center justify-between gap-2">
                        <StatusPill value={entry.kind || "note"} />
                        <span className="text-[10px] font-mono text-muted-foreground">{entry.ts ? new Date(entry.ts).toLocaleString() : ""}</span>
                      </div>
                      <div className="text-sm mt-2">{entry.text}</div>
                      {entry.author && <div className="text-[10px] text-muted-foreground mt-1">{entry.author}</div>}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div>
              <div className="font-head font-bold">Evidence and remediation actions</div>
              <div className="grid grid-cols-2 gap-2 mt-3">
                <button onClick={() => onEvidencePack(control)} data-testid="control-intel-detail-evidence-pack" className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Evidence Pack</button>
                <button onClick={() => onExportLog(control)} data-testid="control-intel-detail-log" className="px-3 py-2 rounded-md border border-border bg-secondary text-xs font-head font-bold flex items-center justify-center gap-1.5"><FileDown className="w-3.5 h-3.5" /> Control Log</button>
              </div>

              {isAdmin && (
                <div className="mt-5">
                  <div className="text-[10px] font-mono uppercase text-muted-foreground">Add to control log</div>
                  <select value={kind} onChange={(e) => setKind(e.target.value)} data-testid="control-intel-note-kind" className="mt-2 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm">
                    <option value="remediation">Remediation</option>
                    <option value="evidence">Evidence</option>
                    <option value="note">Note</option>
                  </select>
                  <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} data-testid="control-intel-note-text" placeholder="Add evidence context, remediation progress or an audit note" className="mt-2 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
                  <button onClick={addNote} disabled={busy || !text.trim()} data-testid="control-intel-note-add" className="mt-2 w-full px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold flex items-center justify-center gap-1.5 disabled:opacity-50">
                    {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Add to Control Log
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  ), document.body);
}
