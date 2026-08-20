import React, { createContext, useContext, useEffect, useState } from "react";
import { api, setToken, getToken } from "./api.js";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const boot = async () => {
      if (getToken()) {
        try {
          setUser(await api.me());
        } catch {
          setToken(null);
        }
      }
      setReady(true);
    };
    boot();
    const onUnauth = () => setUser(null);
    window.addEventListener("zkt-unauthorized", onUnauth);
    return () => window.removeEventListener("zkt-unauthorized", onUnauth);
  }, []);

  const login = async (username, password) => {
    const r = await api.login(username, password);
    setToken(r.access_token);
    setUser(r.user);
    return r.user;
  };
  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, ready, login, logout, isAdmin: user?.role === "admin" }}>
      {children}
    </AuthCtx.Provider>
  );
}
