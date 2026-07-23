import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Pencil, Plus } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";

type Material = {
  id: string;
  sku: string;
  name: string;
  unit: string;
  stock: string;
  reorder_level: string;
  active: boolean;
  low_stock: boolean;
};

type Paginated<T> = { count: number; results: T[] };

const emptyForm = {
  sku: "",
  name: "",
  unit: "u",
  reorder_level: "0",
  active: true,
};

export function MaterialsPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [entry, setEntry] = useState({
    material_id: "",
    movement: "IN",
    quantity: "10",
    notes: "",
  });

  const materials = useQuery({
    queryKey: ["materials"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Material> | Material[]>(
        "/inventory/materials/",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        sku: form.sku.trim(),
        name: form.name.trim(),
        unit: form.unit.trim() || "u",
        reorder_level: form.reorder_level || "0",
        active: form.active,
      };
      if (editingId) {
        await apiClient.patch(`/inventory/materials/${editingId}/`, payload);
      } else {
        await apiClient.post("/inventory/materials/", payload);
      }
    },
    onSuccess: () => {
      setError(null);
      setFormOpen(false);
      setEditingId(null);
      setForm(emptyForm);
      qc.invalidateQueries({ queryKey: ["materials"] });
    },
    onError: () => setError("No se pudo guardar el material."),
  });

  const createEntry = useMutation({
    mutationFn: async () => {
      await apiClient.post("/inventory/entries/", {
        material_id: entry.material_id,
        movement: entry.movement,
        quantity: entry.quantity,
        reason: entry.movement === "IN" ? "PURCHASE" : "MANUAL_ADJUST",
        notes: entry.notes,
      });
    },
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["materials"] });
      qc.invalidateQueries({ queryKey: ["kardex"] });
    },
    onError: () => setError("No se pudo registrar el movimiento."),
  });

  function openEdit(m: Material) {
    setEditingId(m.id);
    setForm({
      sku: m.sku,
      name: m.name,
      unit: m.unit,
      reorder_level: String(m.reorder_level ?? "0"),
      active: m.active,
    });
    setFormOpen(true);
  }

  const columns = useMemo<ColumnDef<Material, unknown>[]>(
    () => [
      { accessorKey: "sku", header: "SKU" },
      { accessorKey: "name", header: "Nombre" },
      { accessorKey: "unit", header: "Unidad" },
      {
        accessorKey: "stock",
        header: "Stock",
        cell: ({ row }) => (
          <span className={row.original.low_stock ? "font-medium text-terracotta-600" : ""}>
            {row.original.stock}
          </span>
        ),
      },
      { accessorKey: "reorder_level", header: "Mínimo" },
      {
        id: "flags",
        header: "",
        cell: ({ row }) => (
          <div className="flex gap-1">
            {row.original.low_stock ? <Badge variant="terracotta">Bajo</Badge> : null}
            {!row.original.active ? <Badge variant="wine">Inactivo</Badge> : null}
          </div>
        ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <button
            type="button"
            title="Editar"
            onClick={() => openEdit(row.original)}
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
        eyebrow="Inventario"
        title="Materiales"
        actions={
          <>
            <Link
              to="/inventory"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps text-green-900 hover:bg-cream-100"
            >
              Productos
            </Link>
            <Button
              type="button"
              size="xs"
              onClick={() => {
                setEditingId(null);
                setForm(emptyForm);
                setFormOpen(true);
              }}
            >
              <Plus strokeWidth={1.5} className="h-3.5 w-3.5" />
              Nuevo
            </Button>
          </>
        }
      />

      {formOpen ? (
        <Card>
          <h2 className="font-serif text-2xl text-green-900">
            {editingId ? "Editar material" : "Nuevo material"}
          </h2>
          <form
            className="mt-4 grid gap-4 md:grid-cols-3"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <div>
              <FieldLabel>SKU</FieldLabel>
              <Input
                required
                value={form.sku}
                disabled={!!editingId}
                onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))}
              />
            </div>
            <div className="md:col-span-2">
              <FieldLabel>Nombre</FieldLabel>
              <Input
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div>
              <FieldLabel>Unidad</FieldLabel>
              <Input
                value={form.unit}
                onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))}
              />
            </div>
            <div>
              <FieldLabel>Stock mínimo</FieldLabel>
              <Input
                type="number"
                step="0.001"
                value={form.reorder_level}
                onChange={(e) => setForm((f) => ({ ...f, reorder_level: e.target.value }))}
              />
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))}
                />
                Activo
              </label>
            </div>
            <div className="flex gap-2 md:col-span-3">
              <Button type="submit" disabled={save.isPending}>
                {editingId ? "Guardar" : "Crear"}
              </Button>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <h2 className="mb-4 font-serif text-xl text-green-900">Movimiento manual</h2>
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            createEntry.mutate();
          }}
          className="grid gap-4 md:grid-cols-5"
        >
          <div className="md:col-span-2">
            <FieldLabel>Material</FieldLabel>
            <select
              required
              className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
              value={entry.material_id}
              onChange={(e) => setEntry((f) => ({ ...f, material_id: e.target.value }))}
            >
              <option value="">Selecciona…</option>
              {(materials.data || []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.sku} · {m.name} ({m.stock} {m.unit})
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel>Movimiento</FieldLabel>
            <select
              className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
              value={entry.movement}
              onChange={(e) => setEntry((f) => ({ ...f, movement: e.target.value }))}
            >
              <option value="IN">Entrada</option>
              <option value="OUT">Salida</option>
              <option value="ADJUST">Ajuste (+/−)</option>
            </select>
          </div>
          <div>
            <FieldLabel>Cantidad</FieldLabel>
            <Input
              required
              type="number"
              step="0.001"
              value={entry.quantity}
              onChange={(e) => setEntry((f) => ({ ...f, quantity: e.target.value }))}
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" className="w-full" disabled={createEntry.isPending}>
              Registrar
            </Button>
          </div>
        </form>
      </Card>

      {error ? <Alert variant="error">{error}</Alert> : null}

      <DataTable
        data={materials.data || []}
        columns={columns}
        searchableKeys={["sku", "name", "unit"]}
        columnFilters={[
          {
            key: "active",
            label: "Activo",
            type: "select",
            options: ["true", "false"],
          },
          {
            key: "low_stock",
            label: "Bajo stock",
            type: "select",
            options: ["true", "false"],
          },
        ]}
        exportFilename="materiales.csv"
        emptyTitle="Sin materiales"
        emptyDescription="Crea cajas, stickers u otros insumos de bodega."
      />
    </div>
  );
}
