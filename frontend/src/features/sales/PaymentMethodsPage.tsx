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

type PaymentMethod = {
  id: string;
  name: string;
  active: boolean;
  aliases: string[];
  is_system: boolean;
};

type Paginated<T> = { count: number; results: T[] };

export function PaymentMethodsPage() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: "", aliases: "", active: true });
  const [editing, setEditing] = useState<PaymentMethod | null>(null);
  const [error, setError] = useState<string | null>(null);

  const methods = useQuery({
    queryKey: ["payment-methods"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<PaymentMethod> | PaymentMethod[]>(
        "/payment-methods/",
      );
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
      };
      if (editing) {
        await apiClient.patch(`/payment-methods/${editing.id}/`, payload);
      } else {
        await apiClient.post("/payment-methods/", payload);
      }
    },
    onSuccess: () => {
      setForm({ name: "", aliases: "", active: true });
      setEditing(null);
      setError(null);
      qc.invalidateQueries({ queryKey: ["payment-methods"] });
    },
    onError: () => setError("No se pudo guardar. ¿Nombre duplicado?"),
  });

  const remove = useMutation({
    mutationFn: async (m: PaymentMethod) => {
      await apiClient.delete(`/payment-methods/${m.id}/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payment-methods"] }),
    onError: () =>
      setError("No se pudo eliminar. Desactívalo si está en uso o es de sistema."),
  });

  const columns = useMemo<ColumnDef<PaymentMethod, unknown>[]>(
    () => [
      { accessorKey: "name", header: "Nombre" },
      {
        accessorKey: "aliases",
        header: "Alias",
        cell: ({ row }) =>
          row.original.aliases?.length ? row.original.aliases.join(", ") : "—",
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
        accessorKey: "is_system",
        header: "Tipo",
        cell: ({ row }) =>
          row.original.is_system ? (
            <Badge variant="dark">Sistema</Badge>
          ) : (
            <Badge variant="sage">Custom</Badge>
          ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                const m = row.original;
                setEditing(m);
                setForm({
                  name: m.name,
                  aliases: (m.aliases || []).join(", "),
                  active: m.active,
                });
              }}
            >
              Editar
            </Button>
            {!row.original.is_system ? (
              <Button
                type="button"
                size="sm"
                variant="primary-wine"
                onClick={() => remove.mutate(row.original)}
              >
                Eliminar
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [remove],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="label-caps text-text-muted">Parametrización</p>
        <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">
          Medios de pago
        </h1>
        <p className="mt-2 max-w-2xl text-text-muted">
          Nutren el desplegable de ventas. Si renombras uno, el cambio se propaga a las
          compras asociadas.
        </p>
        <div className="seeds-divider mt-4 max-w-sm">✦</div>
      </header>

      {error ? <Alert variant="error">{error}</Alert> : null}

      <Card className="seeds-panel">
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-4">
          <div className="md:col-span-2">
            <FieldLabel>Nombre</FieldLabel>
            <Input
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Nequi"
            />
          </div>
          <div>
            <FieldLabel>Alias (coma)</FieldLabel>
            <Input
              value={form.aliases}
              onChange={(e) => setForm((f) => ({ ...f, aliases: e.target.value }))}
              placeholder="nequi, Nequi CO"
            />
          </div>
          <div className="flex items-end gap-3">
            <label className="flex items-center gap-2 text-sm text-text-muted">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))}
                className="accent-green-900"
              />
              Activo
            </label>
            <Button type="submit" disabled={save.isPending}>
              {editing ? "Actualizar" : "Crear"}
            </Button>
            {editing ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setEditing(null);
                  setForm({ name: "", aliases: "", active: true });
                }}
              >
                Cancelar
              </Button>
            ) : null}
          </div>
        </form>
      </Card>

      <DataTable
        data={methods.data || []}
        columns={columns}
        searchableKeys={["name"]}
        emptyTitle="Sin medios de pago"
        emptyDescription="Crea Nequi, Efectivo u otros para el desplegable."
      />
    </div>
  );
}
