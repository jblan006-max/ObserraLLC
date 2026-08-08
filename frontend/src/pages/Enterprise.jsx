import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Building2, Loader2, KeyRound, Users, ShieldCheck, Trash2, Plus, Palette, Cloud } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function Enterprise() {
  const [cfg, setCfg] = useState(null);
  const [live, setLive] = useState(null);
  const [abac, setAbac] = useState([]);
  const [brand, setBrand] = useState(null);
  useEffect(() => {
    api.get("/enterprise/config").then((r) => setCfg(r.data)).catch(() => setCfg({}));
    api.get("/enterprise/live").then((r) => setLive(r.data)).catch(() => setLive({}));
    api.get("/enterprise/abac").then((r) => setAbac(r.data)).catch(() => setAbac([]));
    api.get("/branding").then((r) => setBrand(r.data)).catch(() => setBrand(null));
  }, []);

  const m365 = live?.m365 || {};
  const sso = cfg?.sso || {};
  const scim = cfg?.scim || {};
  const abacOn = cfg?.abac?.enforce;
  const statuses = [
    { key: "m365", label: "Microsoft 365", Icon: Cloud, ok: !!m365.live, warn: m365.configured, text: m365.live ? `LIVE · ${m365.user_count ?? "?"} users` : m365.configured ? "Configured" : "Not connected" },
    { key: "sso", label: "SSO / SAML", Icon: KeyRound, ok: !!(sso.enabled && sso.entity_id), warn: !!sso.entity_id, text: sso.enabled ? "Enabled" : sso.entity_id ? "Configured" : "Not set" },
    { key: "scim", label: "SCIM provisioning", Icon: Users, ok: !!scim.enabled, text: scim.enabled ? `On · ${scim.last_provisioned ?? 0} users` : "Off" },
    { key: "abac", label: "ABAC policy", Icon: ShieldCheck, ok: !!abacOn, warn: abac.length > 0, text: abacOn ? `Enforcing · ${abac.length} rules` : abac.length ? `Monitor · ${abac.length} rules` : "None" },
    { key: "brand", label: "White-label", Icon: Palette, ok: !!(brand && brand.display_name), text: brand?.display_name ? "Branded" : "Default" },
  ];
  const ready = statuses.filter((s) => s.ok).length;

  return (
    <div className="rise space-y-6" data-testid="enterprise-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Building2 className="w-7 h-7 text-primary" /> Enterprise Access</h1>
          <p className="text-sm text-muted-foreground mt-1">Everything needed to run Obserra at enterprise grade — identity source, SSO, SCIM, attribute policy &amp; white-label — on one live dashboard.</p>
        </div>
        <div className="text-right">
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Enterprise readiness</div>
          <div data-testid="enterprise-readiness" className="font-head font-black text-3xl tracking-tight" style={{ color: `hsl(${ready >= 4 ? "142 70% 45%" : ready >= 2 ? "35 90% 55%" : "0 84% 60%"})` }}>{ready}/5</div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4" data-testid="enterprise-status">
        {statuses.map((s) => (
          <div key={s.key} data-testid={`estat-${s.key}`} className="bg-card fact-border rounded-xl p-4">
            <div className="flex items-center justify-between mb-2"><s.Icon className="w-4 h-4 text-muted-foreground" /><span className={`w-2 h-2 rounded-full ${s.ok ? "bg-low" : s.warn ? "bg-med" : "bg-muted-foreground/40"}`} style={s.ok ? { boxShadow: "0 0 6px hsl(142 70% 45%)" } : {}} /></div>
            <div className="font-head font-bold text-sm">{s.label}</div>
            <div className="text-[11px] text-muted-foreground mt-0.5">{s.text}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <div className="space-y-2"><SectionH>Identity source · Microsoft 365</SectionH><LiveM365 /></div>
        <div className="space-y-2"><SectionH>Single sign-on (SAML)</SectionH><SSO /></div>
        <div className="space-y-2"><SectionH>SCIM provisioning</SectionH><SCIM /></div>
        <div className="space-y-2"><SectionH>White-label branding</SectionH><Branding /></div>
        <div className="lg:col-span-2 space-y-2"><SectionH>Attribute-based access (ABAC)</SectionH><ABAC /></div>
      </div>
    </div>
  );
}

function SectionH({ children }) {
  return <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground pt-1">{children}</div>;
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
  const clear = async () => { await api.delete("/enterprise/live/m365"); load(); toast.success("M365 disconnected"); };
  if (!s) return <Spinner />;
  return (
    <div data-testid="live-m365" className="bg-card fact-border rounded-xl p-5 space-y-3 h-full">
      <div className="flex items-center justify-between">
        <div className="font-head font-bold text-sm flex items-center gap-2"><Cloud className="w-4 h-4 text-ai" /> Live Microsoft 365 — auto-connect</div>
        {s.configured
          ? <span data-testid="m365-status" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${s.live ? "bg-low/15 text-low" : "bg-med/15 text-med"}`}>{s.live ? "LIVE" : "NOT LIVE"}</span>
          : <span data-testid="m365-status" className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-secondary/60 text-muted-foreground">NOT CONNECTED</span>}
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
          <p className="text-[11px] text-muted-foreground">Enter your Azure app (client-credentials). When valid, the connector auto-goes LIVE and pulls a real user count + managed devices from Microsoft Graph.</p>
          <Field label="Tenant ID" testid="m365-tenant" value={f.tenant_id} onChange={(e) => setF({ ...f, tenant_id: e.target.value })} />
          <Field label="Client ID" testid="m365-client" value={f.client_id} onChange={(e) => setF({ ...f, client_id: e.target.value })} />
          <Field label="Client Secret" testid="m365-secret" value={f.client_secret} onChange={(e) => setF({ ...f, client_secret: e.target.value })} />
          <button data-testid="m365-verify" disabled={busy} onClick={save} className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? "Verifying…" : "Verify & go live"}</button>
        </div>
      )}
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
    <div data-testid="sso-form" className="bg-card fact-border rounded-xl p-5 space-y-4 h-full">
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
    <div data-testid="scim-panel" className="bg-card fact-border rounded-xl p-5 space-y-4 h-full">
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
    <div data-testid="branding-panel" className="bg-card fact-border rounded-xl p-5 space-y-4 h-full">
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
