import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Loader2, Check, Sparkle, Clock } from "lucide-react";

export default function Billing() {
  const { sub, refreshSub } = useAuth();
  const [plans, setPlans] = useState(null);
  const [interval, setIntervalSel] = useState("monthly");
  const [busy, setBusy] = useState("");

  useEffect(() => { api.get("/billing/plans").then((r) => setPlans(r.data)); refreshSub?.(); }, []);

  const checkout = async (lookup_key) => {
    setBusy(lookup_key);
    try {
      const { data } = await api.post("/billing/checkout", { lookup_key, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch { toast.error("Could not start checkout"); setBusy(""); }
  };

  if (!plans) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6 max-w-4xl">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight">Subscription & Lifecycle</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Plan: <span className="font-mono text-ai uppercase">{sub?.plan}</span> ·
          status: <span className={sub?.active ? "text-low" : "text-crit"}> {sub?.active ? "active" : "inactive"}</span>
          {sub?.plan === "trial" && sub?.trial_end && <span className="inline-flex items-center gap-1 ml-1 text-muted-foreground"><Clock className="w-3 h-3" /> trial ends {new Date(sub.trial_end).toLocaleDateString()}</span>}
          . Access turns off automatically when unpaid.
        </p>
      </div>

      <div className="inline-flex p-1 rounded-full bg-secondary/60 border border-border text-xs font-head font-bold">
        {["monthly", "yearly"].map((iv) => (
          <button key={iv} data-testid={`interval-${iv}`} onClick={() => setIntervalSel(iv)}
            className={`px-4 py-1.5 rounded-full capitalize transition-colors ${interval === iv ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
            {iv}{iv === "yearly" && <span className="ml-1 text-low">save 10%</span>}
          </button>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        {plans.map((p, idx) => {
          const price = interval === "yearly" ? p.yearly : p.monthly;
          return (
            <div key={p.tier} data-testid={`plan-${p.tier}`} className={`rounded-xl p-6 ${idx === 1 ? "ai-border bg-ai/5" : "bg-card fact-border"}`}>
              {idx === 1 && <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-ai mb-2"><Sparkle className="w-3 h-3" /> Recommended</div>}
              <h2 className="font-head font-black text-2xl">{p.name}</h2>
              <div className="mt-2 mb-4">
                <span className="font-head font-black text-4xl">${price.price.toLocaleString()}</span>
                <span className="text-sm text-muted-foreground">/{interval === "yearly" ? "yr" : "mo"}</span>
              </div>
              <ul className="space-y-2 mb-6">
                {p.features.map((f) => <li key={f} className="flex items-center gap-2 text-sm text-muted-foreground"><Check className="w-4 h-4 text-low shrink-0" /> {f}</li>)}
              </ul>
              <button data-testid={`subscribe-${p.tier}`} onClick={() => checkout(price.lookup_key)} disabled={busy === price.lookup_key}
                className={`w-full py-2.5 rounded-md font-head font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50 ${idx === 1 ? "bg-ai text-background" : "bg-primary text-primary-foreground"}`}>
                {busy === price.lookup_key && <Loader2 className="w-4 h-4 animate-spin" />} Subscribe
              </button>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">Deployment: SaaS (managed), Private Cloud, or Hybrid. Test card: <span className="font-mono text-foreground">4242 4242 4242 4242</span>, any future expiry, any CVC.</p>
    </div>
  );
}
