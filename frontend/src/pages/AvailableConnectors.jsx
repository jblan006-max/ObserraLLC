import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Plug, Loader2, Cloud, Bot, Sparkles, MessageSquare, KeyRound, RefreshCw } from "lucide-react";

const StatusPill = ({ ok, warn, off, children, testid }) => {
  const cls = off ? "bg-secondary/60 text-muted-foreground" : ok ? "bg-low/15 text-low" : warn ? "bg-med/15 text-med" : "bg-crit/15 text-crit";
  return <span data-testid={testid} className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${cls}`}>{children}</span>;
};

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

function Catalog() {
  const [list, setList] = useState(null);
  const [busy, setBusy] = useState("");
  const load = () => api.get("/enterprise/connectors").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);
  const act = async (cid, action) => {
    setBusy(`${cid}:${action}`);
    try { await api.post(`/enterprise/connectors/${cid}/${action}`); toast.success(`${cid} ${action}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    setBusy("");
  };
  if (!list) return null;
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {list.map((c) => (
        <div key={c.cid} data-testid={`catalog-connector-${c.cid}`} className="bg-card fact-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-1">
            <div className="font-head font-bold text-sm">{c.name}</div>
            <span className={`w-2 h-2 rounded-full ${c.status === "connected" ? "bg-low" : "bg-muted-foreground/40"}`} style={c.status === "connected" ? { boxShadow: "0 0 6px hsl(142 70% 45%)" } : {}} />
          </div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground">{c.category}</div>
          {c.status === "connected" ? (
            <>
              <div className="text-xs text-muted-foreground mt-2">{c.records_ingested.toLocaleString()} records</div>
              <div className="flex gap-2 mt-3">
                <button data-testid={`sync-${c.cid}`} disabled={!!busy} onClick={() => act(c.cid, "sync")} className="flex-1 flex items-center justify-center gap-1 text-xs py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai"><RefreshCw className="w-3 h-3" /> Sync</button>
                <button data-testid={`disconnect-${c.cid}`} disabled={!!busy} onClick={() => act(c.cid, "disconnect")} className="text-xs py-1.5 px-2 rounded-md text-muted-foreground hover:text-crit">Disconnect</button>
              </div>
            </>
          ) : (
            <button data-testid={`connect-${c.cid}`} disabled={!!busy} onClick={() => act(c.cid, "connect")} className="w-full mt-3 text-xs py-1.5 rounded-md bg-primary text-primary-foreground font-bold disabled:opacity-50">
              {busy === `${c.cid}:connect` ? "…" : "Connect"}
            </button>
          )}
        </div>
      ))}
    </div>
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
        <p className="text-sm text-muted-foreground mt-1">Governed live connectors and integrations. <span className="text-med font-mono text-xs">M365, Copilot, ChatGPT, Teams &amp; SSO go LIVE when you add real credentials; catalog connectors are MOCKED.</span></p>
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
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-3">Catalog connectors</div>
        <Catalog />
      </div>
    </div>
  );
}
