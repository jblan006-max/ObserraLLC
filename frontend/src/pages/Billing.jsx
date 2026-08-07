import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Loader2, Check, Sparkle } from "lucide-react";

export default function Billing() {
  const { user } = useAuth();
  const [plans, setPlans] = useState(null);
  const [org, setOrg] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api.get("/billing/plans").then((r) => setPlans(r.data));
    api.get("/overview").then((r) => setOrg(r.data.org));
  }, []);

  const checkout = async (lookup_key) => {
    setBusy(lookup_key);
    try {
      const { data } = await api.post("/billing/checkout", { lookup_key, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch {
      toast.error("Could not start checkout");
      setBusy("");
    }
  };

  if (!plans) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6 max-w-4xl">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight">Billing & Editions</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Current plan: <span className="font-mono text-ai uppercase">{org?.plan}</span> · webhook-gated entitlements.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        {plans.map((p, idx) => (
          <div key={p.lookup_key} data-testid={`plan-${p.lookup_key}`}
            className={`rounded-lg p-6 ${idx === 1 ? "ai-border bg-ai/5" : "bg-card fact-border"}`}>
            {idx === 1 && <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-ai mb-2"><Sparkle className="w-3 h-3" /> Recommended</div>}
            <h2 className="font-head font-black text-2xl">{p.name}</h2>
            <div className="mt-2 mb-4">
              <span className="font-head font-black text-4xl">${p.price.toLocaleString()}</span>
              <span className="text-sm text-muted-foreground">/{p.interval}</span>
            </div>
            <ul className="space-y-2 mb-6">
              {p.features.map((f) => (
                <li key={f} className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Check className="w-4 h-4 text-low shrink-0" /> {f}
                </li>
              ))}
            </ul>
            <button data-testid={`subscribe-${p.lookup_key}`} onClick={() => checkout(p.lookup_key)} disabled={busy === p.lookup_key}
              className={`w-full py-2.5 rounded-md font-head font-bold text-sm flex items-center justify-center gap-2 transition-opacity hover:opacity-90 disabled:opacity-50 ${idx === 1 ? "bg-ai text-background" : "bg-primary text-primary-foreground"}`}>
              {busy === p.lookup_key && <Loader2 className="w-4 h-4 animate-spin" />} Subscribe
            </button>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">Test card: <span className="font-mono text-foreground">4242 4242 4242 4242</span>, any future expiry, any CVC.</p>
    </div>
  );
}
