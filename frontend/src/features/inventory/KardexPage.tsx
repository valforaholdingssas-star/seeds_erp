import { useQuery } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/PageHeader";

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
    <div className="space-y-3">
      <PageHeader
        eyebrow="Inventario"
        title="Kardex"
        actions={
          <>
            <Link
              to="/inventory"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps text-green-900 hover:bg-cream-100"
            >
              Productos
            </Link>
            <Link
              to="/inventory/materials"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps text-green-900 hover:bg-cream-100"
            >
              Materiales
            </Link>
          </>
        }
      />

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
