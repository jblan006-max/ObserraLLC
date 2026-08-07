import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";

export default function PaymentSuccess() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    const sessionId = params.get("session_id");
    if (!sessionId) { setStatus("error"); return; }
    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      try {
        const { data } = await api.get(`/payments/status/${sessionId}`);
        if (data.payment_status === "paid") { setStatus("paid"); return; }
        if (data.status === "expired" || attempts > 8) { setStatus("error"); return; }
      } catch { if (attempts > 8) { setStatus("error"); return; } }
      setTimeout(poll, 2000);
    };
    poll();
  }, [params]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6 grain">
      <div className="max-w-md w-full bg-card fact-border rounded-lg p-8 text-center rise">
        {status === "checking" && (<><Loader2 className="w-10 h-10 animate-spin text-primary mx-auto mb-4" /><h1 className="font-head font-bold text-xl">Confirming payment…</h1><p className="text-sm text-muted-foreground mt-2">Waiting for Stripe webhook confirmation.</p></>)}
        {status === "paid" && (<><CheckCircle2 className="w-12 h-12 text-low mx-auto mb-4" /><h1 className="font-head font-black text-2xl">Subscription active</h1><p className="text-sm text-muted-foreground mt-2 mb-6">Entitlements granted to your organization.</p><button data-testid="goto-app" onClick={() => navigate("/app")} className="px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm">Go to dashboard</button></>)}
        {status === "error" && (<><XCircle className="w-12 h-12 text-crit mx-auto mb-4" /><h1 className="font-head font-bold text-xl">Payment not confirmed</h1><p className="text-sm text-muted-foreground mt-2 mb-6">If you completed checkout, it may take a moment. Otherwise try again.</p><button onClick={() => navigate("/app/billing")} className="px-5 py-2.5 rounded-md bg-secondary text-foreground font-head font-bold text-sm">Back to billing</button></>)}
      </div>
    </div>
  );
}
