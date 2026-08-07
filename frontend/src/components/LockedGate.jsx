import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Lock, Loader2 } from "lucide-react";

export function LockedGate({ ent }) {
  const [pack, setPack] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api.get("/modules").then((r) => setPack((r.data || []).find((p) => p.entitlement === ent) || null)).catch(() => {});
  }, [ent]);

  const buy = async (lookup_key) => {
    setBusy(lookup_key);
    try {
      const { data } = await api.post("/modules/checkout", { lookup_key, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch { toast.error("Could not start checkout"); setBusy(""); }
  };

  return (
    <div className="flex items-center justify-center min-h-[70vh]" data-testid="locked-gate">
      <div className="max-w-lg w-full bg-card ai-border rounded-2xl p-8 rise text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-ai/10 mb-5"><Lock className="w-6 h-6 text-ai" /></div>
        <h1 className="font-head font-black text-2xl" data-testid="locked-gate-title">{pack ? pack.name : "Add-on required"}</h1>
        <p className="text-sm text-muted-foreground mt-2">{pack?.desc || "This dashboard is part of a paid add-on."}</p>
        {pack && (
          <>
            <div className="flex flex-wrap justify-center gap-1.5 mt-4">
              {pack.pages.map((pg) => (
                <span key={pg} className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-sm bg-secondary/60 text-muted-foreground">{pg}</span>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3 mt-6">
              <button data-testid="gate-buy-monthly" disabled={!!busy} onClick={() => buy(pack.monthly.lookup_key)}
                className="py-3 rounded-lg bg-ai text-background font-head font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50">
                {busy === pack.monthly.lookup_key && <Loader2 className="w-4 h-4 animate-spin" />} Enable · ${pack.monthly.price}/mo
              </button>
              <button data-testid="gate-buy-yearly" disabled={!!busy} onClick={() => buy(pack.yearly.lookup_key)}
                className="py-3 rounded-lg bg-primary text-primary-foreground font-head font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50">
                {busy === pack.yearly.lookup_key && <Loader2 className="w-4 h-4 animate-spin" />} Enable · ${pack.yearly.price}/yr
              </button>
            </div>
            <p className="text-[11px] text-muted-foreground mt-3">Unlocks instantly after checkout · license key emailed to admins. Or get everything with <a href="/app/billing" className="text-ai hover:underline">Enterprise All-Access</a>.</p>
          </>
        )}
      </div>
    </div>
  );
}
