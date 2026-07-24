import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { apiClient } from "@/lib/apiClient";
import { formatCOP } from "@/lib/utils";
import { useAuthStore } from "@/features/auth/store";

type HomeOverview = {
  as_of: string;
  pending_shipments: {
    total: number;
    to_prepare: number;
    to_ship: number;
  };
  failed_events: {
    count: number;
    from: string;
    to: string;
  };
  sales_today: { date: string; sales: string; orders: number };
  sales_yesterday: { date: string; sales: string; orders: number };
};

const links = [
  { to: "/sales", label: "Ventas", hint: "Consolidado · CSV · Resync" },
  { to: "/dispatch", label: "Despachos", hint: "Empaque y guías" },
  { to: "/logistics", label: "Envíos", hint: "Guías y formateo" },
  { to: "/accounting", label: "Facturas", hint: "Alegra · reembolsos · IVA" },
  { to: "/analytics", label: "Métricas", hint: "Panel Looker" },
  { to: "/users", label: "Usuarios", hint: "Contraseñas · equipo" },
  { to: "/roles", label: "Roles", hint: "Permisos por rol" },
  { to: "/integrations/events", label: "Eventos", hint: "Fallidos y reproceso" },
];

function KpiCard({
  label,
  value,
  hint,
  to,
  delayMs = 0,
  tone = "warm-white",
}: {
  label: string;
  value: string;
  hint?: string;
  to: string;
  delayMs?: number;
  tone?: "warm-white" | "cream" | "dark";
}) {
  return (
    <Link
      to={to}
      className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage-500/50 rounded-[32px]"
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <Card
        tone={tone}
        className="h-full animate-[fade-up_520ms_var(--ease-soft)] transition-transform duration-[280ms] ease-soft hover:-translate-y-px"
      >
        <p
          className={`label-caps ${tone === "dark" ? "text-text-on-dark-muted" : "text-text-muted"}`}
        >
          {label}
        </p>
        <p
          className={`mt-3 font-serif text-3xl tracking-tight ${
            tone === "dark" ? "text-text-on-dark" : "text-green-900"
          }`}
        >
          {value}
        </p>
        {hint ? (
          <p
            className={`mt-3 text-sm ${
              tone === "dark" ? "text-text-on-dark-muted" : "text-text-muted"
            }`}
          >
            {hint}
          </p>
        ) : null}
      </Card>
    </Link>
  );
}

export function HomePage() {
  const user = useAuthStore((s) => s.user);
  const overview = useQuery({
    queryKey: ["analytics", "home"],
    queryFn: async () => {
      const { data } = await apiClient.get<HomeOverview>("/analytics/home/");
      return data;
    },
    refetchInterval: 60_000,
  });

  const data = overview.data;
  const loading = overview.isLoading && !data;

  return (
    <div className="space-y-10">
      <header className="max-w-2xl">
        <p className="label-caps text-text-muted">Seeds ERP</p>
        <h1 className="mt-2 font-serif text-5xl tracking-tight text-green-900">
          Hola, {user?.full_name?.split(" ")[0] || "equipo"}
        </h1>
        <p className="mt-3 text-lg text-text-muted">
          Cifras del día para operar sin fricción.
        </p>
        <div className="seeds-divider mt-6">✦</div>
      </header>

      {overview.isError ? (
        <Card tone="cream">
          <p className="text-sm text-terracotta-600">
            No se pudieron cargar las cifras del inicio. Recarga en un momento.
          </p>
        </Card>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Por alistar / enviar"
            value={loading ? "…" : String(data?.pending_shipments.total ?? 0)}
            hint={
              loading
                ? undefined
                : `${data?.pending_shipments.to_prepare ?? 0} por generar · ${data?.pending_shipments.to_ship ?? 0} listos`
            }
            to="/logistics"
            delayMs={0}
          />
          <KpiCard
            label="Eventos fallidos"
            value={loading ? "…" : String(data?.failed_events.count ?? 0)}
            hint="Ayer y hoy"
            to="/integrations/events"
            delayMs={60}
            tone={
              !loading && (data?.failed_events.count ?? 0) > 0 ? "dark" : "warm-white"
            }
          />
          <KpiCard
            label="Ventas hoy"
            value={
              loading ? "…" : formatCOP(Number(data?.sales_today.sales || 0))
            }
            hint={
              loading
                ? undefined
                : `${data?.sales_today.orders ?? 0} pedidos`
            }
            to="/analytics"
            delayMs={120}
          />
          <KpiCard
            label="Ventas ayer"
            value={
              loading
                ? "…"
                : formatCOP(Number(data?.sales_yesterday.sales || 0))
            }
            hint={
              loading
                ? undefined
                : `${data?.sales_yesterday.orders ?? 0} pedidos`
            }
            to="/analytics"
            delayMs={180}
            tone="cream"
          />
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {links.map((l) => (
          <Link
            key={l.to}
            to={l.to}
            className="rounded-[28px] border border-line bg-warm-white/80 px-5 py-5 transition-all duration-[280ms] ease-soft hover:-translate-y-px hover:border-sage-500/40"
          >
            <p className="font-serif text-2xl text-green-900">{l.label}</p>
            <p className="mt-1 text-sm text-text-muted">{l.hint}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
