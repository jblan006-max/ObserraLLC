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
        src="/obserra-mark-flat.svg"
        alt="Obserra"
        className="h-28 w-auto object-contain logo-pulse drop-shadow-[0_8px_30px_rgba(86,184,233,0.3)]"
      />
      <div className="mt-6 font-head font-black text-2xl tracking-[0.35em] pl-[0.35em] text-white">OBSERRA</div>
      <div className="mt-1 text-[9px] font-mono uppercase tracking-[0.22em] text-white/50">
        Executive Protection &amp; Intelligence LLC
      </div>
    </div>
  );
};
