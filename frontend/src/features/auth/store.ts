import { create } from "zustand";
import { persist } from "zustand/middleware";

export type UserRole =
  | "ADMIN"
  | "VENTAS"
  | "LOGISTICA"
  | "CONTABILIDAD"
  | "SUPERVISOR"
  | "VIEWER";

export type AuthUser = {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  status: string;
};

type AuthState = {
  access: string | null;
  refresh: string | null;
  user: AuthUser | null;
  setSession: (access: string, refresh: string, user: AuthUser) => void;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: AuthUser) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      access: null,
      refresh: null,
      user: null,
      setSession: (access, refresh, user) => set({ access, refresh, user }),
      setTokens: (access, refresh) => set({ access, refresh }),
      setUser: (user) => set({ user }),
      logout: () => set({ access: null, refresh: null, user: null }),
    }),
    { name: "seeds-auth" },
  ),
);
