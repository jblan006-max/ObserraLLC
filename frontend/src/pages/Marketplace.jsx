import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Check, Lock, Store } from "lucide-react";

export default function Marketplace() {
  const [packs, setPacks] = useState(null);
  const [interval, setInterval] = useState("monthly");
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/modules").then((r) => setPacks(r.data)); }, []);

  const toggle = (p) => {
    if (p.owned) return;
    setSelected((s) => s.includes(p.entitlement) ? s.filter((x) => x !== p.entitlement) : [...s, p.entitlement]);
  };

  const enable = async () => {
    const keys = packs.filter((p) => selected.includes(p.entitlement) && !p.owned).map((p) => p[interval].lookup_key);
    if (!keys.length) { toast.error("Select at least one add-on to enable"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/modules/checkout", { lookup_keys: keys, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch { toast.error("Could not start checkout"); setBusy(false); }
  };

  if (!packs) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const selCount = packs.filter((p) => selected.includes(p.entitlement) && !p.owned).length;

  return (
    <div className="rise space-y-6 pb-24">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Store className="w-7 h-7 text-primary" /> Dashboard Marketplace</h1>
          <p className="text-sm text-muted-foreground mt-1">Turn on the dashboards your programme needs. Select any packs, pick a billing cadence, and enable them together.</p>
        </div>
        <div className="flex items-center rounded-md bg-secondary/60 p-0.5 text-sm" data-testid="interval-toggle">
          {["monthly", "yearly"].map((iv) => (
            <button key={iv} data-testid={`interval-${iv}`} onClick={() => setInterval(iv)}
              className={`px-3 py-1.5 rounded capitalize transition-colors ${interval === iv ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
              {iv}{iv === "yearly" && <span className="ml-1 text-[10px] text-low">save ~17%</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
        {packs.map((p) => {
          const sel = selected.includes(p.entitlement);
          return (
            <div key={p.id} data-testid={`module-${p.id}`}
              onClick={() => toggle(p)}
              className={`rounded-xl p-6 flex flex-col cursor-pointer transition-colors ${p.owned ? "bg-card fact-border cursor-default" : sel ? "border-2 border-ai bg-ai/10" : "ai-border bg-ai/5 hover:bg-ai/10"}`}>
              <div className="flex items-center justify-between mb-2">
                <h2 className="font-head font-bold text-lg">{p.name}</h2>
                {p.owned ? <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-low/15 text-low">ACTIVE</span>
                  : sel ? <span className="w-5 h-5 rounded-full bg-ai text-background flex items-center justify-center"><Check className="w-3.5 h-3.5" /></span>
                    : <Lock className="w-4 h-4 text-ai" />}
              </div>
              <p className="text-sm text-muted-foreground flex-1">{p.desc}</p>
              <div className="flex flex-wrap gap-1.5 mt-3">
                {p.pages.map((pg) => <span key={pg} className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-secondary/60 text-muted-foreground">{pg}</span>)}
              </div>
              <div className="mt-4 text-sm font-head font-bold">
                {p.owned ? <span className="text-low flex items-center gap-1.5"><Check className="w-4 h-4" /> Activated</span>
                  : <span className="text-ai">${p[interval].price}<span className="text-muted-foreground font-normal">/{interval === "yearly" ? "yr" : "mo"}</span></span>}
              </div>
            </div>
          );
        })}
      </div>

      {selCount > 0 && (
        <div className="fixed bottom-0 left-0 right-0 md:left-60 z-40 border-t border-border bg-background/95 backdrop-blur-xl px-6 py-3 flex items-center justify-between gap-4" data-testid="enable-bar">
          <span className="text-sm text-muted-foreground">{selCount} add-on{selCount > 1 ? "s" : ""} selected · billed {interval}</span>
          <button data-testid="enable-selected" onClick={enable} disabled={busy}
            className="px-6 py-2.5 rounded-md bg-ai text-background font-head font-bold text-sm flex items-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} Enable access
          </button>
        </div>
      )}

      <p className="text-xs text-muted-foreground">Test card: <span className="font-mono text-foreground">4242 4242 4242 4242</span>, any future expiry, any CVC. Each add-on unlocks instantly and emails admins a license key. <a href="/app/billing" className="text-ai hover:underline">Enterprise All-Access</a> includes every pack.</p>
    </div>
  );
}
