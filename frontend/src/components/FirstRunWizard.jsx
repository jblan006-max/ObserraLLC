import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Check, X, Sparkles } from "lucide-react";

const SEEN = "obserra_packs_wizard_seen";

export function FirstRunWizard() {
  const { sub, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [packs, setPacks] = useState([]);
  const [sel, setSel] = useState([]);
  const [interval, setInterval] = useState("monthly");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const check = () => {
      if (!sub || sub.plan === "enterprise" || localStorage.getItem(SEEN)) return;
      const tourKey = user ? `obserra-tour-done-${user.id || user.email}` : null;
      if (tourKey && !localStorage.getItem(tourKey)) return;
      api.get("/modules").then((r) => {
        const data = r.data || [];
        if (data.some((p) => !p.owned)) { setPacks(data); setOpen(true); }
      }).catch(() => {});
    };
    check();
    window.addEventListener("obserra-tour-finished", check);
    return () => window.removeEventListener("obserra-tour-finished", check);
  }, [sub, user]);

  if (!open) return null;

  const dismiss = () => { localStorage.setItem(SEEN, "1"); setOpen(false); };
  const toggle = (p) => { if (p.owned) return; setSel((s) => s.includes(p.entitlement) ? s.filter((x) => x !== p.entitlement) : [...s, p.entitlement]); };
  const enable = async () => {
    const keys = packs.filter((p) => sel.includes(p.entitlement) && !p.owned).map((p) => p[interval].lookup_key);
    if (!keys.length) { toast.error("Pick at least one add-on, or skip for now"); return; }
    setBusy(true);
    try {
      localStorage.setItem(SEEN, "1");
      const { data } = await api.post("/modules/checkout", { lookup_keys: keys, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch { toast.error("Could not start checkout"); setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-background/80 backdrop-blur-sm p-4" data-testid="first-run-wizard">
      <div className="w-full max-w-2xl bg-card ai-border rounded-2xl p-6 md:p-8 rise max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-ai flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5" /> Set up your workspace</div>
            <h1 className="font-head font-black text-2xl mt-1">Choose your dashboards</h1>
            <p className="text-sm text-muted-foreground mt-1">Turn on the modules your programme needs. You can add more anytime from the Marketplace.</p>
          </div>
          <button data-testid="wizard-close" onClick={dismiss} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground"><X className="w-4 h-4" /></button>
        </div>

        <div className="flex items-center rounded-md bg-secondary/60 p-0.5 text-sm w-fit mt-4">
          {["monthly", "yearly"].map((iv) => (
            <button key={iv} data-testid={`wizard-interval-${iv}`} onClick={() => setInterval(iv)}
              className={`px-3 py-1.5 rounded capitalize transition-colors ${interval === iv ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
              {iv}{iv === "yearly" && <span className="ml-1 text-[10px] text-low">save ~17%</span>}
            </button>
          ))}
        </div>

        <div className="grid sm:grid-cols-2 gap-3 mt-4">
          {packs.map((p) => {
            const s = sel.includes(p.entitlement);
            return (
              <button key={p.id} data-testid={`wizard-pack-${p.id}`} disabled={p.owned} onClick={() => toggle(p)}
                className={`text-left rounded-xl p-4 transition-colors ${p.owned ? "bg-card fact-border opacity-70" : s ? "border-2 border-ai bg-ai/10" : "ai-border bg-ai/5 hover:bg-ai/10"}`}>
                <div className="flex items-center justify-between">
                  <span className="font-head font-bold text-sm">{p.name}</span>
                  {p.owned ? <span className="text-[9px] font-mono text-low">ACTIVE</span>
                    : s ? <span className="w-4 h-4 rounded-full bg-ai text-background flex items-center justify-center"><Check className="w-3 h-3" /></span> : null}
                </div>
                <p className="text-xs text-muted-foreground mt-1">{p.desc}</p>
                {!p.owned && <div className="text-xs font-head font-bold text-ai mt-2">${p[interval].price}<span className="text-muted-foreground font-normal">/{interval === "yearly" ? "yr" : "mo"}</span></div>}
              </button>
            );
          })}
        </div>

        <div className="flex items-center justify-end gap-3 mt-6">
          <button data-testid="wizard-skip" onClick={dismiss} className="text-sm text-muted-foreground hover:text-foreground">Skip for now</button>
          <button data-testid="wizard-enable" onClick={enable} disabled={busy}
            className="px-5 py-2.5 rounded-md bg-ai text-background font-head font-bold text-sm flex items-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} Enable selected
          </button>
        </div>
      </div>
    </div>
  );
}
