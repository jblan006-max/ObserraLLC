import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Sparkles, Loader2, ShieldAlert, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

const RATE = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "199 89% 48%", Low: "142 70% 45%" };

// Reusable AI risk-rating + "how to fix" block for any SAP entity (identity, SoD conflict, role,
// account). Rating is grounded server-side in the live access model; the recommendation is AI-written.
// When the fix maps to a real remediation workflow, a one-tap "Apply this fix" button runs it.
// Obserra-standard — mirrors components/AIFix.jsx.
export function AIFix({ entity, refId, accent = "266 85% 66%", onApplied }) {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [applying, setApplying] = useState(false);

  const fetchFix = () => {
    if (!refId) { setD(null); return; }
    setLoading(true);
    api.post("/sap/fix", { entity, ref: refId })
      .then((r) => setD(r.data)).catch(() => setD(null)).finally(() => setLoading(false));
  };
  useEffect(() => { setConfirming(false); setReason(""); fetchFix(); /* eslint-disable-next-line */ }, [entity, refId]);

  const apply = async () => {
    if (!d?.fix_action) return;
    setApplying(true);
    try {
      const fa = d.fix_action;
      const note = reason || "One-tap remediation applied from the AI fix recommendation";
      const { data } = await api.post(fa.endpoint, { ...fa.payload, reason: note, work_note: note });
      const ticket = data?.ticket?.number || data?.tickets?.[0]?.number;
      toast.success(`${fa.label} applied`, { description: ticket ? `ServiceNow ${ticket} opened & auto-closed` : "Recorded to the audit trail" });
      setConfirming(false); setReason("");
      onApplied?.();
      fetchFix();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not apply the fix");
    }
    setApplying(false);
  };

  const rc = d ? RATE[d.rating] || accent : accent;
  return (
    <div data-testid="sap-ai-fix" className="rounded-lg p-3 border" style={{ borderColor: `hsl(${accent} / 0.35)`, background: `hsl(${accent} / 0.05)` }}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider" style={{ color: `hsl(${accent})` }}><Sparkles className="w-3 h-3" /> AI risk rating &amp; fix</div>
        {d && <span data-testid="sap-ai-fix-rating" className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full" style={{ background: `hsl(${rc} / 0.15)`, color: `hsl(${rc})` }}>{d.rating} RISK · {d.score}/100</span>}
      </div>
      {loading && !d && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing the live SAP access model…</div>}
      {d && (
        <div className="space-y-2">
          {d.rationale?.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><ShieldAlert className="w-3 h-3" /> Why this rating</div>
              <ul className="space-y-1" data-testid="sap-ai-fix-rationale">
                {d.rationale.map((r, i) => <li key={i} className="text-[11px] text-foreground/85 flex gap-1.5"><span style={{ color: `hsl(${rc})` }}>•</span> {r}</li>)}
              </ul>
            </div>
          )}
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: `hsl(${accent})` }}>AI recommendation to fix</div>
            <p className="text-sm text-foreground/90 leading-relaxed" data-testid="sap-ai-fix-recommendation">{d.recommendation}</p>
            {d.steps?.length > 0 && (
              <ul className="mt-1.5 space-y-1">
                {d.steps.map((s, i) => <li key={i} className="text-[12px] flex items-start gap-2"><span style={{ color: `hsl(${accent})` }}>→</span> {s}</li>)}
              </ul>
            )}
          </div>
          {d.fix_action && (
            <div className="pt-1" data-testid="sap-ai-fix-apply-wrap">
              {!confirming ? (
                <Button size="sm" className="h-8 gap-1.5" data-testid="sap-ai-fix-apply" onClick={() => setConfirming(true)}>
                  <Wrench className="w-3.5 h-3.5" /> Apply this fix — {d.fix_action.label}
                </Button>
              ) : (
                <div className="space-y-2 rounded-md border border-border/60 p-2" data-testid="sap-ai-fix-confirm">
                  <p className="text-[11px] text-muted-foreground">{d.fix_action.confirm}</p>
                  <Textarea data-testid="sap-ai-fix-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ServiceNow work note (optional)…" rows={2} className="text-xs" />
                  <div className="flex gap-2">
                    <Button size="sm" className="h-8 gap-1.5" data-testid="sap-ai-fix-confirm-btn" disabled={applying} onClick={apply}>{applying ? "Applying…" : "Confirm & run workflow"}</Button>
                    <Button size="sm" variant="outline" className="h-8" onClick={() => setConfirming(false)} disabled={applying}>Cancel</Button>
                  </div>
                </div>
              )}
            </div>
          )}
          {d.model && <div className="text-[9px] font-mono text-muted-foreground pt-1">{d.model} · grounded in the live SAP access snapshot</div>}
        </div>
      )}
    </div>
  );
}
