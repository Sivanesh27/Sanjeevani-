import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setCsrf } from "./api";

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const apply = useCallback((d) => { setCsrf(d.csrf); setUser(d.user); return d; }, []);
  const refresh = useCallback(async () => {
    try { apply(await api.get("/auth/me")); } catch { setUser(null); setCsrf(""); } finally { setLoading(false); }
  }, [apply]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    const h = () => { setUser(null); setCsrf(""); };
    window.addEventListener("sj:unauthorized", h);
    return () => window.removeEventListener("sj:unauthorized", h);
  }, []);

  const value = useMemo(() => ({
    user, loading, refresh, setUser,
    login: async (email, password, face) => { const d = await api.post("/auth/login", { email, password, ...(face ? { face } : {}) }); if (d.user) apply(d); return d; },
    otp: async (otp_token, code) => apply(await api.post("/auth/login/otp", { otp_token, code })),
    faceLogin: async (email, descriptor, nonce) => apply(await api.post("/auth/face/login", { email, descriptor, nonce })),
    register: async (payload) => { const d = await api.post("/auth/register", payload); if (d.user) apply(d); return d; },
    logout: async () => { try { await api.post("/auth/logout"); } finally { setUser(null); setCsrf(""); } },
  }), [user, loading, refresh, apply]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
