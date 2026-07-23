import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

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
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-caps text-text-muted">Contabilidad</p>
          <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">Clientes</h1>
          <p className="mt-2 max-w-xl text-text-muted">
            Se crean al consolidar ventas y se sincronizan con Alegra antes de facturar.
          </p>
        </div>
        <Link
          to="/accounting"
          className="inline-flex min-h-11 items-center rounded-[999px] border border-line px-6 label-caps"
        >
          Facturas
        </Link>
      </header>

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
