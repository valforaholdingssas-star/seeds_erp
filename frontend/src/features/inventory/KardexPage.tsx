import { useQuery } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Badge } from "@/components/ui/Badge";

type KardexRow = {
  id: string;
  item_type: string;
  product_sku: string;
  product_name: string;
  material_sku: string;
  material_name: string;
  movement: string;
  quantity: string;
  balance: string;
  reason: string;
  ref_type: string;
  ref_id: string;
  notes: string;
  created_at: string;
};

type Paginated<T> = { count: number; results: T[] };

export function KardexPage() {
  const kardex = useQuery({
    queryKey: ["kardex"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<KardexRow> | KardexRow[]>(
        "/inventory/kardex/",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const columns = useMemo<ColumnDef<KardexRow, unknown>[]>(
    () => [
      {
        accessorKey: "created_at",
        header: "Fecha",
        cell: ({ getValue }) =>
          new Date(String(getValue())).toLocaleString("es-CO", {
            dateStyle: "short",
            timeStyle: "short",
          }),
      },
      {
        accessorKey: "item_type",
        header: "Tipo",
        cell: ({ getValue }) => (
          <Badge variant={getValue() === "MATERIAL" ? "sage" : "dark"}>
            {String(getValue())}
          </Badge>
        ),
      },
      {
        id: "item",
        header: "Ítem",
        cell: ({ row }) => {
          if (row.original.item_type === "MATERIAL") {
            return `${row.original.material_sku || "—"} · ${row.original.material_name || ""}`;
          }
          return `${row.original.product_sku || "—"} · ${row.original.product_name || ""}`;
        },
      },
      {
        accessorKey: "movement",
        header: "Mov.",
        cell: ({ getValue }) => {
          const m = String(getValue());
          return (
            <Badge variant={m === "OUT" ? "wine" : m === "IN" ? "sage" : "terracotta"}>
              {m}
            </Badge>
          );
        },
      },
      { accessorKey: "quantity", header: "Cantidad" },
      { accessorKey: "balance", header: "Saldo" },
      { accessorKey: "reason", header: "Motivo" },
      {
        id: "ref",
        header: "Ref",
        cell: ({ row }) =>
          row.original.ref_id
            ? `${row.original.ref_type}:${row.original.ref_id.slice(0, 8)}`
            : "—",
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <div className="rounded-[32px] border border-line bg-warm-white/90 p-5 shadow-[var(--shadow-1)] sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="label-caps text-text-muted">Inventario / Kardex</p>
            <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">Kardex</h1>
            <p className="mt-2 max-w-xl text-sm text-text-muted">
              Libro inmutable de movimientos de productos y materiales.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/inventory"
              className="inline-flex min-h-9 items-center rounded-[999px] border border-line px-4 label-caps text-green-900 hover:bg-cream-100"
            >
              Productos
            </Link>
            <Link
              to="/inventory/materials"
              className="inline-flex min-h-9 items-center rounded-[999px] border border-line px-4 label-caps text-green-900 hover:bg-cream-100"
            >
              Materiales
            </Link>
          </div>
        </div>
      </div>

      <DataTable
        data={kardex.data || []}
        columns={columns}
        searchableKeys={[
          "product_sku",
          "product_name",
          "material_sku",
          "material_name",
          "reason",
          "movement",
          "item_type",
        ]}
        columnFilters={[
          {
            key: "item_type",
            label: "Tipo",
            type: "select",
            options: ["PRODUCT", "MATERIAL"],
          },
          {
            key: "movement",
            label: "Movimiento",
            type: "select",
            options: ["IN", "OUT", "ADJUST"],
          },
          {
            key: "reason",
            label: "Motivo",
            type: "select",
            options: ["DISPATCH", "PURCHASE", "MANUAL_ADJUST", "PRODUCTION", "REFUND"],
          },
        ]}
        exportFilename="kardex.csv"
        emptyTitle="Sin movimientos"
        emptyDescription="Despacha un pedido o registra una entrada para ver el kardex."
      />
    </div>
  );
}
