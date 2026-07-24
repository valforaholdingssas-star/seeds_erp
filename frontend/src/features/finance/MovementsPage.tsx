import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";

type Movement = {
  id: string;
  bank: string;
  bank_name: string;
  date: string;
  value: string;
  item: string;
  concept: string;
  status: string;
  is_interbank: boolean;
  efe_label: string;
  financial_account: string | null;
};

type Paginated<T> = { results: T[]; count: number };
type Account = { id: string; full_label: string; code: string; is_leaf: boolean };
type Kpi = {
  total: number;
  classified: number;
  pending: number;
  pct_classified: number;
};

export function MovementsPage() {
  const qc = useQueryClient();
  const now = new Date();
  const [status, setStatus] = useState("POR_CLASIFICAR");
  const [selected, setSelected] = useState<Movement[]>([]);
  const [efeId, setEfeId] = useState("");
  const [interbank, setInterbank] = useState(false);

  const kpi = useQuery({
    queryKey: ["finance-kpi", now.getFullYear(), now.getMonth() + 1],
    queryFn: async () => {
      const { data } = await apiClient.get<Kpi>(
        `/finance/classification/kpi/?year=${now.getFullYear()}&month=${now.getMonth() + 1}`,
      );
      return data;
    },
  });

  const movements = useQuery({
    queryKey: ["finance-movements", status],
    queryFn: async () => {
      const q = status ? `?status=${status}&page_size=200` : "?page_size=200";
      const { data } = await apiClient.get<Paginated<Movement> | Movement[]>(
        `/finance/movements/${q}`,
      );
      return Array.isArray(data) ? data : data.results || [];
    },
  });

  const accounts = useQuery({
    queryKey: ["finance-efe-accounts"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Account> | Account[]>(
        "/finance/accounts/efe/?is_leaf=true&page_size=200",
      );
      return Array.isArray(data) ? data : data.results || [];
    },
  });

  const classify = useMutation({
    mutationFn: async () => {
      await apiClient.post("/finance/movements/bulk-classify/", {
        ids: selected.map((s) => s.id),
        financial_account: efeId || null,
        is_interbank: interbank,
      });
    },
    onSuccess: () => {
      setSelected([]);
      void qc.invalidateQueries({ queryKey: ["finance-movements"] });
      void qc.invalidateQueries({ queryKey: ["finance-kpi"] });
    },
  });

  const columns = useMemo<ColumnDef<Movement, unknown>[]>(
    () => [
      {
        id: "select",
        header: "",
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={selected.some((s) => s.id === row.original.id)}
            onChange={(e) => {
              if (e.target.checked) setSelected((s) => [...s, row.original]);
              else setSelected((s) => s.filter((x) => x.id !== row.original.id));
            }}
            className="h-4 w-4 accent-green-900"
          />
        ),
      },
      { accessorKey: "date", header: "Fecha" },
      { accessorKey: "bank_name", header: "Banco" },
      {
        accessorKey: "item",
        header: "Tipo",
        cell: ({ getValue }) => (
          <Badge variant={getValue() === "INGRESO" ? "sage" : "wine"}>
            {String(getValue())}
          </Badge>
        ),
      },
      {
        accessorKey: "value",
        header: "Valor",
        cell: ({ getValue }) => formatCOP(Number(getValue())),
      },
      {
        accessorKey: "concept",
        header: "Concepto",
        cell: ({ getValue }) => (
          <span className="max-w-[280px] truncate block" title={String(getValue())}>
            {String(getValue() || "—")}
          </span>
        ),
      },
      {
        accessorKey: "efe_label",
        header: "Cuenta EFE",
        cell: ({ row }) => row.original.efe_label || "—",
      },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ row }) => (
          <div className="flex flex-col gap-1">
            <Badge variant={row.original.status === "POR_CLASIFICAR" ? "terracotta" : "sage"}>
              {row.original.status}
            </Badge>
            {row.original.is_interbank ? <Badge variant="dark">Interbancario</Badge> : null}
          </div>
        ),
      },
    ],
    [selected],
  );

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Finanzas"
        title="Clasificación de movimientos"
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              to="/finance"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              EFE
            </Link>
            <Link
              to="/finance/import"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Importar
            </Link>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <p className="label-caps text-text-muted">Clasificado mes</p>
          <p className="mt-1 font-serif text-3xl text-green-900">
            {kpi.data ? `${kpi.data.pct_classified}%` : "—"}
          </p>
        </Card>
        <Card>
          <p className="label-caps text-text-muted">Pendientes</p>
          <p className="mt-1 font-serif text-3xl text-wine-900">{kpi.data?.pending ?? "—"}</p>
        </Card>
        <Card>
          <p className="label-caps text-text-muted">Total mes</p>
          <p className="mt-1 font-serif text-3xl text-green-900">{kpi.data?.total ?? "—"}</p>
        </Card>
      </div>

      <Card>
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <label className="text-xs">
            <span className="label-caps text-text-muted">Filtro estado</span>
            <select
              className="mt-1 block h-9 rounded-full border border-line bg-cream-50 px-3"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">Todos</option>
              <option value="POR_CLASIFICAR">Por clasificar</option>
              <option value="CLASIFICADO">Clasificado</option>
              <option value="CONCILIADO">Conciliado</option>
            </select>
          </label>
          <label className="text-xs grow">
            <span className="label-caps text-text-muted">Cuenta EFE</span>
            <select
              className="mt-1 block h-9 w-full max-w-md rounded-full border border-line bg-cream-50 px-3"
              value={efeId}
              onChange={(e) => setEfeId(e.target.value)}
            >
              <option value="">— seleccionar —</option>
              {(accounts.data || []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.full_label || a.code}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs text-green-900">
            <input
              type="checkbox"
              checked={interbank}
              onChange={(e) => setInterbank(e.target.checked)}
              className="accent-green-900"
            />
            Interbancario
          </label>
          <Button
            type="button"
            disabled={!selected.length || classify.isPending}
            onClick={() => classify.mutate()}
          >
            Clasificar ({selected.length})
          </Button>
        </div>

        <DataTable
          data={movements.data || []}
          columns={columns}
          searchableKeys={["bank_name", "concept", "item", "status", "efe_label"]}
        />
      </Card>
    </div>
  );
}
