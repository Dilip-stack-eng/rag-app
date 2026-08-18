import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { setAuthToken } from "../api/client";
import type { Role } from "../api/types";

interface AuthState {
  token: string | null;
  username: string | null;
  role: Role | null;
}

interface AuthContextValue extends AuthState {
  isAuthenticated: boolean;
  isSuperAdmin: boolean;
  login: (token: string, username: string, role: Role) => void;
  logout: () => void;
}

const STORAGE_KEY = "athena.auth";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function loadStored(): AuthState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { token: null, username: null, role: null };
    return JSON.parse(raw) as AuthState;
  } catch {
    return { token: null, username: null, role: null };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(loadStored);

  // Keep the API client's in-memory token in sync, including on first
  // mount when state is restored from localStorage.
  useEffect(() => {
    setAuthToken(state.token);
  }, [state.token]);

  const login = (token: string, username: string, role: Role) => {
    const next = { token, username, role };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setState(next);
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setState({ token: null, username: null, role: null });
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      isAuthenticated: state.token !== null,
      isSuperAdmin: state.role === "SuperAdmin",
      login,
      logout,
    }),
    [state]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
