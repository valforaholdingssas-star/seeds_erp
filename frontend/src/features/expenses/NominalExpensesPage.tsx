import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonVariants } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn, formatCOP } from "@/lib/utils";

type Expense = {
  id: string;
  title: string;
  amount: string;
  expense_date: string;
  nature: string;
  on_behalf_of: string;
  iva_discountable: string | null;
  iva_already_discounted: boolean;
  status_label: string;
  bank_name: string;
  has_payment_proof: boolean;
  has_provider_invoice: boolean;
};

type Paginated<T> = { results: T[]; count: number };
type Bank = { id: string; name: string };
type ExpenseStatus = { id: string; key: string; label: string; feeds_efe: boolean };

function money(v: string | number | null | undefined) {
  if (v == null || v === "") return "—";
  return formatCOP(Number(v));
}

export function NominalExpensesPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    amount: "",
    expense_date: new Date().toISOString().slice(0, 10),
    on_behalf_of: "",
    iva_discountable: "",
    bank_account: "",
    status: "",
  });
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [invoiceFile, setInvoiceFile] = useState<File | null>(null);

  const statuses = useQuery({
    queryKey: ["expense-statuses"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<ExpenseStatus> | ExpenseStatus[]>(
        "/expenses/statuses/?active=true&page_size=50",
      );
      const rows = Array.isArray(data) ? data : data.results || [];
      return rows.filter((s) => !s.feeds_efe);
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

  const expenses = useQuery({
    queryKey: ["expenses-nominal"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Expense> | Expense[]>(
        "/expenses/?nature=NOMINAL&page_size=300",
      );
      return Array.isArray(data) ? data : data.results || [];
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
      const { data } = await apiClient.post<Expense>("/expenses/", {
        title: form.title,
        concept: form.title,
        amount: form.amount,
        expense_date: form.expense_date,
        nature: "NOMINAL",
        on_behalf_of: form.on_behalf_of,
        iva_discountable: form.iva_discountable || null,
        bank_account: form.bank_account || null,
        efe_account: null,
        status,
      });
      for (const [kind, file] of [
        ["PAYMENT_PROOF", proofFile],
        ["PROVIDER_INVOICE", invoiceFile],
      ] as const) {
        if (!file) continue;
        const fd = new FormData();
        fd.append("file", file);
        fd.append("kind", kind);
        await apiClient.post(`/expenses/${data.id}/attachments/`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      }
      return data;
    },
    onSuccess: () => {
      setForm((f) => ({
        ...f,
        title: "",
        amount: "",
        on_behalf_of: "",
        iva_discountable: "",
      }));
      setProofFile(null);
      setInvoiceFile(null);
      void qc.invalidateQueries({ queryKey: ["expenses-nominal"] });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "No se pudo crear";
      setError(String(msg));
    },
  });

  const columns = useMemo<ColumnDef<Expense, unknown>[]>(
    () => [
      { accessorKey: "expense_date", header: "Fecha" },
      { accessorKey: "title", header: "Título" },
      { accessorKey: "on_behalf_of", header: "A nombre real de" },
      {
        accessorKey: "amount",
        header: "Monto",
        cell: ({ row }) => money(row.original.amount),
      },
      {
        accessorKey: "iva_discountable",
        header: "IVA",
        cell: ({ row }) => money(row.original.iva_discountable),
      },
      { accessorKey: "bank_name", header: "Banco" },
      {
        accessorKey: "status_label",
        header: "Estado",
        cell: ({ row }) => <Badge variant="terracotta">{row.original.status_label}</Badge>,
      },
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
    [],
  );

  const total = (expenses.data || []).reduce((s, e) => s + Number(e.amount || 0), 0);
  const totalIva = (expenses.data || []).reduce(
    (s, e) => s + Number(e.iva_discountable || 0),
    0,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Contabilidad"
        title="Gastos nominales"
        actions={
          <Link
            to="/expenses"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            Gastos de la empresa
          </Link>
        }
      />

      <Alert variant="caution">
        Gastos tramitados a nombre de Seeds pero que <strong>no son de la empresa</strong>.
        No alimentan el EFE, no van a Alegra/contabilidad Seeds y no afectan el modelo
        financiero. Solo para control del contador.
      </Alert>

      {error ? <Alert variant="error">{error}</Alert> : null}

      <div className="flex flex-wrap gap-6 text-sm">
        <p>
          Total: <strong className="font-serif text-lg">{money(total)}</strong>
        </p>
        <p>
          IVA: <strong className="font-serif text-lg">{money(totalIva)}</strong>
        </p>
        <p className="text-text-muted">{expenses.data?.length || 0} registros</p>
      </div>

      <Card>
        <form className="grid gap-3 md:grid-cols-4" onSubmit={(e) => createMut.mutate(e)}>
          <div className="md:col-span-2">
            <FieldLabel>Título / concepto</FieldLabel>
            <Input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel>A nombre real de</FieldLabel>
            <Input
              value={form.on_behalf_of}
              onChange={(e) => setForm({ ...form, on_behalf_of: e.target.value })}
              placeholder="Persona / tercero"
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
            <FieldLabel>Banco (si aplica)</FieldLabel>
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
          <div>
            <FieldLabel>Estado</FieldLabel>
            <select
              className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
            >
              {(statuses.data || []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel>Factura proveedor</FieldLabel>
            <Input
              type="file"
              accept="image/*,.pdf"
              onChange={(e) => setInvoiceFile(e.target.files?.[0] || null)}
            />
            {invoiceFile ? (
              <p className="mt-1 truncate text-xs text-text-muted">{invoiceFile.name}</p>
            ) : null}
          </div>
          <div>
            <FieldLabel>Comprobante de pago</FieldLabel>
            <Input
              type="file"
              accept="image/*,.pdf"
              onChange={(e) => setProofFile(e.target.files?.[0] || null)}
            />
            {proofFile ? (
              <p className="mt-1 truncate text-xs text-text-muted">{proofFile.name}</p>
            ) : null}
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={createMut.isPending}>
              {createMut.isPending ? "Guardando…" : "Registrar nominal"}
            </Button>
          </div>
        </form>
      </Card>

      <DataTable columns={columns} data={expenses.data || []} />
    </div>
  );
}
