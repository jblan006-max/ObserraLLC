import { useEffect, useState } from "react";
import { X, Loader2, Database, User, GitBranch, ShieldCheck, BookOpen, DollarSign } from "lucide-react";
import { api } from "@/lib/api";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString();
const pct = (v) => v == null ? "—" : Math.round(v * 100) + "%";

export function EvidenceModal({ kind, refId, onClose }) {
  const [e, setE] = useState(null);
  useEffect(() => { if (refId) { setE(null); api.get(`/evidence/${kind}/${refId}`).then((r) => setE(r.data)).catch(() => setE(false)); } }, [kind, refId]);
  if (!refId) return null;

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div data-testid="evidence-modal" onClick={(ev) => ev.stopPropagation()}
        className="w-full max-w-2xl max-h-[85vh] bg-card border border-border rounded-xl flex flex-col rise overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">Evidence Intelligence</div>
          <button data-testid="evidence-close" onClick={onClose} className="p-1.5 rounded-md hover:bg-secondary"><X className="w-4 h-4" /></button>
        </div>
        {!e ? <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div> : (
          <div className="flex-1 overflow-y-auto p-6 space-y-5">
            <div>
              <div className="text-sm text-muted-foreground">{e.metric}</div>
              <div className="font-head font-black text-4xl text-ai">{e.value}</div>
            </div>

            <div className="flex flex-wrap gap-1 text-[10px] font-mono text-muted-foreground">
              {[["Metric", e.metric], ["Calculation", "→"], ["Source", "→"], ["Evidence", "→"], ["Control", "→"], ["Risk", "→"], ["Framework", "→"], ["Owner", ""]].map(([k], i, a) => (
                <span key={k} className="flex items-center gap-1"><span className="px-1.5 py-0.5 rounded-sm bg-secondary/60 text-foreground">{k}</span>{i < a.length - 1 && <span className="text-ai">›</span>}</span>
              ))}
            </div>

            <div className="rounded-lg bg-secondary/30 border border-border p-4">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Calculation methodology</div>
              <div className="text-sm">{e.calculation}</div>
              <div className="text-xs text-muted-foreground mt-1">{e.methodology}</div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <Field icon={Database} label="Source system" value={e.source_system} sub={`record ${e.source_record}`} />
              <Field icon={User} label="Evidence owner" value={e.evidence_owner} sub={`validation: ${e.human_validation}`} />
              <Field icon={ShieldCheck} label="Related control" value={(e.related_controls || []).join(", ")} />
              <Field icon={GitBranch} label="Related risk" value={(e.related_risks || []).join(", ") || "—"} />
            </div>

            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5 flex items-center gap-1"><BookOpen className="w-3 h-3" /> Framework mapping</div>
              <div className="flex flex-wrap gap-1.5">
                {(e.frameworks || []).map((f) => <span key={f} className="text-[11px] font-mono px-2 py-1 rounded-sm border border-low/40 text-low">{f}</span>)}
              </div>
            </div>

            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Evidence records</div>
              <ul className="space-y-1">{(e.evidence || []).filter(Boolean).map((x, i) => <li key={i} className="text-sm text-foreground/90 flex gap-2"><span className="text-ai">•</span>{x}</li>)}</ul>
            </div>

            <div className="grid grid-cols-4 gap-3">
              {[["Freshness", e.freshness === "live" ? "Live" : ">24h"], ["Confidence", pct(e.confidence)], ["Completeness", pct(e.completeness)], ["Reliability", pct(e.reliability)]].map(([k, v]) => (
                <div key={k} className="rounded-md bg-secondary/30 border border-border p-2.5 text-center"><div className="text-[9px] font-mono uppercase text-muted-foreground">{k}</div><div className="font-head font-bold">{v}</div></div>
              ))}
            </div>

            {e.financial && (
              <div className="ai-border rounded-lg p-4">
                <div className="text-[10px] font-mono uppercase text-ai mb-2 flex items-center gap-1"><DollarSign className="w-3 h-3" /> Financial quantification</div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div><div className="text-[10px] text-muted-foreground">Inherent ALE</div><div className="font-head font-bold">{fmt(e.financial.inherent_ale)}</div></div>
                  <div><div className="text-[10px] text-muted-foreground">Residual ALE</div><div className="font-head font-bold text-high">{fmt(e.financial.residual_ale)}</div></div>
                  <div><div className="text-[10px] text-muted-foreground">Risk-adjusted</div><div className="font-head font-bold">{fmt(e.financial.risk_adjusted)}</div></div>
                </div>
              </div>
            )}

            <div className="text-[10px] font-mono text-muted-foreground">Last verified: {e.last_verified ? new Date(e.last_verified).toLocaleString() : "—"} · AI reasoning: {e.ai_reasoning}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ icon: Icon, label, value, sub }) {
  return (
    <div className="rounded-md bg-secondary/30 border border-border p-3">
      <div className="text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1"><Icon className="w-3 h-3" /> {label}</div>
      <div className="mt-0.5">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}
