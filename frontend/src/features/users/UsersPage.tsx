import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Alert } from "@/components/ui/Alert";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuthStore } from "@/features/auth/store";
import { fetchMe } from "@/features/auth/api";

type UserRow = {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  role: string;
  status: string;
  modules: string[];
  modules_effective: string[];
};

type ModuleMeta = { key: string; label: string };
type ModulesCatalog = {
  modules: ModuleMeta[];
  role_defaults: Record<string, string[]>;
};

type Paginated<T> = { count: number; results: T[] };

const ROLES = [
  { value: "ADMIN", label: "Administrador" },
  { value: "VENTAS", label: "Ventas" },
  { value: "LOGISTICA", label: "Logística" },
  { value: "CONTABILIDAD", label: "Contabilidad" },
  { value: "SUPERVISOR", label: "Supervisor" },
  { value: "VIEWER", label: "Solo lectura" },
];

const emptyCreate = {
  full_name: "",
  email: "",
  password: "",
  role: "VIEWER",
};

export function UsersPage() {
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const currentId = useAuthStore((s) => s.user?.id);
  const [form, setForm] = useState(emptyCreate);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [editForm, setEditForm] = useState({
    full_name: "",
    phone: "",
    role: "VIEWER",
    status: "ACTIVE",
    password: "",
    modules: [] as string[],
    useCustomModules: false,
  });
  const [editError, setEditError] = useState<string | null>(null);
  const [editOk, setEditOk] = useState<string | null>(null);

  const users = useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<UserRow> | UserRow[]>("/users/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const catalog = useQuery({
    queryKey: ["auth", "modules"],
    queryFn: async () => {
      const { data } = await apiClient.get<ModulesCatalog>("/auth/modules/");
      return data;
    },
  });

  const createUser = useMutation({
    mutationFn: async () => {
      await apiClient.post("/users/", {
        ...form,
        status: "ACTIVE",
        modules: [],
      });
    },
    onSuccess: () => {
      setForm(emptyCreate);
      setError(null);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => setError("No se pudo crear el usuario. Revisa los datos."),
  });

  const updateUser = useMutation({
    mutationFn: async () => {
      if (!editing) return;
      const payload: Record<string, unknown> = {
        full_name: editForm.full_name,
        phone: editForm.phone,
        role: editForm.role,
        status: editForm.status,
        modules: editForm.useCustomModules ? editForm.modules : [],
      };
      if (editForm.password.trim()) {
        payload.password = editForm.password.trim();
      }
      await apiClient.patch(`/users/${editing.id}/`, payload);
    },
    onSuccess: async () => {
      setEditOk(
        editForm.password.trim()
          ? "Usuario actualizado (contraseña cambiada)."
          : "Usuario actualizado.",
      );
      setEditError(null);
      setEditForm((f) => ({ ...f, password: "" }));
      qc.invalidateQueries({ queryKey: ["users"] });
      if (editing && editing.id === currentId) {
        const me = await fetchMe();
        setUser(me);
      }
    },
    onError: () => {
      setEditOk(null);
      setEditError("No se pudo guardar. Revisa los datos.");
    },
  });

  useEffect(() => {
    if (!editing) return;
    const defaults = catalog.data?.role_defaults?.[editing.role] || [];
    const custom = (editing.modules || []).length > 0;
    setEditForm({
      full_name: editing.full_name,
      phone: editing.phone || "",
      role: editing.role,
      status: editing.status,
      password: "",
      modules: custom ? [...editing.modules] : [...defaults],
      useCustomModules: custom,
    });
    setEditError(null);
    setEditOk(null);
  }, [editing, catalog.data]);

  const columns = useMemo<ColumnDef<UserRow, unknown>[]>(
    () => [
      { accessorKey: "full_name", header: "Nombre" },
      { accessorKey: "email", header: "Email" },
      {
        accessorKey: "role",
        header: "Rol",
        cell: ({ getValue }) => {
          const v = String(getValue());
          const label = ROLES.find((r) => r.value === v)?.label || v;
          return <Badge variant="dark">{label}</Badge>;
        },
      },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ getValue }) => (
          <Badge variant={getValue() === "ACTIVE" ? "sage" : "terracotta"}>
            {String(getValue())}
          </Badge>
        ),
      },
      {
        id: "perms",
        header: "Permisos",
        cell: ({ row }) =>
          (row.original.modules || []).length > 0 ? (
            <Badge variant="terracotta">Personalizados</Badge>
          ) : (
            <Badge variant="sage">Por rol</Badge>
          ),
      },
      {
        id: "actions",
        header: "Acciones",
        cell: ({ row }) => (
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={() => setEditing(row.original)}
          >
            Rol / contraseña
          </Button>
        ),
      },
    ],
    [],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    createUser.mutate();
  }

  function onEditSubmit(e: FormEvent) {
    e.preventDefault();
    updateUser.mutate();
  }

  function toggleModule(key: string) {
    setEditForm((f) => {
      const has = f.modules.includes(key);
      return {
        ...f,
        modules: has ? f.modules.filter((m) => m !== key) : [...f.modules, key],
      };
    });
  }

  function applyRoleDefaults(role: string) {
    const defaults = catalog.data?.role_defaults?.[role] || [];
    setEditForm((f) => ({
      ...f,
      role,
      modules: [...defaults],
      useCustomModules: false,
    }));
  }

  return (
    <div className="space-y-3">
      <PageHeader eyebrow="Parametrización" title="Usuarios y roles" />

      <Alert variant="info">
        Para cambiar el rol o la contraseña de alguien: en la tabla de abajo pulsa{" "}
        <strong>Rol / contraseña</strong>. Solo visible si entras como ADMIN
        (menú → Parametrización → Usuarios y roles).
      </Alert>

      <Card>
        <p className="mb-3 label-caps text-text-muted">Crear usuario</p>
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <div>
            <FieldLabel>Nombre</FieldLabel>
            <Input
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              required
            />
          </div>
          <div>
            <FieldLabel>Email</FieldLabel>
            <Input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              required
            />
          </div>
          <div>
            <FieldLabel>Contraseña</FieldLabel>
            <Input
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              required
              minLength={8}
            />
          </div>
          <div>
            <FieldLabel>Rol</FieldLabel>
            <select
              className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <Button type="submit" className="w-full" disabled={createUser.isPending}>
              Crear
            </Button>
          </div>
        </form>
        {error ? (
          <Alert variant="error" className="mt-4">
            {error}
          </Alert>
        ) : null}
      </Card>

      {editing ? (
        <Card tone="cream">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <p className="label-caps text-text-muted">Rol, contraseña y permisos</p>
              <p className="mt-1 font-serif text-2xl text-green-900">{editing.email}</p>
            </div>
            <Button type="button" size="xs" variant="ghost" onClick={() => setEditing(null)}>
              Cerrar
            </Button>
          </div>

          <form onSubmit={onEditSubmit} className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <div>
                <FieldLabel>Nombre</FieldLabel>
                <Input
                  value={editForm.full_name}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, full_name: e.target.value }))
                  }
                  required
                />
              </div>
              <div>
                <FieldLabel>Teléfono</FieldLabel>
                <Input
                  value={editForm.phone}
                  onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                />
              </div>
              <div>
                <FieldLabel>Rol</FieldLabel>
                <select
                  className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
                  value={editForm.role}
                  onChange={(e) => applyRoleDefaults(e.target.value)}
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <FieldLabel>Estado</FieldLabel>
                <select
                  className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
                  value={editForm.status}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, status: e.target.value }))
                  }
                >
                  <option value="ACTIVE">Activo</option>
                  <option value="SUSPENDED">Suspendido</option>
                </select>
              </div>
            </div>

            <div className="max-w-md">
              <FieldLabel>Nueva contraseña</FieldLabel>
              <Input
                type="password"
                value={editForm.password}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, password: e.target.value }))
                }
                minLength={8}
                placeholder="Dejar vacío para no cambiar"
                autoComplete="new-password"
              />
              <p className="mt-1 text-xs text-text-muted">Mínimo 8 caracteres si la cambias.</p>
            </div>

            <div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="label-caps text-text-muted">Módulos visibles</p>
                  <p className="mt-1 text-sm text-text-muted">
                    Por defecto siguen el rol. Activa personalización para este usuario.
                  </p>
                </div>
                <label className="flex items-center gap-2 text-sm text-green-900">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-green-900"
                    checked={editForm.useCustomModules}
                    onChange={(e) => {
                      const on = e.target.checked;
                      setEditForm((f) => ({
                        ...f,
                        useCustomModules: on,
                        modules: on
                          ? f.modules.length
                            ? f.modules
                            : catalog.data?.role_defaults?.[f.role] || []
                          : catalog.data?.role_defaults?.[f.role] || [],
                      }));
                    }}
                  />
                  Personalizar permisos
                </label>
              </div>

              <div
                className={`grid gap-2 sm:grid-cols-2 lg:grid-cols-3 ${
                  editForm.useCustomModules ? "" : "opacity-60"
                }`}
              >
                {(catalog.data?.modules || []).map((m) => (
                  <label
                    key={m.key}
                    className="flex items-center gap-2 rounded-[14px] border border-line bg-warm-white/80 px-3 py-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-green-900"
                      disabled={!editForm.useCustomModules}
                      checked={editForm.modules.includes(m.key)}
                      onChange={() => toggleModule(m.key)}
                    />
                    {m.label}
                  </label>
                ))}
              </div>
            </div>

            {editError ? (
              <Alert variant="error">{editError}</Alert>
            ) : null}
            {editOk ? <Alert variant="success">{editOk}</Alert> : null}

            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={updateUser.isPending}>
                {updateUser.isPending ? "Guardando…" : "Guardar cambios"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setEditing(null)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <DataTable
        data={users.data || []}
        columns={columns}
        searchableKeys={["full_name", "email", "role", "status"]}
        emptyTitle="Aún no hay usuarios"
        emptyDescription="Crea el primero con el formulario de arriba."
      />
    </div>
  );
}
