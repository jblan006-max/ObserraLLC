import { useEffect, useState } from "react";
import { ArrowRight, ArrowLeft, FlaskConical, Loader2, X, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const STEPS = [
  {
    tab: "mission",
    eyebrow: "Mission Control",
    title: "At-risk controls surface instantly",
    body: "We seeded a live demo journey. Watch the AT-RISK and INEFFECTIVE counts jump and the AI Control Advisor flag the weakest control — every number recomputed from the (demo) control feed.",
  },
  {
    tab: "remediation",
    eyebrow: "Remediation & Drift",
    title: "Owners get nudged automatically",
    body: "The priority queue fills with the at-risk controls grouped by owner, and the owner-reminder preview opens on its own so you can see exactly who Obserra would nudge.",
  },
  {
    tab: "defensibility",
    eyebrow: "Defensibility",
    title: "Every auditor touch is on the record",
    body: "Access log, reviewer timeline (view\u2192download timing), engagement analytics and the weekly assurance recap — a full chain of custody. Each row is clearly tagged DEMO.",
  },
  {
    tab: "defensibility",
    eyebrow: "All done",
    title: "That's the prospect walkthrough",
    body: "Everything you just saw was clearly-labelled DEMO data, kept fully separate from live evidence. Clear it when you're finished — the header ribbon can also clear it in one tap.",
    finish: true,
  },
];

export function ProspectTour({ open, onClose, openTab }) {
  const [step, setStep] = useState(0);
  const [seeding, setSeeding] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    (async () => {
      setSeeding(true);
      try {
        await api.post("/control-intelligence/auditor-link/demo/seed");
        window.dispatchEvent(new Event("ci-demo-changed"));
      } catch (e) {
        toast.error("Unable to start the walkthrough demo.");
      } finally {
        if (!cancelled) {
          setSeeding(false);
          setStep(0);
          openTab?.(STEPS[0].tab);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;
  const s = STEPS[step];
  const go = (i) => {
    setStep(i);
    openTab?.(STEPS[i].tab);
  };

  const clearAndClose = async () => {
    setBusy(true);
    try {
      await api.post("/control-intelligence/auditor-link/demo/clear");
      window.dispatchEvent(new Event("ci-demo-changed"));
      toast.success("Demo cleared.");
    } catch (e) {
      toast.error("Unable to clear the demo.");
    } finally {
      setBusy(false);
      onClose?.();
    }
  };

  return (
    <div data-testid="prospect-tour" className="fixed inset-x-0 bottom-0 z-[9998] flex justify-center p-4 pointer-events-none">
      <div className="pointer-events-auto w-full max-w-lg rounded-2xl border border-med/40 bg-card shadow-2xl rise overflow-hidden">
        <div className="h-1 w-full bg-secondary/60">
          <div
            className="h-full bg-med transition-all duration-300"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>
        <div className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[10px] font-mono uppercase tracking-widest text-med flex items-center gap-1.5">
                <FlaskConical className="w-3 h-3" /> Prospect walkthrough · {s.eyebrow}
              </div>
              <h2 data-testid="prospect-tour-title" className="font-head font-black text-xl mt-1">
                {s.title}
              </h2>
            </div>
            <button
              onClick={onClose}
              data-testid="prospect-tour-close"
              className="shrink-0 text-muted-foreground hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed mt-2">
            {seeding ? "Seeding a live demo journey\u2026" : s.body}
          </p>
          <div className="flex items-center gap-2 mt-5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all ${i === step ? "w-6 bg-med" : "w-1.5 bg-secondary"}`}
              />
            ))}
            <div className="flex-1" />
            {step > 0 && (
              <button
                onClick={() => go(step - 1)}
                data-testid="prospect-tour-back"
                className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back
              </button>
            )}
            {s.finish ? (
              <>
                <button
                  onClick={onClose}
                  data-testid="prospect-tour-keep"
                  className="rounded-lg border border-border px-3 py-2 text-xs font-head font-bold text-muted-foreground hover:text-foreground"
                >
                  Keep demo
                </button>
                <button
                  onClick={clearAndClose}
                  disabled={busy}
                  data-testid="prospect-tour-clear"
                  className="flex items-center gap-1.5 rounded-lg bg-crit/90 text-white px-4 py-2 text-xs font-head font-bold disabled:opacity-50"
                >
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} Clear demo &amp; finish
                </button>
              </>
            ) : (
              <button
                onClick={() => go(step + 1)}
                disabled={seeding}
                data-testid="prospect-tour-next"
                className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-head font-bold disabled:opacity-50"
              >
                Next <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
