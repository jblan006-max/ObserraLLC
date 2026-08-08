import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Plug, Loader2, Cloud, Bot, Sparkles, MessageSquare, KeyRound, RefreshCw, Search, X } from "lucide-react";

const StatusPill = ({ ok, warn, off, children, testid }) => {
  const cls = off ? "bg-secondary/60 text-muted-foreground" : ok ? "bg-low/15 text-low" : warn ? "bg-med/15 text-med" : "bg-crit/15 text-crit";
  return <span data-testid={testid} className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${cls}`}>{children}</span>;
};

function relTime(iso) {
  if (!iso) return null;
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function SyncMeta({ s, kind, reload }) {
  const [busy, setBusy] = useState(false);
  const synced = s?.synced_at;
  const stale = synced ? (Date.now() - new Date(synced).getTime() > 36 * 3600 * 1000) : true;
  const recheck = async () => {
    setBusy(true);
    try { await api.post(`/enterprise/live/${kind}/recheck`); toast.success("Re-checked connection"); reload(); }
    catch { toast.error("Re-check failed"); }
    setBusy(false);
  };
  return (
    <div className="flex items-center gap-2 pt-1" data-testid={`${kind}-sync-meta`}>
      <span data-testid={`${kind}-last-sync`} className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${synced && !stale ? "bg-low/15 text-low" : "bg-med/15 text-med"}`}>
        {synced ? `Synced ${relTime(synced)}` : "Awaiting first live sync"}
      </span>
      <button data-testid={`${kind}-recheck`} disabled={busy} onClick={recheck} className="text-[10px] text-ai hover:underline disabled:opacity-50">{busy ? "Checking…" : "Re-check"}</button>
    </div>
  );
}

function Field({ label, testid, ...props }) {
  return (<label className="block"><span className="text-xs text-muted-foreground mb-1.5 block">{label}</span>
    <input data-testid={testid} {...props} className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>);
}

function ConnectorShell({ icon: Icon, title, desc, status, children, testid }) {
  return (
    <div data-testid={testid} className="bg-card fact-border rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-head font-bold text-sm flex items-center gap-2"><Icon className="w-4 h-4 text-ai" /> {title}</div>
        {status}
      </div>
      {desc && <p className="text-[11px] text-muted-foreground">{desc}</p>}
      {children}
    </div>
  );
}

function GraphConnector({ kind, icon, title, desc, live, reload, seatsLabel }) {
  const s = live[kind];
  const [f, setF] = useState({ tenant_id: "", client_id: "", client_secret: "" });
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const save = async () => {
    if (!f.tenant_id || !f.client_id || !f.client_secret) { toast.error("All fields required"); return; }
    setBusy(true);
    try {
      await api.put(`/enterprise/live/${kind}`, f);
      setF({ tenant_id: "", client_id: "", client_secret: "" }); setEditing(false);
      toast.success(`${title} connected`);
      reload();
    } catch { toast.error("Save failed"); }
    setBusy(false);
  };
  const clear = async () => { await api.delete(`/enterprise/live/${kind}`); toast.success(`${title} disconnected`); reload(); };
  const configured = s?.configured && !editing;
  return (
    <ConnectorShell icon={icon} title={title} desc={configured ? null : desc} testid={`connector-${kind}`}
      status={<StatusPill testid={`${kind}-status`} off={!s?.configured} ok={s?.live} >{!s?.configured ? "NOT SET" : s.live ? "LIVE" : "NOT LIVE"}</StatusPill>}>
      {configured ? (
        <div className="text-xs space-y-1">
          <div className="font-mono text-muted-foreground">Tenant: {s.tenant_id} · App: {s.client_id_masked}</div>
          <div className="text-muted-foreground">{s.live ? (s[seatsLabel.key] != null ? `${s[seatsLabel.key]} ${seatsLabel.label}` : s.status) : s.status}</div>
          <SyncMeta s={s} kind={kind} reload={reload} />
          <div className="flex gap-2 pt-1">
            <button data-testid={`${kind}-update`} onClick={() => setEditing(true)} className="text-xs px-3 py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai">Update creds</button>
            <button data-testid={`${kind}-disconnect`} onClick={clear} className="text-xs px-3 py-1.5 rounded-md text-muted-foreground hover:text-crit">Disconnect</button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <Field label="Tenant ID" testid={`${kind}-tenant`} value={f.tenant_id} onChange={(e) => setF({ ...f, tenant_id: e.target.value })} />
          <Field label="Client ID" testid={`${kind}-client`} value={f.client_id} onChange={(e) => setF({ ...f, client_id: e.target.value })} />
          <Field label="Client Secret" testid={`${kind}-secret`} value={f.client_secret} onChange={(e) => setF({ ...f, client_secret: e.target.value })} />
          <button data-testid={`${kind}-verify`} disabled={busy} onClick={save} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? "Connecting…" : "Save & connect"}</button>
        </div>
      )}
    </ConnectorShell>
  );
}

function OpenAIConnector({ live, reload }) {
  const s = live.openai;
  const [f, setF] = useState({ api_key: "", org: "" });
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const save = async () => {
    if (!f.api_key) { toast.error("API key required"); return; }
    setBusy(true);
    try {
      const { data } = await api.put("/enterprise/live/openai", f);
      setF({ api_key: "", org: "" }); setEditing(false);
      toast.success(data.model_count != null ? `ChatGPT connected · ${data.model_count} models` : "ChatGPT connected");
      reload();
    } catch { toast.error("Save failed"); }
    setBusy(false);
  };
  const clear = async () => { await api.delete("/enterprise/live/openai"); toast.success("ChatGPT disconnected"); reload(); };
  const configured = s?.configured && !editing;
  return (
    <ConnectorShell icon={Sparkles} title="ChatGPT (OpenAI)" desc={configured ? null : "Connect your OpenAI API key to govern ChatGPT usage. We validate the key against OpenAI and go LIVE."} testid="connector-openai"
      status={<StatusPill testid="openai-status" off={!s?.configured} ok={s?.live}>{!s?.configured ? "NOT SET" : s.live ? "LIVE" : "NOT LIVE"}</StatusPill>}>
      {configured ? (
        <div className="text-xs space-y-1">
          <div className="font-mono text-muted-foreground">Key: {s.api_key_masked}{s.org ? ` · Org: ${s.org}` : ""}</div>
          <div className="text-muted-foreground">{s.live ? `${s.model_count ?? "?"} models available` : s.status}</div>
          <SyncMeta s={s} kind="openai" reload={reload} />
          <div className="flex gap-2 pt-1">
            <button data-testid="openai-update" onClick={() => setEditing(true)} className="text-xs px-3 py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai">Update key</button>
            <button data-testid="openai-disconnect" onClick={clear} className="text-xs px-3 py-1.5 rounded-md text-muted-foreground hover:text-crit">Disconnect</button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <Field label="OpenAI API Key" testid="openai-key" value={f.api_key} onChange={(e) => setF({ ...f, api_key: e.target.value })} placeholder="sk-…" />
          <Field label="OpenAI Org ID (optional)" testid="openai-org" value={f.org} onChange={(e) => setF({ ...f, org: e.target.value })} placeholder="org-…" />
          <button data-testid="openai-verify" disabled={busy} onClick={save} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? "Connecting…" : "Save & connect"}</button>
        </div>
      )}
    </ConnectorShell>
  );
}

function TeamsConnector({ live, reload }) {
  const s = live.teams;
  const [f, setF] = useState({ webhook_url: "", channel_name: "" });
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const save = async () => {
    if (!f.webhook_url) { toast.error("Webhook URL required"); return; }
    setBusy(true);
    try {
      await api.put("/enterprise/live/teams", f);
      setF({ webhook_url: "", channel_name: "" }); setEditing(false);
      toast.success("Teams connected — reports can be shared to the channel");
      reload();
    } catch { toast.error("Save failed"); }
    setBusy(false);
  };
  const clear = async () => { await api.delete("/enterprise/live/teams"); toast.success("Teams disconnected"); reload(); };
  const configured = s?.configured && !editing;
  return (
    <ConnectorShell icon={MessageSquare} title="Microsoft Teams — Report Share" desc={configured ? null : "Paste a Teams Incoming Webhook. Once ready, board & Studio reports can be pushed straight into a Teams channel."} testid="connector-teams"
      status={<StatusPill testid="teams-status" off={!s?.configured} ok={s?.valid} warn={s?.configured && !s?.valid}>{!s?.configured ? "NOT SET" : s.valid ? "READY" : "INVALID"}</StatusPill>}>
      {configured ? (
        <div className="text-xs space-y-1">
          <div className="font-mono text-muted-foreground">Webhook: {s.webhook_masked}{s.channel_name ? ` · #${s.channel_name}` : ""}</div>
          <div className="text-muted-foreground">{s.status}</div>
          <div className="flex gap-2 pt-1">
            <button data-testid="teams-update" onClick={() => setEditing(true)} className="text-xs px-3 py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai">Update webhook</button>
            <button data-testid="teams-disconnect" onClick={clear} className="text-xs px-3 py-1.5 rounded-md text-muted-foreground hover:text-crit">Disconnect</button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <Field label="Teams Incoming Webhook URL" testid="teams-webhook" value={f.webhook_url} onChange={(e) => setF({ ...f, webhook_url: e.target.value })} placeholder="https://…webhook.office.com/…" />
          <Field label="Channel name (optional)" testid="teams-channel" value={f.channel_name} onChange={(e) => setF({ ...f, channel_name: e.target.value })} placeholder="Security Board" />
          <button data-testid="teams-verify" disabled={busy} onClick={save} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? "Connecting…" : "Save & connect"}</button>
        </div>
      )}
    </ConnectorShell>
  );
}

function SSOConnector({ live, reload }) {
  const s = live.sso;
  const [f, setF] = useState({ metadata_url: "", entity_id: "" });
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const save = async () => {
    if (!f.metadata_url) { toast.error("Metadata URL required"); return; }
    setBusy(true);
    try {
      await api.put("/enterprise/live/sso", f);
      setF({ metadata_url: "", entity_id: "" }); setEditing(false);
      toast.success("SSO connected");
      reload();
    } catch { toast.error("Save failed"); }
    setBusy(false);
  };
  const clear = async () => { await api.delete("/enterprise/live/sso"); toast.success("SSO cleared"); reload(); };
  const configured = s?.configured && !editing;
  return (
    <ConnectorShell icon={KeyRound} title="SSO / SAML (IdP metadata)" desc={configured ? null : "Paste your IdP metadata URL. We validate it live and mark SSO ready. App login stays on Google/JWT until full SAML sign-in is enabled."} testid="connector-sso"
      status={<StatusPill testid="sso-live-status" off={!s?.configured} ok={s?.valid} warn={s?.configured && !s?.valid}>{!s?.configured ? "NOT SET" : s.valid ? "READY" : "INVALID"}</StatusPill>}>
      {configured ? (
        <div className="text-xs space-y-1">
          <div className="font-mono text-muted-foreground">Entity: {s.entity_id || "—"}</div>
          <div className="text-muted-foreground">{s.status}</div>
          <SyncMeta s={s} kind="sso" reload={reload} />
          <div className="flex gap-2 pt-1">
            <button data-testid="sso-update" onClick={() => setEditing(true)} className="text-xs px-3 py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai">Update</button>
            <button data-testid="sso-clear" onClick={clear} className="text-xs px-3 py-1.5 rounded-md text-muted-foreground hover:text-crit">Clear</button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <Field label="IdP Metadata URL" testid="sso-metadata" value={f.metadata_url} onChange={(e) => setF({ ...f, metadata_url: e.target.value })} />
          <button data-testid="sso-validate" disabled={busy} onClick={save} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? "Connecting…" : "Save & connect"}</button>
        </div>
      )}
    </ConnectorShell>
  );
}

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
function Catalog() {
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
  if (!cat) return null;
  return (
    <>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <span className="text-[11px] text-muted-foreground" data-testid="catalog-connected-count">{cat.connected}/{cat.total} live · real connectivity probes, no fake connects</span>
        <button data-testid="auto-discover-connect" disabled={!!busy} onClick={discover} className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-bold flex items-center gap-1.5 disabled:opacity-50">
          {busy === "discover" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />} Auto-Discover &amp; Connect
        </button>
      </div>
      <div className="space-y-6">
        {cat.categories.map((group) => (
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
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      {form && <ConnectForm item={form} busy={busy === form.id} onClose={() => setForm(null)} onSubmit={submitConnect} />}
    </>
  );
}

export default function AvailableConnectors() {
  const [live, setLive] = useState(null);
  const reload = () => api.get("/enterprise/live").then((r) => setLive(r.data)).catch(() => setLive({}));
  useEffect(() => { reload(); }, []);
  if (!live) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  return (
    <div className="rise space-y-6" data-testid="available-connectors-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Plug className="w-7 h-7 text-primary" /> Available Connectors</h1>
        <p className="text-sm text-muted-foreground mt-1">Governed live connectors and integrations. <span className="text-med font-mono text-xs">Enter credentials to go LIVE — Auto-Discover probes every catalog provider with a real authenticated call and only marks it connected on a genuine 2xx. No fake connects; a daily health check flags any silent credential expiry.</span></p>
      </div>

      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-3">Live connectors</div>
        <div className="grid md:grid-cols-2 gap-4">
          <GraphConnector kind="m365" icon={Cloud} title="Microsoft 365" desc="Enter your Azure app (client-credentials). When valid, it auto-goes LIVE and pulls a real user count from Microsoft Graph." live={live} reload={reload} seatsLabel={{ key: "user_count", label: "users synced from Microsoft Graph" }} />
          <GraphConnector kind="copilot" icon={Bot} title="Microsoft Copilot" desc="Connect an Azure app to govern Copilot. Validates a Microsoft Graph token and reports licensed Copilot seats." live={live} reload={reload} seatsLabel={{ key: "seats", label: "Copilot seats licensed" }} />
          <OpenAIConnector live={live} reload={reload} />
          <TeamsConnector live={live} reload={reload} />
          <SSOConnector live={live} reload={reload} />
        </div>
      </div>

      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-3">Connector catalog — real probes</div>
        <Catalog />
      </div>
    </div>
  );
}
