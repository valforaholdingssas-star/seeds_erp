import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn } from "@/lib/utils";

type PackLine = {
  color: string;
  tipo: string;
  tipo_label: string;
  quantity: number;
  product_name: string;
};

type DispatchRow = {
  id: string;
  tracking_number: string;
  sale_external_id: string;
  qty_dorados: number;
  qty_plateados: number;
  pack_lines: PackLine[];
  status: string;
  sent_at: string | null;
};

type PackProduct = {
  key: string;
  label: string;
  color: string;
  tipo: string;
  product_name: string;
  units: number;
  orders: number;
};

type PackSummary = {
  orders: number;
  total_units: number;
  by_color: { DORADO: number; PLATEADO: number; OTRO: number };
  products: PackProduct[];
};

type Tab = "pack" | "ready" | "sent";

function boxTone(color: string) {
  if (color === "DORADO") {
    return {
      card: "border-terracotta-600/25 bg-gradient-to-br from-[#fff8f0] to-cream-100",
      num: "text-terracotta-600",
      chip: "bg-terracotta-600/10 text-terracotta-600",
      accent: "bg-terracotta-600/80",
    };
  }
  if (color === "PLATEADO") {
    return {
      card: "border-green-900/20 bg-gradient-to-br from-warm-white to-cream-100",
      num: "text-green-900",
      chip: "bg-green-900/10 text-green-900",
      accent: "bg-green-900/70",
    };
  }
  return {
    card: "border-sage-500/25 bg-gradient-to-br from-warm-white to-[#f4f8f4]",
    num: "text-sage-500",
    chip: "bg-sage-500/15 text-green-900",
    accent: "bg-sage-500/80",
  };
}

function PackBoxesView({ summary }: { summary: PackSummary | undefined }) {
  if (!summary) {
    return <p className="text-text-muted">Cargando cajas…</p>;
  }

  if (!summary.orders) {
    return (
      <Card className="seeds-panel px-8 py-14 text-center">
        <p className="font-serif text-3xl text-green-900">Nada por empacar</p>
        <p className="mt-2 text-text-muted">
          Cuando haya guías listas para enviar, aquí verás las cajas por producto.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card tone="dark" className="seeds-panel-dark">
          <p className="relative z-10 label-caps text-text-on-dark-muted">Pedidos</p>
          <p className="relative z-10 mt-2 font-serif text-5xl tracking-tight">
            {summary.orders}
          </p>
          <p className="relative z-10 mt-2 text-sm text-text-on-dark-muted">
            cajas / pedidos a empacar
          </p>
        </Card>
        <Card className="seeds-panel">
          <p className="label-caps text-text-muted">Unidades totales</p>
          <p className="mt-2 font-serif text-5xl tracking-tight text-green-900">
            {summary.total_units}
          </p>
          <p className="mt-2 text-sm text-text-muted">piezas a sacar de bodega</p>
        </Card>
        <Card>
          <p className="label-caps text-text-muted">Por color</p>
          <div className="mt-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-muted">Dorados</span>
              <span className="font-serif text-3xl text-terracotta-600">
                {summary.by_color.DORADO}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-muted">Plateados</span>
              <span className="font-serif text-3xl text-green-900">
                {summary.by_color.PLATEADO}
              </span>
            </div>
            {summary.by_color.OTRO > 0 ? (
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-muted">Otros</span>
                <span className="font-serif text-3xl text-sage-500">
                  {summary.by_color.OTRO}
                </span>
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      <div>
        <div className="mb-4 flex items-end justify-between gap-3">
          <div>
            <h2 className="font-serif text-2xl text-green-900">Cajas por producto</h2>
            <p className="mt-1 text-sm text-text-muted">
              El número grande es cuántas piezas sacar. Abajo, en cuántos pedidos van.
            </p>
          </div>
          <div className="seeds-divider hidden max-w-xs sm:flex">✦</div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {summary.products.map((p) => {
            const tone = boxTone(p.color);
            return (
              <div
                key={p.key}
                className={cn(
                  "relative overflow-hidden rounded-[28px] border p-6 shadow-[var(--shadow-1)]",
                  tone.card,
                )}
              >
                <div
                  className={cn(
                    "absolute right-0 top-0 h-16 w-16 translate-x-6 -translate-y-6 rounded-full opacity-40",
                    tone.accent,
                  )}
                />
                <p className={cn("label-caps inline-flex rounded-full px-2.5 py-1", tone.chip)}>
                  {p.color || "PRODUCTO"}
                </p>
                <p className="mt-4 min-h-[3.2rem] font-serif text-2xl leading-tight text-green-900">
                  {p.label}
                </p>
                <p className={cn("mt-4 font-serif text-6xl leading-none tracking-tight", tone.num)}>
                  {p.units}
                </p>
                <p className="mt-2 text-sm text-text-muted">
                  {p.units === 1 ? "unidad" : "unidades"} · en {p.orders}{" "}
                  {p.orders === 1 ? "pedido" : "pedidos"}
                </p>
                {/* mini visual boxes */}
                <div className="mt-5 flex flex-wrap gap-1.5">
                  {Array.from({ length: Math.min(p.units, 24) }).map((_, i) => (
                    <span
                      key={i}
                      className={cn("h-3 w-3 rounded-[3px]", tone.accent)}
                      aria-hidden
                    />
                  ))}
                  {p.units > 24 ? (
                    <span className="label-caps text-text-soft">+{p.units - 24}</span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function DispatchPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("pack");
  const [selected, setSelected] = useState<DispatchRow[]>([]);

  const rows = useQuery({
    queryKey: ["dispatch", tab === "sent" ? "sent" : "ready"],
    enabled: tab !== "pack",
    queryFn: async () => {
      const { data } = await apiClient.get<DispatchRow[]>("/logistics/dispatch/", {
        params: tab === "sent" ? { sent: "1" } : undefined,
      });
      return data;
    },
  });

  const pack = useQuery({
    queryKey: ["dispatch-pack"],
    enabled: tab === "pack",
    queryFn: async () => {
      const { data } = await apiClient.get<PackSummary>("/logistics/dispatch/pack-summary/");
      return data;
    },
    refetchInterval: tab === "pack" ? 15_000 : false,
  });

  const markSent = useMutation({
    mutationFn: async (ids: string[]) => {
      await apiClient.post("/logistics/dispatch/mark-sent/", { ids });
    },
    onSuccess: () => {
      setSelected([]);
      qc.invalidateQueries({ queryKey: ["dispatch"] });
      qc.invalidateQueries({ queryKey: ["dispatch-pack"] });
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
  });

  const columns = useMemo<ColumnDef<DispatchRow, unknown>[]>(
    () => [
      {
        id: "select",
        header: "",
        cell: ({ row }) =>
          tab === "ready" ? (
            <input
              type="checkbox"
              checked={row.getIsSelected()}
              onChange={row.getToggleSelectedHandler()}
              className="h-4 w-4 accent-green-900"
            />
          ) : null,
      },
      { accessorKey: "tracking_number", header: "Guía" },
      { accessorKey: "sale_external_id", header: "Pedido" },
      {
        id: "tipo",
        header: "Tipo de producto",
        cell: ({ row }) => {
          const lines = row.original.pack_lines || [];
          if (!lines.length) {
            return <span className="text-text-soft">—</span>;
          }
          return (
            <div className="min-w-[160px] space-y-1">
              {lines.map((line, idx) => {
                const colorLabel =
                  line.color === "DORADO"
                    ? "Dorado"
                    : line.color === "PLATEADO"
                      ? "Plateado"
                      : line.color || "";
                return (
                  <p key={`${line.tipo}-${line.color}-${idx}`} className="text-xs leading-snug text-green-900">
                    <span className="font-medium">{line.tipo_label}</span>
                    {colorLabel ? (
                      <span className="text-text-muted"> · {colorLabel}</span>
                    ) : null}
                    <span className="text-text-soft"> ×{line.quantity}</span>
                  </p>
                );
              })}
            </div>
          );
        },
      },
      {
        accessorKey: "qty_dorados",
        header: "Dorados",
        cell: ({ getValue }) => <Badge variant="sage">{String(getValue())}</Badge>,
      },
      {
        accessorKey: "qty_plateados",
        header: "Plateados",
        cell: ({ getValue }) => <Badge variant="dark">{String(getValue())}</Badge>,
      },
    ],
    [tab],
  );

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Bodega"
        title="Despachos"
        actions={
          <>
            <Button
              type="button"
              size="xs"
              variant={tab === "pack" ? "primary-dark" : "outline"}
              onClick={() => setTab("pack")}
            >
              Empacar
            </Button>
            <Button
              type="button"
              size="xs"
              variant={tab === "ready" ? "primary-dark" : "outline"}
              onClick={() => setTab("ready")}
            >
              Listos
            </Button>
            <Button
              type="button"
              size="xs"
              variant={tab === "sent" ? "primary-dark" : "outline"}
              onClick={() => setTab("sent")}
            >
              Enviados
            </Button>
            {tab === "ready" ? (
              <Button
                type="button"
                size="xs"
                disabled={!selected.length || markSent.isPending}
                onClick={() => markSent.mutate(selected.map((s) => s.id))}
              >
                Marcar enviado
              </Button>
            ) : null}
          </>
        }
      />

      {tab === "pack" ? (
        <PackBoxesView summary={pack.data} />
      ) : (
        <DataTable
          data={rows.data || []}
          columns={columns}
          searchableKeys={["tracking_number", "sale_external_id"]}
          onSelectionChange={setSelected}
          emptyTitle={tab === "ready" ? "Nada por despachar" : "Sin históricos"}
          emptyDescription={
            tab === "ready"
              ? "Aparecen aquí cuando la guía queda lista para enviar."
              : "Los pedidos marcados como enviados se listan aquí."
          }
        />
      )}
    </div>
  );
}
