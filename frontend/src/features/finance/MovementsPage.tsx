import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { InlineSelect } from "@/components/ui/InlineSelect";
import { PageHeader } from "@/components/ui/PageHeader";
import { PaginationBar } from "@/components/ui/PaginationBar";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
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

type Bank = { id: string; name: string; active: boolean };
type Paginated<T> = { results: T[]; count: number };
type Account = { id: string; full_label: string; code: string; is_leaf: boolean };
type Kpi = {
  total: number;
  classified: number;
  pending: number;
  pct_classified: number;
};

const STATUS_TABS = [
  { value: "POR_CLASIFICAR", label: "Por clasificar" },
  { value: "CLASIFICADO", label: "Clasificados" },
  { value: "CONCILIADO", label: "Conciliados" },
  { value: "", label: "Todos" },
] as const;

export function MovementsPage() {
  const qc = useQueryClient();
  const now = new Date();
  const monthStart = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
  const today = now.toISOString().slice(0, 10);

  const [status, setStatus] = useState("POR_CLASIFICAR");
  const [bankId, setBankId] = useState("");
  const [item, setItem] = useState("");
  const [dateFrom, setDateFrom] = useState(monthStart);
  const [dateTo, setDateTo] = useState(today);
  const [valueMin, setValueMin] = useState("");
  const [valueMax, setValueMax] = useState("");
  const [conceptInput, setConceptInput] = useState("");
  const concept = useDebouncedValue(conceptInput, 350);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [selected, setSelected] = useState<Movement[]>([]);
  const [efeId, setEfeId] = useState("");
  const [interbank, setInterbank] = useState(false);

  useEffect(() => {
    setPage(1);
    setSelected([]);
  }, [status, bankId, item, dateFrom, dateTo, valueMin, valueMax, concept]);

  const kpi = useQuery({
    queryKey: ["finance-kpi", now.getFullYear(), now.getMonth() + 1],
    queryFn: async () => {
      const { data } = await apiClient.get<Kpi>(
        `/finance/classification/kpi/?year=${now.getFullYear()}&month=${now.getMonth() + 1}`,
      );
      return data;
    },
  });

  const banks = useQuery({
    queryKey: ["finance-banks"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Bank> | Bank[]>(
        "/finance/banks/?page_size=100",
      );
      return Array.isArray(data) ? data : data.results || [];
    },
  });

  const movements = useQuery({
    queryKey: [
      "finance-movements",
      status,
      bankId,
      item,
      dateFrom,
      dateTo,
      valueMin,
      valueMax,
      concept,
      page,
      pageSize,
    ],
    queryFn: async () => {
      const q = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        ordering: "-date",
      });
      if (status) q.set("status", status);
      if (bankId) q.set("bank", bankId);
      if (item) q.set("item", item);
      if (dateFrom) q.set("date_from", dateFrom);
      if (dateTo) q.set("date_to", dateTo);
      if (valueMin.trim()) q.set("value_min", valueMin.trim());
      if (valueMax.trim()) q.set("value_max", valueMax.trim());
      if (concept.trim()) q.set("search", concept.trim());
      const { data } = await apiClient.get<Paginated<Movement>>(
        `/finance/movements/?${q}`,
      );
      return {
        results: data.results || [],
        count: data.count ?? 0,
      };
    },
  });

  const accounts = useQuery({
    queryKey: ["finance-efe-accounts"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Account> | Account[]>(
        "/finance/accounts/efe/?is_leaf=true&page_size=500",
      );
      return Array.isArray(data) ? data : data.results || [];
    },
  });

  const efeOptions = useMemo(
    () => [
      { value: "", label: "— sin cuenta —" },
      ...(accounts.data || []).map((a) => ({
        value: a.id,
        label: a.full_label || a.code,
      })),
    ],
    [accounts.data],
  );

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

  const patchOne = useMutation({
    mutationFn: async (payload: {
      id: string;
      financial_account: string | null;
      is_interbank?: boolean;
    }) => {
      const { data } = await apiClient.patch<Movement>(
        `/finance/movements/${payload.id}/`,
        {
          financial_account: payload.financial_account,
          ...(payload.is_interbank !== undefined
            ? { is_interbank: payload.is_interbank }
            : {}),
        },
      );
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["finance-movements"] });
      void qc.invalidateQueries({ queryKey: ["finance-kpi"] });
    },
  });

  const rows = movements.data?.results || [];
  const totalCount = movements.data?.count || 0;

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
          <span className="block max-w-[280px] truncate" title={String(getValue())}>
            {String(getValue() || "—")}
          </span>
        ),
      },
      {
        id: "efe",
        header: "Cuenta EFE",
        cell: ({ row }) => (
          <InlineSelect
            value={row.original.financial_account || ""}
            display={row.original.efe_label || "Asignar EFE"}
            tone={row.original.financial_account ? "sage" : "terracotta"}
            options={efeOptions}
            onChange={async (next) => {
              await patchOne.mutateAsync({
                id: row.original.id,
                financial_account: next || null,
              });
            }}
          />
        ),
      },
      {
        id: "interbank",
        header: "Interb.",
        cell: ({ row }) => (
          <input
            type="checkbox"
            className="h-4 w-4 accent-green-900"
            checked={row.original.is_interbank}
            title="Marcar interbancario"
            onChange={(e) => {
              void patchOne.mutateAsync({
                id: row.original.id,
                financial_account: row.original.financial_account,
                is_interbank: e.target.checked,
              });
            }}
          />
        ),
      },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ row }) => (
          <Badge variant={row.original.status === "POR_CLASIFICAR" ? "terracotta" : "sage"}>
            {row.original.status.replaceAll("_", " ")}
          </Badge>
        ),
      },
    ],
    [selected, efeOptions, patchOne],
  );

  function clearFilters() {
    setBankId("");
    setItem("");
    setDateFrom(monthStart);
    setDateTo(today);
    setValueMin("");
    setValueMax("");
    setConceptInput("");
  }

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

      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => (
          <Button
            key={tab.label}
            type="button"
            size="sm"
            variant={status === tab.value ? "primary-dark" : "ghost"}
            onClick={() => setStatus(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      <Card className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <div>
            <FieldLabel>Desde</FieldLabel>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div>
            <FieldLabel>Hasta</FieldLabel>
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div>
            <FieldLabel>Banco</FieldLabel>
            <select
              className="mt-0 block h-11 w-full rounded-[16px] border border-line bg-warm-white px-4 text-[15px]"
              value={bankId}
              onChange={(e) => setBankId(e.target.value)}
            >
              <option value="">Todos</option>
              {(banks.data || []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel>Tipo</FieldLabel>
            <select
              className="mt-0 block h-11 w-full rounded-[16px] border border-line bg-warm-white px-4 text-[15px]"
              value={item}
              onChange={(e) => setItem(e.target.value)}
            >
              <option value="">Todos</option>
              <option value="INGRESO">Ingreso</option>
              <option value="EGRESO">Egreso</option>
            </select>
          </div>
          <div>
            <FieldLabel>Valor mín.</FieldLabel>
            <Input
              inputMode="decimal"
              placeholder="0"
              value={valueMin}
              onChange={(e) => setValueMin(e.target.value)}
            />
          </div>
          <div>
            <FieldLabel>Valor máx.</FieldLabel>
            <Input
              inputMode="decimal"
              placeholder="—"
              value={valueMax}
              onChange={(e) => setValueMax(e.target.value)}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <Button type="button" size="sm" variant="outline" onClick={clearFilters}>
            Limpiar filtros
          </Button>
          <p className="text-sm text-text-muted">
            Usa el buscador de la tabla para filtrar por concepto / referencia en toda la base.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3 border-t border-line pt-4">
          <label className="text-xs grow">
            <span className="label-caps text-text-muted">Cuenta EFE (lote)</span>
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
            Clasificar lote ({selected.length})
          </Button>
        </div>

        <p className="text-sm text-text-muted">
          Clic en la cuenta EFE de cada fila para clasificar o reclasificar. Usa la pestaña
          «Clasificados» para revisar lo ya asignado.
        </p>

        <PaginationBar
          page={page}
          pageSize={pageSize}
          total={totalCount}
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

        <DataTable
          data={rows}
          columns={columns}
          searchQuery={conceptInput}
          onSearchQueryChange={setConceptInput}
          searchTotalCount={totalCount}
          emptyTitle="Sin movimientos"
          emptyDescription="Ajusta filtros o importa extractos bancarios."
        />
      </Card>
    </div>
  );
}
