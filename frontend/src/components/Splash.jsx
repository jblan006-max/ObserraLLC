import { useEffect, useState } from "react";

export const Splash = () => {
  const [phase, setPhase] = useState("show");

  useEffect(() => {
    if (sessionStorage.getItem("obserra-splash-seen")) {
      setPhase("gone");
      return;
    }
    const t1 = setTimeout(() => setPhase("fade"), 1200);
    const t2 = setTimeout(() => {
      setPhase("gone");
      sessionStorage.setItem("obserra-splash-seen", "1");
    }, 1800);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);

  if (phase === "gone") return null;

  return (
    <div
      data-testid="app-splash"
      className={`fixed inset-0 z-[9999] flex flex-col items-center justify-center transition-opacity duration-500 ${
        phase === "fade" ? "opacity-0" : "opacity-100"
      }`}
      style={{ backgroundColor: "#061F3B" }}
    >
      <img
        src="/brand-mark.png"
        alt="Obserra"
        className="h-24 w-auto object-contain logo-pulse drop-shadow-[0_8px_30px_rgba(86,184,233,0.3)]"
      />
      <img src="/brand-wordmark.png" alt="OBSERRA — Executive Protection & Intelligence LLC" className="mt-6 h-12 w-auto object-contain" />
    </div>
  );
};
