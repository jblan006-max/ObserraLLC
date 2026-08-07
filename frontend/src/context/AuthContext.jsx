import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [sub, setSub] = useState(null);
  const [mode, setMode] = useState(() => localStorage.getItem("eios_mode") || "executive");

  const refreshSub = useCallback(async () => {
    try { const { data } = await api.get("/subscription"); setSub(data); } catch { setSub(null); }
  }, []);

  useEffect(() => {
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => setUser(false));
  }, []);

  useEffect(() => { if (user) refreshSub(); }, [user, refreshSub]);

  const switchMode = (m) => { setMode(m); localStorage.setItem("eios_mode", m); };

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setUser(data); return data;
  };
  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    setUser(data); return data;
  };
  const logout = async () => { await api.post("/auth/logout"); setUser(false); setSub(null); };

  return (
    <AuthContext.Provider value={{ user, setUser, sub, refreshSub, mode, switchMode, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
