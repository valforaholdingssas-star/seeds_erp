import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import { BarChart, DonutChart, LineChart } from "@/components/charts/SimpleCharts";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";

type Overview = {
  summary: {
    from: string;
    to: string;
    kpis: {
      goal: string;
      sales: string;
      performance_pct: number;
      projection: string;
      daily_expected: string;
      sales_to_date: string;
      avg_daily: string;
      vde_units: number;
      orders: number;
    };
    previous: { delta_pct: number | null; total_value: string } | null;
  };
  by_channel: { series: Array<{ label: string; total: string; orders: number }> };
  by_seller: { series: Array<{ label: string; total: string; orders: number }> };
  by_city: { series: Array<{ label: string; total: string; orders: number }> };
  timeseries: {
    points: Array<{ date: string; total: string; daily_expected: string; avg: string }>;
  };
  weekday: {
    month: Array<{ label: string; total: string }>;
    historic: Array<{ label: string; total: string }>;
  };
  year: {
    year: number;
    previous_year: number;
    points: Array<{ label: string; current: string; previous: string }>;
  };
};

function Kpi({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card tone="cream" className="!p-5">
      <p className="label-caps text-text-muted">{label}</p>
      <p className="mt-2 font-serif text-3xl tracking-tight text-green-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-text-soft">{hint}</p>}
    </Card>
  );
}

export function AnalyticsPage() {
  const today = new Date();
  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1)
    .toISOString()
    .slice(0, 10);
  const monthEnd = today.toISOString().slice(0, 10);
  const [from, setFrom] = useState(monthStart);
  const [to, setTo] = useState(monthEnd);
  const [source, setSource] = useState("");
  const [tab, setTab] = useState<"global" | "canal" | "comercial">("global");

  const overview = useQuery({
    queryKey: ["analytics-overview", from, to, source],
    queryFn: async () => {
      const params = new URLSearchParams({ from, to });
      if (source) params.set("source", source);
      const { data } = await apiClient.get<Overview>(
        `/analytics/sales/overview/?${params.toString()}`,
      );
      return data;
    },
  });

  const kpis = overview.data?.summary.kpis;
  const delta = overview.data?.summary.previous?.delta_pct;

  const weekdaySeries = useMemo(() => {
    const month = overview.data?.weekday.month || [];
    return month.map((m) => ({ label: m.label, value: Number(m.total) }));
  }, [overview.data]);

  const channelSeries = useMemo(
    () =>
      (overview.data?.by_channel.series || []).map((s) => ({
        label: s.label,
        value: Number(s.total),
      })),
    [overview.data],
  );

  const citySeries = useMemo(
    () =>
      (overview.data?.by_city.series || []).map((s) => ({
        label: s.label,
        value: Number(s.total),
      })),
    [overview.data],
  );

  const dailyPoints = useMemo(
    () =>
      (overview.data?.timeseries.points || []).map((p) => ({
        date: p.date,
        total: Number(p.total),
        expected: Number(p.daily_expected),
        avg: Number(p.avg),
      })),
    [overview.data],
  );

  const yearPoints = useMemo(
    () =>
      (overview.data?.year.points || []).map((p) => ({
        label: p.label,
        current: Number(p.current),
        previous: Number(p.previous),
      })),
    [overview.data],
  );

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Analítica"
        title="Métricas"
        actions={
          <>
            {(["global", "canal", "comercial"] as const).map((t) => (
              <Button
                key={t}
                type="button"
                size="xs"
                variant={tab === t ? "primary-dark" : "outline"}
                onClick={() => setTab(t)}
              >
                {t}
              </Button>
            ))}
          </>
        }
      />

      <Card tone="warm-white" className="grid gap-4 sm:grid-cols-4">
        <div>
          <FieldLabel>Desde</FieldLabel>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div>
          <FieldLabel>Hasta</FieldLabel>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <FieldLabel>Canal</FieldLabel>
          <select
            className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3 text-[15px]"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="ECOMMERCE">Ecommerce</option>
            <option value="SHOPIFY">Ecommerce 2</option>
            <option value="KOMMO">Kommo</option>
            <option value="FERIAS">Ferias</option>
            <option value="MANUAL">Manual</option>
          </select>
        </div>
      </Card>

      {kpis && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="Meta período" value={formatCOP(Number(kpis.goal))} />
          <Kpi
            label="Ventas (sin IVA)"
            value={formatCOP(Number(kpis.sales))}
            hint={
              delta == null
                ? `${kpis.orders} pedidos`
                : `${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta)}% vs período ant.`
            }
          />
          <Kpi label="Performance" value={`${kpis.performance_pct}%`} />
          <Kpi label="Proyección" value={formatCOP(Number(kpis.projection))} />
          <Kpi label="Venta diaria esperada" value={formatCOP(Number(kpis.daily_expected))} />
          <Kpi label="Promedio diario" value={formatCOP(Number(kpis.avg_daily))} />
          <Kpi label="Venta a la fecha" value={formatCOP(Number(kpis.sales_to_date))} />
          <Kpi label="VDE unidades" value={String(kpis.vde_units)} />
        </div>
      )}

      {(tab === "global" || tab === "canal") && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card tone="cream">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-serif text-2xl text-green-900">Por día de semana</h2>
              <Badge variant="sage">Mes actual</Badge>
            </div>
            <BarChart series={weekdaySeries} />
          </Card>
          <Card tone="cream">
            <h2 className="mb-4 font-serif text-2xl text-green-900">Por canal</h2>
            {channelSeries.length ? (
              <DonutChart series={channelSeries} />
            ) : (
              <p className="text-sm text-text-soft">Sin datos en el rango.</p>
            )}
          </Card>
        </div>
      )}

      {tab !== "comercial" && (
        <Card tone="warm-white">
          <h2 className="mb-4 font-serif text-2xl text-green-900">Ventas diarias</h2>
          {dailyPoints.length ? (
            <LineChart
              points={dailyPoints}
              seriesKeys={[
                { key: "total", color: "#112918", label: "Real" },
                { key: "expected", color: "#62986C", label: "Esperada" },
                { key: "avg", color: "#93403A", label: "Promedio" },
              ]}
            />
          ) : (
            <p className="text-sm text-text-soft">Sin puntos en el rango.</p>
          )}
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card tone="cream">
          <h2 className="mb-4 font-serif text-2xl text-green-900">
            Año {overview.data?.year.year} vs {overview.data?.year.previous_year}
          </h2>
          {yearPoints.length ? (
            <LineChart
              points={yearPoints}
              seriesKeys={[
                { key: "current", color: "#112918", label: "Actual" },
                { key: "previous", color: "#CA9697", label: "Anterior" },
              ]}
            />
          ) : (
            <p className="text-sm text-text-soft">Sin serie anual.</p>
          )}
        </Card>
        <Card tone="cream">
          <h2 className="mb-4 font-serif text-2xl text-green-900">
            {tab === "comercial" ? "Por comercial" : "Por ciudad"}
          </h2>
          {tab === "comercial" ? (
            <BarChart
              series={(overview.data?.by_seller.series || []).map((s) => ({
                label: s.label,
                value: Number(s.total),
              }))}
            />
          ) : citySeries.length ? (
            <DonutChart series={citySeries.slice(0, 8)} />
          ) : (
            <p className="text-sm text-text-soft">Sin ciudades.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
