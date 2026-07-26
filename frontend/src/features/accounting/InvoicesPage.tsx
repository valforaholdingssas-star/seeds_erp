import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { KanbanBoard, type KanbanItem } from "@/components/kanban/KanbanBoard";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { MockModeBanner } from "@/components/ui/MockModeBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { PaginationBar } from "@/components/ui/PaginationBar";
import { formatCOP } from "@/lib/utils";
import { useBatchConsole } from "@/features/batch/batchStore";

const INV_STATUSES = ["POR_GENERAR", "ENVIANDO", "GENERADA", "FALLIDA", "ANULADA"] as const;

type Invoice = {
  id: string;
  sale_external_id: string;
  customer_name: string;
  customer_id_number: string;
  customer_alegra_synced: boolean;
  customer_alegra_id: string;
  can_issue: boolean;
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

function errDetail(err: unknown): string {
  const ax = err as { response?: { data?: { detail?: string } }; message?: string };
  return ax.response?.data?.detail || ax.message || "Error desconocido";
}

export function InvoicesPage() {
  const qc = useQueryClient();
  const openBatch = useBatchConsole((s) => s.openBatch);
  const [view, setView] = useState<"tabla" | "kanban">("tabla");
  const [selected, setSelected] = useState<Invoice[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [readyOnly, setReadyOnly] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  useEffect(() => {
    setPage(1);
    setSelected([]);
  }, [readyOnly, statusFilter]);

  const invoices = useQuery({
    queryKey: ["invoices", readyOnly, statusFilter, page, pageSize],
    queryFn: async () => {
      const q = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        ordering: "-created_at",
      });
      if (readyOnly) {
        q.set("ready", "1");
      } else if (statusFilter) {
        q.set("status", statusFilter);
      }
      const { data } = await apiClient.get<Paginated<Invoice>>(
        `/accounting/invoices/?${q}`,
      );
      return {
        results: data.results || [],
        count: data.count ?? 0,
      };
    },
  });

  const readyMeta = useQuery({
    queryKey: ["invoices", "ready-count"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Invoice>>(
        "/accounting/invoices/?ready=1&page_size=1",
      );
      return data.count ?? 0;
    },
  });

  const rows = invoices.data?.results || [];
  const totalCount = invoices.data?.count || 0;
  const readyCount = readyMeta.data ?? 0;

  const issue = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Invoice>(`/accounting/invoices/${id}/issue/`);
      return data;
    },
    onSuccess: (data) => {
      setErr(null);
      setMsg(`Factura ${data.number || data.status}`);
      void qc.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (e) => {
      setMsg(null);
      setErr(errDetail(e));
    },
  });

  const reconcile = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/accounting/invoices/${id}/reconcile/`);
    },
    onSuccess: () => {
      setErr(null);
      void qc.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (e) => setErr(errDetail(e)),
  });

  const bulk = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await apiClient.post("/accounting/invoices/bulk-issue/", { ids });
      return data;
    },
    onSuccess: async (data) => {
      setErr(null);
      setMsg(`Emisión en lote iniciada · ${data.total} ítems`);
      void openBatch(data.id);
      void qc.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (e) => {
      setMsg(null);
      setErr(errDetail(e));
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
      setErr(null);
      setMsg("Reembolso registrado.");
      void qc.invalidateQueries({ queryKey: ["invoices"] });
      void qc.invalidateQueries({ queryKey: ["sales"] });
    },
    onError: (e) => setErr(errDetail(e)),
  });

  const selectableReady = selected.filter((s) => s.can_issue);

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
            disabled={!row.original.can_issue}
            title={
              row.original.can_issue
                ? "Seleccionar"
                : "Requiere contacto sincronizado en Alegra"
            }
          />
        ),
      },
      { accessorKey: "sale_external_id", header: "Pedido" },
      { accessorKey: "customer_name", header: "Cliente" },
      {
        id: "contacto",
        header: "Contacto Alegra",
        cell: ({ row }) =>
          row.original.customer_alegra_synced && row.original.customer_alegra_id ? (
            <Badge variant="sage">{row.original.customer_alegra_id}</Badge>
          ) : (
            <Badge variant="terracotta">Sin sync</Badge>
          ),
      },
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
                disabled={!row.original.can_issue || issue.isPending}
                title={
                  row.original.can_issue
                    ? "Emitir en Alegra"
                    : "Sincroniza el cliente en Contabilidad → Clientes primero"
                }
                onClick={() => {
                  setErr(null);
                  setMsg(null);
                  issue.mutate(row.original.id);
                }}
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
      rows.map((inv) => ({
        id: inv.id,
        columnId: INV_STATUSES.includes(inv.status as (typeof INV_STATUSES)[number])
          ? inv.status
          : "POR_GENERAR",
        title: inv.customer_name || inv.sale_external_id,
        subtitle: `${formatCOP(Number(inv.total || 0))} · ${
          inv.can_issue ? "listo" : "sin contacto"
        } · ${inv.number || "sin número"}`,
      })),
    [rows],
  );

  const pager = (
    <PaginationBar
      page={page}
      pageSize={pageSize}
      total={totalCount}
      pageSizeOptions={[25, 50, 100, 200]}
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
              disabled={!selectableReady.length || bulk.isPending || view !== "tabla"}
              onClick={() => bulk.mutate(selectableReady.map((s) => s.id))}
            >
              Emitir lote ({selectableReady.length})
            </Button>
          </>
        }
      />

      {msg ? <Alert variant="success">{msg}</Alert> : null}
      {err ? <Alert variant="error">{err}</Alert> : null}

      <MockModeBanner providers={["alegra"]} />

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant={readyOnly ? "primary-dark" : "ghost"}
          onClick={() => {
            setReadyOnly(true);
            setStatusFilter("");
          }}
        >
          Listas para emitir{readyCount ? ` (${readyCount})` : ""}
        </Button>
        <Button
          type="button"
          size="sm"
          variant={!readyOnly && !statusFilter ? "primary-dark" : "ghost"}
          onClick={() => {
            setReadyOnly(false);
            setStatusFilter("");
          }}
        >
          Todas
        </Button>
        {INV_STATUSES.map((s) => (
          <Button
            key={s}
            type="button"
            size="sm"
            variant={!readyOnly && statusFilter === s ? "primary-dark" : "ghost"}
            onClick={() => {
              setReadyOnly(false);
              setStatusFilter(s);
            }}
          >
            {s.replaceAll("_", " ")}
          </Button>
        ))}
      </div>

      <p className="text-sm text-text-muted">
        Por defecto se muestran solo facturas cuyo contacto ya está en Alegra
        ({readyCount} listas). Hay más de mil pendientes de sync de cliente.
      </p>

      {pager}

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
          data={rows}
          columns={columns}
          searchableKeys={["sale_external_id", "customer_name", "status", "number"]}
          onSelectionChange={setSelected}
          exportFilename="facturas.csv"
          emptyTitle="Sin facturas"
          emptyDescription={
            readyOnly
              ? "No hay facturas con contacto ya sincronizado. Sincroniza clientes primero."
              : "Al consolidar una venta se crea el registro por generar."
          }
        />
      )}

      {pager}
    </div>
  );
}
