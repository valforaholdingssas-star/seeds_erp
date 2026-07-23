import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, type FormEvent } from "react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";

type Seller = {
  id: string;
  name: string;
  user: string | null;
  user_detail: { id: string; full_name: string; email: string } | null;
  is_system: boolean;
  active: boolean;
  aliases: string[];
  needs_review: boolean;
  monthly_goal: string | null;
};

type Paginated<T> = { count: number; results: T[] };
type UserOption = { id: string; full_name: string; email: string };

export function SellersPage() {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    aliases: "",
    user: "",
    active: true,
    monthly_goal: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Seller | null>(null);

  const sellers = useQuery({
    queryKey: ["sellers"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Seller> | Seller[]>("/sellers/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const users = useQuery({
    queryKey: ["users-options"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<UserOption> | UserOption[]>("/users/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name.trim(),
        aliases: form.aliases
          .split(",")
          .map((a) => a.trim())
          .filter(Boolean),
        active: form.active,
        user: form.user || null,
        is_system: false,
        needs_review: false,
        monthly_goal: form.monthly_goal ? form.monthly_goal : null,
      };
      if (editing) {
        await apiClient.patch(`/sellers/${editing.id}/`, payload);
      } else {
        await apiClient.post("/sellers/", payload);
      }
    },
    onSuccess: () => {
      setForm({ name: "", aliases: "", user: "", active: true, monthly_goal: "" });
      setEditing(null);
      setError(null);
      qc.invalidateQueries({ queryKey: ["sellers"] });
    },
    onError: () => setError("No se pudo guardar el vendedor. Revisa el nombre y los alias."),
  });

  const toggleActive = useMutation({
    mutationFn: async (seller: Seller) => {
      await apiClient.patch(`/sellers/${seller.id}/`, { active: !seller.active });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sellers"] }),
  });

  const remove = useMutation({
    mutationFn: async (seller: Seller) => {
      await apiClient.delete(`/sellers/${seller.id}/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sellers"] }),
    onError: () => setError("No se pudo eliminar. Los vendedores de sistema están protegidos."),
  });

  const columns = useMemo<ColumnDef<Seller, unknown>[]>(
    () => [
      { accessorKey: "name", header: "Nombre" },
      {
        accessorKey: "aliases",
        header: "Alias",
        cell: ({ getValue }) => {
          const aliases = (getValue() as string[]) || [];
          return aliases.length ? aliases.join(", ") : "—";
        },
      },
      {
        id: "user",
        header: "Usuario",
        cell: ({ row }) => row.original.user_detail?.full_name || "Sin vincular",
      },
      {
        accessorKey: "is_system",
        header: "Tipo",
        cell: ({ row }) =>
          row.original.is_system ? (
            <Badge variant="dark">Sistema</Badge>
          ) : row.original.needs_review ? (
            <Badge variant="terracotta">Por revisar</Badge>
          ) : (
            <Badge variant="sage">Comercial</Badge>
          ),
      },
      {
        accessorKey: "monthly_goal",
        header: "Meta mes",
        cell: ({ row }) =>
          row.original.monthly_goal
            ? Number(row.original.monthly_goal).toLocaleString("es-CO")
            : "—",
      },
      {
        accessorKey: "active",
        header: "Estado",
        cell: ({ row }) => (
          <Badge variant={row.original.active ? "sage" : "terracotta"}>
            {row.original.active ? "Activo" : "Inactivo"}
          </Badge>
        ),
      },
      {
        id: "actions",
        header: "Acciones",
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                const s = row.original;
                setEditing(s);
                setForm({
                  name: s.name,
                  aliases: (s.aliases || []).join(", "),
                  user: s.user || "",
                  active: s.active,
                  monthly_goal: s.monthly_goal || "",
                });
              }}
            >
              Editar
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => toggleActive.mutate(row.original)}
            >
              {row.original.active ? "Desactivar" : "Activar"}
            </Button>
            {!row.original.is_system ? (
              <Button
                type="button"
                variant="primary-wine"
                size="sm"
                onClick={() => remove.mutate(row.original)}
              >
                Eliminar
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [remove, toggleActive],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <div className="space-y-3">
      <PageHeader eyebrow="Comercial" title="Vendedores" />

      <Card>
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <div>
            <FieldLabel>Nombre</FieldLabel>
            <Input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
              disabled={Boolean(editing?.is_system)}
              placeholder="VENDEDORA 1"
            />
          </div>
          <div>
            <FieldLabel>Meta mensual (COP)</FieldLabel>
            <Input
              value={form.monthly_goal}
              onChange={(e) => setForm((f) => ({ ...f, monthly_goal: e.target.value }))}
              placeholder="50000000"
            />
          </div>
          <div>
            <FieldLabel>Alias (separados por coma)</FieldLabel>
            <Input
              value={form.aliases}
              onChange={(e) => setForm((f) => ({ ...f, aliases: e.target.value }))}
              placeholder="Marina, Maji"
            />
          </div>
          <div>
            <FieldLabel>Usuario vinculado</FieldLabel>
            <select
              className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
              value={form.user}
              onChange={(e) => setForm((f) => ({ ...f, user: e.target.value }))}
              disabled={Boolean(editing?.is_system)}
            >
              <option value="">Sin vincular</option>
              {(users.data || []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name} · {u.email}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end gap-3">
            <label className="flex items-center gap-2 text-sm text-text-muted">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))}
                className="h-4 w-4 accent-green-900"
              />
              Activo
            </label>
          </div>
          <div className="flex items-end gap-2">
            {editing ? (
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={() => {
                  setEditing(null);
                  setForm({ name: "", aliases: "", user: "", active: true, monthly_goal: "" });
                }}
              >
                Cancelar
              </Button>
            ) : null}
            <Button type="submit" className="w-full" disabled={save.isPending}>
              {editing ? "Guardar" : "Crear"}
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
        data={sellers.data || []}
        columns={columns}
        searchableKeys={["name"]}
        emptyTitle="Sin vendedores"
        emptyDescription="Crea el primero o espera el seed de sistema al arrancar el API."
      />
    </div>
  );
}
