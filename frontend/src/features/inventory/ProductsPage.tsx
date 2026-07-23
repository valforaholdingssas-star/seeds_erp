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
import { KIT_TYPES, kitTypeLabel } from "@/lib/kitTypes";

type Product = {
  id: string;
  sku: string;
  name: string;
  color: string;
  tipo: string;
  woo_product_id: string;
  stock: number;
  reorder_level: number;
  active: boolean;
  is_generic: boolean;
  low_stock: boolean;
};

type Paginated<T> = { count: number; results: T[] };

const emptyForm = {
  sku: "",
  name: "",
  color: "DORADO",
  tipo: "",
  woo_product_id: "",
  reorder_level: "5",
  is_generic: false,
  active: true,
};

export function ProductsPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [entry, setEntry] = useState({
    product_id: "",
    movement: "IN",
    quantity: "10",
    notes: "",
  });

  const products = useQuery({
    queryKey: ["products"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Product> | Product[]>(
        "/inventory/products/",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const alerts = useQuery({
    queryKey: ["products-alerts"],
    queryFn: async () => {
      const { data } = await apiClient.get<Product[]>("/inventory/products/alerts/");
      return data;
    },
  });

  const saveProduct = useMutation({
    mutationFn: async () => {
      const payload = {
        sku: form.sku.trim(),
        name: form.name.trim(),
        color: form.color,
        tipo: form.tipo.trim(),
        woo_product_id: form.woo_product_id.trim(),
        reorder_level: Number(form.reorder_level) || 0,
        is_generic: form.is_generic,
        active: form.active,
      };
      if (editingId) {
        await apiClient.patch(`/inventory/products/${editingId}/`, payload);
      } else {
        await apiClient.post("/inventory/products/", payload);
      }
    },
    onSuccess: () => {
      setError(null);
      setFormOpen(false);
      setEditingId(null);
      setForm(emptyForm);
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["products-alerts"] });
    },
    onError: () => setError("No se pudo guardar el producto (¿SKU duplicado?)."),
  });

  const createEntry = useMutation({
    mutationFn: async () => {
      await apiClient.post("/inventory/entries/", {
        product_id: entry.product_id,
        movement: entry.movement,
        quantity: entry.quantity,
        reason: entry.movement === "IN" ? "PURCHASE" : "MANUAL_ADJUST",
        notes: entry.notes,
      });
    },
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["kardex"] });
      qc.invalidateQueries({ queryKey: ["products-alerts"] });
    },
    onError: () => setError("No se pudo registrar el movimiento."),
  });

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(p: Product) {
    setEditingId(p.id);
    setForm({
      sku: p.sku,
      name: p.name,
      color: p.color || "DORADO",
      tipo: p.tipo || "",
      woo_product_id: p.woo_product_id || "",
      reorder_level: String(p.reorder_level ?? 0),
      is_generic: p.is_generic,
      active: p.active,
    });
    setFormOpen(true);
  }

  const columns = useMemo<ColumnDef<Product, unknown>[]>(
    () => [
      { accessorKey: "sku", header: "SKU" },
      { accessorKey: "name", header: "Nombre" },
      {
        accessorKey: "color",
        header: "Color",
        cell: ({ getValue }) => <Badge variant="dark">{String(getValue() || "—")}</Badge>,
      },
      {
        accessorKey: "tipo",
        header: "Tipo de kit",
        cell: ({ getValue }) => kitTypeLabel(String(getValue() || "")) || "—",
      },
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
          <div className="flex flex-wrap gap-1">
            {row.original.low_stock ? <Badge variant="terracotta">Bajo</Badge> : null}
            {row.original.is_generic ? <Badge variant="sage">Genérico</Badge> : null}
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
    <div className="space-y-6">
      <div className="rounded-[32px] border border-line bg-warm-white/90 p-5 shadow-[var(--shadow-1)] sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="label-caps text-text-muted">Inventario / Productos</p>
            <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">Productos</h1>
            <p className="mt-2 max-w-xl text-sm text-text-muted">
              Alta y edición en ERP. El stock baja al marcar despacho como enviado.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/inventory/materials"
              className="inline-flex min-h-9 items-center rounded-[999px] border border-line px-4 label-caps text-green-900 hover:bg-cream-100"
            >
              Materiales
            </Link>
            <Link
              to="/inventory/kardex"
              className="inline-flex min-h-9 items-center rounded-[999px] border border-line px-4 label-caps text-green-900 hover:bg-cream-100"
            >
              Kardex
            </Link>
            <Button type="button" size="sm" onClick={openCreate}>
              <Plus strokeWidth={1.5} className="h-3.5 w-3.5" />
              Nuevo
            </Button>
          </div>
        </div>
      </div>

      {(alerts.data?.length || 0) > 0 ? (
        <Alert variant="caution">
          {alerts.data!.length} producto(s) bajo mínimo:{" "}
          {alerts.data!
            .slice(0, 5)
            .map((p) => p.sku)
            .join(", ")}
          {alerts.data!.length > 5 ? "…" : ""}
        </Alert>
      ) : null}

      {formOpen ? (
        <Card>
          <h2 className="font-serif text-2xl text-green-900">
            {editingId ? "Editar producto" : "Nuevo producto"}
          </h2>
          <form
            className="mt-4 grid gap-4 md:grid-cols-3"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              saveProduct.mutate();
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
              <FieldLabel>Color</FieldLabel>
              <select
                className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
                value={form.color}
                onChange={(e) => setForm((f) => ({ ...f, color: e.target.value }))}
              >
                <option value="DORADO">Dorado</option>
                <option value="PLATEADO">Plateado</option>
                <option value="OTRO">Otro</option>
              </select>
            </div>
            <div>
              <FieldLabel>Tipo de kit</FieldLabel>
              <select
                className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
                value={form.tipo}
                onChange={(e) => setForm((f) => ({ ...f, tipo: e.target.value }))}
              >
                <option value="">Sin tipo / genérico</option>
                {KIT_TYPES.map((k) => (
                  <option key={k.value} value={k.value}>
                    {k.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FieldLabel>Woo product ID</FieldLabel>
              <Input
                value={form.woo_product_id}
                onChange={(e) => setForm((f) => ({ ...f, woo_product_id: e.target.value }))}
              />
            </div>
            <div>
              <FieldLabel>Stock mínimo</FieldLabel>
              <Input
                type="number"
                value={form.reorder_level}
                onChange={(e) => setForm((f) => ({ ...f, reorder_level: e.target.value }))}
              />
            </div>
            <div className="flex items-end gap-4 pb-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_generic}
                  onChange={(e) => setForm((f) => ({ ...f, is_generic: e.target.checked }))}
                />
                Genérico
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))}
                />
                Activo
              </label>
            </div>
            <div className="flex items-end gap-2 md:col-span-3">
              <Button type="submit" disabled={saveProduct.isPending}>
                {editingId ? "Guardar cambios" : "Crear"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setFormOpen(false);
                  setEditingId(null);
                }}
              >
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
            <FieldLabel>Producto</FieldLabel>
            <select
              required
              className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3"
              value={entry.product_id}
              onChange={(e) => setEntry((f) => ({ ...f, product_id: e.target.value }))}
            >
              <option value="">Selecciona…</option>
              {(products.data || []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} · {p.name} ({p.stock})
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
              step="1"
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
        data={products.data || []}
        columns={columns}
        searchableKeys={["sku", "name", "color", "tipo", "woo_product_id"]}
        columnFilters={[
          {
            key: "color",
            label: "Color",
            type: "select",
            options: ["DORADO", "PLATEADO", "OTRO"],
          },
          {
            key: "tipo",
            label: "Tipo de kit",
            type: "select",
            options: KIT_TYPES.map((k) => k.value),
          },
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
        exportFilename="productos.csv"
        emptyTitle="Sin productos"
        emptyDescription="Crea el primero con el botón Nuevo."
      />
    </div>
  );
}
