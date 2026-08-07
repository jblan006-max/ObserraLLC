import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Building2, Loader2, Plug, KeyRound, Users, ShieldCheck, Trash2, Plus, RefreshCw, Palette, Cloud } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const TABS = [["sso", "SSO / SAML", KeyRound], ["scim", "SCIM", Users], ["abac", "ABAC", ShieldCheck], ["branding", "Branding", Palette]];

export default function Enterprise() {
  const [tab, setTab] = useState("sso");
  return (
    <div className="rise space-y-6">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Building2 className="w-7 h-7 text-primary" /> Enterprise Access</h1>
        <p className="text-sm text-muted-foreground mt-1">Enterprise identity, provisioning, ABAC &amp; white-label branding. <span className="text-med font-mono text-xs">Live connectors now live in the Available Connectors page.</span></p>
      </div>
      <div className="flex gap-1 border-b border-border overflow-x-auto whitespace-nowrap -mx-1 px-1">
        {TABS.map(([id, label, Icon]) => (
          <button key={id} data-testid={`etab-${id}`} onClick={() => setTab(id)}
            className={`shrink-0 flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>
      {tab === "sso" && <SSO />}
      {tab === "scim" && <SCIM />}
      {tab === "abac" && <ABAC />}
      {tab === "branding" && <Branding />}
    </div>
  );
}

function LiveM365() {
  const [s, setS] = useState(null);
  const [f, setF] = useState({ tenant_id: "", client_id: "", client_secret: "" });
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/enterprise/live").then((r) => setS(r.data.m365));
  useEffect(() => { load(); }, []);
  const save = async () => {
    if (!f.tenant_id || !f.client_id || !f.client_secret) { toast.error("All M365 fields required"); return; }
    setBusy(true);
    try {
      const { data } = await api.put("/enterprise/live/m365", f);
      setS(data); setF({ tenant_id: "", client_id: "", client_secret: "" });
      if (data.live) toast.success(`M365 LIVE · ${data.user_count ?? "?"} users`);
      else toast.error(`Not live: ${data.status}`);
    } catch { toast.error("Save failed"); }
    setBusy(false);
  };
  const clear = async () => { await api.delete("/enterprise/live/m365"); load(); toast.success("M365 disconnected — reverted to mocked"); };
  if (!s) return null;
  return (
    <div data-testid="live-m365" className="bg-card fact-border rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-head font-bold text-sm flex items-center gap-2"><Cloud className="w-4 h-4 text-ai" /> Live Microsoft 365 — auto-connect</div>
        {s.configured
          ? <span data-testid="m365-status" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${s.live ? "bg-low/15 text-low" : "bg-med/15 text-med"}`}>{s.live ? "LIVE" : "NOT LIVE"}</span>
          : <span data-testid="m365-status" className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-secondary/60 text-muted-foreground">MOCKED</span>}
      </div>
      {s.configured ? (
        <div className="text-xs space-y-1">
          <div className="font-mono text-muted-foreground">Tenant: {s.tenant_id} · App: {s.client_id_masked}</div>
          <div className="text-muted-foreground">{s.live ? `${s.user_count ?? "?"} users synced from Microsoft Graph` : s.status}</div>
          <div className="flex gap-2 pt-1">
            <button data-testid="m365-update" disabled={busy} onClick={() => setS({ ...s, configured: false })} className="text-xs px-3 py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai">Update creds</button>
            <button data-testid="m365-disconnect" onClick={clear} className="text-xs px-3 py-1.5 rounded-md text-muted-foreground hover:text-crit">Disconnect</button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-[11px] text-muted-foreground">Enter your Azure app (client-credentials). When valid, the connector auto-goes LIVE and pulls a real user count from Microsoft Graph. Left blank, it stays mocked.</p>
          <Field label="Tenant ID" testid="m365-tenant" value={f.tenant_id} onChange={(e) => setF({ ...f, tenant_id: e.target.value })} />
          <Field label="Client ID" testid="m365-client" value={f.client_id} onChange={(e) => setF({ ...f, client_id: e.target.value })} />
          <Field label="Client Secret" testid="m365-secret" value={f.client_secret} onChange={(e) => setF({ ...f, client_secret: e.target.value })} />
          <button data-testid="m365-verify" disabled={busy} onClick={save} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? "Verifying…" : "Verify & go live"}</button>
        </div>
      )}
    </div>
  );
}

function LiveSSO() {
  const [s, setS] = useState(null);
  const [f, setF] = useState({ metadata_url: "", entity_id: "" });
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/enterprise/live").then((r) => setS(r.data.sso));
  useEffect(() => { load(); }, []);
  const save = async () => {
    if (!f.metadata_url) { toast.error("Metadata URL required"); return; }
    setBusy(true);
    try {
      const { data } = await api.put("/enterprise/live/sso", f); setS(data);
      if (data.valid) toast.success("SSO metadata validated — Configured / ready");
      else toast.error(`Invalid: ${data.status}`);
    } catch { toast.error("Save failed"); }
    setBusy(false);
  };
  const clear = async () => { await api.delete("/enterprise/live/sso"); setF({ metadata_url: "", entity_id: "" }); load(); toast.success("SSO cleared"); };
  if (!s) return null;
  return (
    <div data-testid="live-sso" className="bg-card fact-border rounded-xl p-6 max-w-xl space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-head font-bold text-sm flex items-center gap-2"><KeyRound className="w-4 h-4 text-ai" /> Live SSO (SAML) — auto-connect</div>
        {s.configured
          ? <span data-testid="sso-live-status" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${s.valid ? "bg-low/15 text-low" : "bg-med/15 text-med"}`}>{s.valid ? "CONFIGURED / READY" : "INVALID"}</span>
          : <span data-testid="sso-live-status" className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-secondary/60 text-muted-foreground">NOT SET</span>}
      </div>
      <p className="text-[11px] text-muted-foreground">Paste your IdP metadata URL. We validate it live and mark SSO ready. App login stays on Google/JWT until full SAML sign-in is enabled as its own phase.</p>
      <Field label="IdP Metadata URL" testid="sso-metadata" value={f.metadata_url} onChange={(e) => setF({ ...f, metadata_url: e.target.value })} />
      {s.configured && <div className="text-xs font-mono text-muted-foreground">Entity: {s.entity_id || "—"} · {s.status}</div>}
      <div className="flex gap-2">
        <button data-testid="sso-validate" disabled={busy} onClick={save} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? "Validating…" : "Validate & mark ready"}</button>
        {s.configured && <button data-testid="sso-clear" onClick={clear} className="text-xs px-3 py-1.5 rounded-md text-muted-foreground hover:text-crit">Clear</button>}
      </div>
    </div>
  );
}

function Connectors() {
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
  if (!list) return <Spinner />;
  return (
    <div className="space-y-6">
      <LiveM365 />
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {list.map((c) => (
        <div key={c.cid} data-testid={`connector-${c.cid}`} className="bg-card fact-border rounded-xl p-4">
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
    </div>
  );
}

function SSO() {
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/enterprise/config").then((r) => setCfg(r.data.sso)); }, []);
  const save = async () => {
    setBusy(true);
    try { const { data } = await api.put("/enterprise/sso", cfg); setCfg(data); toast.success("SSO configuration saved"); }
    catch { toast.error("Save failed"); }
    setBusy(false);
  };
  if (!cfg) return <Spinner />;
  return (
    <div data-testid="sso-form" className="bg-card fact-border rounded-xl p-6 max-w-xl space-y-4">
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input data-testid="sso-enabled" type="checkbox" checked={cfg.enabled} onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} /> Enable SAML 2.0 single sign-on
      </label>
      <Field label="Identity Provider Entity ID" testid="sso-entity" value={cfg.entity_id} onChange={(e) => setCfg({ ...cfg, entity_id: e.target.value })} />
      <Field label="IdP SSO URL" testid="sso-url" value={cfg.sso_url} onChange={(e) => setCfg({ ...cfg, sso_url: e.target.value })} />
      <button data-testid="sso-save" disabled={busy} onClick={save} className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">Save SSO</button>
      <p className="text-[11px] text-muted-foreground">Live IdP metadata validation now lives in <span className="text-ai">Available Connectors → SSO / SAML</span>.</p>
    </div>
  );
}

function SCIM() {
  const [scim, setScim] = useState(null);
  useEffect(() => { api.get("/enterprise/config").then((r) => setScim(r.data.scim)); }, []);
  const toggle = async () => { const { data } = await api.post("/enterprise/scim/toggle"); setScim(data); toast.success(`SCIM ${data.enabled ? "enabled" : "disabled"}`); };
  if (!scim) return <Spinner />;
  return (
    <div data-testid="scim-panel" className="bg-card fact-border rounded-xl p-6 max-w-xl space-y-4">
      <div className="flex items-center justify-between">
        <div><div className="font-head font-bold text-sm">SCIM 2.0 Provisioning</div><div className="text-xs text-muted-foreground">Auto-provision & deprovision users from your IdP.</div></div>
        <button data-testid="scim-toggle" onClick={toggle} className={`text-xs px-3 py-2 rounded-md font-bold ${scim.enabled ? "bg-low/15 text-low" : "bg-primary text-primary-foreground"}`}>{scim.enabled ? "Enabled" : "Enable"}</button>
      </div>
      {scim.enabled && (
        <div className="space-y-2 text-xs font-mono">
          <div><span className="text-muted-foreground">Base URL:</span> {scim.base_url}</div>
          <div className="break-all"><span className="text-muted-foreground">Bearer token:</span> <span className="bg-secondary/60 px-2 py-0.5 rounded">{scim.token}</span></div>
          <div><span className="text-muted-foreground">Users provisioned:</span> {scim.last_provisioned}</div>
        </div>
      )}
    </div>
  );
}

function ABAC() {
  const [rules, setRules] = useState(null);
  const [enforce, setEnforce] = useState(false);
  const [form, setForm] = useState({ attribute: "", operator: "equals", value: "", resource: "", effect: "allow" });
  const load = () => {
    api.get("/enterprise/abac").then((r) => setRules(r.data));
    api.get("/enterprise/config").then((r) => setEnforce(r.data.abac?.enforce || false));
  };
  useEffect(() => { load(); }, []);
  const toggleEnforce = async () => { const { data } = await api.post("/enterprise/abac/enforce", { enforce: !enforce }); setEnforce(data.enforce); toast.success(`ABAC enforcement ${data.enforce ? "ON" : "OFF"}`); };
  const add = async () => {
    if (!form.attribute || !form.resource) { toast.error("Attribute and resource required"); return; }
    try { await api.post("/enterprise/abac", form); toast.success("Rule added"); setForm({ attribute: "", operator: "equals", value: "", resource: "", effect: "allow" }); load(); }
    catch { toast.error("Failed"); }
  };
  const del = async (id) => { await api.delete(`/enterprise/abac/${id}`); load(); };
  if (!rules) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="bg-card fact-border rounded-xl p-4 flex items-center justify-between">
        <div><div className="font-head font-bold text-sm">Request-path enforcement</div><div className="text-xs text-muted-foreground">When ON, matching deny rules block API calls (fail-safe: default allow).</div></div>
        <button data-testid="abac-enforce-toggle" onClick={toggleEnforce} className={`text-xs px-3 py-2 rounded-md font-bold ${enforce ? "bg-crit/15 text-crit" : "bg-secondary/60 text-muted-foreground"}`}>{enforce ? "Enforcing" : "Monitor only"}</button>
      </div>
      <div data-testid="abac-form" className="bg-card fact-border rounded-xl p-4 grid sm:grid-cols-6 gap-2 items-end">
        <Field label="Attribute" testid="abac-attribute" value={form.attribute} onChange={(e) => setForm({ ...form, attribute: e.target.value })} />
        <div><span className="text-xs text-muted-foreground mb-1.5 block">Operator</span>
          <Select value={form.operator} onValueChange={(v) => setForm({ ...form, operator: v })}><SelectTrigger data-testid="abac-operator" className="bg-secondary/60"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="equals">equals</SelectItem><SelectItem value="not_equals">not equals</SelectItem><SelectItem value="in">in</SelectItem></SelectContent></Select></div>
        <Field label="Value" testid="abac-value" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
        <Field label="Resource" testid="abac-resource" value={form.resource} onChange={(e) => setForm({ ...form, resource: e.target.value })} />
        <div><span className="text-xs text-muted-foreground mb-1.5 block">Effect</span>
          <Select value={form.effect} onValueChange={(v) => setForm({ ...form, effect: v })}><SelectTrigger data-testid="abac-effect" className="bg-secondary/60"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="allow">allow</SelectItem><SelectItem value="deny">deny</SelectItem></SelectContent></Select></div>
        <button data-testid="abac-add" onClick={add} className="flex items-center justify-center gap-1 py-2.5 rounded-md bg-primary text-primary-foreground font-bold text-sm"><Plus className="w-4 h-4" /> Add</button>
      </div>
      {rules.length === 0 ? <div className="text-sm text-muted-foreground text-center py-8">No ABAC rules yet — attribute rules augment role-based access.</div> : (
        <div className="bg-card fact-border rounded-xl divide-y divide-border/60">
          {rules.map((r) => (
            <div key={r.rule_id} data-testid={`abac-${r.rule_id}`} className="flex items-center gap-3 px-4 py-3 text-sm">
              <span className="font-mono text-xs text-ai">{r.rule_id}</span>
              <span><b>{r.effect}</b> access to <span className="font-mono">{r.resource}</span> when <span className="font-mono">{r.attribute} {r.operator} {r.value}</span></span>
              <button data-testid={`abac-del-${r.rule_id}`} onClick={() => del(r.rule_id)} className="ml-auto text-muted-foreground hover:text-crit"><Trash2 className="w-4 h-4" /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Branding() {
  const [b, setB] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/branding").then((r) => setB(r.data)); }, []);
  const save = async () => {
    setBusy(true);
    try { const { data } = await api.put("/branding", b); setB(data); const { applyBranding } = await import("@/lib/brand"); applyBranding(data); toast.success("Branding saved — chrome restyled"); }
    catch { toast.error("Save failed"); }
    setBusy(false);
  };
  if (!b) return <Spinner />;
  return (
    <div data-testid="branding-panel" className="bg-card fact-border rounded-xl p-6 max-w-xl space-y-4">
      <div className="text-xs text-muted-foreground">White-label the tenant experience — display name, accent color and logo.</div>
      <Field label="Display name" testid="brand-name" value={b.display_name} onChange={(e) => setB({ ...b, display_name: e.target.value })} />
      <Field label="Logo URL" testid="brand-logo" value={b.logo_url} onChange={(e) => setB({ ...b, logo_url: e.target.value })} />
      <div className="flex items-center gap-3">
        <input data-testid="brand-accent" type="color" value={b.accent} onChange={(e) => setB({ ...b, accent: e.target.value })} className="w-12 h-10 rounded-md bg-secondary/60 cursor-pointer" />
        <span className="text-sm font-mono">{b.accent}</span>
      </div>
      <button data-testid="brand-save" disabled={busy} onClick={save} className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">Save branding</button>
    </div>
  );
}

const Spinner = () => <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
function Field({ label, testid, ...props }) {
  return (<label className="block"><span className="text-xs text-muted-foreground mb-1.5 block">{label}</span>
    <input data-testid={testid} {...props} className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>);
}
