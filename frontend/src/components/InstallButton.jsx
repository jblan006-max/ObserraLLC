import { useEffect, useState } from "react";
import { Download, Share, X } from "lucide-react";

function isStandalone() {
  try {
    return window.matchMedia?.("(display-mode: standalone)")?.matches || window.navigator.standalone === true;
  } catch { return false; }
}
function isIOS() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent || "") && !window.MSStream;
}

// In-app "Install Obserra" button. Uses the browser's native PWA install prompt
// (beforeinstallprompt) on Chrome/Edge/Android; on iOS Safari (no such event) it shows a
// short Add-to-Home-Screen hint. Renders nothing once installed / running standalone.
export function InstallButton({ className = "" }) {
  const [deferred, setDeferred] = useState(null);
  const [installed, setInstalled] = useState(isStandalone());
  const [showIosHint, setShowIosHint] = useState(false);
  const ios = isIOS();

  useEffect(() => {
    if (installed) return undefined;
    const onPrompt = (e) => { e.preventDefault(); setDeferred(e); };
    const onInstalled = () => { setInstalled(true); setDeferred(null); };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, [installed]);

  if (installed) return null;
  // Non-iOS: only show once the browser says the app is installable.
  if (!ios && !deferred) return null;

  const click = async () => {
    if (ios) { setShowIosHint(true); return; }
    if (!deferred) return;
    deferred.prompt();
    try {
      const { outcome } = await deferred.userChoice;
      if (outcome === "accepted") setInstalled(true);
    } catch { /* dismissed */ }
    setDeferred(null);
  };

  return (
    <>
      <button data-testid="install-app-button" onClick={click} title="Install Obserra as an app"
        className={`inline-flex items-center gap-1.5 text-xs font-head font-bold px-3 py-1.5 rounded-full border border-primary/40 text-primary hover:bg-primary/10 transition-colors ${className}`}>
        <Download className="w-3.5 h-3.5" strokeWidth={2} /> Install app
      </button>
      {showIosHint && (
        <div data-testid="install-ios-hint" className="fixed inset-0 z-[9998] flex items-end sm:items-center justify-center bg-black/50 p-4" onClick={() => setShowIosHint(false)}>
          <div className="bg-card border border-border rounded-2xl p-5 max-w-sm w-full" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-head font-bold text-base">Install Obserra</h3>
              <button data-testid="install-ios-close" onClick={() => setShowIosHint(false)} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              On iPhone/iPad: tap the <Share className="inline w-4 h-4 mx-0.5 -mt-0.5" /> <b className="text-foreground">Share</b> button in Safari,
              then choose <b className="text-foreground">Add to Home Screen</b>. Obserra will launch full-screen like a native app.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
