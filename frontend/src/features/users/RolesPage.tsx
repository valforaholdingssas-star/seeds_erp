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
type RoleMap = Record<string, string[]>;

type Payload = {
  modules: ModuleMeta[];
  role_defaults: RoleMap;
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

export function RolesPage() {
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const [draft, setDraft] = useState<RoleMap>({});
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
    if (data.data?.role_defaults) {
      setDraft(
        Object.fromEntries(
          Object.entries(data.data.role_defaults).map(([role, mods]) => [
            role,
            [...mods],
          ]),
        ),
      );
    }
  }, [data.data]);

  const roles = useMemo(
    () => Object.keys(ROLE_LABELS).filter((r) => draft[r] || data.data?.role_defaults?.[r]),
    [draft, data.data],
  );

  const modules = data.data?.modules || [];

  const save = useMutation({
    mutationFn: async () => {
      const { data: res } = await apiClient.put<Payload & { detail: string }>(
        "/auth/role-permissions/",
        { role_defaults: draft },
      );
      return res;
    },
    onSuccess: async (res) => {
      setMessage(
        res.detail ||
          "Roles actualizados. Los usuarios sin permisos personalizados heredan estos módulos.",
      );
      setError(null);
      setDraft(res.role_defaults);
      qc.invalidateQueries({ queryKey: ["auth", "role-permissions"] });
      qc.invalidateQueries({ queryKey: ["auth", "modules"] });
      const me = await fetchMe();
      setUser(me);
    },
    onError: () => {
      setMessage(null);
      setError("No se pudo guardar la matriz de roles.");
    },
  });

  function toggle(role: string, moduleKey: string) {
    if (role === "ADMIN" && ADMIN_LOCKED.has(moduleKey)) return;
    setDraft((prev) => {
      const current = new Set(prev[role] || []);
      if (current.has(moduleKey)) current.delete(moduleKey);
      else current.add(moduleKey);
      if (!current.has("home")) current.add("home");
      return { ...prev, [role]: Array.from(current) };
    });
  }

  function resetRole(role: string) {
    const original = data.data?.role_defaults?.[role] || ["home"];
    setDraft((prev) => ({ ...prev, [role]: [...original] }));
  }

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Parametrización"
        title="Roles"
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
        Aquí defines qué módulos ve cada <strong>rol</strong>. Al guardar, se aplica a{" "}
        <strong>todos</strong> los usuarios de ese rol (salvo quienes tengan permisos
        personalizados en{" "}
        <Link to="/users" className="underline underline-offset-2">
          Usuarios
        </Link>
        ).
      </Alert>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {message ? <Alert variant="success">{message}</Alert> : null}

      <Card className="overflow-x-auto">
        {data.isLoading ? (
          <p className="text-sm text-text-muted">Cargando matriz…</p>
        ) : (
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="sticky left-0 bg-warm-white px-3 py-3 label-caps text-text-muted">
                  Módulo
                </th>
                {roles.map((role) => (
                  <th key={role} className="px-3 py-3 text-center">
                    <p className="label-caps text-text-muted">{ROLE_LABELS[role] || role}</p>
                    <button
                      type="button"
                      className="mt-1 text-[10px] text-text-soft underline-offset-2 hover:underline"
                      onClick={() => resetRole(role)}
                    >
                      Restablecer
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {modules.map((mod) => (
                <tr key={mod.key} className="border-b border-line/60">
                  <td className="sticky left-0 bg-warm-white px-3 py-2.5 font-medium text-green-900">
                    {mod.label}
                  </td>
                  {roles.map((role) => {
                    const checked = (draft[role] || []).includes(mod.key);
                    const locked = role === "ADMIN" && ADMIN_LOCKED.has(mod.key);
                    return (
                      <td key={`${role}-${mod.key}`} className="px-3 py-2 text-center">
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-green-900"
                          checked={checked}
                          disabled={locked}
                          title={
                            locked
                              ? "Obligatorio para ADMIN (evita quedarte sin acceso)"
                              : undefined
                          }
                          onChange={() => toggle(role, mod.key)}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
