import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";

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

export function CustomersPage() {
  const qc = useQueryClient();
  const customers = useQuery({
    queryKey: ["customers"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Customer> | Customer[]>(
        "/accounting/customers/",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const sync = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/accounting/customers/${id}/sync-alegra/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });

  const columns = useMemo<ColumnDef<Customer, unknown>[]>(
    () => [
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
            onClick={() => sync.mutate(row.original.id)}
          >
            Sincronizar
          </Button>
        ),
      },
    ],
    [sync],
  );

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Contabilidad"
        title="Clientes"
        actions={
          <>
            <Link
              to="/accounting"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Facturas
            </Link>
          </>
        }
      />

      <DataTable
        data={customers.data || []}
        columns={columns}
        searchableKeys={["name", "id_number", "email", "city"]}
        emptyTitle="Sin clientes"
        emptyDescription="Aparecen al promover ventas al consolidado."
      />
    </div>
  );
}
