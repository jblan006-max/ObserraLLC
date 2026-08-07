import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail, API, api } from "@/lib/api";
import { QRLogin } from "@/components/QRLogin";
import { NetworkBackground } from "@/components/NetworkBackground";
import { ShieldHalf, Loader2, Apple, KeyRound, QrCode, ArrowLeft } from "lucide-react";

export default function Auth() {
  const { login, register } = useAuth();
  const [tab, setTab] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", name: "", org_name: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [providers, setProviders] = useState({ google: true, passwordless: true, apple: false, sso: false });

  useEffect(() => { api.get("/auth/providers").then((r) => setProviders(r.data)).catch(() => {}); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (tab === "login") await login(form.email, form.password);
      else await register(form);
    } catch (e2) {
      setErr(formatApiErrorDetail(e2.response?.data?.detail) || e2.message);
    }
    setBusy(false);
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="min-h-screen grid lg:grid-cols-2 grain">
      <div className="relative hidden lg:flex flex-col justify-between p-12 border-r border-border overflow-hidden">
        <img alt="" src="https://images.unsplash.com/photo-1644088379091-d574269d422f?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200"
          className="absolute inset-0 w-full h-full object-cover opacity-[0.08]" />
        <NetworkBackground className="absolute inset-0 w-full h-full opacity-70" />
        <div className="relative flex flex-col items-center text-center gap-6">
          <img src="/brand-mark.png" alt="Obserra mark" className="h-40 xl:h-52 w-auto object-contain logo-pulse drop-shadow-[0_8px_30px_rgba(86,184,233,0.25)]" />
          <img src="/brand-wordmark.png" alt="OBSERRA — Executive Protection & Intelligence LLC" className="h-16 xl:h-20 w-auto object-contain" />
        </div>
        <div className="relative space-y-6">
          <h1 className="font-head font-black text-5xl leading-[1.05] tracking-tight">
            Enterprise Intelligence,<br /><span className="text-ai">two altitudes.</span>
          </h1>
          <p className="text-muted-foreground max-w-md text-base leading-relaxed">
            Cyber Risk Register, Executive Dashboard and AI Governance Suite on one evidence-grounded platform. Every metric carries its source, freshness and confidence.
          </p>
          <div className="flex gap-3 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
            <span className="px-2 py-1 rounded-sm border border-border">Executive Mode</span>
            <span className="px-2 py-1 rounded-sm border border-border">Operational Mode</span>
            <span className="px-2 py-1 rounded-sm ai-border text-ai">Evidence-backed AI</span>
          </div>
        </div>
        <div className="relative flex items-center gap-3 text-xs font-mono text-muted-foreground">
          <span>Multi-tenant · Immutable audit · Board-ready</span>
          <a data-testid="visit-site-link" href="https://www.obserrallc.com/" target="_blank" rel="noopener noreferrer"
            className="text-ai hover:underline">Visit us at obserrallc.com →</a>
        </div>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm rise">
          <div className="lg:hidden mb-8 flex flex-col items-center text-center gap-4">
            <img src="/brand-mark.png" alt="Obserra mark" className="h-24 w-auto object-contain drop-shadow-[0_6px_20px_rgba(86,184,233,0.25)]" />
            <img src="/brand-wordmark.png" alt="OBSERRA — Executive Protection & Intelligence LLC" className="h-14 w-auto object-contain" />
          </div>
          <div className="flex gap-1 p-1 bg-secondary/50 rounded-lg mb-6 text-sm">
            {["login", "register"].map((t) => (
              <button key={t} data-testid={`auth-tab-${t}`} onClick={() => { setTab(t); setErr(""); }}
                className={`flex-1 py-2 rounded-md font-medium capitalize transition-colors duration-200 ${
                  tab === t ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                {t === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          {tab === "login" && showQR ? (
            <div className="space-y-4">
              <button type="button" data-testid="qr-back" onClick={() => setShowQR(false)}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
                <ArrowLeft className="w-3.5 h-3.5" /> Use email &amp; password
              </button>
              <QRLogin />
            </div>
          ) : (
          <form onSubmit={submit} className="space-y-4">
            {tab === "register" && (
              <>
                <Field label="Full name" testid="auth-name" value={form.name} onChange={set("name")} required />
                <Field label="Organization" testid="auth-org" value={form.org_name} onChange={set("org_name")} placeholder="Acme Corp" />
              </>
            )}
            <Field label="Work email" type="email" testid="auth-email" value={form.email} onChange={set("email")} required />
            <Field label="Password" type="password" testid="auth-password" value={form.password} onChange={set("password")} required />

            {err && <p data-testid="auth-error" className="text-xs text-crit">{err}</p>}

            <button data-testid="auth-submit" disabled={busy} type="submit"
              className="w-full py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50">
              {busy && <Loader2 className="w-4 h-4 animate-spin" />}
              {tab === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
          )}

          {!showQR && (
            <>
              <div className="flex items-center gap-3 my-4">
                <div className="h-px flex-1 bg-border" /><span className="text-[10px] font-mono uppercase text-muted-foreground">or</span><div className="h-px flex-1 bg-border" />
              </div>
              {/* REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH */}
              <button type="button" data-testid="google-signin" onClick={() => {
                const redirectUrl = window.location.origin + "/app";
                window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
              }} className="w-full py-2.5 rounded-md bg-white text-gray-800 font-head font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity">
                <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="" className="w-4 h-4" /> Continue with Google
              </button>

              <button type="button" data-testid="apple-signin"
                onClick={() => providers.apple ? (window.location.href = `${API}/auth/apple`) : setErr("Apple Sign In isn't attached yet. An admin can connect it under Enterprise → Available Connectors, then this button signs you in with your Apple ID instantly.")}
                className="w-full mt-2 py-2.5 rounded-md bg-black text-white font-head font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity">
                <Apple className="w-4 h-4" /> Continue with Apple
              </button>

              <button type="button" data-testid="sso-signin"
                onClick={() => providers.sso ? (window.location.href = `${API}/auth/sso`) : setErr("Enterprise SSO isn't attached yet. An admin can connect your Okta/Azure IdP under Enterprise → Available Connectors, then this button signs you in with your company account.")}
                className="w-full mt-2 py-2.5 rounded-md bg-secondary/70 border border-border text-foreground font-head font-bold text-sm flex items-center justify-center gap-2 hover:bg-secondary transition-colors">
                <KeyRound className="w-4 h-4" /> Continue with Enterprise SSO
              </button>

              {tab === "login" && (
                <button type="button" data-testid="qr-toggle" onClick={() => setShowQR(true)}
                  className="w-full mt-2 py-2.5 rounded-md bg-ai/10 border border-ai/30 text-ai font-head font-bold text-sm flex items-center justify-center gap-2 hover:bg-ai/20 transition-colors">
                  <QrCode className="w-4 h-4" /> Passwordless — sign in with QR
                </button>
              )}
            </>
          )}

          {tab === "login" && !showQR && (
            <>
              <a data-testid="visit-site-link-mobile" href="https://www.obserrallc.com/" target="_blank" rel="noopener noreferrer"
                className="mt-6 block text-center text-xs text-ai hover:underline">Visit us at obserrallc.com →</a>
            </>
          )}

          <div data-testid="auth-legal" className="mt-6 pt-4 border-t border-border/60 space-y-2">
            <div className="text-center text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
              Property of Obserra — Executive Protection &amp; Intelligence LLC
            </div>
            <div className="flex items-center justify-center gap-1.5 flex-wrap">
              <span data-testid="tag-proprietary" className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-sm border border-ai/30 text-ai">Proprietary &amp; Confidential</span>
              <span data-testid="tag-priority" className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-sm border border-med/40 text-med">Priority — Restricted</span>
              <span data-testid="tag-authorized" className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-sm border border-border text-muted-foreground">Authorized Access Only</span>
            </div>
            <p data-testid="auth-disclaimer" className="text-[10px] leading-relaxed text-muted-foreground text-center max-w-sm mx-auto">
              This is a private, monitored system containing confidential and proprietary information of Obserra — Executive Protection &amp; Intelligence LLC. Access is restricted to authorized users only. Unauthorized access, use, or disclosure is prohibited and may be unlawful. All activity is logged and audited. © {new Date().getFullYear()} Obserra LLC. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, testid, type = "text", ...props }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted-foreground mb-1.5 block">{label}</span>
      <input data-testid={testid} type={type} {...props}
        className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary transition-shadow" />
    </label>
  );
}
