import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Presentation, Wrench, Eye, ArrowRight, ArrowLeft } from "lucide-react";

const STEPS = [
  {
    icon: Eye,
    accent: "text-ai",
    title: "Welcome to Obserra",
    body: "One evidence-grounded platform, viewed at two altitudes. Every metric carries its source, freshness and confidence — switch altitude anytime from the toggle in the top bar.",
  },
  {
    icon: Presentation,
    accent: "text-primary",
    title: "Executive Mode",
    body: "The boardroom view. KPIs are framed in dollar-impact and posture — financial exposure, risk reduction and compliance readiness — so leadership sees what matters without the noise.",
  },
  {
    icon: Wrench,
    accent: "text-ai",
    title: "Operational Mode",
    body: "The hands-on view. The same data as live counts and signals — open risks, control gaps, connector health — so your team can act on specifics in real time.",
  },
];

export const OnboardingTour = () => {
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [open, setOpen] = useState(false);

  const key = user ? `obserra-tour-done-${user.id || user.email}` : null;

  useEffect(() => {
    if (!key) return;
    if (localStorage.getItem(key)) return;
    const t = setTimeout(() => setOpen(true), 600);
    return () => clearTimeout(t);
  }, [key]);

  const finish = () => {
    if (key) localStorage.setItem(key, "1");
    setOpen(false);
  };

  if (!open) return null;
  const s = STEPS[step];
  const Icon = s.icon;
  const last = step === STEPS.length - 1;

  return (
    <div data-testid="onboarding-tour" className="fixed inset-0 z-[9997] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={finish} />
      <div className="relative w-full max-w-md rounded-2xl border border-border bg-card shadow-2xl rise overflow-hidden">
        <div className="h-1 w-full bg-secondary/60">
          <div className="h-full bg-ai transition-all duration-300" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
        </div>
        <div className="p-7">
          <div className={`inline-flex items-center justify-center w-12 h-12 rounded-xl bg-secondary/60 ${s.accent} mb-5`}>
            <Icon className="w-6 h-6" />
          </div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">
            Step {step + 1} of {STEPS.length}
          </div>
          <h2 data-testid="tour-title" className="font-head font-black text-2xl mb-3">{s.title}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">{s.body}</p>

          <div className="flex items-center gap-2 mt-6">
            {STEPS.map((_, i) => (
              <span key={i} data-testid={`tour-dot-${i}`}
                className={`h-1.5 rounded-full transition-all duration-300 ${i === step ? "w-6 bg-ai" : "w-1.5 bg-secondary"}`} />
            ))}
            <div className="flex-1" />
            <button data-testid="tour-skip" onClick={finish}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2">
              Skip
            </button>
          </div>

          <div className="flex items-center gap-3 mt-5">
            {step > 0 && (
              <button data-testid="tour-back" onClick={() => setStep((v) => v - 1)}
                className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back
              </button>
            )}
            <div className="flex-1" />
            {last ? (
              <button data-testid="tour-finish" onClick={finish}
                className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-5 py-2.5 text-sm font-head font-bold hover:opacity-90 transition-opacity">
                Get started <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button data-testid="tour-next" onClick={() => setStep((v) => v + 1)}
                className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-5 py-2.5 text-sm font-head font-bold hover:opacity-90 transition-opacity">
                Next <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
