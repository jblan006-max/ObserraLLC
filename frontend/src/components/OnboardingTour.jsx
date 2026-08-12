import { useEffect, useLayoutEffect, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { ArrowRight, ArrowLeft } from "lucide-react";

const EXEC_STEPS = [
  { title: "Welcome to Obserra EU CRA Governance",
    body: "Your command center for EU Cyber Resilience Act (Regulation (EU) 2024/2847) product compliance. Classification, conformity readiness, SBOMs, Article 14 reporting clocks and CE declarations recompute live from your product records — every fact traceable to a tamper-evident regulatory ledger. Switch altitude anytime from the toggle in the top bar." },
  { title: "Executive Mode", spotlight: true,
    body: "The boardroom view — highlighted above. CRA posture framed for leadership: how many products are classified and market-ready, which Article 14 clocks are running, and where CE declarations are blocked — without the noise." },
  { title: "Operational Mode", spotlight: true,
    body: "Flip the same toggle to Operational for the working view — register and classify products, run regulation-mapped assessments, generate SBOMs and drive the certification and reporting workflows your team owns day to day." },
  { title: "Start at EU CRA Governance", spotlight: true, target: "nav-eu-cra-governance",
    body: "Highlighted in the sidebar — EU CRA Governance is your product-compliance home: classification, certification portal, SBOM, Article 14 reporting, notified-body sign-off, CE declaration and the regulatory ledger. Come back here anytime." },
];

const OPS_STEPS = [
  { title: "Welcome to Obserra EU CRA Governance",
    body: "This is your operational cockpit for EU Cyber Resilience Act compliance. Every step — classification, assessment, SBOM, vulnerability reporting and CE declaration — is grounded in your live product records and written to a tamper-evident ledger, so you always know exactly what's real." },
  { title: "Operational Mode", spotlight: true,
    body: "The toggle above keeps you in Operational view — register products, run regulation-mapped readiness assessments, generate SBOMs, start Article 14 reporting clocks and manage notified-body sign-off. This is your working surface." },
  { title: "Where you'll work",
    body: "Jump into EU CRA Governance from the sidebar to classify products, issue secure certification-portal links and drive the CE declaration. The Obserrian Advisor can help you interpret the regulation too." },
  { title: "Start at EU CRA Governance", spotlight: true, target: "nav-eu-cra-governance",
    body: "Highlighted in the sidebar — EU CRA Governance is your compliance home base: classification, certification portal, SBOM, reporting clocks and CE declaration, with the Obserrian Advisor one click away." },
];

export const OnboardingTour = () => {
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState(null);

  const isOps = user?.role === "operational";
  const steps = isOps ? OPS_STEPS : EXEC_STEPS;
  const key = user ? `obserra-tour-done-${user.id || user.email}` : null;

  useEffect(() => {
    if (!key || localStorage.getItem(key)) return;
    // Don't auto-launch onboarding over the admin-only System Health console.
    if (typeof window !== "undefined" && window.location.pathname.startsWith("/app/system-health")) return;
    const t = setTimeout(() => { setStep(0); setOpen(true); }, 600);
    return () => clearTimeout(t);
  }, [key]);

  useEffect(() => {
    const replay = () => { setStep(0); setOpen(true); };
    window.addEventListener("obserra-replay-tour", replay);
    return () => window.removeEventListener("obserra-replay-tour", replay);
  }, []);

  const spotlight = open && steps[step]?.spotlight;
  const measure = useCallback(() => {
    const target = steps[step]?.target || "mode-toggle";
    const el = document.querySelector(`[data-testid="${target}"]`);
    if (el) {
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    } else setRect(null);
  }, [steps, step]);

  useLayoutEffect(() => {
    if (!spotlight) return;
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [spotlight, step, measure]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const finish = () => {
    if (key) localStorage.setItem(key, "1");
    try { window.dispatchEvent(new Event("obserra-tour-finished")); } catch (e) {}
    setOpen(false);
  };
  const dismissTemporary = () => setOpen(false);

  if (!open) return null;
  const s = steps[step];
  const last = step === steps.length - 1;
  const hole = spotlight && rect
    ? { top: rect.top - 8, left: rect.left - 8, width: rect.width + 16, height: rect.height + 16 }
    : null;

  return (
    <div data-testid="onboarding-tour" className="fixed inset-0 z-[9997] pointer-events-none">
      {hole ? (
        <>
          <div className="fixed" style={{ ...hole, borderRadius: 9999, boxShadow: "0 0 0 9999px rgba(2,6,15,0.84)", pointerEvents: "none" }} />
          <div className="fixed tour-pulse-ring" style={{ ...hole, pointerEvents: "none" }} />
        </>
      ) : (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={dismissTemporary} />
      )}

      <div className="absolute inset-0 flex items-center justify-center p-4 pointer-events-none">
        <div role="dialog" aria-modal="true" aria-labelledby="obserra-tour-title" className="pointer-events-auto w-full max-w-md rounded-2xl border border-border bg-card shadow-2xl rise overflow-hidden">
          <div className="h-1 w-full bg-secondary/60">
            <div className="h-full bg-ai transition-all duration-300" style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
          </div>
          {s.img && <img src={s.img} alt="" data-testid="tour-preview" className="w-full h-40 object-cover object-top border-b border-border" />}
          <div className="p-7">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-secondary/60 mb-5 p-2">
              <img src="/brand-mark.png" alt="Obserra" className="w-full h-full object-contain" />
            </div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">
              Step {step + 1} of {steps.length} · {isOps ? "Operational" : "Executive"} tour
            </div>
            <h2 id="obserra-tour-title" data-testid="tour-title" className="font-head font-black text-2xl mb-3">{s.title}</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">{s.body}</p>

            <div className="flex items-center gap-2 mt-6">
              {steps.map((_, i) => (
                <span key={i} data-testid={`tour-dot-${i}`}
                  className={`h-1.5 rounded-full transition-all duration-300 ${i === step ? "w-6 bg-ai" : "w-1.5 bg-secondary"}`} />
              ))}
              <div className="flex-1" />
              <button data-testid="tour-skip" onClick={finish}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2">Skip</button>
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
    </div>
  );
};
