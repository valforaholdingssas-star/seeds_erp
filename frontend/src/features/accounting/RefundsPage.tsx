import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

type Refund = {
  id: string;
  invoice_number: string;
  sale_external_id: string;
  status: string;
  reason: string;
  alegra_credit_note_id: string;
  manual_void_pending: boolean;
  created_at: string;
};

type Paginated<T> = { count: number; results: T[] };

export function RefundsPage() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState<string | null>(null);

  const refunds = useQuery({
    queryKey: ["refunds"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Refund> | Refund[]>(
        "/accounting/refunds/",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const confirm = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/accounting/refunds/${id}/confirm-void/`);
    },
    onSuccess: () => {
      setMsg("Anulación manual confirmada.");
      qc.invalidateQueries({ queryKey: ["refunds"] });
    },
  });

  const columns = useMemo<ColumnDef<Refund, unknown>[]>(
    () => [
      { accessorKey: "invoice_number", header: "Factura" },
      { accessorKey: "sale_external_id", header: "Venta" },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ row }) => <Badge variant="terracotta">{row.original.status}</Badge>,
      },
      { accessorKey: "reason", header: "Motivo" },
      {
        accessorKey: "manual_void_pending",
        header: "Anular DIAN",
        cell: ({ row }) =>
          row.original.manual_void_pending ? (
            <Badge variant="wine">Pendiente</Badge>
          ) : (
            <Badge variant="sage">OK</Badge>
          ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) =>
          row.original.manual_void_pending ? (
            <Button
              type="button"
              size="sm"
              variant="primary-wine"
              onClick={() => confirm.mutate(row.original.id)}
            >
              Confirmar anulación
            </Button>
          ) : null,
      },
    ],
    [confirm],
  );

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-caps text-text-muted">Contabilidad</p>
          <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">Reembolsos</h1>
          <p className="mt-2 max-w-xl text-text-muted">
            Notas crédito emitidas. Confirma la anulación manual cuando esté lista en Alegra/DIAN.
          </p>
        </div>
        <Link
          to="/accounting"
          className="inline-flex min-h-11 items-center rounded-[999px] border border-line px-6 label-caps"
        >
          Facturas
        </Link>
      </header>
      {msg && <Alert variant="success">{msg}</Alert>}
      <DataTable
        data={refunds.data || []}
        columns={columns}
        searchableKeys={["invoice_number", "sale_external_id", "reason", "status"]}
        columnFilters={[
          {
            key: "status",
            label: "Estado",
            type: "select",
            options: ["NOTA_CREDITO_EMITIDA", "CERRADO"],
          },
        ]}
        emptyTitle="Sin reembolsos"
        emptyDescription="Aparecen al registrar un reembolso desde facturas."
      />
    </div>
  );
}
