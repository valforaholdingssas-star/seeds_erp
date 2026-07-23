import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, type FormEvent } from "react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Alert } from "@/components/ui/Alert";

type UserRow = {
  id: string;
  full_name: string;
  email: string;
  role: string;
  status: string;
  phone: string;
};

type Paginated<T> = { count: number; results: T[] };

export function UsersPage() {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    role: "VIEWER",
  });
  const [error, setError] = useState<string | null>(null);

  const users = useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<UserRow> | UserRow[]>("/users/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const createUser = useMutation({
    mutationFn: async () => {
      await apiClient.post("/users/", {
        ...form,
        status: "ACTIVE",
      });
    },
    onSuccess: () => {
      setForm({ full_name: "", email: "", password: "", role: "VIEWER" });
      setError(null);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => setError("No se pudo crear el usuario. Revisa los datos."),
  });

  const columns = useMemo<ColumnDef<UserRow, unknown>[]>(
    () => [
      {
        id: "select",
        header: "",
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
            className="h-4 w-4 accent-green-900"
          />
        ),
      },
      { accessorKey: "full_name", header: "Nombre" },
      { accessorKey: "email", header: "Email" },
      {
        accessorKey: "role",
        header: "Rol",
        cell: ({ getValue }) => <Badge variant="dark">{String(getValue())}</Badge>,
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
    ],
    [],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    createUser.mutate();
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="label-caps text-text-muted">Usuarios y roles</p>
        <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">Equipo</h1>
        <p className="mt-2 max-w-xl text-text-muted">
          Administra quién acompaña cada módulo. Solo ADMIN puede crear o editar.
        </p>
      </header>

      <Card>
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-1">
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
              {["ADMIN", "VENTAS", "LOGISTICA", "CONTABILIDAD", "SUPERVISOR", "VIEWER"].map(
                (r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ),
              )}
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
