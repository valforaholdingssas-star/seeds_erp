import { create } from "zustand";
import { persist } from "zustand/middleware";

export type UserRole =
  | "ADMIN"
  | "VENTAS"
  | "LOGISTICA"
  | "CONTABILIDAD"
  | "SUPERVISOR"
  | "VIEWER";

export type CrudFlags = { c: boolean; r: boolean; u: boolean; d: boolean };
export type CrudAction = keyof CrudFlags;

export type AuthUser = {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  status: string;
  modules?: string[];
  modules_effective?: string[];
  permissions_effective?: Record<string, CrudFlags>;
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

/** Check effective CRUD for a module (from /auth/me or login payload). */
export function useCan(module: string, action: CrudAction = "r") {
  const perms = useAuthStore((s) => s.user?.permissions_effective);
  const modules = useAuthStore((s) => s.user?.modules_effective);
  if (perms && perms[module]) return Boolean(perms[module][action]);
  // Fallback: module list only implies read
  if (modules?.includes(module)) return action === "r";
  return false;
}
