import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";

export default function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const sid = new URLSearchParams(location.hash.replace(/^#/, "")).get("session_id");
    window.history.replaceState(null, "", window.location.pathname);
    (async () => {
      try {
        const { data } = await api.post("/auth/google/session", {}, { headers: { "X-Session-ID": sid } });
        setUser(data);
        navigate("/app", { replace: true });
      } catch (e) {
        const reason = e?.response?.data?.detail
          || "Google sign-in didn't complete. Please try again.";
        navigate(`/?auth_error=${encodeURIComponent(reason)}`, { replace: true });
      }
    })();
  }, [location, navigate, setUser]);

  return <div className="min-h-screen flex items-center justify-center grain"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
}
