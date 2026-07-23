import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { KanbanBoard, type KanbanItem } from "@/components/kanban/KanbanBoard";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { InlineText } from "@/components/ui/InlineText";
import { MockModeBanner } from "@/components/ui/MockModeBanner";
import { formatCOP } from "@/lib/utils";
import { useBatchConsole } from "@/features/batch/batchStore";

const SHIP_STATUSES = [
  "POR_GENERAR",
  "LISTO_PARA_ENVIAR",
  "GUIA_FALLIDA",
  "REVISAR",
  "ENVIADO",
] as const;

type Shipment = {
  id: string;
  sale_external_id: string;
  customer_name: string;
  address_raw: string;
  city_raw: string;
  address_mirror: string;
  city_mirror: string;
  state_mirror: string;
  address_formatted: string;
  generated_city: string;
  generated_state: string;
  generated_address: string;
  status: string;
  tracking_number: string;
  shipping_cost: string | null;
  warning: boolean;
  warning_detail: string;
  last_error: string;
  do_not_ship: boolean;
  geo_city_name: string | null;
};

type Paginated<T> = { count: number; results: T[] };
type Batch = {
  id: string;
  status: string;
  total: number;
  done: number;
  success: number;
  failed: number;
};

const statusVariant: Record<string, "sage" | "terracotta" | "wine" | "dark"> = {
  POR_GENERAR: "dark",
  LISTO_PARA_ENVIAR: "sage",
  GUIA_FALLIDA: "wine",
  REVISAR: "terracotta",
  ENVIADO: "sage",
};

export function ShipmentsPage() {
  const qc = useQueryClient();
  const openBatch = useBatchConsole((s) => s.openBatch);
  const [view, setView] = useState<"tabla" | "kanban">("tabla");
  const [selected, setSelected] = useState<Shipment[]>([]);
  const [batchMsg, setBatchMsg] = useState<string | null>(null);
  const [bulkCity, setBulkCity] = useState("");
  const [bulkState, setBulkState] = useState("");

  const shipments = useQuery({
    queryKey: ["shipments"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Shipment> | Shipment[]>(
        "/logistics/shipments/",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const patchMirror = useMutation({
    mutationFn: async ({
      id,
      fields,
    }: {
      id: string;
      fields: Partial<Pick<Shipment, "address_mirror" | "city_mirror" | "state_mirror">>;
    }) => {
      await apiClient.patch(`/logistics/shipments/${id}/`, fields);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shipments"] }),
  });

  const bulkUpdate = useMutation({
    mutationFn: async (payload: {
      ids: string[];
      fields: Record<string, string>;
    }) => {
      await apiClient.post("/logistics/shipments/bulk-update/", payload);
    },
    onSuccess: () => {
      setBulkCity("");
      setBulkState("");
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
  });

  const formatOne = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/logistics/shipments/${id}/format-ai/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shipments"] }),
  });

  const formatBatch = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await apiClient.post<Batch>("/logistics/shipments/format-ai/", {
        ids,
      });
      return data;
    },
    onSuccess: (data) => {
      setBatchMsg(`Formateo: ${data.success}/${data.total} listos (${data.status})`);
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
  });

  const generate = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await apiClient.post<Batch>("/logistics/shipments/generate/", {
        ids,
      });
      return data;
    },
    onSuccess: async (data) => {
      setBatchMsg(`Lote guías iniciado · ${data.total} ítems`);
      void openBatch(data.id);
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
  });

  const retry = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/logistics/shipments/${id}/retry/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shipments"] }),
  });

  const columns = useMemo<ColumnDef<Shipment, unknown>[]>(
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
      { accessorKey: "sale_external_id", header: "Pedido" },
      { accessorKey: "customer_name", header: "Cliente" },
      {
        id: "addr",
        header: "Dirección (espejo)",
        cell: ({ row }) => {
          const s = row.original;
          return (
            <div className="min-w-[220px] max-w-[280px] space-y-1">
              <p className="truncate text-[11px] text-text-soft" title={s.address_raw}>
                Origen: {s.address_raw || "—"}
              </p>
              <InlineText
                value={s.address_mirror}
                multiline
                placeholder="Editar espejo…"
                onSave={async (address_mirror) => {
                  await patchMirror.mutateAsync({ id: s.id, fields: { address_mirror } });
                }}
              />
              {s.address_formatted ? (
                <p
                  className={
                    s.warning
                      ? "truncate text-xs text-terracotta-600"
                      : "truncate text-xs text-sage-500"
                  }
                  title={s.address_formatted}
                >
                  Envia: {s.address_formatted}
                </p>
              ) : null}
              {s.generated_address && s.generated_address !== s.address_mirror ? (
                <p className="truncate text-[10px] text-text-soft" title={s.generated_address}>
                  Gen: {s.generated_address}
                </p>
              ) : null}
            </div>
          );
        },
      },
      {
        id: "city",
        header: "Ciudad / Dpto",
        cell: ({ row }) => {
          const s = row.original;
          const cityMismatch =
            s.warning &&
            s.generated_city &&
            s.city_mirror &&
            s.generated_city.toLowerCase() !== s.city_mirror.toLowerCase();
          return (
            <div className="min-w-[140px] space-y-1">
              <InlineText
                value={s.city_mirror || s.city_raw}
                placeholder="Ciudad…"
                onSave={async (city_mirror) => {
                  await patchMirror.mutateAsync({ id: s.id, fields: { city_mirror } });
                }}
              />
              <InlineText
                value={s.state_mirror}
                placeholder="Departamento…"
                className="text-xs text-text-muted"
                onSave={async (state_mirror) => {
                  await patchMirror.mutateAsync({ id: s.id, fields: { state_mirror } });
                }}
              />
              {s.geo_city_name ? (
                <p className="text-[10px] text-text-soft">Geo: {s.geo_city_name}</p>
              ) : null}
              {s.generated_city ? (
                <p
                  className={
                    cityMismatch
                      ? "text-[10px] font-medium text-terracotta-600"
                      : "text-[10px] text-sage-500"
                  }
                  title={s.warning_detail || ""}
                >
                  Envia: {s.generated_city}
                  {s.generated_state ? `, ${s.generated_state}` : ""}
                </p>
              ) : null}
            </div>
          );
        },
      },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ row }) => (
          <div className="space-y-1">
            <Badge variant={statusVariant[row.original.status] || "dark"}>
              {row.original.status}
            </Badge>
            {row.original.warning ? (
              <span title={row.original.warning_detail || "Discrepancia con Envia"}>
                <Badge variant="terracotta">Warning</Badge>
              </span>
            ) : null}
            {row.original.do_not_ship ? <Badge variant="wine">No enviar</Badge> : null}
            {row.original.last_error ? (
              <p className="max-w-[140px] truncate text-[10px] text-wine-900" title={row.original.last_error}>
                {row.original.last_error}
              </p>
            ) : null}
          </div>
        ),
      },
      {
        accessorKey: "tracking_number",
        header: "Guía",
        cell: ({ row }) => row.original.tracking_number || "—",
      },
      {
        accessorKey: "shipping_cost",
        header: "Costo",
        cell: ({ getValue }) => (getValue() ? formatCOP(Number(getValue())) : "—"),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              title="Formatear con IA"
              onClick={() => formatOne.mutate(row.original.id)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line text-green-900 hover:bg-cream-100"
            >
              <Sparkles strokeWidth={1.5} className="h-3.5 w-3.5" />
            </button>
            {row.original.status === "GUIA_FALLIDA" ? (
              <button
                type="button"
                title="Reintentar"
                onClick={() => retry.mutate(row.original.id)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-wine-900/30 text-wine-900 hover:bg-wine-900/10"
              >
                <RefreshCw strokeWidth={1.5} className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </div>
        ),
      },
    ],
    [formatOne, retry, patchMirror],
  );

  const selectedIds = selected.map((s) => s.id);

  const kanbanItems = useMemo<KanbanItem[]>(
    () =>
      (shipments.data || []).map((s) => ({
        id: s.id,
        columnId: SHIP_STATUSES.includes(s.status as (typeof SHIP_STATUSES)[number])
          ? s.status
          : "REVISAR",
        title: s.customer_name || s.sale_external_id,
        subtitle: `${s.city_mirror || s.city_raw || "—"} · ${s.tracking_number || "sin guía"}`,
      })),
    [shipments.data],
  );

  return (
    <div className="space-y-6">
      <div className="rounded-[32px] border border-line bg-warm-white/90 p-5 shadow-[var(--shadow-1)] sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="label-caps text-text-muted">Logística / Envíos</p>
            <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">Envíos</h1>
            <p className="mt-2 max-w-xl text-sm text-text-muted">
              Clic en dirección o ciudad para editar el espejo. El contraste Envia aparece en
              verde o terracota si hay warning.
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
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!selectedIds.length || formatBatch.isPending}
              onClick={() => formatBatch.mutate(selectedIds)}
            >
              Formatear
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!selectedIds.length || generate.isPending}
              onClick={() => generate.mutate(selectedIds)}
            >
              Generar guías
            </Button>
          </div>
        </div>
      </div>

      <MockModeBanner providers={["envia"]} />

      {batchMsg ? <Alert variant="info">{batchMsg}</Alert> : null}

      {view === "kanban" ? (
        <KanbanBoard
          columns={SHIP_STATUSES.map((s) => ({
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
          data={shipments.data || []}
          columns={columns}
          searchableKeys={[
            "sale_external_id",
            "customer_name",
            "city_mirror",
            "status",
            "tracking_number",
            "address_mirror",
          ]}
          columnFilters={[
            {
              key: "status",
              label: "Estado",
              type: "select",
              options: [...SHIP_STATUSES],
            },
            {
              key: "warning",
              label: "Warning",
              type: "select",
              options: ["true", "false"],
            },
            {
              key: "do_not_ship",
              label: "No enviar",
              type: "select",
              options: ["true", "false"],
            },
            { key: "city_mirror", label: "Ciudad" },
          ]}
          onSelectionChange={setSelected}
          exportFilename="envios.csv"
          hint="Los filtros warning/do_not_ship usan true/false."
          bulkActions={
            <>
              <input
                className="rounded-[999px] border border-line-dark/30 bg-green-950/30 px-3 py-1.5 text-sm text-text-on-dark placeholder:text-text-on-dark-muted"
                placeholder="Ciudad espejo…"
                value={bulkCity}
                onChange={(e) => setBulkCity(e.target.value)}
              />
              <input
                className="rounded-[999px] border border-line-dark/30 bg-green-950/30 px-3 py-1.5 text-sm text-text-on-dark placeholder:text-text-on-dark-muted"
                placeholder="Dpto espejo…"
                value={bulkState}
                onChange={(e) => setBulkState(e.target.value)}
              />
              <Button
                type="button"
                size="sm"
                variant="cream"
                disabled={
                  (!bulkCity && !bulkState) || !selected.length || bulkUpdate.isPending
                }
                onClick={() => {
                  const fields: Record<string, string> = {};
                  if (bulkCity.trim()) fields.city_mirror = bulkCity.trim();
                  if (bulkState.trim()) fields.state_mirror = bulkState.trim();
                  bulkUpdate.mutate({ ids: selectedIds, fields });
                }}
              >
                Aplicar espejos
              </Button>
              <Button
                type="button"
                size="sm"
                variant="cream"
                disabled={!selectedIds.length || formatBatch.isPending}
                onClick={() => formatBatch.mutate(selectedIds)}
              >
                Formatear
              </Button>
              <Button
                type="button"
                size="sm"
                variant="cream"
                disabled={!selectedIds.length || generate.isPending}
                onClick={() => generate.mutate(selectedIds)}
              >
                Generar guías
              </Button>
            </>
          }
          emptyTitle="Sin envíos pendientes"
          emptyDescription="Los pedidos del consolidado con entrega Envia aparecen aquí."
        />
      )}
    </div>
  );
}
