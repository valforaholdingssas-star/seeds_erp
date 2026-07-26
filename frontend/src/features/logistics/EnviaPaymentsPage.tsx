import { useQuery } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PaginationBar } from "@/components/ui/PaginationBar";
import { formatCOP } from "@/lib/utils";

type EnviaPayment = {
  id: string;
  sale_external_id: string;
  customer_name: string;
  status: string;
  carrier: string;
  service: string;
  tracking_number: string;
  shipping_cost: string;
  envia_shipment_id: string;
  city: string;
  sent_at: string | null;
  created_at: string | null;
};

type EnviaPaymentsResponse = {
  count: number;
  total_paid: string;
  page: number;
  page_size: number;
  results: EnviaPayment[];
  hint: string;
};

export function EnviaPaymentsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const yearStart = `${new Date().getFullYear()}-01-01`;
  const [from, setFrom] = useState(yearStart);
  const [to, setTo] = useState(today);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const data = useQuery({
    queryKey: ["envia-payments", from, to, page, pageSize],
    queryFn: async () => {
      const q = new URLSearchParams({
        from,
        to,
        page: String(page),
        page_size: String(pageSize),
      });
      const { data: res } = await apiClient.get<EnviaPaymentsResponse>(
        `/logistics/envia-payments/?${q}`,
      );
      return res;
    },
  });

  const columns = useMemo<ColumnDef<EnviaPayment, unknown>[]>(
    () => [
      { accessorKey: "sale_external_id", header: "Pedido" },
      { accessorKey: "customer_name", header: "Cliente" },
      { accessorKey: "city", header: "Ciudad" },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ getValue }) => <Badge variant="dark">{String(getValue())}</Badge>,
      },
      { accessorKey: "carrier", header: "Carrier" },
      { accessorKey: "tracking_number", header: "Guía" },
      {
        accessorKey: "shipping_cost",
        header: "Pago Envia",
        cell: ({ getValue }) => formatCOP(Number(getValue() || 0)),
      },
      {
        id: "when",
        header: "Fecha",
        cell: ({ row }) =>
          (row.original.sent_at || row.original.created_at || "—").slice(0, 10),
      },
    ],
    [],
  );

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Logística"
        title="Pagos Envia"
        actions={
          <>
            <Link
              to="/logistics"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Envíos
            </Link>
            <Link
              to="/expenses"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Gastos
            </Link>
          </>
        }
      />

      <p className="max-w-3xl text-sm text-text-muted">
        Registro de costos de guía pagados a Envia (gasto a terceros). Panel aparte de
        gastos operativos; aún no se sincroniza con Alegra.
      </p>

      <Card tone="cream" className="grid max-w-xl gap-4 sm:grid-cols-2">
        <div>
          <FieldLabel>Desde</FieldLabel>
          <Input
            type="date"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div>
          <FieldLabel>Hasta</FieldLabel>
          <Input
            type="date"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </Card>

      <Card className="seeds-panel max-w-sm">
        <p className="label-caps text-text-muted">Total pagado a Envia</p>
        <p className="mt-3 font-serif text-4xl text-green-900">
          {formatCOP(Number(data.data?.total_paid || 0))}
        </p>
        <p className="mt-2 text-sm text-text-muted">
          {data.data?.count ?? 0} guías con costo
        </p>
      </Card>

      <PaginationBar
        page={page}
        pageSize={pageSize}
        total={data.data?.count || 0}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
      />

      <DataTable
        data={data.data?.results || []}
        columns={columns}
        searchableKeys={["sale_external_id", "customer_name", "tracking_number", "city"]}
        emptyTitle="Sin pagos Envia"
        emptyDescription="Aparecen cuando una guía genera shipping_cost."
        hint={data.data?.hint}
      />
    </div>
  );
}
