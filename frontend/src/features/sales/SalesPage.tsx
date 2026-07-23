import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Undo2 } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { KanbanBoard, type KanbanItem } from "@/components/kanban/KanbanBoard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { InlineSelect } from "@/components/ui/InlineSelect";
import { formatCOP } from "@/lib/utils";
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

type Paginated<T> = { count: number; results: T[] };
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

  const sales = useQuery({
    queryKey: ["sales"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Sale> | Sale[]>("/sales/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const paymentMethods = useQuery({
    queryKey: ["payment-methods-active"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<PayMethod> | PayMethod[]>(
        "/payment-methods/",
        { params: { active_only: "1" } },
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const withdraw = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/sales/${id}/withdraw/`, { reason: "manual" });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sales"] }),
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
              title="Retirar"
              onClick={() => withdraw.mutate(row.original.id)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line text-terracotta-600 transition-colors hover:bg-terracotta-600/10"
            >
              <Undo2 strokeWidth={1.5} className="h-3.5 w-3.5" />
            </button>
          </div>
        ),
      },
    ],
    [withdraw, patchSale, payOptions],
  );

  const kanbanItems = useMemo<KanbanItem[]>(
    () =>
      (sales.data || []).map((s) => ({
        id: s.id,
        columnId: s.source,
        title: s.customer_name || s.external_id,
        subtitle: `${formatCOP(Number(s.total_value))} · ${s.city_raw || "—"}`,
      })),
    [sales.data],
  );

  return (
    <div className="space-y-6">
      <div className="rounded-[32px] border border-line bg-warm-white/90 p-5 shadow-[var(--shadow-1)] sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="label-caps text-text-muted">Ventas / Consolidado</p>
            <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">
              Consolidado
            </h1>
            <p className="mt-2 max-w-xl text-sm text-text-muted">
              Solo processing/completed. Clic en medio de pago o entrega para editar en
              la fila.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant={view === "tabla" ? "primary-dark" : "outline"}
              onClick={() => setView("tabla")}
            >
              Tabla
            </Button>
            <Button
              type="button"
              size="sm"
              variant={view === "kanban" ? "primary-dark" : "outline"}
              onClick={() => setView("kanban")}
            >
              Kanban
            </Button>
            <Link
              to="/sales/resync"
              className="inline-flex min-h-9 items-center justify-center rounded-[999px] border border-line px-4 label-caps text-green-900 hover:bg-cream-100"
            >
              Resync Woo
            </Link>
            <Link
              to="/sales/import"
              className="inline-flex min-h-9 items-center justify-center rounded-[999px] border border-line px-4 label-caps text-green-900 hover:bg-cream-100"
            >
              Importar
            </Link>
            <Link
              to="/sales/ferias"
              className="inline-flex min-h-9 items-center justify-center rounded-[999px] border border-line px-4 label-caps text-green-900 hover:bg-cream-100"
            >
              Feria
            </Link>
            <Link
              to="/sales/manual"
              className="inline-flex min-h-9 items-center justify-center rounded-[999px] bg-green-900 px-4 label-caps text-text-on-dark hover:bg-green-950"
            >
              Manual
            </Link>
          </div>
        </div>
      </div>

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
          data={sales.data || []}
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
                  selected.forEach((s) => withdraw.mutate(s.id));
                }}
              >
                Retirar selección
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
