import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Loader2, Check, Lock, Store } from "lucide-react";

export default function Marketplace() {
  const { refreshSub } = useAuth();
  const [modules, setModules] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => { api.get("/modules").then((r) => setModules(r.data)); }, []);

  const buy = async (m) => {
    setBusy(m.id);
    try {
      const { data } = await api.post("/modules/checkout", { lookup_key: m.lookup_key, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch { toast.error("Could not start checkout"); setBusy(""); }
  };

  if (!modules) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-6">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Store className="w-7 h-7 text-primary" /> Dashboard Marketplace</h1>
        <p className="text-sm text-muted-foreground mt-1">Activate additional dashboards on demand. Not all apps are enabled at once — turn on what your programme needs.</p>
      </div>
      <div className="grid md:grid-cols-3 gap-5">
        {modules.map((m) => (
          <div key={m.id} data-testid={`module-${m.id}`} className={`rounded-xl p-6 flex flex-col ${m.owned ? "bg-card fact-border" : "ai-border bg-ai/5"}`}>
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-head font-bold text-lg">{m.name}</h2>
              {m.owned ? <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/15 text-low">ACTIVE</span>
                       : <Lock className="w-4 h-4 text-ai" />}
            </div>
            <p className="text-sm text-muted-foreground flex-1">{m.desc}</p>
            <div className="mt-4">
              {m.included ? (
                <div className="text-xs font-mono text-muted-foreground">Included with subscription</div>
              ) : m.owned ? (
                <div className="flex items-center gap-1.5 text-sm text-low"><Check className="w-4 h-4" /> Activated</div>
              ) : (
                <button data-testid={`buy-${m.id}`} onClick={() => buy(m)} disabled={busy === m.id}
                  className="w-full py-2.5 rounded-md bg-ai text-background font-head font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50">
                  {busy === m.id && <Loader2 className="w-4 h-4 animate-spin" />} Add · ${m.price}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">Test card: <span className="font-mono text-foreground">4242 4242 4242 4242</span>, any future expiry, any CVC. Enterprise plan includes all add-ons.</p>
    </div>
  );
}
