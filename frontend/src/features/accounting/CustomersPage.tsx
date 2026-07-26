import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { MockModeBanner } from "@/components/ui/MockModeBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { PaginationBar } from "@/components/ui/PaginationBar";
import { useBatchConsole } from "@/features/batch/batchStore";

type Customer = {
  id: string;
  name: string;
  id_type: string;
  id_number: string;
  email: string;
  city: string;
  alegra_synced: boolean;
  alegra_id: string;
};

type Paginated<T> = { count: number; results: T[] };

type NormalizeResult = {
  updated: number;
  skipped: number;
  failed: number;
  errors: { id: string; name?: string; detail: string }[];
};

type BatchJob = {
  id: string;
  job_type: string;
  status: string;
  total: number;
  done: number;
  success: number;
  failed: number;
};

function errDetail(err: unknown): string {
  const ax = err as { response?: { data?: { detail?: string | object } }; message?: string };
  const d = ax.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") return JSON.stringify(d);
  return ax.message || "Error desconocido";
}

export function CustomersPage() {
  const qc = useQueryClient();
  const openBatch = useBatchConsole((s) => s.openBatch);
  const [selected, setSelected] = useState<Customer[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "pending" | "synced">("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  useEffect(() => {
    setPage(1);
    setSelected([]);
  }, [filter]);

  const customers = useQuery({
    queryKey: ["customers", filter, page, pageSize],
    queryFn: async () => {
      const q = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        ordering: "name",
      });
      if (filter === "pending") q.set("alegra_synced", "false");
      if (filter === "synced") q.set("alegra_synced", "true");
      const { data } = await apiClient.get<Paginated<Customer>>(
        `/accounting/customers/?${q}`,
      );
      return {
        results: data.results || [],
        count: data.count ?? 0,
      };
    },
  });

  const pendingMeta = useQuery({
    queryKey: ["customers", "pending-count"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Customer>>(
        "/accounting/customers/?alegra_synced=false&page_size=1",
      );
      return data.count ?? 0;
    },
  });

  const syncedMeta = useQuery({
    queryKey: ["customers", "synced-count"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Customer>>(
        "/accounting/customers/?alegra_synced=true&page_size=1",
      );
      return data.count ?? 0;
    },
  });

  const syncOne = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<BatchJob>(
        "/accounting/customers/bulk-sync-alegra/",
        { ids: [id] },
      );
      return data;
    },
    onSuccess: async (data) => {
      setErr(null);
      setMsg(`Sincronización iniciada · ${data.total} cliente(s)`);
      await openBatch(data.id);
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (e) => {
      setMsg(null);
      setErr(errDetail(e));
    },
  });

  const syncBulk = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await apiClient.post<BatchJob>(
        "/accounting/customers/bulk-sync-alegra/",
        { ids },
      );
      return data;
    },
    onSuccess: async (data) => {
      setSelected([]);
      setErr(null);
      setMsg(`Sincronización Alegra iniciada · ${data.total} cliente(s)`);
      await openBatch(data.id);
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (e) => {
      setMsg(null);
      setErr(errDetail(e));
    },
  });

  const normalizeDocs = useMutation({
    mutationFn: async (ids: string[] | null) => {
      const { data } = await apiClient.post<NormalizeResult>(
        "/accounting/customers/bulk-normalize-documents/",
        ids?.length ? { ids } : {},
      );
      return data;
    },
    onSuccess: (data) => {
      setSelected([]);
      const failHint =
        data.failed > 0
          ? ` · Fallidos: ${data.errors
              .slice(0, 3)
              .map((e) => `${e.name || e.id}: ${e.detail}`)
              .join(" | ")}${data.errors.length > 3 ? "…" : ""}`
          : "";
      setMsg(
        `Documentos formateados: ${data.updated} actualizado(s)` +
          (data.skipped ? `, ${data.skipped} sin cambios` : "") +
          ".",
      );
      if (data.failed > 0) {
        setErr(`${data.failed} no se pudieron formatear${failHint}`);
      } else {
        setErr(null);
      }
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (e) => {
      setMsg(null);
      setErr(errDetail(e));
    },
  });

  function runNormalize(ids: string[] | null) {
    const scope =
      ids && ids.length > 0
        ? `los ${ids.length} seleccionado(s)`
        : "todos los documentos con caracteres no numéricos";
    if (
      !window.confirm(
        `¿Formatear ${scope}?\nSe quitarán puntos, guiones y letras; solo quedarán números.`,
      )
    ) {
      return;
    }
    setErr(null);
    setMsg(null);
    normalizeDocs.mutate(ids);
  }

  const healNames = useMutation({
    mutationFn: async (payload: {
      ids: string[] | null;
      unsynced_only?: boolean;
    }) => {
      const { data } = await apiClient.post<{
        updated: number;
        skipped: number;
        failed: number;
        processed: number;
        errors: { id: string; name?: string; detail: string }[];
      }>("/accounting/customers/bulk-heal-names/", {
        ...(payload.ids?.length ? { ids: payload.ids } : {}),
        limit: 200,
        unsynced_only: Boolean(payload.unsynced_only),
      });
      return data;
    },
    onSuccess: (data) => {
      setMsg(
        `Nombres actualizados desde Kommo: ${data.updated} · sin cambio ${data.skipped}` +
          (data.failed ? ` · fallidos ${data.failed}` : "") +
          ".",
      );
      if (data.failed > 0) {
        setErr(data.errors[0]?.detail || "Algunos nombres no se pudieron actualizar.");
      } else {
        setErr(null);
      }
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (e) => {
      setMsg(null);
      setErr(errDetail(e));
    },
  });

  function runHealNames(ids: string[] | null, unsyncedOnly = false) {
    const scope =
      ids && ids.length > 0
        ? `los ${ids.length} seleccionado(s)`
        : unsyncedOnly
          ? "contactos pendientes (aún no sincronizados)"
          : "clientes con nombre débil (ID de lead)";
    if (
      !window.confirm(
        `¿Actualizar nombres desde Kommo (${scope})?\nSe usa el nombre del contacto en Kommo.`,
      )
    ) {
      return;
    }
    setErr(null);
    setMsg(null);
    healNames.mutate({ ids, unsynced_only: unsyncedOnly });
  }

  const columns = useMemo<ColumnDef<Customer, unknown>[]>(
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
            onClick={(e) => e.stopPropagation()}
          />
        ),
      },
      { accessorKey: "name", header: "Nombre" },
      {
        id: "doc",
        header: "Documento",
        cell: ({ row }) => `${row.original.id_type} ${row.original.id_number}`,
      },
      { accessorKey: "email", header: "Email" },
      { accessorKey: "city", header: "Ciudad" },
      {
        accessorKey: "alegra_synced",
        header: "Alegra",
        cell: ({ row }) =>
          row.original.alegra_synced ? (
            <Badge variant="sage">{row.original.alegra_id.slice(0, 12)}</Badge>
          ) : (
            <Badge variant="terracotta">Pendiente</Badge>
          ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={syncOne.isPending || syncBulk.isPending}
            onClick={(e) => {
              e.stopPropagation();
              setErr(null);
              setMsg(null);
              syncOne.mutate(row.original.id);
            }}
          >
            {syncOne.isPending && syncOne.variables === row.original.id
              ? "…"
              : "Sincronizar"}
          </Button>
        ),
      },
    ],
    [syncOne, syncBulk.isPending],
  );

  const rows = customers.data?.results || [];
  const totalCount = customers.data?.count || 0;
  const pendingCount = pendingMeta.data ?? 0;
  const syncedCount = syncedMeta.data ?? 0;

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
        title="Clientes"
        actions={
          <>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={healNames.isPending}
              onClick={() =>
                runHealNames(
                  selected.length > 0 ? selected.map((s) => s.id) : null,
                  selected.length === 0 && filter === "pending",
                )
              }
            >
              {healNames.isPending
                ? "Actualizando nombres…"
                : selected.length > 0
                  ? `Nombres Kommo (${selected.length})`
                  : filter === "pending"
                    ? "Nombres pendientes"
                    : "Actualizar nombres"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={normalizeDocs.isPending}
              onClick={() =>
                runNormalize(
                  selected.length > 0 ? selected.map((s) => s.id) : null,
                )
              }
            >
              {normalizeDocs.isPending
                ? "Formateando…"
                : selected.length > 0
                  ? `Formatear docs (${selected.length})`
                  : "Formatear documentos"}
            </Button>
            <Link
              to="/accounting"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Facturas
            </Link>
          </>
        }
      />

      <MockModeBanner />

      {msg ? <Alert variant="success">{msg}</Alert> : null}
      {err ? <Alert variant="error">{err}</Alert> : null}

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["all", "Todos"],
            ["pending", `Pendientes${pendingCount ? ` (${pendingCount})` : ""}`],
            ["synced", `Sincronizados${syncedCount ? ` (${syncedCount})` : ""}`],
          ] as const
        ).map(([k, label]) => (
          <Button
            key={k}
            type="button"
            size="sm"
            variant={filter === k ? "primary-dark" : "ghost"}
            onClick={() => setFilter(k)}
          >
            {label}
          </Button>
        ))}
      </div>

      {filter === "pending" ? (
        <p className="text-sm text-text-muted">
          Si ves un ID de lead en lugar del nombre, usa «Nombres pendientes» para
          traer el nombre real desde Kommo (igual que en sincronizados).
        </p>
      ) : null}

      {pager}

      <DataTable
        data={rows}
        columns={columns}
        searchableKeys={["name", "id_number", "email", "city"]}
        emptyTitle="Sin clientes"
        emptyDescription="Aparecen al promover ventas al consolidado."
        onSelectionChange={setSelected}
        bulkActions={
          selected.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={normalizeDocs.isPending}
                onClick={() => runNormalize(selected.map((s) => s.id))}
              >
                {normalizeDocs.isPending
                  ? "Formateando…"
                  : `Formatear docs (${selected.length})`}
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={syncBulk.isPending}
                onClick={() => {
                  setErr(null);
                  setMsg(null);
                  syncBulk.mutate(selected.map((s) => s.id));
                }}
              >
                {syncBulk.isPending
                  ? "Iniciando…"
                  : `Sincronizar Alegra (${selected.length})`}
              </Button>
            </div>
          ) : null
        }
        hint="Al sincronizar se abre el panel de lote (como en envíos/facturas) con el estado de cada cliente. Usa el paginador para recorrer todas las páginas."
      />

      {pager}
    </div>
  );
}
