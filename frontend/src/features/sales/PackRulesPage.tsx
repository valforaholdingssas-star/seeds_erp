import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, type FormEvent } from "react";
import { Pencil, Plus } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";

type PackRule = {
  id: string;
  woo_product_id: string;
  name_contains: string;
  multiplier: number;
  active: boolean;
};

type Paginated<T> = { count: number; results: T[] };

const empty = {
  woo_product_id: "",
  name_contains: "",
  multiplier: "3",
  active: true,
};

export function PackRulesPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(empty);

  const rules = useQuery({
    queryKey: ["pack-rules"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<PackRule> | PackRule[]>("/pack-rules/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        woo_product_id: form.woo_product_id.trim(),
        name_contains: form.name_contains.trim(),
        multiplier: Number(form.multiplier) || 1,
        active: form.active,
      };
      if (editingId) {
        await apiClient.patch(`/pack-rules/${editingId}/`, payload);
      } else {
        await apiClient.post("/pack-rules/", payload);
      }
    },
    onSuccess: () => {
      setError(null);
      setOpen(false);
      setEditingId(null);
      setForm(empty);
      qc.invalidateQueries({ queryKey: ["pack-rules"] });
    },
    onError: () => setError("No se pudo guardar. Revisa woo_product_id único."),
  });

  const columns = useMemo<ColumnDef<PackRule, unknown>[]>(
    () => [
      {
        accessorKey: "woo_product_id",
        header: "Woo ID",
        cell: ({ getValue }) => String(getValue() || "—"),
      },
      {
        accessorKey: "name_contains",
        header: "Nombre contiene",
        cell: ({ getValue }) => String(getValue() || "—"),
      },
      {
        accessorKey: "multiplier",
        header: "×",
        cell: ({ getValue }) => <Badge variant="dark">×{String(getValue())}</Badge>,
      },
      {
        accessorKey: "active",
        header: "Estado",
        cell: ({ getValue }) =>
          getValue() ? <Badge variant="sage">Activa</Badge> : <Badge variant="wine">Off</Badge>,
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <button
            type="button"
            title="Editar"
            onClick={() => {
              const r = row.original;
              setEditingId(r.id);
              setForm({
                woo_product_id: r.woo_product_id,
                name_contains: r.name_contains,
                multiplier: String(r.multiplier),
                active: r.active,
              });
              setOpen(true);
            }}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line text-green-900 hover:bg-cream-100"
          >
            <Pencil strokeWidth={1.5} className="h-3.5 w-3.5" />
          </button>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Parámetros"
        title="Pack rules"
        actions={
          <>
            <Button
              type="button"
              size="xs"
              onClick={() => {
                setEditingId(null);
                setForm(empty);
                setOpen(true);
              }}
            >
              <Plus strokeWidth={1.5} className="h-3.5 w-3.5" />
              Nueva regla
            </Button>
          </>
        }
      />

      {open ? (
        <Card>
          <h2 className="font-serif text-2xl text-green-900">
            {editingId ? "Editar regla" : "Nueva regla"}
          </h2>
          <form
            className="mt-4 grid gap-4 md:grid-cols-2"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <div>
              <FieldLabel>Woo product ID</FieldLabel>
              <Input
                value={form.woo_product_id}
                onChange={(e) => setForm((f) => ({ ...f, woo_product_id: e.target.value }))}
                placeholder="602"
              />
            </div>
            <div>
              <FieldLabel>Nombre contiene</FieldLabel>
              <Input
                value={form.name_contains}
                onChange={(e) => setForm((f) => ({ ...f, name_contains: e.target.value }))}
                placeholder="3 kits"
              />
            </div>
            <div>
              <FieldLabel>Multiplicador</FieldLabel>
              <Input
                required
                type="number"
                min={1}
                value={form.multiplier}
                onChange={(e) => setForm((f) => ({ ...f, multiplier: e.target.value }))}
              />
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))}
                />
                Activa
              </label>
            </div>
            <div className="flex gap-2 md:col-span-2">
              <Button type="submit" disabled={save.isPending}>
                Guardar
              </Button>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      {error ? <Alert variant="error">{error}</Alert> : null}

      <DataTable
        data={rules.data || []}
        columns={columns}
        searchableKeys={["woo_product_id", "name_contains"]}
        columnFilters={[
          {
            key: "active",
            label: "Activa",
            type: "select",
            options: ["true", "false"],
          },
        ]}
        exportFilename="pack-rules.csv"
        emptyTitle="Sin reglas"
        emptyDescription="El seed crea la regla 602 ×3; puedes añadir más aquí."
      />
    </div>
  );
}
