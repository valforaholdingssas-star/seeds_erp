import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";

type Cuatrimestre = {
  key: string;
  label: string;
  year: number;
  from: string;
  to: string;
  is_current: boolean;
  is_past: boolean;
  iva_recaudado: string;
  iva_facturado: string;
  a_pagar: string;
  sales_count: number;
  invoices_count: number;
};

type DeductibleItem = {
  id: string;
  title: string;
  expense_date: string | null;
  amount: string;
  iva_discountable: string;
  iva_already_discounted: boolean;
  provider_name: string;
};

type IvaDashboard = {
  year: number;
  from: string | null;
  to: string | null;
  iva_recaudado: {
    amount: string;
    net_value: string;
    total_value: string;
    count: number;
    hint: string;
  };
  iva_facturado: {
    amount: string;
    total: string;
    count: number;
    hint: string;
  };
  cuatrimestres: Cuatrimestre[];
  cuatrimestre_actual: Cuatrimestre | null;
  iva_descontable: {
    disponible: string;
    disponible_count: number;
    ya_descontado: string;
    ya_descontado_count: number;
    hint: string;
    items: DeductibleItem[];
  };
};

export function IvaPage() {
  const qc = useQueryClient();
  const thisYear = new Date().getFullYear();
  const today = new Date().toISOString().slice(0, 10);
  const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    .toISOString()
    .slice(0, 10);
  const [year, setYear] = useState(thisYear);
  const [from, setFrom] = useState(monthStart);
  const [to, setTo] = useState(today);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const summary = useQuery({
    queryKey: ["iva-summary", year, from, to],
    queryFn: async () => {
      const q = new URLSearchParams({
        year: String(year),
        from,
        to,
      });
      const { data } = await apiClient.get<IvaDashboard>(
        `/accounting/iva/summary/?${q}`,
      );
      return data;
    },
  });

  const markDiscounted = useMutation({
    mutationFn: async (ids: string[]) => {
      await apiClient.post("/expenses/bulk-update/", {
        ids,
        iva_already_discounted: true,
      });
    },
    onSuccess: () => {
      setErr(null);
      setMsg("IVA marcado como ya descontado.");
      void qc.invalidateQueries({ queryKey: ["iva-summary"] });
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { detail?: string } }; message?: string };
      setMsg(null);
      setErr(ax.response?.data?.detail || ax.message || "No se pudo marcar el IVA.");
    },
  });

  const s = summary.data;
  const years = useMemo(
    () => [thisYear - 1, thisYear, thisYear + 1],
    [thisYear],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Contabilidad"
        title="IVA"
        actions={
          <>
            <Link
              to="/accounting/customers"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Clientes
            </Link>
            <Link
              to="/accounting"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Facturas
            </Link>
          </>
        }
      />

      {msg ? <Alert variant="success">{msg}</Alert> : null}
      {err ? <Alert variant="error">{err}</Alert> : null}

      <Card tone="cream" className="grid max-w-3xl gap-4 sm:grid-cols-3">
        <div>
          <FieldLabel>Año (cuatrimestres)</FieldLabel>
          <select
            className="mt-1 w-full rounded-[12px] border border-line bg-warm-white px-3 py-2 text-sm"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        <div>
          <FieldLabel>Desde (resumen)</FieldLabel>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div>
          <FieldLabel>Hasta (resumen)</FieldLabel>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card className="seeds-panel">
          <p className="label-caps text-text-muted">IVA recaudado</p>
          <p className="mt-3 font-serif text-3xl text-green-900">
            {formatCOP(Number(s?.iva_recaudado.amount || 0))}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Ventas activas · {s?.iva_recaudado.count ?? 0} pedidos
          </p>
          <p className="mt-1 text-[11px] text-text-soft">{s?.iva_recaudado.hint}</p>
        </Card>
        <Card tone="dark" className="seeds-panel-dark">
          <p className="relative z-10 label-caps text-text-on-dark-muted">IVA facturado</p>
          <p className="relative z-10 mt-3 font-serif text-3xl">
            {formatCOP(Number(s?.iva_facturado.amount || 0))}
          </p>
          <p className="relative z-10 mt-2 text-sm text-text-on-dark-muted">
            Facturas GENERADA · {s?.iva_facturado.count ?? 0} docs
          </p>
          <p className="relative z-10 mt-1 text-[11px] text-text-on-dark-muted/80">
            {s?.iva_facturado.hint}
          </p>
        </Card>
        <Card className="seeds-panel">
          <p className="label-caps text-text-muted">IVA descontable</p>
          <p className="mt-3 font-serif text-3xl text-green-900">
            {formatCOP(Number(s?.iva_descontable.disponible || 0))}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Disponible · {s?.iva_descontable.disponible_count ?? 0} gastos
          </p>
          <p className="mt-1 text-[11px] text-text-soft">{s?.iva_descontable.hint}</p>
        </Card>
        <Card className="seeds-panel">
          <p className="label-caps text-text-muted">Ya descontado</p>
          <p className="mt-3 font-serif text-3xl text-green-900">
            {formatCOP(Number(s?.iva_descontable.ya_descontado || 0))}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            {s?.iva_descontable.ya_descontado_count ?? 0} gastos marcados
          </p>
        </Card>
      </div>

      <section className="space-y-2">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="font-serif text-2xl text-green-950">Cuatrimestres {year}</h2>
            <p className="text-sm text-text-muted">
              A pagar = IVA facturado del período. El descontable se aplica aparte, sin
              amarrarlo al cuatrimestre.
            </p>
          </div>
          {s?.cuatrimestre_actual ? (
            <Badge variant="sage">Actual: {s.cuatrimestre_actual.label}</Badge>
          ) : null}
        </div>
        <div className="overflow-x-auto rounded-[20px] border border-line bg-warm-white">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line bg-cream-50 text-[10px] label-caps text-text-muted">
              <tr>
                <th className="px-4 py-3">Período</th>
                <th className="px-4 py-3">IVA recaudado</th>
                <th className="px-4 py-3">IVA facturado</th>
                <th className="px-4 py-3">A pagar</th>
                <th className="px-4 py-3">Docs</th>
              </tr>
            </thead>
            <tbody>
              {(s?.cuatrimestres || []).map((c) => (
                <tr
                  key={c.key}
                  className={
                    c.is_current
                      ? "bg-sage-500/10"
                      : "border-t border-line/70"
                  }
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-text-dark">{c.label}</div>
                    <div className="text-[11px] text-text-soft">
                      {c.from} → {c.to}
                      {c.is_current ? " · actual" : c.is_past ? " · cerrado" : " · próximo"}
                    </div>
                  </td>
                  <td className="px-4 py-3">{formatCOP(Number(c.iva_recaudado))}</td>
                  <td className="px-4 py-3 font-medium">
                    {formatCOP(Number(c.iva_facturado))}
                  </td>
                  <td className="px-4 py-3 font-serif text-lg text-green-900">
                    {formatCOP(Number(c.a_pagar))}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {c.invoices_count} fact. · {c.sales_count} ventas
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-2">
        <div>
          <h2 className="font-serif text-2xl text-green-950">IVA descontable</h2>
          <p className="text-sm text-text-muted">
            Gastos empresa con IVA. Márcalos cuando ya los hayas descontado en tu
            declaración; no dependen del cuatrimestre.
          </p>
        </div>
        <div className="overflow-x-auto rounded-[20px] border border-line bg-warm-white">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line bg-cream-50 text-[10px] label-caps text-text-muted">
              <tr>
                <th className="px-4 py-3">Gasto</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">Proveedor</th>
                <th className="px-4 py-3">IVA</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {(s?.iva_descontable.items || []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-text-muted">
                    No hay IVA descontable pendiente.
                  </td>
                </tr>
              ) : (
                (s?.iva_descontable.items || []).map((item) => (
                  <tr key={item.id} className="border-t border-line/70">
                    <td className="px-4 py-3">
                      <div className="font-medium text-text-dark">{item.title}</div>
                      <div className="text-[11px] text-text-soft">
                        Total gasto {formatCOP(Number(item.amount))}
                      </div>
                    </td>
                    <td className="px-4 py-3">{item.expense_date || "—"}</td>
                    <td className="px-4 py-3">{item.provider_name || "—"}</td>
                    <td className="px-4 py-3 font-medium">
                      {formatCOP(Number(item.iva_discountable))}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={markDiscounted.isPending}
                        onClick={() => {
                          if (
                            !window.confirm(
                              `¿Marcar IVA de «${item.title}» como ya descontado?`,
                            )
                          ) {
                            return;
                          }
                          markDiscounted.mutate([item.id]);
                        }}
                      >
                        Marcar descontado
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
