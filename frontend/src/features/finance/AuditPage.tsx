import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { SignedBarChart } from "@/components/charts/SimpleCharts";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCompactCOP, formatCOP } from "@/lib/utils";

type AuditRow = {
  bank: string;
  date: string;
  reports: string;
  banks_net: string;
  interbank: string;
  validation: string;
  out_of_tolerance: boolean;
};

type AuditResponse = {
  year: number;
  month: number;
  tolerance: string;
  banks: string[];
  rows: AuditRow[];
  totals: Array<{
    bank: string;
    reports: string;
    banks_net: string;
    validation: string;
    out_of_tolerance_days: number;
  }>;
  chart: Record<string, Array<{ label: string; validation: number; out_of_tolerance: boolean }>>;
  unmapped_count: number;
};

export function AuditPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [bank, setBank] = useState("");

  const audit = useQuery({
    queryKey: ["finance-audit", year, month, bank],
    queryFn: async () => {
      const q = new URLSearchParams({ year: String(year), month: String(month) });
      if (bank) q.set("bank", bank);
      const { data } = await apiClient.get<AuditResponse>(
        `/finance/audit/reports-vs-banks/?${q.toString()}`,
      );
      return data;
    },
  });

  const chartSeries = useMemo(() => {
    const data = audit.data;
    if (!data) return [];
    const bankKey = bank || data.banks[0];
    if (!bankKey) return [];
    return (data.chart[bankKey] || []).map((p) => ({
      label: p.label,
      value: p.validation,
      color: p.out_of_tolerance ? "#93403A" : "#62986C",
    }));
  }, [audit.data, bank]);

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Finanzas"
        title="Auditoría de ingresos"
        actions={
          <Link
            to="/finance"
            className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
          >
            EFE
          </Link>
        }
      />

      <Card>
        <div className="flex flex-wrap gap-3">
          <label className="text-xs">
            <span className="label-caps text-text-muted">Año</span>
            <input
              type="number"
              className="mt-1 block h-9 w-24 rounded-full border border-line bg-cream-50 px-3"
              value={year}
              onChange={(e) => setYear(Number(e.target.value) || year)}
            />
          </label>
          <label className="text-xs">
            <span className="label-caps text-text-muted">Mes</span>
            <input
              type="number"
              min={1}
              max={12}
              className="mt-1 block h-9 w-20 rounded-full border border-line bg-cream-50 px-3"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value) || month)}
            />
          </label>
          <label className="text-xs">
            <span className="label-caps text-text-muted">Banco</span>
            <select
              className="mt-1 block h-9 rounded-full border border-line bg-cream-50 px-3"
              value={bank}
              onChange={(e) => setBank(e.target.value)}
            >
              <option value="">Todos (gráfico: primero)</option>
              {(audit.data?.banks || []).map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="mt-3 text-sm text-text-muted">
          Validación = ingreso neto bancos (sin interbancarios) − reportes del equipo. Tolerancia ±
          {audit.data ? formatCOP(Number(audit.data.tolerance)) : "…"}.
        </p>
      </Card>

      <Card>
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="label-caps text-text-muted">
              Discrepancia diaria · {bank || audit.data?.banks?.[0] || "—"}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Arriba (+) = entró más al banco de lo reportado · Abajo (−) = se reportó más de lo que
              entró
            </p>
          </div>
          <div className="flex gap-3 text-[10px] label-caps text-text-muted">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-sm bg-sage-500" /> Cuadra / bajo
              tolerancia
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-sm bg-wine-900" /> Fuera de tolerancia
            </span>
          </div>
        </div>
        {chartSeries.length ? (
          <SignedBarChart series={chartSeries} height={220} formatValue={formatCompactCOP} />
        ) : (
          <p className="text-sm text-text-muted">Sin datos para graficar este mes.</p>
        )}
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(audit.data?.totals || []).map((t) => (
          <Card key={t.bank}>
            <p className="font-serif text-xl text-green-900">{t.bank}</p>
            <p className="mt-2 text-xs text-text-muted">Reportes {formatCOP(Number(t.reports))}</p>
            <p className="text-xs text-text-muted">Bancos netos {formatCOP(Number(t.banks_net))}</p>
            <p className="mt-1 text-sm text-green-900">
              Validación {formatCOP(Number(t.validation))}
            </p>
            {t.out_of_tolerance_days ? (
              <Badge variant="wine" className="mt-2">
                {t.out_of_tolerance_days} días fuera
              </Badge>
            ) : (
              <Badge variant="sage" className="mt-2">
                Cuadra
              </Badge>
            )}
          </Card>
        ))}
      </div>

      {audit.data?.unmapped_count ? (
        <Card>
          <p className="text-sm text-wine-900">
            {audit.data.unmapped_count} ventas con medio de pago sin mapear a un banco. Ajusta
            aliases en Finanzas → Bancos.
          </p>
        </Card>
      ) : null}

      <Card className="overflow-auto">
        <table className="min-w-full text-left text-xs">
          <thead>
            <tr className="border-b border-line label-caps text-text-muted">
              <th className="px-2 py-2">Fecha</th>
              <th className="px-2 py-2">Banco</th>
              <th className="px-2 py-2 text-right">Reportes</th>
              <th className="px-2 py-2 text-right">Interbanc.</th>
              <th className="px-2 py-2 text-right">Bancos netos</th>
              <th className="px-2 py-2 text-right">Validación</th>
            </tr>
          </thead>
          <tbody>
            {(audit.data?.rows || []).map((r) => (
              <tr
                key={`${r.bank}-${r.date}`}
                className={`border-b border-line/50 ${r.out_of_tolerance ? "bg-wine-900/5" : ""}`}
              >
                <td className="px-2 py-1.5">{r.date}</td>
                <td className="px-2 py-1.5">{r.bank}</td>
                <td className="px-2 py-1.5 text-right">{formatCOP(Number(r.reports))}</td>
                <td className="px-2 py-1.5 text-right">{formatCOP(Number(r.interbank))}</td>
                <td className="px-2 py-1.5 text-right">{formatCOP(Number(r.banks_net))}</td>
                <td
                  className={`px-2 py-1.5 text-right font-medium tabular-nums ${
                    r.out_of_tolerance ? "text-wine-900" : "text-green-900"
                  }`}
                >
                  {formatCOP(Number(r.validation))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
