import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Fingerprint, Apple, KeyRound, Loader2, CheckCircle2 } from "lucide-react";

const inputCls = "w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary";

function Badge({ ok, label }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-sm border ${ok ? "border-low/40 text-low" : "border-border text-muted-foreground"}`}>
      {ok && <CheckCircle2 className="w-3 h-3" />}{ok ? "Connected" : "Not set"} · {label}
    </span>
  );
}

export function SsoCard() {
  const [cfg, setCfg] = useState(null);
  const [apple, setApple] = useState({ team_id: "", service_id: "", key_id: "", private_key_p8: "" });
  const [oidc, setOidc] = useState({ discovery_url: "", client_id: "", client_secret: "", issuer: "" });
  const [saml, setSaml] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/admin/sso").then(({ data }) => {
    setCfg(data);
    setApple({ team_id: data.apple.team_id || "", service_id: data.apple.service_id || "", key_id: data.apple.key_id || "", private_key_p8: "" });
    setOidc({ discovery_url: data.oidc.discovery_url || "", client_id: data.oidc.client_id || "", client_secret: "", issuer: data.oidc.issuer || "" });
    setSaml(data.saml_metadata_url || "");
  }).catch(() => {});
  useEffect(() => { load(); }, []);

  const put = async (payload, msg) => {
    setBusy(true);
    try { await api.put("/admin/sso", payload); toast.success(msg); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not save"); }
    setBusy(false);
  };

  const setA = (k) => (e) => setApple((f) => ({ ...f, [k]: e.target.value }));
  const setO = (k) => (e) => setOidc((f) => ({ ...f, [k]: e.target.value }));

  if (!cfg) return null;

  return (
    <div className="bg-card fact-border rounded-xl p-6 space-y-6" data-testid="sso-config-settings">
      <div className="flex items-center gap-2"><Fingerprint className="w-4 h-4 text-ai" /><h2 className="font-head font-bold text-lg">Apple &amp; Enterprise SSO</h2></div>
      <p className="text-sm text-muted-foreground -mt-3">Connect your own Apple Sign In and enterprise identity provider. Credentials are encrypted at rest and used only at sign-in — no server config needed.</p>

      {/* Apple */}
      <div className="space-y-3 border-t border-border pt-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-head font-bold"><Apple className="w-4 h-4" /> Sign in with Apple</div>
          <Badge ok={cfg.apple_configured} label="Apple" />
        </div>
        <div className="grid sm:grid-cols-3 gap-3">
          <input data-testid="apple-team-id" className={inputCls} placeholder="Team ID" value={apple.team_id} onChange={setA("team_id")} />
          <input data-testid="apple-service-id" className={inputCls} placeholder="Services ID (client_id)" value={apple.service_id} onChange={setA("service_id")} />
          <input data-testid="apple-key-id" className={inputCls} placeholder="Key ID" value={apple.key_id} onChange={setA("key_id")} />
        </div>
        <textarea data-testid="apple-p8" rows={4} className={`${inputCls} font-mono text-xs`} placeholder="Paste the complete .p8 private key contents (leave blank to keep existing)" value={apple.private_key_p8} onChange={setA("private_key_p8")} />
        <div className="flex gap-2">
          <button data-testid="apple-save" disabled={busy} onClick={() => put({ apple }, "Apple Sign In saved")}
            className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} Save Apple
          </button>
          {cfg.apple_configured && <button data-testid="apple-clear" disabled={busy} onClick={() => put({ clear_apple: true }, "Apple config removed")}
            className="px-4 py-2 rounded-md text-sm text-muted-foreground hover:text-crit hover:bg-crit/10 transition-colors">Remove</button>}
        </div>
      </div>

      {/* Enterprise OIDC */}
      <div className="space-y-3 border-t border-border pt-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-head font-bold"><KeyRound className="w-4 h-4" /> Enterprise SSO (OIDC — Okta / Azure AD / Google Workspace)</div>
          <Badge ok={cfg.oidc_configured} label="OIDC" />
        </div>
        <input data-testid="oidc-discovery" className={inputCls} placeholder="Discovery URL (…/.well-known/openid-configuration)" value={oidc.discovery_url} onChange={setO("discovery_url")} />
        <div className="grid sm:grid-cols-2 gap-3">
          <input data-testid="oidc-client-id" className={inputCls} placeholder="Client ID" value={oidc.client_id} onChange={setO("client_id")} />
          <input data-testid="oidc-client-secret" type="password" autoComplete="new-password" className={inputCls} placeholder="Client secret (blank to keep existing)" value={oidc.client_secret} onChange={setO("client_secret")} />
        </div>
        <div className="flex gap-2">
          <button data-testid="oidc-save" disabled={busy} onClick={() => put({ oidc }, "Enterprise SSO saved")}
            className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} Save Enterprise SSO
          </button>
          {cfg.oidc_configured && <button data-testid="oidc-clear" disabled={busy} onClick={() => put({ clear_oidc: true }, "Enterprise SSO removed")}
            className="px-4 py-2 rounded-md text-sm text-muted-foreground hover:text-crit hover:bg-crit/10 transition-colors">Remove</button>}
        </div>
      </div>

      {/* SAML metadata (optional) */}
      <div className="space-y-3 border-t border-border pt-4">
        <div className="flex items-center gap-2 text-sm font-head font-bold">SAML metadata URL <span className="text-muted-foreground font-normal">(optional)</span></div>
        <div className="flex gap-2">
          <input data-testid="saml-metadata" className={inputCls} placeholder="https://idp.example.com/metadata.xml" value={saml} onChange={(e) => setSaml(e.target.value)} />
          <button data-testid="saml-save" disabled={busy} onClick={() => put({ saml_metadata_url: saml }, "SAML metadata saved")}
            className="px-4 py-2 rounded-md bg-secondary/70 border border-border font-head font-bold text-sm shrink-0 hover:bg-secondary transition-colors">Save</button>
        </div>
      </div>

      <p className="text-[11px] text-muted-foreground border-t border-border pt-3">
        Register these callback URLs with your provider: <code className="font-mono">/api/auth/apple/callback</code> (Apple) and <code className="font-mono">/api/auth/sso/callback</code> (OIDC).
      </p>
    </div>
  );
}
