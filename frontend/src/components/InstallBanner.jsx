import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";

export const InstallBanner = () => {
  const [promptEvent, setPromptEvent] = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const isStandalone =
      window.matchMedia?.("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;
    if (isStandalone || localStorage.getItem("obserra-install-dismissed")) return;

    const handler = (e) => {
      e.preventDefault();
      setPromptEvent(e);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const install = async () => {
    if (!promptEvent) return;
    promptEvent.prompt();
    await promptEvent.userChoice;
    setPromptEvent(null);
    setVisible(false);
  };

  const dismiss = () => {
    localStorage.setItem("obserra-install-dismissed", "1");
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      data-testid="install-banner"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[9998] w-[calc(100%-2rem)] max-w-md rise"
    >
      <div className="flex items-center gap-3 rounded-xl border border-border bg-secondary/95 backdrop-blur-md px-4 py-3 shadow-2xl">
        <img src="/obserra-mark-flat.svg" alt="" className="h-9 w-9 rounded-md flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-foreground">Install Obserra</div>
          <div className="text-xs text-muted-foreground truncate">Add to your home screen for one-tap access.</div>
        </div>
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
