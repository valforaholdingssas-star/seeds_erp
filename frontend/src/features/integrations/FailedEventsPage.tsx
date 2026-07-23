import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";

type EventRow = {
  id: string;
  source: string;
  event_type: string;
  status: string;
  error: string;
  attempts: number;
  received_at: string;
};

type Paginated<T> = { count: number; results: T[] };

export function FailedEventsPage() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState<string | null>(null);

  const events = useQuery({
    queryKey: ["integration-events"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<EventRow> | EventRow[]>(
        "/integrations/events/?status=FAILED",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const reprocess = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/integrations/events/${id}/reprocess/`);
    },
    onSuccess: () => {
      setMsg("Evento encolado para reprocesar.");
      qc.invalidateQueries({ queryKey: ["integration-events"] });
    },
  });

  const columns = useMemo<ColumnDef<EventRow, unknown>[]>(
    () => [
      { accessorKey: "source", header: "Fuente" },
      { accessorKey: "event_type", header: "Tipo" },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ row }) => <Badge variant="wine">{row.original.status}</Badge>,
      },
      { accessorKey: "attempts", header: "Intentos" },
      {
        accessorKey: "error",
        header: "Error",
        cell: ({ row }) => (
          <span className="line-clamp-2 max-w-xs text-xs text-text-muted">
            {row.original.error || "—"}
          </span>
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
            onClick={() => reprocess.mutate(row.original.id)}
          >
            Reprocesar
          </Button>
        ),
      },
    ],
    [reprocess],
  );

  return (
    <div className="space-y-3">
      <PageHeader eyebrow="Integraciones" title="Eventos fallidos" />
      {msg && <Alert variant="success">{msg}</Alert>}
      <DataTable
        data={events.data || []}
        columns={columns}
        searchableKeys={["source", "event_type", "error"]}
        columnFilters={[
          { key: "source", label: "Fuente", type: "select", options: ["WOOCOMMERCE", "KOMMO"] },
        ]}
        emptyTitle="Sin fallos"
        emptyDescription="Los webhooks fallidos aparecen aquí para recovery."
        exportFilename="eventos-fallidos.csv"
      />
    </div>
  );
}
