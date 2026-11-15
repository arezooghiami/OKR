import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, configureClient, hasSession, login as apiLogin, logout as apiLogout } from "../api/client";
import type { Me } from "../api/types";

interface AuthState {
  me: Me | null;
  ready: boolean;
  signIn: (u: string, p: string) => Promise<void>;
  signOut: () => Promise<void>;
}

/** Org-wide users (system admin, a role granted without a unit, e.g. observers) land on the organisation
 * overview; people whose roles are tied to units land on their unit. */
export const isOrgWide = (me: Me | null) => !!me && (me.is_system_admin || me.roles.some((r) => r.units.length === 0));

const Ctx = createContext<AuthState | null>(null);
export const useAuth = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider missing");
  return v;
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(!hasSession());

  useEffect(() => {
    configureClient({ onUnauthorized: () => setMe(null) });
    if (hasSession()) api<Me>("/me").then(setMe).catch(() => setMe(null)).finally(() => setReady(true));
  }, []);

  const signIn = useCallback(async (u: string, p: string) => {
    await apiLogin(u, p);
    setMe(await api<Me>("/me"));
  }, []);
  const signOut = useCallback(async () => {
    await apiLogout();
    setMe(null);
  }, []);

  const value = useMemo(() => ({ me, ready, signIn, signOut }), [me, ready, signIn, signOut]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
