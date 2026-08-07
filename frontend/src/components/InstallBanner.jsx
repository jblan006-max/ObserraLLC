import { useEffect, useRef, useState } from "react";
import { Download, X } from "lucide-react";

const SNOOZE_MS = 7 * 24 * 60 * 60 * 1000;

export const InstallBanner = () => {
  const promptRef = useRef(null);
  const [visible, setVisible] = useState(false);
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    const isStandalone =
      window.matchMedia?.("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;
    if (isStandalone || localStorage.getItem("obserra-install-dismissed")) return;

    const laterAt = Number(localStorage.getItem("obserra-install-later") || 0);
    if (laterAt && Date.now() - laterAt < SNOOZE_MS) return;

    const handler = (e) => {
      e.preventDefault();
      promptRef.current = e;
      setVisible(true);
      requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const close = (cb) => {
    setEntered(false);
    setTimeout(() => {
      setVisible(false);
      cb?.();
    }, 300);
  };

  const install = async () => {
    if (!promptRef.current) return;
    promptRef.current.prompt();
    await promptRef.current.userChoice;
    promptRef.current = null;
    close();
  };

  const later = () => close(() => localStorage.setItem("obserra-install-later", String(Date.now())));
  const dismiss = () => close(() => localStorage.setItem("obserra-install-dismissed", "1"));

  if (!visible) return null;

  return (
    <div
      data-testid="install-banner"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[9998] w-[calc(100%-2rem)] max-w-md"
      style={{
        transition: "opacity 300ms ease-out, transform 300ms cubic-bezier(0.16,1,0.3,1)",
        opacity: entered ? 1 : 0,
        transform: `translateX(-50%) translateY(${entered ? "0" : "16px"})`,
      }}
    >
      <div className="flex items-center gap-3 rounded-xl border border-border bg-secondary/95 backdrop-blur-md px-4 py-3 shadow-2xl">
        <img src="/brand-mark.png" alt="" className="h-9 w-9 object-contain flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-foreground">Install Obserra</div>
          <div className="text-xs text-muted-foreground truncate">Add to your home screen for one-tap access.</div>
        </div>
        <button
          data-testid="install-banner-later"
          onClick={later}
          className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors px-1"
        >
          Later
        </button>
        <button
          data-testid="install-banner-install"
          onClick={install}
          className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium px-3 py-2 hover:opacity-90 transition-opacity"
        >
          <Download className="w-3.5 h-3.5" /> Install
        </button>
        <button
          data-testid="install-banner-dismiss"
          onClick={dismiss}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
