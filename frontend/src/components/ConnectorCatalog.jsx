import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { Loader2, RefreshCw, Search, X } from "lucide-react";

const STATE_META = {
  connected: { label: "LIVE", cls: "bg-low/15 text-low" },
  credentials_required: { label: "CREDENTIALS", cls: "bg-med/15 text-med" },
  auth_failed: { label: "AUTH FAILED", cls: "bg-crit/15 text-crit" },
  unreachable: { label: "UNREACHABLE", cls: "bg-crit/15 text-crit" },
  error: { label: "ERROR", cls: "bg-med/15 text-med" },
  available: { label: "AVAILABLE", cls: "bg-secondary/60 text-muted-foreground" },
};

function ConnectForm({ item, onClose, onSubmit, busy }) {
  const [values, setValues] = useState({});
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/65 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="bg-card border border-border rounded-2xl w-full max-w-md p-6 space-y-4" data-testid={`connect-form-${item.id}`}>
        <div className="flex items-center justify-between">
          <h3 className="font-head font-bold text-lg">Connect {item.name}</h3>
          <button data-testid="connect-form-close" onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
        </div>
        <p className="text-xs text-muted-foreground">Credentials run a REAL live probe against {item.name}. It is only marked live on a genuine 2xx — otherwise you get the honest failure. Every attempt is written to the Defensibility Ledger.</p>
        {(item.fields || []).map((f) => (
          <label key={f.key} className="block">
            <span className="text-xs text-muted-foreground mb-1.5 block">{f.label}</span>
            <input data-testid={`connect-field-${item.id}-${f.key}`} type={f.secret ? "password" : "text"} placeholder={f.placeholder || ""}
              value={values[f.key] || ""} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
              className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
          </label>
        ))}
        <button data-testid={`connect-submit-${item.id}`} disabled={busy} onClick={() => onSubmit(values)}
          className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">
          {busy ? "Probing live…" : "Save & connect (live probe)"}
        </button>
      </div>
    </div>
  );
}

// Real enterprise connector catalog — every card is driven by /api/connectors. Auto-Discover runs
// LIVE authenticated probes; a connector only reads "LIVE" on a genuine HTTP 2xx, otherwise it
// truthfully reports "CREDENTIALS / AUTH FAILED / UNREACHABLE". Zero fake connects (No-Mock).
export function ConnectorCatalog({ onlyCategories }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [cat, setCat] = useState(null);
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState(null);
  const load = () => api.get("/connectors/catalog").then((r) => setCat(r.data)).catch(() => setCat(null));
  useEffect(() => { load(); }, []);
  const discover = async () => {
    setBusy("discover");
    try {
      const { data } = await api.post("/connectors/discover");
      const s = data.summary;
      toast.success(`Auto-discover: ${s.connected} connected · ${s.credentials_required} need credentials · ${(s.auth_failed || 0) + (s.unreachable || 0) + (s.error || 0)} unavailable`);
      load();
    } catch { toast.error("Auto-discovery failed"); }
    setBusy("");
  };
  const test = async (id) => {
    setBusy(id);
    try { const { data } = await api.post(`/connectors/${id}/test`); toast[data.state === "connected" ? "success" : "error"](`${id}: ${data.detail}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Test failed"); }
    setBusy("");
  };
  const disconnect = async (id) => { setBusy(id); try { await api.post(`/connectors/${id}/disconnect`); toast.success(`${id} disconnected`); load(); } catch { toast.error("Failed"); } setBusy(""); };
  const submitConnect = async (values) => {
    const id = form.id; setBusy(id);
    try {
      const { data } = await api.post(`/connectors/${id}/connect`, { creds: values });
      if (data.state === "connected") toast.success(`${id} connected live (HTTP ${data.http_status})`);
      else toast.error(`${id}: ${data.detail}`);
      setForm(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Connect failed"); }
    setBusy("");
  };
  if (!cat) return <div className="flex items-center justify-center h-32"><Loader2 className="w-5 h-5 animate-spin text-primary" /></div>;
  let groups = cat.categories || [];
  if (onlyCategories?.length) groups = groups.filter((g) => onlyCategories.includes(g.name));
  return (
    <div data-testid="connector-catalog">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <span className="text-[11px] text-muted-foreground" data-testid="catalog-connected-count">{cat.connected}/{cat.total} live · real connectivity probes, no fake connects</span>
        {isAdmin && (
          <button data-testid="auto-discover-connect" disabled={!!busy} onClick={discover} className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-bold flex items-center gap-1.5 disabled:opacity-50">
            {busy === "discover" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />} Auto-Discover &amp; Connect all
          </button>
        )}
      </div>
      <div className="space-y-6">
        {groups.map((group) => (
          <div key={group.name} data-testid={`catalog-group-${group.name.replace(/[^a-zA-Z0-9]/g, "-")}`}>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-2">{group.name}</div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {group.items.map((c) => {
                const m = STATE_META[c.state] || STATE_META.available;
                return (
                  <div key={c.id} data-testid={`catalog-connector-${c.id}`} className="bg-card fact-border rounded-xl p-4 flex flex-col">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="font-head font-bold text-sm truncate">{c.name}</div>
                      <span data-testid={`catalog-${c.id}-status`} className={`shrink-0 text-[9px] font-mono px-2 py-0.5 rounded-full ${m.cls}`}>{m.label}</span>
                    </div>
                    <div className="text-[9px] font-mono uppercase text-muted-foreground/70">{c.auth} · {c.connection_state}</div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {(c.capabilities || []).slice(0, 4).map((cap) => <span key={cap} className="text-[9px] px-1.5 py-0.5 rounded-sm bg-secondary/60 text-muted-foreground">{cap}</span>)}
                    </div>
                    {c.detail && <p className="text-[10px] text-muted-foreground mt-2 line-clamp-2">{c.detail}</p>}
                    {c.creds_masked && <div className="text-[9px] font-mono text-muted-foreground mt-1">key {c.creds_masked}{c.source ? ` · ${c.source}` : ""}</div>}
                    {isAdmin ? (
                      <div className="flex gap-2 mt-3 pt-2 mt-auto">
                        {c.state === "connected" ? (
                          <>
                            <button data-testid={`test-${c.id}`} disabled={!!busy} onClick={() => test(c.id)} className="flex-1 flex items-center justify-center gap-1 text-xs py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai disabled:opacity-50">{busy === c.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Test</button>
                            <button data-testid={`disconnect-${c.id}`} disabled={!!busy} onClick={() => disconnect(c.id)} className="text-xs py-1.5 px-2 rounded-md text-muted-foreground hover:text-crit disabled:opacity-50">Disconnect</button>
                          </>
                        ) : c.connectable ? (
                          <>
                            <button data-testid={`connect-${c.id}`} disabled={!!busy} onClick={() => setForm(c)} className="flex-1 text-xs py-1.5 rounded-md bg-primary text-primary-foreground font-bold disabled:opacity-50">Connect</button>
                            <button data-testid={`test-${c.id}`} disabled={!!busy} onClick={() => test(c.id)} className="text-xs py-1.5 px-2 rounded-md bg-ai/10 border border-ai/30 text-ai disabled:opacity-50">Test</button>
                          </>
                        ) : (
                          <span className="text-[10px] text-muted-foreground italic py-1.5">Customer OAuth / tenant setup required</span>
                        )}
                      </div>
                    ) : (
                      <div className="mt-3 pt-2 mt-auto text-[10px] text-muted-foreground italic">Admin access required to connect</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      {form && <ConnectForm item={form} busy={busy === form.id} onClose={() => setForm(null)} onSubmit={submitConnect} />}
    </div>
  );
}
