import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
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
  concept: string;
  amount: string;
  bank_account: string | null;
  bank_name: string;
  expense_date: string;
  payment_date: string | null;
  efe_account: string | null;
  efe_label: string;
  status_key: string;
  status_label: string;
  has_payment_proof: boolean;
  has_provider_invoice: boolean;
  responsible_name: string;
};

type Bank = { id: string; name: string };
type Account = { id: string; full_label: string; is_leaf: boolean };
type Paginated<T> = { results: T[]; count: number };

type PayablesPayload = {
  reembolsos: { count: number; total_amount: string; results: Expense[] };
  cuentas: { count: number; total_amount: string; results: Expense[] };
};

type Kind = "reembolso" | "cuenta";

function money(v: string | number | null | undefined) {
  if (v == null || v === "") return "—";
  return formatCOP(Number(v));
}

export function PayablesPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [paying, setPaying] = useState<Expense | null>(null);
  const [createKind, setCreateKind] = useState<Kind>("reembolso");
  const [form, setForm] = useState({
    title: "",
    amount: "",
    expense_date: new Date().toISOString().slice(0, 10),
    concept: "",
  });
  const [payForm, setPayForm] = useState({
    payment_date: new Date().toISOString().slice(0, 10),
    bank_account: "",
    efe_account: "",
    register_in_efe: false,
  });
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [invoiceFile, setInvoiceFile] = useState<File | null>(null);

  const payables = useQuery({
    queryKey: ["expenses-payables"],
    queryFn: async () => {
      const { data } = await apiClient.get<PayablesPayload>("/expenses/payables/");
      return data;
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

  const accounts = useQuery({
    queryKey: ["finance-efe-accounts-leaves"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Account> | Account[]>(
        "/finance/accounts/efe/?is_leaf=true&page_size=500",
      );
      return Array.isArray(data) ? data : data.results || [];
    },
  });

  const createMut = useMutation({
    mutationFn: async (e: FormEvent) => {
      e.preventDefault();
      setError(null);
      setOkMsg(null);
      await apiClient.post("/expenses/payables/", {
        kind: createKind,
        title: form.title,
        amount: form.amount,
        expense_date: form.expense_date,
        concept: form.concept || form.title,
      });
    },
    onSuccess: () => {
      setForm((f) => ({ ...f, title: "", amount: "", concept: "" }));
      setOkMsg(
        createKind === "reembolso"
          ? "Reembolso registrado en la cola."
          : "Cuenta por pagar registrada.",
      );
      void qc.invalidateQueries({ queryKey: ["expenses-payables"] });
      void qc.invalidateQueries({ queryKey: ["expenses"] });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "No se pudo crear";
      setError(String(msg));
    },
  });

  const payMut = useMutation({
    mutationFn: async () => {
      if (!paying) return;
      setError(null);
      setOkMsg(null);
      const fd = new FormData();
      fd.append("payment_date", payForm.payment_date);
      if (payForm.bank_account) fd.append("bank_account", payForm.bank_account);
      if (payForm.efe_account) fd.append("efe_account", payForm.efe_account);
      fd.append("register_in_efe", payForm.register_in_efe ? "true" : "false");
      if (proofFile) fd.append("payment_proof", proofFile);
      if (invoiceFile) fd.append("provider_invoice", invoiceFile);
      const { data } = await apiClient.post(`/expenses/${paying.id}/mark-paid/`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data as Expense & { warnings?: string[] };
    },
    onSuccess: (data) => {
      setPaying(null);
      setProofFile(null);
      setInvoiceFile(null);
      setPayForm({
        payment_date: new Date().toISOString().slice(0, 10),
        bank_account: "",
        efe_account: "",
        register_in_efe: false,
      });
      const warn = data?.warnings?.length ? ` · ${data.warnings.join(" ")}` : "";
      setOkMsg(
        `Pagado y enviado a gastos (${data?.status_label || "ok"})${warn}`,
      );
      void qc.invalidateQueries({ queryKey: ["expenses-payables"] });
      void qc.invalidateQueries({ queryKey: ["expenses"] });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "No se pudo registrar el pago";
      setError(String(msg));
    },
  });

  const leafAccounts = useMemo(
    () => (accounts.data || []).filter((a) => a.is_leaf),
    [accounts.data],
  );

  const openPay = (exp: Expense) => {
    setError(null);
    setPaying(exp);
    setPayForm({
      payment_date: new Date().toISOString().slice(0, 10),
      bank_account: exp.bank_account || "",
      efe_account: exp.efe_account || "",
      register_in_efe: Boolean(exp.efe_account),
    });
    setProofFile(null);
    setInvoiceFile(null);
  };

  const Column = ({
    title,
    hint,
    total,
    count,
    items,
    tone,
  }: {
    title: string;
    hint: string;
    total: string;
    count: number;
    items: Expense[];
    tone: "clay" | "sage";
  }) => (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-2">
        <div>
          <h2 className="font-serif text-xl text-green-900">{title}</h2>
          <p className="text-sm text-text-muted">{hint}</p>
        </div>
        <div className="text-right">
          <p className="label-caps text-text-muted">{count} ítems</p>
          <p className="font-serif text-lg text-green-900">{money(total)}</p>
        </div>
      </div>
      <div className="space-y-2">
        {items.length === 0 ? (
          <Card className="text-sm text-text-muted">Nada pendiente.</Card>
        ) : (
          items.map((exp) => (
            <Card
              key={exp.id}
              className={`border ${
                tone === "clay" ? "border-terracotta/25" : "border-sage-300/40"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-green-900">{exp.title}</p>
                  <p className="mt-1 text-sm text-text-muted">
                    {money(exp.amount)} · {exp.expense_date}
                    {exp.responsible_name ? ` · ${exp.responsible_name}` : ""}
                  </p>
                  {exp.efe_label ? (
                    <p className="mt-1 text-xs text-sage-700">{exp.efe_label}</p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant={tone === "clay" ? "terracotta" : "sage"}>
                      {exp.status_label}
                    </Badge>
                    <span className="text-[11px] text-text-muted">
                      {exp.has_payment_proof ? "✓ comprobante" : "· sin comprobante"} ·{" "}
                      {exp.has_provider_invoice ? "✓ factura" : "· sin factura"}
                    </span>
                  </div>
                </div>
                <Button size="sm" variant="primary-dark" onClick={() => openPay(exp)}>
                  Registrar pago
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>
    </section>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Finanzas"
        title="Por pagar"
        actions={
          <Link
            to="/expenses"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            Ir a gastos
          </Link>
        }
      />

      {error ? <Alert variant="error">{error}</Alert> : null}
      {okMsg ? <Alert variant="success">{okMsg}</Alert> : null}

      <Card>
        <form className="grid gap-3 md:grid-cols-6" onSubmit={(e) => createMut.mutate(e)}>
          <div className="md:col-span-6 flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={createKind === "reembolso" ? "primary-dark" : "ghost"}
              onClick={() => setCreateKind("reembolso")}
            >
              Nuevo reembolso
            </Button>
            <Button
              type="button"
              size="sm"
              variant={createKind === "cuenta" ? "primary-dark" : "ghost"}
              onClick={() => setCreateKind("cuenta")}
            >
              Nueva cuenta por pagar
            </Button>
          </div>
          <div className="md:col-span-3">
            <FieldLabel>
              {createKind === "reembolso" ? "A quién / concepto" : "Proveedor / concepto"}
            </FieldLabel>
            <Input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder={
                createKind === "reembolso"
                  ? "Reembolso Cami por envío…"
                  : "Factura proveedor…"
              }
            />
          </div>
          <div>
            <FieldLabel>Monto</FieldLabel>
            <Input
              required
              type="number"
              step="0.01"
              min="0"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
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
          <div className="flex items-end">
            <Button type="submit" disabled={createMut.isPending}>
              Agregar a cola
            </Button>
          </div>
        </form>
      </Card>

      <div className="grid gap-8 lg:grid-cols-2">
        <Column
          title="Reembolsos por pagar"
          hint="Dinero que la empresa debe a alguien que pagó de su bolsillo."
          total={payables.data?.reembolsos.total_amount || "0"}
          count={payables.data?.reembolsos.count || 0}
          items={payables.data?.reembolsos.results || []}
          tone="clay"
        />
        <Column
          title="Cuentas por pagar"
          hint="Facturas u obligaciones pendientes de pago al proveedor."
          total={payables.data?.cuentas.total_amount || "0"}
          count={payables.data?.cuentas.count || 0}
          items={payables.data?.cuentas.results || []}
          tone="sage"
        />
      </div>

      {paying ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-green-950/40 p-4 sm:items-center">
          <Card className="max-h-[90vh] w-full max-w-lg overflow-y-auto space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="label-caps text-text-muted">Registrar pago</p>
                <h3 className="font-serif text-xl text-green-900">{paying.title}</h3>
                <p className="text-sm text-text-muted">{money(paying.amount)}</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setPaying(null)}>
                Cerrar
              </Button>
            </div>

            <div className="grid gap-3">
              <div>
                <FieldLabel>Fecha de pago</FieldLabel>
                <Input
                  type="date"
                  required
                  value={payForm.payment_date}
                  onChange={(e) =>
                    setPayForm({ ...payForm, payment_date: e.target.value })
                  }
                />
              </div>
              <div>
                <FieldLabel>Banco / cuenta de salida</FieldLabel>
                <select
                  className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
                  value={payForm.bank_account}
                  onChange={(e) =>
                    setPayForm({ ...payForm, bank_account: e.target.value })
                  }
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
                <FieldLabel>Cuenta EFE (opcional)</FieldLabel>
                <select
                  className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
                  value={payForm.efe_account}
                  onChange={(e) =>
                    setPayForm({ ...payForm, efe_account: e.target.value })
                  }
                >
                  <option value="">Asignar después en Gastos</option>
                  {leafAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.full_label}
                    </option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={payForm.register_in_efe}
                  onChange={(e) =>
                    setPayForm({ ...payForm, register_in_efe: e.target.checked })
                  }
                />
                Registrar ya en EFE (requiere banco + cuenta EFE)
              </label>
              <div>
                <FieldLabel>Comprobante de pago</FieldLabel>
                <input
                  type="file"
                  accept="image/*,application/pdf"
                  className="mt-1 block w-full text-xs"
                  onChange={(e) => setProofFile(e.target.files?.[0] || null)}
                />
              </div>
              <div>
                <FieldLabel>Factura del proveedor</FieldLabel>
                <input
                  type="file"
                  accept="image/*,application/pdf"
                  className="mt-1 block w-full text-xs"
                  onChange={(e) => setInvoiceFile(e.target.files?.[0] || null)}
                />
              </div>
            </div>

            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="ghost" onClick={() => setPaying(null)}>
                Cancelar
              </Button>
              <Button
                variant="primary-dark"
                disabled={payMut.isPending || !payForm.payment_date}
                onClick={() => payMut.mutate()}
              >
                {payMut.isPending ? "Guardando…" : "Pagar y enviar a gastos"}
              </Button>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
