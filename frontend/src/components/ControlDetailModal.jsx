import { X, ShieldCheck, Layers, Info, CheckCircle2, XCircle, MinusCircle } from "lucide-react";
import { AIFix } from "@/components/AIFix";

const STATUS = {
  aligned: { label: "Aligned — evidence-backed", color: "142 70% 45%", Icon: CheckCircle2 },
  met: { label: "Met by default (unverified)", color: "199 70% 50%", Icon: CheckCircle2 },
  gap: { label: "Gap — open finding", color: "0 84% 60%", Icon: XCircle },
  not_assessed: { label: "Not assessed", color: "215 15% 55%", Icon: MinusCircle },
  Passing: { label: "Passing", color: "142 70% 45%", Icon: CheckCircle2 },
  Drifting: { label: "Drifting", color: "35 90% 55%", Icon: Info },
  Failing: { label: "Failing", color: "0 84% 60%", Icon: XCircle },
  "Evidence Stale": { label: "Evidence stale", color: "15 80% 55%", Icon: Info },
};

// Clickable control drill-down for the Compliance crosswalk: framework mapping + status +
// the AI risk rating & recommended action (grounded per-control via /advisor/fix).
export function ControlDetailModal({ focus, accent = "160 84% 39%", onClose }) {
  if (!focus) return null;
  const st = STATUS[focus.status] || STATUS.met;
  const StIcon = st.Icon;
  const isGap = focus.status === "gap" || focus.status === "Failing" || focus.status === "Drifting" || focus.status === "Evidence Stale";
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div data-testid="control-detail-modal" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl max-h-[86vh] overflow-y-auto bg-card border rounded-2xl p-6 space-y-4 rise"
        style={{ borderColor: `hsl(${accent} / 0.4)`, boxShadow: `inset 0 1px 0 hsl(${accent} / 0.3)` }}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[11px]" style={{ color: `hsl(${accent})` }}>{focus.ref}</div>
            <div className="font-head font-black text-xl tracking-tight break-words">{focus.title}</div>
            <div className="text-xs text-muted-foreground">{focus.subtitle}</div>
          </div>
          <button data-testid="control-modal-close" onClick={onClose} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span data-testid="control-modal-status" className="inline-flex items-center gap-1.5 text-[11px] font-mono font-bold px-2.5 py-1 rounded-full"
            style={{ background: `hsl(${st.color} / 0.15)`, color: `hsl(${st.color})` }}>
            <StIcon className="w-3.5 h-3.5" /> {st.label}
          </span>
          {focus.criticality && <span className="text-[10px] font-mono uppercase px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">{focus.criticality} criticality</span>}
          {focus.effectiveness != null && <span className="text-[10px] font-mono px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground">{focus.effectiveness}% effective</span>}
        </div>

        {/* AI risk rating & recommended action — grounded per control */}
        {focus.obserraId ? (
          <div data-testid="control-modal-aifix"><AIFix entity="control" refId={focus.obserraId} accent={accent} /></div>
        ) : isGap ? (
          <div data-testid="control-modal-policygap" className="rounded-lg p-3 border" style={{ borderColor: `hsl(0 84% 60% / 0.35)`, background: "hsl(0 84% 60% / 0.05)" }}>
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-crit mb-1"><Info className="w-3 h-3" /> Recommended action</div>
            <p className="text-sm text-foreground/90 leading-relaxed">{focus.recommendation || "No Obserra control is mapped to this requirement yet. Author a compensating control and attach evidence, then re-scan to move it from Gap → Aligned."}</p>
          </div>
        ) : (
          <div data-testid="control-modal-note" className="rounded-lg p-3 border" style={{ borderColor: `hsl(${accent} / 0.35)`, background: `hsl(${accent} / 0.05)` }}>
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: `hsl(${accent})` }}><ShieldCheck className="w-3 h-3" /> Posture &amp; recommended action</div>
            <p className="text-sm text-foreground/90 leading-relaxed">{focus.recommendation || "Met by default from the hardened baseline posture. Collect and attach independent evidence (or run a live self-scan) to strengthen this requirement from Met → Aligned."}</p>
          </div>
        )}

        {/* Why this verdict */}
        {focus.why && (
          <div className="bg-secondary/20 rounded-lg p-3">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><Info className="w-3 h-3" /> Why this verdict</div>
            <p className="text-xs text-foreground/85 leading-relaxed">{focus.why}</p>
          </div>
        )}

        {/* Framework crosswalk mapping */}
        {focus.mappings && (
          <div className="bg-secondary/20 rounded-lg p-3 space-y-2" data-testid="control-modal-mappings">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Layers className="w-3 h-3" /> Mapped across frameworks</div>
            {Object.entries(focus.mappings).map(([fw, ids]) => (
              <div key={fw} className="flex items-start gap-2 text-xs py-1 border-b border-border/40 last:border-0">
                <span className="w-24 shrink-0 text-muted-foreground">{fw}</span>
                <div className="flex flex-wrap gap-1 min-w-0">
                  {(ids || []).length === 0 ? <span className="text-muted-foreground/50 italic">n/a</span> :
                    ids.map((id) => <span key={id} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{id}</span>)}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Covered-by Obserra controls (framework-browser context) */}
        {focus.mappedTo?.length > 0 && (
          <div className="bg-secondary/20 rounded-lg p-3" data-testid="control-modal-coveredby">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1"><ShieldCheck className="w-3 h-3" /> Covered by Obserra controls</div>
            <div className="flex flex-wrap gap-1.5">
              {focus.mappedTo.map((m) => (
                <span key={m.control_id} className="text-[10px] font-mono px-2 py-0.5 rounded-sm border"
                  style={{ background: `hsl(${m.compliant ? "142 70% 45%" : "0 84% 60%"} / 0.1)`, color: `hsl(${m.compliant ? "142 70% 45%" : "0 84% 60%"})`, borderColor: `hsl(${m.compliant ? "142 70% 45%" : "0 84% 60%"} / 0.2)` }}>
                  {m.control_id} · {m.effectiveness}%
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
