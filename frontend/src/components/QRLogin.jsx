import { useEffect, useState, useRef } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Loader2, CheckCircle2, RefreshCw, Smartphone } from "lucide-react";

export function QRLogin() {
  const { setUser } = useAuth();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("starting");
  const timer = useRef();

  const start = async () => {
    setStatus("starting");
    try {
      const { data } = await api.post("/auth/qr/start");
      setData(data);
      setStatus("pending");
    } catch { setStatus("expired"); }
  };

  useEffect(() => { start(); return () => clearInterval(timer.current); }, []);

  useEffect(() => {
    if (!data || status === "claimed" || status === "expired" || status === "starting") return;
    timer.current = setInterval(async () => {
      try {
        const { data: x } = await api.post("/auth/qr/poll", { poll_token: data.poll_token });
        setStatus(x.status);
        if (x.status === "claimed") { clearInterval(timer.current); setUser(x.user); }
      } catch (e) {
        if (e.response?.status === 410) { setStatus("expired"); clearInterval(timer.current); }
      }
    }, 2000);
    return () => clearInterval(timer.current);
  }, [data, status]);

  return (
    <div data-testid="qr-login" className="flex flex-col items-center text-center rise">
      <div className="relative p-4 rounded-xl bg-white">
        {data && status !== "starting" ? (
          <QRCodeSVG value={data.approve_url} size={196} level="M"
            imageSettings={{ src: "/logo.png", height: 0, width: 0, excavate: false }} />
        ) : (
          <div className="w-[196px] h-[196px] flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        )}
        {(status === "approved" || status === "claimed") && (
          <div className="absolute inset-4 rounded-lg bg-background/90 flex flex-col items-center justify-center gap-2">
            <CheckCircle2 className="w-10 h-10 text-low" />
            <span className="text-xs font-mono text-foreground">{status === "claimed" ? "Signing in…" : "Approved on device"}</span>
          </div>
        )}
      </div>
      <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
        <Smartphone className="w-3.5 h-3.5" />
        {status === "expired" ? "QR expired" : "Scan with an authenticated device to approve"}
      </div>
      {status === "expired" && (
        <button data-testid="qr-regenerate" onClick={start}
          className="mt-3 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-secondary/60 hover:bg-secondary transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Generate new code
        </button>
      )}
      <div className="mt-2 text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Passwordless · single-use · 3 min</div>
    </div>
  );
}
