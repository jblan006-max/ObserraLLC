import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Loader2, Check, Sparkle, Clock, ExternalLink, Users, ChevronUp, ChevronDown } from "lucide-react";

export default function Billing() {
  const { sub, refreshSub, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [plans, setPlans] = useState(null);
  const [summary, setSummary] = useState(null);
  const [openPack, setOpenPack] = useState(null);
  const [seatQ, setSeatQ] = useState("");
  const [interval, setIntervalSel] = useState("monthly");
  const [busy, setBusy] = useState("");
  const [mods, setMods] = useState([]);
  const [portalBusy, setPortalBusy] = useState(false);

  useEffect(() => { api.get("/billing/plans").then((r) => setPlans(r.data)); api.get("/modules").then((r) => setMods(r.data || [])); refreshSub?.(); }, []);
  useEffect(() => { if (user?.role === "admin") api.get("/billing/access-summary").then((r) => setSummary(r.data)).catch(() => {}); }, [user]);

  const openPortal = async () => {
    setPortalBusy(true);
    try {
      const { data } = await api.post("/billing/portal", { origin_url: window.location.origin });
      window.location.href = data.portal_url;
    } catch (e) { toast.error(e.response?.data?.detail || "Could not open the billing portal"); setPortalBusy(false); }
  };

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
      {isAdmin && summary && (
        <div data-testid="seats-access-summary" className="bg-card fact-border rounded-xl p-6 space-y-3">
          <h2 className="font-head font-bold text-lg flex items-center gap-2"><Users className="w-5 h-5 text-ai" /> Seats &amp; Access</h2>
          <p className="text-sm text-muted-foreground -mt-1">Which teammates can reach each paid pack right now.</p>
          <input data-testid="seat-search" value={seatQ} onChange={(e) => setSeatQ(e.target.value)} placeholder="Find a teammate by name or email…"
            className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
          <div>
            {summary.filter((s) => !seatQ.trim() || (s.owned && s.seats.some((u) => `${u.name || ""} ${u.email}`.toLowerCase().includes(seatQ.trim().toLowerCase())))).map((s) => (
              <div key={s.id} className="border-b border-border/50 last:border-0">
                <button data-testid={`seat-row-${s.id}`} onClick={() => s.owned && setOpenPack(openPack === s.id ? null : s.id)}
                  className={`w-full flex items-center justify-between gap-3 py-2.5 text-left ${s.owned ? "cursor-pointer hover:opacity-80" : "cursor-default"}`}>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${s.owned ? "bg-low" : "bg-muted-foreground/40"}`} />
                    <span className="text-sm font-medium truncate">{s.name}</span>
                    {!s.owned && <span className="text-[10px] font-mono uppercase text-muted-foreground border border-border rounded px-1.5 py-0.5 shrink-0">not owned</span>}
                  </div>
                  <div className="flex items-center gap-2 shrink-0 text-sm text-muted-foreground">
                    {s.owned ? `${s.seat_count} of ${s.total_members} teammates` : "—"}
                    {s.owned && ((seatQ.trim() || openPack === s.id) ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />)}
                  </div>
                </button>
                {(seatQ.trim() || openPack === s.id) && s.owned && (
                  <div data-testid={`seat-detail-${s.id}`} className="pb-3 pl-3.5 flex flex-wrap gap-1.5">
                    {(seatQ.trim() ? s.seats.filter((u) => `${u.name || ""} ${u.email}`.toLowerCase().includes(seatQ.trim().toLowerCase())) : s.seats).length === 0
                      ? <span className="text-xs text-muted-foreground">No teammates have this access yet.</span>
                      : (seatQ.trim() ? s.seats.filter((u) => `${u.name || ""} ${u.email}`.toLowerCase().includes(seatQ.trim().toLowerCase())) : s.seats).map((u) => <span key={u.email} className="text-xs bg-secondary/60 rounded-full px-2.5 py-1">{u.name || u.email}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-muted-foreground">Deployment: SaaS (managed), Private Cloud, or Hybrid. Test card: <span className="font-mono text-foreground">4242 4242 4242 4242</span>, any future expiry, any CVC.</p>
    </div>
  );
}
