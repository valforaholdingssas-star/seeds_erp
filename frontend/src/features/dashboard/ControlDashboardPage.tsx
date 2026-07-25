import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";

type Indicator = {
  key: string;
  label: string;
  module: string;
  description: string;
  unit: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  value: string;
  amount: string | null;
  target_url: string;
  sparkline: string[];
  order: number;
};

type DashboardPayload = {
  as_of: string;
  role: string;
  critical: Indicator[];
  indicators: Indicator[];
};

const MODULES = [
  "ALL",
  "EXPENSES",
  "FINANCE",
  "ACCOUNTING",
  "SALES",
  "LOGISTICS",
  "INVENTORY",
] as const;

function toneClass(severity: string) {
  if (severity === "CRITICAL") return "border-wine/40 bg-wine/5";
  if (severity === "WARNING") return "border-terracotta/40 bg-terracotta/5";
  return "border-sage-300/50 bg-warm-white";
}

function valueLabel(ind: Indicator) {
  const n = Number(ind.value);
  if (ind.unit === "PERCENT") return `${n.toFixed(1)}%`;
  if (ind.unit === "AMOUNT") return formatCOP(n);
  return String(Math.round(n));
}

function MiniSpark({ values }: { values: string[] }) {
  if (!values.length) {
    return <div className="h-8 text-[10px] text-text-muted">Sin histórico</div>;
  }
  const nums = values.map(Number);
  const max = Math.max(...nums, 1);
  return (
    <div className="flex h-8 items-end gap-0.5">
      {nums.map((v, i) => (
        <div
          key={i}
          className="w-1.5 rounded-sm bg-sage-500/70"
          style={{ height: `${Math.max(8, (v / max) * 100)}%` }}
        />
      ))}
    </div>
  );
}

export function ControlDashboardPage() {
  const [params, setParams] = useSearchParams();
  const module = params.get("module") || "ALL";

  const dash = useQuery({
    queryKey: ["control-dashboard", module],
    queryFn: async () => {
      const q = module !== "ALL" ? `?module=${module}` : "";
      const { data } = await apiClient.get<DashboardPayload>(`/dashboard/${q}`);
      return data;
    },
    refetchInterval: 60_000,
  });

  const byModule = (dash.data?.indicators || []).reduce<Record<string, Indicator[]>>(
    (acc, ind) => {
      (acc[ind.module] ||= []).push(ind);
      return acc;
    },
    {},
  );

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Control" title="Torre de control" />

      <div className="flex flex-wrap gap-2">
        {MODULES.map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              const next = new URLSearchParams(params);
              if (m === "ALL") next.delete("module");
              else next.set("module", m);
              setParams(next);
            }}
            className={`rounded-full px-3 py-1 text-xs ${
              module === m
                ? "bg-green-900 text-warm-white"
                : "bg-cream text-text-muted hover:bg-sage-100"
            }`}
          >
            {m === "ALL" ? "Todos" : m}
          </button>
        ))}
      </div>

      {(dash.data?.critical || []).length > 0 ? (
        <section className="space-y-3">
          <h2 className="label-caps text-wine">Alertas críticas</h2>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {dash.data!.critical.map((ind) => (
              <Link key={ind.key} to={ind.target_url || "#"}>
                <Card className={`h-full border ${toneClass("CRITICAL")}`}>
                  <p className="label-caps text-wine">{ind.module}</p>
                  <p className="mt-2 font-serif text-xl text-green-900">{ind.label}</p>
                  <p className="mt-2 text-2xl font-medium text-wine">{valueLabel(ind)}</p>
                  {ind.amount ? (
                    <p className="mt-1 text-sm text-text-muted">{formatCOP(Number(ind.amount))}</p>
                  ) : null}
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {Object.entries(byModule).map(([mod, inds]) => (
        <section key={mod} className="space-y-3">
          <h2 className="label-caps text-text-muted">{mod}</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {inds.map((ind) => (
              <Link key={ind.key} to={ind.target_url || "#"}>
                <Card className={`h-full border transition-transform hover:-translate-y-px ${toneClass(ind.severity)}`}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-green-900">{ind.label}</p>
                    <span className="text-[10px] uppercase tracking-wide text-text-muted">
                      {ind.severity}
                    </span>
                  </div>
                  <p className="mt-3 font-serif text-3xl text-green-900">{valueLabel(ind)}</p>
                  {ind.amount ? (
                    <p className="mt-1 text-sm text-text-muted">{formatCOP(Number(ind.amount))}</p>
                  ) : null}
                  <div className="mt-3">
                    <MiniSpark values={ind.sparkline} />
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ))}

      {dash.isLoading ? <p className="text-sm text-text-muted">Cargando indicadores…</p> : null}
      {dash.isError ? (
        <p className="text-sm text-wine">No se pudo cargar el dashboard de control.</p>
      ) : null}
    </div>
  );
}
