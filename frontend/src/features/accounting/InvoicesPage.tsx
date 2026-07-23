import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { KanbanBoard, type KanbanItem } from "@/components/kanban/KanbanBoard";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { MockModeBanner } from "@/components/ui/MockModeBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";
import { useBatchConsole } from "@/features/batch/batchStore";

const INV_STATUSES = ["POR_GENERAR", "ENVIANDO", "GENERADA", "FALLIDA", "ANULADA"] as const;

type Invoice = {
  id: string;
  sale_external_id: string;
  customer_name: string;
  customer_id_number: string;
  status: string;
  number: string;
  total: string;
  iva: string;
  pdf_url: string;
  last_error: string;
  attempts: number;
};

type Paginated<T> = { count: number; results: T[] };

const statusVariant: Record<string, "sage" | "terracotta" | "wine" | "dark"> = {
  POR_GENERAR: "dark",
  ENVIANDO: "terracotta",
  GENERADA: "sage",
  FALLIDA: "wine",
  ANULADA: "wine",
};

export function InvoicesPage() {
  const qc = useQueryClient();
  const openBatch = useBatchConsole((s) => s.openBatch);
  const [view, setView] = useState<"tabla" | "kanban">("tabla");
  const [selected, setSelected] = useState<Invoice[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  const invoices = useQuery({
    queryKey: ["invoices"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Invoice> | Invoice[]>(
        "/accounting/invoices/",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const issue = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Invoice>(`/accounting/invoices/${id}/issue/`);
      return data;
    },
    onSuccess: (data) => {
      setMsg(`Factura ${data.number || data.status}`);
      qc.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: () => setMsg("No se pudo emitir. Si está ENVIANDO, reconcilia primero."),
  });

  const reconcile = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/accounting/invoices/${id}/reconcile/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoices"] }),
  });

  const bulk = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await apiClient.post("/accounting/invoices/bulk-issue/", { ids });
      return data;
    },
    onSuccess: async (data) => {
      setMsg(`Emisión en lote iniciada · ${data.total} ítems`);
      void openBatch(data.id);
      qc.invalidateQueries({ queryKey: ["invoices"] });
    },
  });

  const refund = useMutation({
    mutationFn: async (invoiceId: string) => {
      await apiClient.post("/accounting/refunds/", {
        invoice_id: invoiceId,
        reason: "Reembolso desde panel",
      });
    },
    onSuccess: () => {
      setMsg("Reembolso registrado.");
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["sales"] });
    },
  });

  const columns = useMemo<ColumnDef<Invoice, unknown>[]>(
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
            disabled={row.original.status !== "POR_GENERAR"}
          />
        ),
      },
      { accessorKey: "sale_external_id", header: "Pedido" },
      { accessorKey: "customer_name", header: "Cliente" },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ getValue }) => (
          <Badge variant={statusVariant[String(getValue())] || "dark"}>
            {String(getValue())}
          </Badge>
        ),
      },
      { accessorKey: "number", header: "Número" },
      {
        accessorKey: "total",
        header: "Total",
        cell: ({ getValue }) => formatCOP(Number(getValue() || 0)),
      },
      {
        accessorKey: "iva",
        header: "IVA",
        cell: ({ getValue }) => formatCOP(Number(getValue() || 0)),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {row.original.status === "POR_GENERAR" || row.original.status === "FALLIDA" ? (
              <Button
                type="button"
                size="sm"
                variant="primary-wine"
                onClick={() => issue.mutate(row.original.id)}
              >
                Emitir
              </Button>
            ) : null}
            {row.original.status === "ENVIANDO" || row.original.status === "FALLIDA" ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => reconcile.mutate(row.original.id)}
              >
                Reconciliar
              </Button>
            ) : null}
            {row.original.status === "GENERADA" ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => refund.mutate(row.original.id)}
              >
                Reembolsar
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [issue, reconcile, refund],
  );

  const kanbanItems = useMemo<KanbanItem[]>(
    () =>
      (invoices.data || []).map((inv) => ({
        id: inv.id,
        columnId: INV_STATUSES.includes(inv.status as (typeof INV_STATUSES)[number])
          ? inv.status
          : "POR_GENERAR",
        title: inv.customer_name || inv.sale_external_id,
        subtitle: `${formatCOP(Number(inv.total || 0))} · ${inv.number || "sin número"}`,
      })),
    [invoices.data],
  );

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Contabilidad"
        title="Facturas"
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
              to="/accounting/refunds"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Reembolsos
            </Link>
            <Link
              to="/accounting/iva"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              IVA
            </Link>
            <Link
              to="/accounting/customers"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Clientes
            </Link>
            <Button
              type="button"
              size="xs"
              variant="primary-wine"
              disabled={!selected.length || bulk.isPending || view !== "tabla"}
              onClick={() => bulk.mutate(selected.map((s) => s.id))}
            >
              Emitir lote
            </Button>
          </>
        }
      />

      {msg ? <Alert variant="info">{msg}</Alert> : null}

      <MockModeBanner providers={["alegra"]} />

      {view === "kanban" ? (
        <KanbanBoard
          columns={INV_STATUSES.map((s) => ({
            id: s,
            label: s.replaceAll("_", " "),
            badge: <Badge variant={statusVariant[s] || "dark"}>{s}</Badge>,
          }))}
          items={kanbanItems}
          canDrop={() => false}
          onMove={() => undefined}
        />
      ) : (
        <DataTable
          data={invoices.data || []}
          columns={columns}
          searchableKeys={["sale_external_id", "customer_name", "status", "number"]}
          columnFilters={[
            {
              key: "status",
              label: "Estado",
              type: "select",
              options: [...INV_STATUSES],
            },
          ]}
          onSelectionChange={setSelected}
          exportFilename="facturas.csv"
          emptyTitle="Sin facturas"
          emptyDescription="Al consolidar una venta se crea el registro por generar."
        />
      )}
    </div>
  );
}
