import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { healthCheck } from "@/lib/apiClient";
import { useAuthStore } from "@/features/auth/store";

const links = [
  { to: "/sales", label: "Ventas", hint: "Consolidado · CSV · Resync" },
  { to: "/logistics", label: "Envíos", hint: "Guías y formateo" },
  { to: "/accounting", label: "Facturas", hint: "Alegra · reembolsos · IVA" },
  { to: "/analytics", label: "Métricas", hint: "Panel Looker" },
  { to: "/leads", label: "Leads", hint: "Kanban comercial" },
  { to: "/ai", label: "Asistente", hint: "Tools + RAG" },
];

export function HomePage() {
  const user = useAuthStore((s) => s.user);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: healthCheck,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-10">
      <header className="max-w-2xl">
        <p className="label-caps text-text-muted">Seeds ERP</p>
        <h1 className="mt-2 font-serif text-5xl tracking-tight text-green-900">
          Hola, {user?.full_name?.split(" ")[0] || "equipo"}
        </h1>
        <p className="mt-3 text-lg text-text-muted">
          Operación calmada para acompañar el día. Autocuidado también es un sistema que respira.
        </p>
        <div className="seeds-divider mt-6">✦</div>
      </header>

      <div className="grid gap-5 md:grid-cols-3">
        <Card className="seeds-panel animate-[fade-up_520ms_var(--ease-soft)]">
          <p className="label-caps text-text-muted">API</p>
          <p className="mt-3 font-serif text-3xl text-green-900">
            {health.isLoading ? "…" : health.data?.status === "ok" ? "Lista" : "Revisar"}
          </p>
          <div className="mt-4">
            <Badge variant={health.data?.status === "ok" ? "sage" : "terracotta"}>
              {health.data?.service || "seeds-erp"}
            </Badge>
          </div>
        </Card>
        <Card className="animate-[fade-up_520ms_var(--ease-soft)] [animation-delay:80ms]">
          <p className="label-caps text-text-muted">Tu rol</p>
          <p className="mt-3 font-serif text-3xl text-green-900">{user?.role}</p>
          <p className="mt-3 text-sm text-text-muted">
            Permisos cerrados por defecto. El backend valida siempre.
          </p>
        </Card>
        <Card tone="dark" className="seeds-panel-dark animate-[fade-up_520ms_var(--ease-soft)] [animation-delay:160ms]">
          <p className="relative z-10 label-caps text-text-on-dark-muted">Manifiesto</p>
          <p className="relative z-10 mt-3 font-serif text-2xl leading-snug">
            Lo mínimo, con el tiempo, florece.
          </p>
          <p className="relative z-10 mt-3 text-sm text-text-on-dark-muted">
            Verde profundo · crema ritual · vino con intención.
          </p>
        </Card>
      </div>

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
