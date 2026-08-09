import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ArrowUpCircle, X, Sparkles, DownloadCloud, Loader2 } from "lucide-react";

export const UpdateBanner = () => {
  const { user } = useAuth();
  const [info, setInfo] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [modal, setModal] = useState(false);
  const [upgrading, setUpgrading] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") return;
    api
      .get("/deploy/version")
      .then(({ data }) => {
        if (data?.update_available && !localStorage.getItem(`obserra-update-dismissed-${data.latest}`)) {
          setInfo(data);
        }
      })
      .catch(() => {});
  }, [user]);

  if (user?.role !== "admin" || !info || dismissed) return null;

  const close = () => {
    localStorage.setItem(`obserra-update-dismissed-${info.latest}`, "1");
    setDismissed(true);
    setModal(false);
  };

  const upgrade = async () => {
    setUpgrading(true);
    try {
      const { data } = await api.post("/deploy/upgrade");
      toast.success(`Upgrade started — the app will pull ${info.latest} and restart (${data.compose || "configured stack"}).`);
      setModal(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Automatic upgrade isn't available on this deployment.");
    }
    setUpgrading(false);
  };

  const changelog = Array.isArray(info.changelog) ? info.changelog : [];

  return (
    <>
      <div
        data-testid="update-banner"
        className="fixed top-0 inset-x-0 z-[60] bg-ai text-white px-4 py-2 flex items-center justify-center gap-3 text-sm shadow-lg"
      >
        <ArrowUpCircle className="w-4 h-4 shrink-0" />
        <span data-testid="update-banner-text">
          Obserra SAP UAC <b>v{info.latest}</b> is available — you're on v{info.current}.
        </span>
        <button
          data-testid="update-banner-view"
          onClick={() => setModal(true)}
          className="underline font-semibold whitespace-nowrap hover:opacity-90"
        >
          What's new
        </button>
        <button
          data-testid="update-banner-dismiss"
          onClick={close}
          className="ml-1 opacity-80 hover:opacity-100"
          aria-label="Dismiss update notice"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {modal && (
        <div
          data-testid="update-modal"
          className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4"
          onClick={() => setModal(false)}
        >
          <div
            className="bg-card fact-border rounded-2xl shadow-2xl w-full max-w-lg p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-5 h-5 text-ai" />
              <h3 className="font-head font-bold text-lg">What's new in v{info.latest}</h3>
            </div>
            <p className="text-xs font-mono text-muted-foreground mb-4">You're currently running v{info.current}</p>
            {info.notes && (
              <p data-testid="update-modal-notes" className="text-sm text-foreground mb-3">{info.notes}</p>
            )}
            {changelog.length > 0 && (
              <ul className="text-sm text-muted-foreground space-y-1.5 mb-3 list-disc pl-5">
                {changelog.map((c, i) => (
                  <li key={i}>{typeof c === "string" ? c : `${c.version || ""} ${c.notes || ""}`.trim()}</li>
                ))}
              </ul>
            )}
            <div className="flex items-center justify-end gap-2 pt-2">
              {info.url && (
                <a
                  data-testid="update-modal-link"
                  href={info.url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-2 text-sm font-head font-bold text-ai hover:underline"
                >
                  Release notes
                </a>
              )}
              <button
                data-testid="update-modal-upgrade"
                onClick={upgrade}
                disabled={upgrading}
                className="px-4 py-2 rounded-md bg-ai text-white font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50"
              >
                {upgrading ? <Loader2 className="w-4 h-4 animate-spin" /> : <DownloadCloud className="w-4 h-4" />} Pull latest &amp; restart
              </button>
              <button
                data-testid="update-modal-close"
                onClick={() => setModal(false)}
                className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
              >
                Later
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
