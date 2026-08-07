import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/api";
import { QRLogin } from "@/components/QRLogin";
import { NetworkBackground } from "@/components/NetworkBackground";
import { ShieldHalf, Loader2 } from "lucide-react";

export default function Auth() {
  const { login, register } = useAuth();
  const [tab, setTab] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", name: "", org_name: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [showQR, setShowQR] = useState(false);

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
        <div className="relative">
          <img src="/logo.png" alt="Obserra — Executive Protection & Intelligence LLC" className="h-20 w-auto object-contain logo-pulse" />
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
          <div className="lg:hidden mb-8">
            <img src="/logo.png" alt="Obserra — Executive Protection & Intelligence LLC" className="h-16 w-auto object-contain" />
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

          {tab === "login" && (
            <button type="button" data-testid="qr-toggle" onClick={() => setShowQR((v) => !v)}
              className="w-full text-xs text-ai hover:underline mb-4">
              {showQR ? "← Use email & password" : "⌁ Sign in with QR code (passwordless)"}
            </button>
          )}

          {tab === "login" && showQR ? <QRLogin /> : (
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
            </>
          )}

          {tab === "login" && !showQR && (
            <>
              <p className="mt-6 text-xs text-muted-foreground text-center">
                Demo: <span className="font-mono text-foreground">jblan2026@gmail.com</span> / <span className="font-mono text-foreground">Obserra2026!</span>
              </p>
              <a data-testid="visit-site-link-mobile" href="https://www.obserrallc.com/" target="_blank" rel="noopener noreferrer"
                className="mt-3 block text-center text-xs text-ai hover:underline">Visit us at obserrallc.com →</a>
            </>
          )}
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
