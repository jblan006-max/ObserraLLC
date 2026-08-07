import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Loader2, ShieldCheck, CheckCircle2, XCircle, Globe } from "lucide-react";

export default function QRApprove() {
  const { token } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState("ready");

  const approve = async () => {
    setState("approving");
    try {
      await api.post("/auth/qr/approve", { qr_token: token });
      setState("approved");
    } catch (e) {
      setState(e.response?.status === 410 ? "expired" : "error");
    }
  };

  if (user === null)
    return <div className="min-h-screen flex items-center justify-center grain"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="min-h-screen flex items-center justify-center p-6 grain">
      <div className="max-w-sm w-full bg-card border border-border rounded-lg p-8 text-center rise">
        <img src="/logo.png" alt="Obserra" className="h-10 w-auto object-contain mx-auto mb-6" />
        {!user ? (
          <>
            <ShieldCheck className="w-10 h-10 text-med mx-auto mb-3" />
            <h1 className="font-head font-bold text-lg">Sign in required</h1>
            <p className="text-sm text-muted-foreground mt-2 mb-6">Approve device sign-ins only from an already-authenticated session. Please sign in on this device, then reopen the link.</p>
            <button onClick={() => navigate("/")} className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm">Go to sign in</button>
          </>
        ) : state === "approved" ? (
          <>
            <CheckCircle2 className="w-12 h-12 text-low mx-auto mb-3" />
            <h1 className="font-head font-black text-xl">Sign-in approved</h1>
            <p className="text-sm text-muted-foreground mt-2">Return to the other device — it will sign in automatically.</p>
          </>
        ) : state === "expired" || state === "error" ? (
          <>
            <XCircle className="w-12 h-12 text-crit mx-auto mb-3" />
            <h1 className="font-head font-bold text-xl">{state === "expired" ? "Code expired" : "Approval failed"}</h1>
            <p className="text-sm text-muted-foreground mt-2">Generate a fresh QR code on the signing-in device.</p>
          </>
        ) : (
          <>
            <Globe className="w-10 h-10 text-ai mx-auto mb-3" />
            <h1 className="font-head font-bold text-lg">Approve sign-in?</h1>
            <p className="text-sm text-muted-foreground mt-2 mb-1">A device is requesting access to</p>
            <p className="font-mono text-sm text-foreground mb-6">{user.email}</p>
            <p className="text-[11px] text-muted-foreground mb-5">Only approve if you just scanned this code yourself.</p>
            <button data-testid="qr-approve-btn" onClick={approve} disabled={state === "approving"}
              className="w-full py-2.5 rounded-md bg-ai text-background font-head font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-50">
              {state === "approving" && <Loader2 className="w-4 h-4 animate-spin" />} Approve sign-in
            </button>
          </>
        )}
      </div>
    </div>
  );
}
