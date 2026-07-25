import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { KanbanBoard, type KanbanItem } from "@/components/kanban/KanbanBoard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { InlineSelect } from "@/components/ui/InlineSelect";
import { PageHeader } from "@/components/ui/PageHeader";
import { PaginationBar } from "@/components/ui/PaginationBar";
import { formatCOP, formatSaleDate } from "@/lib/utils";
import { formatSaleItemLine } from "@/lib/kitTypes";

type Sale = {
  id: string;
  source: string;
  external_id: string;
  customer_name: string;
  email: string;
  phone: string;
  city_raw: string;
  total_value: string;
  status: string;
  state: string;
  payment_account: string;
  payment_method: string | null;
  payment_method_detail: { id: string; name: string } | null;
  fulfillment_type: string;
  seller_detail: { id: string; name: string } | null;
  closed_at: string | null;
  items: { color: string; tipo?: string; quantity: number }[];
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };
type PayMethod = { id: string; name: string };

const SOURCES = ["ECOMMERCE", "KOMMO", "FERIAS", "MANUAL"];

const FULFILLMENT_OPTIONS = [
  { value: "ENVIA", label: "Envia" },
  { value: "DOMICILIO", label: "Domicilio" },
  { value: "OFICINA", label: "Oficina" },
];

function fulfillmentTone(v: string): "dark" | "sage" | "terracotta" {
  if (v === "DOMICILIO") return "terracotta";
  if (v === "OFICINA") return "sage";
  return "dark";
}

export function SalesPage() {
  const qc = useQueryClient();
  const [view, setView] = useState<"tabla" | "kanban">("tabla");
  const [selected, setSelected] = useState<Sale[]>([]);
  const [bulkPaymentId, setBulkPaymentId] = useState("");
  const [bulkFulfillment, setBulkFulfillment] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const sales = useQuery({
    queryKey: ["sales", page, pageSize],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Sale>>("/sales/", {
        params: { page, page_size: pageSize },
      });
      return {
        results: data.results || [],
        count: data.count ?? 0,
      };
    },
  });

  const paymentMethods = useQuery({
    queryKey: ["payment-methods-active"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<PayMethod> | PayMethod[]>(
        "/payment-methods/",
        { params: { active_only: "1", page_size: 200 } },
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const withdraw = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/sales/${id}/withdraw/`, { reason: "manual" });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sales"] });
      qc.invalidateQueries({ queryKey: ["shipments"] });
      qc.invalidateQueries({ queryKey: ["invoices"] });
    },
  });

  const patchSale = useMutation({
    mutationFn: async ({ id, fields }: { id: string; fields: Record<string, unknown> }) => {
      await apiClient.patch(`/sales/${id}/`, fields);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sales"] }),
  });

  const bulkUpdate = useMutation({
    mutationFn: async ({ ids, fields }: { ids: string[]; fields: Record<string, unknown> }) => {
      await apiClient.post("/sales/bulk-update/", { ids, fields });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sales"] }),
  });

  const payOptions = useMemo(
    () => (paymentMethods.data || []).map((m) => ({ value: m.id, label: m.name })),
    [paymentMethods.data],
  );

  const saleRows = sales.data?.results || [];
  const totalCount = sales.data?.count || 0;

  const columns = useMemo<ColumnDef<Sale, unknown>[]>(
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
      {
        accessorKey: "external_id",
        header: "ID",
        cell: ({ row }) => (
          <Link
            to={`/sales/${row.original.id}`}
            className="text-green-900 underline-offset-2 hover:underline"
            data-testid="sale-link"
          >
            {row.original.external_id}
          </Link>
        ),
      },
      {
        accessorKey: "source",
        header: "Canal",
        cell: ({ getValue }) => <Badge variant="dark">{String(getValue())}</Badge>,
      },
      {
        accessorKey: "closed_at",
        header: "Fecha venta",
        cell: ({ getValue }) => (
          <span className="whitespace-nowrap text-sm">
            {formatSaleDate(getValue() as string | null)}
          </span>
        ),
      },
      { accessorKey: "customer_name", header: "Cliente" },
      {
        id: "contact",
        header: "Contacto",
        cell: ({ row }) => (
          <div className="min-w-[120px] text-xs text-text-muted">
            <p className="truncate">{row.original.phone || "—"}</p>
            <p className="truncate">{row.original.email || ""}</p>
          </div>
        ),
      },
      { accessorKey: "city_raw", header: "Ciudad" },
      {
        id: "seller",
        header: "Comercial",
        cell: ({ row }) => row.original.seller_detail?.name || "—",
      },
      {
        id: "items",
        header: "Kits",
        cell: ({ row }) => {
          const items = row.original.items || [];
          if (!items.length) return "—";
          return (
            <div className="min-w-[160px] space-y-0.5 text-xs">
              {items.map((i, idx) => (
                <p key={`${i.color}-${i.tipo}-${idx}`}>{formatSaleItemLine(i)}</p>
              ))}
            </div>
          );
        },
      },
      {
        accessorKey: "total_value",
        header: "Valor",
        cell: ({ getValue }) => formatCOP(Number(getValue() || 0)),
      },
      {
        id: "payment",
        header: "Medio de pago",
        cell: ({ row }) => {
          const sale = row.original;
          const currentId = sale.payment_method || sale.payment_method_detail?.id || "";
          const options =
            currentId && !payOptions.some((o) => o.value === currentId)
              ? [
                  {
                    value: currentId,
                    label: sale.payment_method_detail?.name || sale.payment_account || "Actual",
                  },
                  ...payOptions,
                ]
              : payOptions.length
                ? payOptions
                : [{ value: "", label: sale.payment_account || "Sin medio" }];

          return (
            <InlineSelect
              value={currentId || options[0]?.value || ""}
              display={sale.payment_method_detail?.name || sale.payment_account || "—"}
              options={options.filter((o) => o.value)}
              tone="sage"
              disabled={!payOptions.length}
              onChange={async (payment_method) => {
                await patchSale.mutateAsync({ id: sale.id, fields: { payment_method } });
              }}
            />
          );
        },
      },
      {
        accessorKey: "fulfillment_type",
        header: "Entrega",
        cell: ({ row }) => {
          const v = row.original.fulfillment_type || "ENVIA";
          return (
            <InlineSelect
              value={v}
              options={FULFILLMENT_OPTIONS}
              tone={fulfillmentTone(v)}
              onChange={async (fulfillment_type) => {
                await patchSale.mutateAsync({
                  id: row.original.id,
                  fields: { fulfillment_type },
                });
              }}
            />
          );
        },
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ getValue }) => <Badge variant="sage">{String(getValue())}</Badge>,
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center gap-1.5">
            <Link
              to={`/sales/${row.original.id}`}
              title="Ver detalle"
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line text-green-900 transition-colors hover:bg-cream-100"
            >
              <Eye strokeWidth={1.5} className="h-3.5 w-3.5" />
            </Link>
            <button
              type="button"
              title="Eliminar"
              onClick={() => {
                if (
                  !window.confirm(
                    "¿Eliminar esta venta? También se borrará su envío y factura pendientes.",
                  )
                ) {
                  return;
                }
                withdraw.mutate(row.original.id);
              }}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line text-terracotta-600 transition-colors hover:bg-terracotta-600/10"
            >
              <Trash2 strokeWidth={1.5} className="h-3.5 w-3.5" />
            </button>
          </div>
        ),
      },
    ],
    [withdraw, patchSale, payOptions],
  );

  const kanbanItems = useMemo<KanbanItem[]>(
    () =>
      saleRows.map((s) => ({
        id: s.id,
        columnId: s.source,
        title: s.customer_name || s.external_id,
        subtitle: `${formatCOP(Number(s.total_value))} · ${s.city_raw || "—"}`,
      })),
    [saleRows],
  );

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Ventas"
        title="Consolidado"
        actions={
          <>
            <Button
              type="button"
              size="xs"
              variant={view === "tabla" ? "primary-dark" : "outline"}
              onClick={() => setView("tabla")}
            >
              Tabla
            </Button>
            <Button
              type="button"
              size="xs"
              variant={view === "kanban" ? "primary-dark" : "outline"}
              onClick={() => setView("kanban")}
            >
              Kanban
            </Button>
            <Link
              to="/sales/resync"
              className="inline-flex min-h-7 items-center justify-center rounded-[999px] border border-line px-3 text-[10px] label-caps text-green-900 hover:bg-cream-100"
            >
              Resync Woo
            </Link>
            <Link
              to="/sales/import"
              className="inline-flex min-h-7 items-center justify-center rounded-[999px] border border-line px-3 text-[10px] label-caps text-green-900 hover:bg-cream-100"
            >
              Importar
            </Link>
            <Link
              to="/sales/ferias"
              className="inline-flex min-h-7 items-center justify-center rounded-[999px] border border-line px-3 text-[10px] label-caps text-green-900 hover:bg-cream-100"
            >
              Feria
            </Link>
            <Link
              to="/sales/manual"
              className="inline-flex min-h-7 items-center justify-center rounded-[999px] bg-green-900 px-3 text-[10px] label-caps text-text-on-dark hover:bg-green-950"
            >
              Manual
            </Link>
          </>
        }
      />

      <PaginationBar
        page={page}
        pageSize={pageSize}
        total={totalCount}
        onPageChange={(p) => {
          setPage(p);
          setSelected([]);
        }}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
          setSelected([]);
        }}
      />

      {view === "kanban" ? (
        <KanbanBoard
          columns={SOURCES.map((s) => ({
            id: s,
            label: s,
            badge: <Badge variant="dark">{s}</Badge>,
          }))}
          items={kanbanItems}
          canDrop={() => false}
          onMove={() => undefined}
        />
      ) : (
        <DataTable
          data={saleRows}
          columns={columns}
          searchableKeys={[
            "external_id",
            "customer_name",
            "city_raw",
            "source",
            "status",
            "payment_account",
            "fulfillment_type",
            "phone",
            "email",
          ]}
          columnFilters={[
            { key: "source", label: "Canal", type: "select", options: SOURCES },
            {
              key: "fulfillment_type",
              label: "Entrega",
              type: "select",
              options: ["ENVIA", "DOMICILIO", "OFICINA"],
            },
            { key: "payment_account", label: "Medio de pago" },
            { key: "city_raw", label: "Ciudad" },
            { key: "status", label: "Status" },
          ]}
          onSelectionChange={setSelected}
          exportFilename="ventas.csv"
          hint="Scroll horizontal si la tabla no cabe. Clic en los pills para editar."
          bulkActions={
            <>
              <select
                className="rounded-[999px] border border-line-dark/30 bg-green-950/30 px-3 py-1.5 text-sm text-text-on-dark"
                value={bulkPaymentId}
                onChange={(e) => setBulkPaymentId(e.target.value)}
              >
                <option value="">Medio de pago…</option>
                {(paymentMethods.data || []).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                size="sm"
                variant="cream"
                disabled={!bulkPaymentId || !selected.length || bulkUpdate.isPending}
                onClick={() =>
                  bulkUpdate.mutate({
                    ids: selected.map((s) => s.id),
                    fields: { payment_method: bulkPaymentId },
                  })
                }
              >
                Asignar medio
              </Button>
              <select
                className="rounded-[999px] border border-line-dark/30 bg-green-950/30 px-3 py-1.5 text-sm text-text-on-dark"
                value={bulkFulfillment}
                onChange={(e) => setBulkFulfillment(e.target.value)}
              >
                <option value="">Entrega…</option>
                {FULFILLMENT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                size="sm"
                variant="cream"
                disabled={!bulkFulfillment || !selected.length || bulkUpdate.isPending}
                onClick={() =>
                  bulkUpdate.mutate({
                    ids: selected.map((s) => s.id),
                    fields: { fulfillment_type: bulkFulfillment },
                  })
                }
              >
                Asignar entrega
              </Button>
              <Button
                type="button"
                size="sm"
                variant="cream"
                onClick={() => {
                  if (
                    !window.confirm(
                      `¿Eliminar ${selected.length} venta(s)? También se borrarán envíos y facturas pendientes.`,
                    )
                  ) {
                    return;
                  }
                  selected.forEach((s) => withdraw.mutate(s.id));
                }}
              >
                Eliminar selección
              </Button>
            </>
          }
          emptyTitle="Sin ventas activas"
          emptyDescription="Crea una venta de feria o manual, o espera un webhook de Woo/Kommo."
        />
      )}
    </div>
  );
}
