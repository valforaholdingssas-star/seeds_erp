import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { KanbanBoard, type KanbanItem } from "@/components/kanban/KanbanBoard";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";

type ExpenseStatus = {
  id: string;
  key: string;
  label: string;
  order: number;
  feeds_efe: boolean;
  color: string;
};

type Expense = {
  id: string;
  title: string;
  concept: string;
  amount: string;
  bank_account: string | null;
  bank_name: string;
  expense_date: string;
  efe_account: string | null;
  efe_label: string;
  status: string;
  status_key: string;
  status_label: string;
  status_color: string;
  feeds_efe: boolean;
  responsible_name: string;
  iva_discountable: string | null;
  iva_already_discounted: boolean;
  amortize: boolean;
  amortization_months: number | null;
  reconciled: boolean;
  has_payment_proof: boolean;
  has_provider_invoice: boolean;
};

type Paginated<T> = { results: T[]; count: number };
type Account = { id: string; full_label: string; code: string; is_leaf: boolean };
type Bank = { id: string; name: string };

type Tab = "board" | "table" | "reembolsos" | "iva";

function money(v: string | number | null | undefined) {
  if (v == null || v === "") return "—";
  return formatCOP(Number(v));
}

export function ExpensesPage() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "board";
  const statusKeyFilter = params.get("status_key") || "";
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Expense[]>([]);
  const [bulkEfe, setBulkEfe] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    amount: "",
    expense_date: new Date().toISOString().slice(0, 10),
    bank_account: "",
    efe_account: "",
    status: "",
    nature: "EMPRESA",
    on_behalf_of: "",
    amortize: false,
    amortization_months: "",
    iva_discountable: "",
  });

  const statuses = useQuery({
    queryKey: ["expense-statuses"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<ExpenseStatus> | ExpenseStatus[]>(
        "/expenses/statuses/?active=true&page_size=50",
      );
      const rows = Array.isArray(data) ? data : data.results || [];
      return [...rows].sort((a, b) => a.order - b.order);
    },
  });

  const expenses = useQuery({
    queryKey: ["expenses", statusKeyFilter, "EMPRESA"],
    queryFn: async () => {
      const q = new URLSearchParams({ page_size: "300", nature: "EMPRESA" });
      if (statusKeyFilter) q.set("status_key", statusKeyFilter);
      const { data } = await apiClient.get<Paginated<Expense> | Expense[]>(
        `/expenses/?${q}`,
      );
      return Array.isArray(data) ? data : data.results || [];
    },
  });

  const reimbursements = useQuery({
    queryKey: ["expenses-reimb"],
    enabled: tab === "reembolsos",
    queryFn: async () => {
      const { data } = await apiClient.get<{
        total_amount: string;
        results: Expense[];
      }>("/expenses/reimbursements/");
      return data;
    },
  });

  const iva = useQuery({
    queryKey: ["expenses-iva"],
    enabled: tab === "iva",
    queryFn: async () => {
      const { data } = await apiClient.get<{ total_iva: string; results: Expense[] }>(
        "/expenses/iva/?pending=true&nature=EMPRESA",
      );
      return data;
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

  const banks = useQuery({
    queryKey: ["finance-banks"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Bank> | Bank[]>(
        "/finance/banks/?page_size=50",
      );
      return Array.isArray(data) ? data : data.results || [];
    },
  });

  const detail = useQuery({
    queryKey: ["expense", detailId],
    enabled: !!detailId,
    queryFn: async () => {
      const { data } = await apiClient.get<Expense>(`/expenses/${detailId}/`);
      return data;
    },
  });

  const createMut = useMutation({
    mutationFn: async (e: FormEvent) => {
      e.preventDefault();
      setError(null);
      const status =
        form.status ||
        statuses.data?.find((s) => s.key === "GASTOS_POR_REGISTRAR")?.id ||
        statuses.data?.[0]?.id;
      await apiClient.post("/expenses/", {
        title: form.title,
        concept: form.title,
        amount: form.amount,
        expense_date: form.expense_date,
        bank_account: form.bank_account || null,
        efe_account: form.nature === "NOMINAL" ? null : form.efe_account || null,
        nature: form.nature,
        on_behalf_of: form.on_behalf_of,
        status,
        amortize: form.nature === "EMPRESA" ? form.amortize : false,
        amortization_months:
          form.nature === "EMPRESA" && form.amortization_months
            ? Number(form.amortization_months)
            : null,
        iva_discountable: form.iva_discountable || null,
      });
    },
    onSuccess: () => {
      const wasNominal = form.nature === "NOMINAL";
      setForm((f) => ({
        ...f,
        title: "",
        amount: "",
        iva_discountable: "",
        on_behalf_of: "",
        nature: "EMPRESA",
      }));
      void qc.invalidateQueries({ queryKey: ["expenses"] });
      void qc.invalidateQueries({ queryKey: ["expenses-nominal"] });
      if (wasNominal) {
        setError(null);
        window.location.assign("/expenses/nominales");
      }
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "No se pudo crear el gasto";
      setError(String(msg));
    },
  });

  const transitionMut = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) => {
      setError(null);
      const { data } = await apiClient.post(`/expenses/${id}/transition/`, { status });
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["expenses"] });
      void qc.invalidateQueries({ queryKey: ["expense"] });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Transición rechazada";
      setError(String(msg));
    },
  });

  const bulkMut = useMutation({
    mutationFn: async () => {
      await apiClient.post("/expenses/bulk-update/", {
        ids: selected.map((s) => s.id),
        efe_account: bulkEfe || null,
      });
    },
    onSuccess: () => {
      setSelected([]);
      void qc.invalidateQueries({ queryKey: ["expenses"] });
    },
  });

  const uploadMut = useMutation({
    mutationFn: async ({
      id,
      kind,
      file,
    }: {
      id: string;
      kind: string;
      file: File;
    }) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("kind", kind);
      await apiClient.post(`/expenses/${id}/attachments/`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["expense"] });
      void qc.invalidateQueries({ queryKey: ["expenses"] });
    },
  });

  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params);
    next.set("tab", t);
    setParams(next);
  };

  const columns = useMemo<ColumnDef<Expense, unknown>[]>(
    () => [
      {
        id: "sel",
        header: "",
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={selected.some((s) => s.id === row.original.id)}
            onChange={(e) => {
              if (e.target.checked) setSelected((s) => [...s, row.original]);
              else setSelected((s) => s.filter((x) => x.id !== row.original.id));
            }}
          />
        ),
      },
      {
        accessorKey: "expense_date",
        header: "Fecha",
      },
      {
        accessorKey: "title",
        header: "Título",
        cell: ({ row }) => (
          <button
            type="button"
            className="text-left text-green-900 hover:underline"
            onClick={() => setDetailId(row.original.id)}
          >
            {row.original.title}
          </button>
        ),
      },
      {
        accessorKey: "amount",
        header: "Monto",
        cell: ({ row }) => money(row.original.amount),
      },
      {
        accessorKey: "status_label",
        header: "Estado",
        cell: ({ row }) => (
          <Badge variant={row.original.status_color === "wine" ? "wine" : "sage"}>
            {row.original.status_label}
          </Badge>
        ),
      },
      { accessorKey: "efe_label", header: "Cuenta EFE" },
      { accessorKey: "bank_name", header: "Banco" },
      {
        id: "docs",
        header: "Docs",
        cell: ({ row }) => (
          <span className="text-xs text-text-muted">
            {row.original.has_payment_proof ? "✓ pago" : "· pago"} ·{" "}
            {row.original.has_provider_invoice ? "✓ factura" : "· factura"}
          </span>
        ),
      },
    ],
    [selected],
  );

  const kanbanItems: KanbanItem[] = useMemo(
    () =>
      (expenses.data || []).map((e) => ({
        id: e.id,
        columnId: e.status,
        title: e.title,
        subtitle: `${money(e.amount)} · ${e.expense_date}`,
      })),
    [expenses.data],
  );

  const kanbanColumns = useMemo(
    () =>
      (statuses.data || []).map((s) => ({
        id: s.id,
        label: s.label,
        badge: (
          <span className="text-xs text-text-muted">
            {(expenses.data || []).filter((e) => e.status === s.id).length}
          </span>
        ),
      })),
    [statuses.data, expenses.data],
  );

  const rowsForTable =
    tab === "reembolsos"
      ? reimbursements.data?.results || []
      : tab === "iva"
        ? iva.data?.results || []
        : expenses.data || [];

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Finanzas" title="Gastos" />

      {error ? <Alert variant="error">{error}</Alert> : null}

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["board", "Board"],
            ["table", "Table"],
            ["reembolsos", "Reembolsos"],
            ["iva", "IVA"],
          ] as const
        ).map(([k, label]) => (
          <Button
            key={k}
            variant={tab === k ? "primary-dark" : "ghost"}
            size="sm"
            onClick={() => setTab(k)}
          >
            {label}
          </Button>
        ))}
      </div>

      <Card>
        <form className="grid gap-3 md:grid-cols-4" onSubmit={(e) => createMut.mutate(e)}>
          <div className="md:col-span-2">
            <FieldLabel>Título</FieldLabel>
            <Input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel>Monto (total)</FieldLabel>
            <Input
              required
              type="number"
              step="0.01"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel>IVA descontable</FieldLabel>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.iva_discountable}
              onChange={(e) => setForm({ ...form, iva_discountable: e.target.value })}
              placeholder="0.00"
            />
          </div>
          <div>
            <FieldLabel>Fecha</FieldLabel>
            <Input
              required
              type="date"
              value={form.expense_date}
              onChange={(e) => setForm({ ...form, expense_date: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel>Naturaleza</FieldLabel>
            <select
              className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
              value={form.nature}
              onChange={(e) => setForm({ ...form, nature: e.target.value })}
            >
              <option value="EMPRESA">De la empresa (EFE / contabilidad)</option>
              <option value="NOMINAL">
                Nominal — a nombre de Seeds, no es de la empresa
              </option>
            </select>
          </div>
          {form.nature === "NOMINAL" ? (
            <div>
              <FieldLabel>A nombre real de</FieldLabel>
              <Input
                value={form.on_behalf_of}
                onChange={(e) => setForm({ ...form, on_behalf_of: e.target.value })}
                placeholder="Persona / tercero"
              />
            </div>
          ) : null}
          <div>
            <FieldLabel>Banco</FieldLabel>
            <select
              className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
              value={form.bank_account}
              onChange={(e) => setForm({ ...form, bank_account: e.target.value })}
            >
              <option value="">—</option>
              {(banks.data || []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          {form.nature === "EMPRESA" ? (
            <div>
              <FieldLabel>Cuenta EFE</FieldLabel>
              <select
                className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
                value={form.efe_account}
                onChange={(e) => setForm({ ...form, efe_account: e.target.value })}
              >
                <option value="">—</option>
                {(accounts.data || [])
                  .filter((a) => a.is_leaf)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.full_label}
                    </option>
                  ))}
              </select>
            </div>
          ) : null}
          <div>
            <FieldLabel>Estado</FieldLabel>
            <select
              className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
            >
              {(statuses.data || [])
                .filter((s) => form.nature === "EMPRESA" || !s.feeds_efe)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
            </select>
          </div>
          {form.nature === "EMPRESA" ? (
            <div className="flex items-end gap-3">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.amortize}
                  onChange={(e) => setForm({ ...form, amortize: e.target.checked })}
                />
                Amortizar
              </label>
              {form.amortize ? (
                <Input
                  type="number"
                  min={1}
                  placeholder="Meses"
                  value={form.amortization_months}
                  onChange={(e) =>
                    setForm({ ...form, amortization_months: e.target.value })
                  }
                />
              ) : null}
            </div>
          ) : (
            <p className="md:col-span-2 self-end text-xs text-terracotta-600">
              Al guardar se enviará al módulo de gastos nominales (sin EFE).
            </p>
          )}
          <div className="flex items-end">
            <Button type="submit" disabled={createMut.isPending}>
              Crear gasto
            </Button>
          </div>
        </form>
      </Card>

      {tab === "reembolsos" ? (
        <p className="text-sm text-text-muted">
          Total por pagar: <strong>{money(reimbursements.data?.total_amount)}</strong>
        </p>
      ) : null}
      {tab === "iva" ? (
        <p className="text-sm text-text-muted">
          IVA pendiente: <strong>{money(iva.data?.total_iva)}</strong>
        </p>
      ) : null}

      {tab === "board" ? (
        <KanbanBoard
          columns={kanbanColumns}
          items={kanbanItems}
          onMove={(itemId, toColumnId) =>
            transitionMut.mutate({ id: itemId, status: toColumnId })
          }
          renderCard={(item) => {
            const exp = (expenses.data || []).find((e) => e.id === item.id);
            return (
              <button
                type="button"
                className="w-full text-left"
                onClick={() => setDetailId(item.id)}
              >
                <p className="font-medium text-green-900 line-clamp-2">{item.title}</p>
                <p className="mt-1 text-xs text-text-muted">{item.subtitle}</p>
                {exp?.efe_label ? (
                  <p className="mt-1 text-[11px] text-sage-700">{exp.efe_label}</p>
                ) : null}
              </button>
            );
          }}
        />
      ) : (
        <>
          {selected.length > 0 ? (
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[240px] flex-1">
                <FieldLabel>Atribuir EFE a {selected.length} gastos</FieldLabel>
                <select
                  className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
                  value={bulkEfe}
                  onChange={(e) => setBulkEfe(e.target.value)}
                >
                  <option value="">—</option>
                  {(accounts.data || [])
                    .filter((a) => a.is_leaf)
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.full_label}
                      </option>
                    ))}
                </select>
              </div>
              <Button
                onClick={() => bulkMut.mutate()}
                disabled={!bulkEfe || bulkMut.isPending}
              >
                Aplicar
              </Button>
            </div>
          ) : null}
          <DataTable columns={columns} data={rowsForTable} />
        </>
      )}

      {detailId && detail.data ? (
        <Card className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="font-serif text-xl text-green-900">{detail.data.title}</h3>
              <p className="text-sm text-text-muted">
                {money(detail.data.amount)} · {detail.data.expense_date} ·{" "}
                {detail.data.status_label}
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setDetailId(null)}>
              Cerrar
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2 text-sm">
            <p>
              <span className="text-text-muted">EFE:</span> {detail.data.efe_label || "—"}
            </p>
            <p>
              <span className="text-text-muted">Banco:</span> {detail.data.bank_name || "—"}
            </p>
            <p>
              <span className="text-text-muted">IVA descontable:</span>{" "}
              {money(detail.data.iva_discountable)}
              {detail.data.iva_already_discounted ? " (ya descontado)" : ""}
            </p>
            <p>
              <span className="text-text-muted">Conciliado:</span>{" "}
              {detail.data.reconciled ? "Sí" : "No"}
            </p>
            <p>
              <span className="text-text-muted">Amortización:</span>{" "}
              {detail.data.amortize
                ? `${detail.data.amortization_months || 1} meses`
                : "No (N=1)"}
            </p>
          </div>
          <div className="flex flex-wrap gap-4">
            <label className="text-sm">
              Subir comprobante
              <input
                type="file"
                accept="image/*,application/pdf"
                className="mt-1 block text-xs"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file)
                    uploadMut.mutate({
                      id: detail.data!.id,
                      kind: "PAYMENT_PROOF",
                      file,
                    });
                }}
              />
            </label>
            <label className="text-sm">
              Subir factura
              <input
                type="file"
                accept="image/*,application/pdf"
                className="mt-1 block text-xs"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file)
                    uploadMut.mutate({
                      id: detail.data!.id,
                      kind: "PROVIDER_INVOICE",
                      file,
                    });
                }}
              />
            </label>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
