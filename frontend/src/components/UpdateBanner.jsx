import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ArrowUpCircle, X } from "lucide-react";

export const UpdateBanner = () => {
  const { user } = useAuth();
  const [info, setInfo] = useState(null);
  const [dismissed, setDismissed] = useState(false);

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
  };

  return (
    <div
      data-testid="update-banner"
      className="fixed top-0 inset-x-0 z-[60] bg-ai text-white px-4 py-2 flex items-center justify-center gap-3 text-sm shadow-lg"
    >
      <ArrowUpCircle className="w-4 h-4 shrink-0" />
      <span data-testid="update-banner-text">
        Obserra SAP UAC <b>v{info.latest}</b> is available — you're on v{info.current}.
        {info.notes ? ` ${info.notes}` : ""}
      </span>
      {info.url && (
        <a
          data-testid="update-banner-link"
          href={info.url}
          target="_blank"
          rel="noreferrer"
          className="underline font-semibold whitespace-nowrap"
        >
          Release notes
        </a>
      )}
      <button
        data-testid="update-banner-dismiss"
        onClick={close}
        className="ml-2 opacity-80 hover:opacity-100"
        aria-label="Dismiss update notice"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
