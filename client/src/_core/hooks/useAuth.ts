import { useCallback, useMemo } from "react";

type UseAuthOptions = {
  redirectOnUnauthenticated?: boolean;
  redirectPath?: string;
};

type DevelopmentUser = {
  id: string;
  name: string;
  email: string;
};

function getDevelopmentUser(): DevelopmentUser {
  const existing = window.localStorage.getItem("forma_development_user");
  if (existing) {
    const user = JSON.parse(existing) as DevelopmentUser;
    window.localStorage.setItem("forma_development_user_id", user.id);
    return user;
  }
  const id = window.localStorage.getItem("forma_development_user_id") ?? crypto.randomUUID();
  const user = { id, name: "Forma user", email: "local@forma.dev" };
  window.localStorage.setItem("forma_development_user_id", id);
  window.localStorage.setItem("forma_development_user", JSON.stringify(user));
  return user;
}

/**
 * Development-only auth adapter. Production FastAPI accepts only verified JWT bearer tokens.
 * A real issuer/session exchange is tracked as an explicit architecture TODO.
 */
export function useAuth(_options?: UseAuthOptions) {
  const user = useMemo(() => getDevelopmentUser(), []);
  const logout = useCallback(async () => {
    window.localStorage.removeItem("forma_workspace_id");
    window.localStorage.removeItem("forma_development_user");
    window.localStorage.removeItem("forma_development_user_id");
    window.location.reload();
  }, []);

  return {
    user,
    loading: false,
    error: null,
    isAuthenticated: true,
    refresh: async () => undefined,
    logout,
  };
}
