import { useEffect, useState } from "react";
import { ArrowRight, ArrowLeft, Siren, X } from "lucide-react";

const STEPS = [
  {
    tab: "mission",
    target: "crisis-kpi-severity",
    eyebrow: "Mission Control",
    title: "The command center",
    body: "Six live KPIs — crisis severity, modeled crisis score, active incidents, financial exposure, decisions pending and response progress — all recomputed from the live risk, incident, control and response feeds.",
  },
  {
    tab: "command",
    target: "crisis-incident-command",
    eyebrow: "Incident Command",
    title: "Persistent crisis cases",
    body: "Open a crisis case with an incident commander and executive sponsor, then drive it through Detection to Recovery. Every case, action and event is stored and audit-logged.",
  },
  {
    tab: "decisions",
    target: "crisis-decision-room",
    eyebrow: "Executive Decision Room",
    title: "Decisions that can't wait",
    body: "Raise time-critical executive decisions with business and technical impact context, then approve them in one tap. Each approval is written to the audit trail.",
  },
  {
    tab: "impact",
    target: "crisis-business-impact",
    eyebrow: "Business Impact",
    title: "Technical event to business consequence",
    body: "Residual financial exposure and the highest-value enterprise risks, drawn straight from the risk engine — no invented loss numbers.",
  },
  {
    tab: "response",
    target: "crisis-response-actions",
    eyebrow: "Containment & Recovery",
    title: "Track every response action",
    body: "Containment, recovery, legal and communication actions move Open to Executing to Verified. External containment is never claimed until an integrated system verifies it.",
  },
  {
    tab: "timeline",
    target: "crisis-timeline",
    eyebrow: "Timeline & Evidence",
    title: "A forensic chain of custody",
    body: "Crisis events, incident timestamps and audit records merge into one executive timeline — every row tagged FACT.",
  },
  {
    tab: "briefing",
    target: "crisis-briefing",
    eyebrow: "Executive Briefing",
    title: "Board-ready in one click",
    body: "The Obserra Crisis Advisor summarizes the whole crisis, and the board brief exports as a sealed PDF. That's the walkthrough — jump into any tab to command a live crisis.",
    finish: true,
  },
];

export function CrisisTour({ open, onClose, openTab }) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState(null);

  useEffect(() => {
    if (!open) return;
    setStep(0);
    openTab?.(STEPS[0].tab);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return undefined;
    const targetId = STEPS[step].target;
    const measure = () => {
      if (!targetId) return setRect(null);
      const el = document.querySelector(`[data-testid="${targetId}"]`);
      if (!el) return setRect(null);
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    const scrollT = setTimeout(() => {
      if (targetId) {
        document.querySelector(`[data-testid="${targetId}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 120);
    const t1 = setTimeout(measure, 520);
    const t2 = setTimeout(measure, 950);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      clearTimeout(scrollT);
      clearTimeout(t1);
      clearTimeout(t2);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [open, step]);

  if (!open) return null;
  const s = STEPS[step];
  const go = (i) => {
    setStep(i);
    openTab?.(STEPS[i].tab);
  };

  return (
    <>
      {rect && (
        <div
          data-testid="crisis-tour-spotlight"
          className="fixed z-[9997] pointer-events-none rounded-xl ring-4 ring-crit transition-all duration-300"
          style={{
            top: rect.top - 8,
            left: rect.left - 8,
            width: rect.width + 16,
            height: rect.height + 16,
            boxShadow: "0 0 0 9999px rgba(3, 7, 18, 0.55)",
          }}
        />
      )}
      <div data-testid="crisis-tour" className="fixed inset-x-0 bottom-0 z-[9998] flex justify-center p-4 pointer-events-none">
        <div className="pointer-events-auto w-full max-w-lg rounded-2xl border border-crit/40 bg-card shadow-2xl rise overflow-hidden">
          <div className="h-1 w-full bg-secondary/60">
            <div className="h-full bg-crit transition-all duration-300" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
          </div>
          <div className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[10px] font-mono uppercase tracking-widest text-crit flex items-center gap-1.5">
                  <Siren className="w-3 h-3" /> Crisis walkthrough · {s.eyebrow}
                </div>
                <h2 data-testid="crisis-tour-title" className="font-head font-black text-xl mt-1">{s.title}</h2>
              </div>
              <button onClick={onClose} data-testid="crisis-tour-close" className="shrink-0 text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mt-2">{s.body}</p>
            <div className="flex items-center gap-2 mt-5">
              {STEPS.map((_, i) => (
                <span key={i} className={`h-1.5 rounded-full transition-all ${i === step ? "w-6 bg-crit" : "w-1.5 bg-secondary"}`} />
              ))}
              <div className="flex-1" />
              {step > 0 && (
                <button onClick={() => go(step - 1)} data-testid="crisis-tour-back" className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground">
                  <ArrowLeft className="w-3.5 h-3.5" /> Back
                </button>
              )}
              {s.finish ? (
                <button onClick={onClose} data-testid="crisis-tour-finish" className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-head font-bold">
                  Finish
                </button>
              ) : (
                <button onClick={() => go(step + 1)} data-testid="crisis-tour-next" className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-head font-bold">
                  Next <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
