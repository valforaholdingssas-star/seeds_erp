import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { fetchMe } from "@/features/auth/api";
import { useAuthStore } from "@/features/auth/store";

type ModuleMeta = { key: string; label: string };
type CrudMeta = { key: "c" | "r" | "u" | "d"; label: string };
type CrudFlags = { c: boolean; r: boolean; u: boolean; d: boolean };
type RolePerms = Record<string, Record<string, CrudFlags>>;

type Payload = {
  modules: ModuleMeta[];
  crud: CrudMeta[];
  role_defaults: Record<string, string[]>;
  role_permissions: RolePerms;
  detail?: string;
};

const ROLE_LABELS: Record<string, string> = {
  ADMIN: "Administrador",
  VENTAS: "Ventas",
  LOGISTICA: "Logística",
  CONTABILIDAD: "Contabilidad",
  SUPERVISOR: "Supervisor",
  VIEWER: "Solo lectura",
};

const ADMIN_LOCKED = new Set(["home", "users", "roles"]);
const EMPTY: CrudFlags = { c: false, r: false, u: false, d: false };
const FULL: CrudFlags = { c: true, r: true, u: true, d: true };

function flagsOrEmpty(f?: CrudFlags): CrudFlags {
  return f ? { c: !!f.c, r: !!f.r, u: !!f.u, d: !!f.d } : { ...EMPTY };
}

export function RolesPage() {
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const [activeRole, setActiveRole] = useState("VENTAS");
  const [draft, setDraft] = useState<RolePerms>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const data = useQuery({
    queryKey: ["auth", "role-permissions"],
    queryFn: async () => {
      const { data: res } = await apiClient.get<Payload>("/auth/role-permissions/");
      return res;
    },
  });

  useEffect(() => {
    if (data.data?.role_permissions) {
      setDraft(
        Object.fromEntries(
          Object.entries(data.data.role_permissions).map(([role, mods]) => [
            role,
            Object.fromEntries(
              Object.entries(mods).map(([m, f]) => [m, flagsOrEmpty(f)]),
            ),
          ]),
        ),
      );
    }
  }, [data.data]);

  const roles = useMemo(() => Object.keys(ROLE_LABELS), []);
  const modules = data.data?.modules || [];
  const crudKeys = data.data?.crud || [
    { key: "c" as const, label: "Crear" },
    { key: "r" as const, label: "Ver" },
    { key: "u" as const, label: "Editar" },
    { key: "d" as const, label: "Eliminar" },
  ];

  const save = useMutation({
    mutationFn: async () => {
      const { data: res } = await apiClient.put<Payload>(
        "/auth/role-permissions/",
        { role_permissions: draft },
      );
      return res;
    },
    onSuccess: async (res) => {
      setMessage(
        res.detail ||
          "Permisos CRUD guardados. Se propagan a todos los usuarios del rol (sin override personal).",
      );
      setError(null);
      if (res.role_permissions) setDraft(res.role_permissions);
      qc.invalidateQueries({ queryKey: ["auth", "role-permissions"] });
      qc.invalidateQueries({ queryKey: ["auth", "modules"] });
      const me = await fetchMe();
      setUser(me);
    },
    onError: () => {
      setMessage(null);
      setError("No se pudo guardar la matriz CRUD.");
    },
  });

  function toggle(moduleKey: string, letter: keyof CrudFlags) {
    if (activeRole === "ADMIN" && ADMIN_LOCKED.has(moduleKey)) return;
    setDraft((prev) => {
      const roleMap = { ...(prev[activeRole] || {}) };
      const current = flagsOrEmpty(roleMap[moduleKey]);
      const next = { ...current, [letter]: !current[letter] };
      // Ver is required if any write is on
      if ((next.c || next.u || next.d) && !next.r) next.r = true;
      if (next.c || next.r || next.u || next.d) {
        roleMap[moduleKey] = next;
      } else {
        delete roleMap[moduleKey];
      }
      if (!roleMap.home) roleMap.home = { ...EMPTY, r: true };
      return { ...prev, [activeRole]: roleMap };
    });
  }

  function setModuleAll(moduleKey: string, on: boolean) {
    if (activeRole === "ADMIN" && ADMIN_LOCKED.has(moduleKey)) return;
    setDraft((prev) => {
      const roleMap = { ...(prev[activeRole] || {}) };
      if (on) roleMap[moduleKey] = { ...FULL };
      else delete roleMap[moduleKey];
      if (!roleMap.home) roleMap.home = { ...EMPTY, r: true };
      return { ...prev, [activeRole]: roleMap };
    });
  }

  function resetRole() {
    const original = data.data?.role_permissions?.[activeRole] || {};
    setDraft((prev) => ({
      ...prev,
      [activeRole]: Object.fromEntries(
        Object.entries(original).map(([m, f]) => [m, flagsOrEmpty(f)]),
      ),
    }));
  }

  const roleMap = draft[activeRole] || {};

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Parametrización"
        title="Roles · permisos CRUD"
        actions={
          <Button
            type="button"
            size="sm"
            disabled={save.isPending || data.isLoading}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Guardando…" : "Guardar roles"}
          </Button>
        }
      />

      <Alert variant="info">
        Define <strong>Crear / Ver / Editar / Eliminar</strong> por módulo y rol. Al
        guardar se aplica a <strong>todos</strong> los usuarios de ese rol (salvo
        override en{" "}
        <Link to="/users" className="underline underline-offset-2">
          Usuarios
        </Link>
        ). La API también valida estos permisos.
      </Alert>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {message ? <Alert variant="success">{message}</Alert> : null}

      <div className="flex flex-wrap gap-2">
        {roles.map((role) => (
          <Button
            key={role}
            type="button"
            size="xs"
            variant={activeRole === role ? "primary-dark" : "outline"}
            onClick={() => setActiveRole(role)}
          >
            {ROLE_LABELS[role]}
          </Button>
        ))}
        <Button type="button" size="xs" variant="ghost" onClick={resetRole}>
          Restablecer rol
        </Button>
      </div>

      <Card className="overflow-x-auto">
        {data.isLoading ? (
          <p className="text-sm text-text-muted">Cargando matriz…</p>
        ) : (
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="sticky left-0 bg-warm-white px-3 py-3 label-caps text-text-muted">
                  Módulo
                </th>
                {crudKeys.map((c) => (
                  <th key={c.key} className="px-3 py-3 text-center label-caps text-text-muted">
                    {c.label}
                  </th>
                ))}
                <th className="px-3 py-3 text-center label-caps text-text-muted">Todo</th>
              </tr>
            </thead>
            <tbody>
              {modules.map((mod) => {
                const flags = flagsOrEmpty(roleMap[mod.key]);
                const locked = activeRole === "ADMIN" && ADMIN_LOCKED.has(mod.key);
                const allOn = flags.c && flags.r && flags.u && flags.d;
                return (
                  <tr key={mod.key} className="border-b border-line/60">
                    <td className="sticky left-0 bg-warm-white px-3 py-2.5 font-medium text-green-900">
                      {mod.label}
                      {locked ? (
                        <span className="ml-2 text-[10px] text-text-soft">(obligatorio)</span>
                      ) : null}
                    </td>
                    {crudKeys.map((c) => (
                      <td key={c.key} className="px-3 py-2 text-center">
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-green-900"
                          checked={flags[c.key]}
                          disabled={locked}
                          onChange={() => toggle(mod.key, c.key)}
                        />
                      </td>
                    ))}
                    <td className="px-3 py-2 text-center">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-green-900"
                        checked={allOn}
                        disabled={locked}
                        onChange={() => setModuleAll(mod.key, !allOn)}
                        title="Marcar / desmarcar CRUD completo"
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
