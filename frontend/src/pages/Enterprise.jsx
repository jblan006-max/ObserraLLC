import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Building2, Loader2, Plug, KeyRound, Users, ShieldCheck, Trash2, Plus, RefreshCw, Palette } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const TABS = [["connectors", "Connectors", Plug], ["sso", "SSO / SAML", KeyRound], ["scim", "SCIM", Users], ["abac", "ABAC", ShieldCheck], ["branding", "Branding", Palette]];

export default function Enterprise() {
  const [tab, setTab] = useState("connectors");
  return (
    <div className="rise space-y-6">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Building2 className="w-7 h-7 text-primary" /> Enterprise Access</h1>
        <p className="text-sm text-muted-foreground mt-1">Governed connectors and enterprise identity. <span className="text-med font-mono text-xs">External integrations are MOCKED in this environment.</span></p>
      </div>
      <div className="flex gap-1 border-b border-border">
        {TABS.map(([id, label, Icon]) => (
          <button key={id} data-testid={`etab-${id}`} onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>
      {tab === "connectors" && <Connectors />}
      {tab === "sso" && <SSO />}
      {tab === "scim" && <SCIM />}
      {tab === "abac" && <ABAC />}
      {tab === "branding" && <Branding />}
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
    try { const { data } = await api.put("/branding", b); setB(data); document.documentElement.style.setProperty("--brand-accent", data.accent); document.title = data.display_name; toast.success("Branding saved"); }
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
