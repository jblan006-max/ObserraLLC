import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";

export default function ForcePasswordReset() {
  const { setUser } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault(); setErr("");
    if (next !== confirm) { setErr("New passwords do not match"); return; }
    if (next.length < 8) { setErr("New password must be at least 8 characters"); return; }
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      const { data } = await api.get("/auth/me");
      setUser(data);
      toast.success("Password updated — welcome to Obserra EIOS");
    } catch (e2) { setErr(formatApiErrorDetail(e2.response?.data?.detail) || e2.message); }
    setBusy(false);
  };

  return (
    <div className="min-h-screen grain flex items-center justify-center p-6">
      <div className="w-full max-w-sm rise">
        <img src="/logo.png" alt="Obserra" className="h-14 w-auto object-contain mb-6 logo-pulse" />
        <div className="flex items-center gap-2 mb-1"><ShieldCheck className="w-5 h-5 text-ai" /><h1 className="font-head font-black text-2xl">Set your password</h1></div>
        <p className="text-sm text-muted-foreground mb-6">For security, please replace your temporary password before continuing.</p>
        <form onSubmit={submit} data-testid="force-reset-form" className="space-y-4">
          <Field label="Temporary password" testid="fr-current" value={current} onChange={(e) => setCurrent(e.target.value)} />
          <Field label="New password" testid="fr-new" value={next} onChange={(e) => setNext(e.target.value)} />
          <Field label="Confirm new password" testid="fr-confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          {err && <p data-testid="fr-error" className="text-xs text-crit">{err}</p>}
          <button data-testid="fr-submit" disabled={busy} type="submit"
            className="w-full py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />} Set password &amp; continue
          </button>
        </form>
      </div>
    </div>
  );
}

function Field({ label, testid, ...props }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted-foreground mb-1.5 block">{label}</span>
      <input data-testid={testid} type="password" required {...props}
        className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
    </label>
  );
}
