import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn, formatCOP } from "@/lib/utils";

type EfeLine = {
  code: string;
  name: string;
  full_label: string;
  kind: string;
  is_leaf: boolean;
  depth: number;
  real: Record<string, string>;
  budget: Record<string, string>;
  variance: Record<string, string>;
};

type EfeMatrix = {
  year: number;
  months: string[];
  lines: EfeLine[];
  closed_months: Record<string, unknown>;
};

const KIND_STYLE: Record<
  string,
  { row: string; sticky: string; label: string; badge: "sage" | "wine" | "terracotta" | "dark"; accent: string }
> = {
  VENTAS: {
    row: "bg-[#eef6ef]/70",
    sticky: "bg-[#eef6ef]",
    label: "text-green-900",
    badge: "sage",
    accent: "border-l-[3px] border-l-sage-500",
  },
  COGS: {
    row: "bg-[#fff4ee]/80",
    sticky: "bg-[#fff4ee]",
    label: "text-terracotta-600",
    badge: "terracotta",
    accent: "border-l-[3px] border-l-terracotta-600",
  },
  INGRESO: {
    row: "bg-[#eef3f8]/80",
    sticky: "bg-[#eef3f8]",
    label: "text-[#1e3a5f]",
    badge: "dark",
    accent: "border-l-[3px] border-l-[#3d6b9a]",
  },
  ADMIN: {
    row: "bg-[#f7f0f0]/90",
    sticky: "bg-[#f7f0f0]",
    label: "text-wine-900",
    badge: "wine",
    accent: "border-l-[3px] border-l-wine-900",
  },
  COSTO: {
    row: "bg-[#f8f1e8]/90",
    sticky: "bg-[#f8f1e8]",
    label: "text-[#6b4423]",
    badge: "terracotta",
    accent: "border-l-[3px] border-l-[#c47a3a]",
  },
  GASTO: {
    row: "bg-[#f5eef2]/90",
    sticky: "bg-[#f5eef2]",
    label: "text-[#5c2a4a]",
    badge: "wine",
    accent: "border-l-[3px] border-l-rose-300",
  },
  PASIVO: {
    row: "bg-[#f3f3f0]/90",
    sticky: "bg-[#f3f3f0]",
    label: "text-text-muted",
    badge: "dark",
    accent: "border-l-[3px] border-l-line",
  },
};

function depthType(depth: number, isLeaf: boolean) {
  if (depth === 0) {
    return {
      name: "font-serif text-[15px] tracking-tight font-medium",
      amount: "text-[13px] font-semibold",
      rowExtra: "border-t border-line/80",
    };
  }
  if (depth === 1) {
    return {
      name: "text-[12.5px] font-semibold tracking-wide",
      amount: "text-[12px] font-medium",
      rowExtra: "",
    };
  }
  if (!isLeaf) {
    return {
      name: "text-[11.5px] font-medium",
      amount: "text-[11px] font-medium",
      rowExtra: "",
    };
  }
  return {
    name: "text-[11px] font-normal text-text-muted",
    amount: "text-[11px] font-normal",
    rowExtra: "",
  };
}

function amountClass(value: number, kind: string) {
  if (!value) return "text-text-soft";
  if (kind === "VENTAS" || kind === "INGRESO") {
    return value < 0 ? "text-wine-900" : "text-green-900";
  }
  if (value > 0) return "text-terracotta-600";
  return "text-green-900";
}

function monthKey(year: number, month: number) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function focusMonths(year: number, months: string[]) {
  const now = new Date();
  let curMonth = 12;
  if (year === now.getFullYear()) curMonth = now.getMonth() + 1;
  else if (year > now.getFullYear()) curMonth = 1;
  const current = monthKey(year, curMonth);
  const prev =
    curMonth === 1 ? null : monthKey(year, curMonth - 1);
  return {
    current: months.includes(current) ? current : months[months.length - 1] || current,
    previous: prev && months.includes(prev) ? prev : null,
  };
}

function pctOfSales(value: number, sales: number): number | null {
  if (!sales) return null;
  return (value / sales) * 100;
}

function formatPct(pct: number | null, digits = 1) {
  if (pct == null || Number.isNaN(pct)) return "—";
  return `${pct.toFixed(digits)}%`;
}

export function EfePage() {
  const yearNow = new Date().getFullYear();
  const [year, setYear] = useState(yearNow);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [viewMode, setViewMode] = useState<"cop" | "pct">("cop");

  const efe = useQuery({
    queryKey: ["finance-efe", year],
    queryFn: async () => {
      const { data } = await apiClient.get<EfeMatrix>(`/finance/efe/?year=${year}`);
      return data;
    },
  });

  const months = efe.data?.months || [];

  const salesByMonth = useMemo(() => {
    const ventas = efe.data?.lines.find((l) => l.code === "1");
    const out: Record<string, number> = {};
    for (const m of months) {
      out[m] = Number(ventas?.real[m] || 0);
    }
    return out;
  }, [efe.data, months]);

  const focus = useMemo(() => focusMonths(year, months), [year, months]);

  const visible = useMemo(() => {
    const lines = efe.data?.lines || [];
    return lines.filter((line) => {
      const parts = line.code.split(".");
      for (let i = 1; i < parts.length; i++) {
        const parent = parts.slice(0, i).join(".");
        if (collapsed[parent]) return false;
      }
      return true;
    });
  }, [efe.data, collapsed]);

  function cellDisplay(line: EfeLine, m: string) {
    const v = Number(line.real[m] || 0);
    if (viewMode === "cop") {
      return {
        text: v ? formatCOP(v) : "—",
        cls: amountClass(v, line.kind),
        title: undefined as string | undefined,
      };
    }
    const pct = pctOfSales(v, salesByMonth[m] || 0);
    return {
      text: formatPct(pct),
      cls: pct == null ? "text-text-soft" : amountClass(v, line.kind),
      title: v ? `${formatCOP(v)} · base ventas ${formatCOP(salesByMonth[m] || 0)}` : undefined,
    };
  }

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Finanzas"
        title="Modelo financiero (EFE)"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-full border border-line bg-cream-50 p-0.5">
              <Button
                type="button"
                size="xs"
                variant={viewMode === "cop" ? "primary-dark" : "ghost"}
                onClick={() => setViewMode("cop")}
              >
                $ Valores
              </Button>
              <Button
                type="button"
                size="xs"
                variant={viewMode === "pct" ? "primary-dark" : "ghost"}
                onClick={() => setViewMode("pct")}
              >
                % ventas
              </Button>
            </div>
            <Link
              to="/finance/movements"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Clasificación
            </Link>
            <Link
              to="/finance/import"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Extractos
            </Link>
            <Link
              to="/finance/audit"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Auditoría
            </Link>
            <input
              type="number"
              className="h-8 w-24 rounded-full border border-line bg-cream-50 px-3 text-sm"
              value={year}
              onChange={(e) => setYear(Number(e.target.value) || yearNow)}
            />
            <Button type="button" variant="outline" onClick={() => efe.refetch()}>
              Actualizar
            </Button>
          </div>
        }
      />

      <Card tone="cream" className="flex flex-wrap gap-2 px-4 py-3">
        {(
          [
            ["VENTAS", "Ventas", "bg-sage-500"],
            ["COGS", "COGS", "bg-terracotta-600"],
            ["INGRESO", "Recaudo", "bg-[#3d6b9a]"],
            ["COSTO", "Costos op.", "bg-[#c47a3a]"],
            ["GASTO", "Gastos", "bg-rose-300"],
            ["ADMIN", "Admin", "bg-wine-900"],
            ["PASIVO", "Pasivos", "bg-text-soft"],
          ] as const
        ).map(([kind, label, dot]) => (
          <span
            key={kind}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] label-caps",
              KIND_STYLE[kind]?.row,
              KIND_STYLE[kind]?.label,
            )}
          >
            <span className={cn("h-2 w-2 rounded-full", dot)} />
            {label}
          </span>
        ))}
        <p className="w-full text-[11px] text-text-muted sm:ml-auto sm:w-auto">
          {viewMode === "pct"
            ? `% sobre 1. VENTAS NETAS · mes act. ${focus.current.slice(5)}${
                focus.previous ? ` · mes ant. ${focus.previous.slice(5)}` : ""
              }`
            : "Árbol de cuentas · toggle % ventas para ver peso sobre ventas"}
        </p>
      </Card>

      <Card className="overflow-auto">
        {efe.isLoading ? (
          <p className="text-sm text-text-muted">Cargando EFE…</p>
        ) : (
          <table className="min-w-full text-left">
            <thead>
              <tr className="border-b border-line bg-green-900 text-text-on-dark">
                <th className="sticky left-0 z-10 bg-green-900 px-3 py-2.5 text-[10px] label-caps tracking-wider">
                  Cuenta
                </th>
                {months.map((m) => (
                  <th
                    key={m}
                    className={cn(
                      "px-2.5 py-2.5 text-right text-[10px] label-caps tracking-wider",
                      m === focus.current && "bg-sage-500/30",
                      m === focus.previous && "bg-white/10",
                    )}
                  >
                    {m.slice(5)}
                    {m === focus.current ? " · act" : m === focus.previous ? " · ant" : ""}
                  </th>
                ))}
                {viewMode === "pct" ? (
                  <>
                    <th className="bg-sage-500/40 px-2.5 py-2.5 text-right text-[10px] label-caps">
                      % mes act.
                    </th>
                    <th className="bg-white/10 px-2.5 py-2.5 text-right text-[10px] label-caps">
                      % mes ant.
                    </th>
                    <th className="px-2.5 py-2.5 text-right text-[10px] label-caps">Δ pp</th>
                  </>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {visible.map((line) => {
                const style = KIND_STYLE[line.kind] || KIND_STYLE.PASIVO;
                const type = depthType(line.depth, line.is_leaf);
                const stickyBg = line.depth === 0 ? style.sticky : line.is_leaf ? "bg-warm-white" : style.sticky;
                const curPct = pctOfSales(
                  Number(line.real[focus.current] || 0),
                  salesByMonth[focus.current] || 0,
                );
                const prevPct = focus.previous
                  ? pctOfSales(
                      Number(line.real[focus.previous] || 0),
                      salesByMonth[focus.previous] || 0,
                    )
                  : null;
                const deltaPp =
                  curPct != null && prevPct != null ? curPct - prevPct : null;
                return (
                  <tr
                    key={line.code}
                    className={cn(
                      "border-b border-line/50 transition-colors hover:brightness-[0.98]",
                      line.depth === 0 ? style.row : line.is_leaf ? "bg-warm-white/80" : style.row,
                      type.rowExtra,
                      line.depth === 0 && style.accent,
                    )}
                  >
                    <td className={cn("sticky left-0 z-[1] px-2 py-1.5 whitespace-nowrap", stickyBg)}>
                      <button
                        type="button"
                        className={cn("flex max-w-[320px] items-center gap-1.5 text-left", style.label, type.name)}
                        style={{ paddingLeft: `${Math.min(line.depth, 5) * 14}px` }}
                        onClick={() => {
                          if (line.is_leaf) return;
                          setCollapsed((c) => ({ ...c, [line.code]: !c[line.code] }));
                        }}
                      >
                        {!line.is_leaf ? (
                          <span className="inline-block w-3 shrink-0 text-[10px] opacity-70">
                            {collapsed[line.code] ? "▸" : "▾"}
                          </span>
                        ) : (
                          <span className="inline-block w-3 shrink-0" />
                        )}
                        <span className="truncate">{line.full_label}</span>
                        {line.depth === 0 ? (
                          <Badge variant={style.badge} className="ml-1 shrink-0">
                            {line.kind}
                          </Badge>
                        ) : null}
                      </button>
                    </td>
                    {months.map((m) => {
                      const cell = cellDisplay(line, m);
                      return (
                        <td
                          key={m}
                          title={cell.title}
                          className={cn(
                            "px-2 py-1.5 text-right tabular-nums",
                            type.amount,
                            cell.cls,
                            m === focus.current && "bg-sage-500/10",
                            m === focus.previous && viewMode === "pct" && "bg-cream-100/80",
                          )}
                        >
                          {cell.text}
                        </td>
                      );
                    })}
                    {viewMode === "pct" ? (
                      <>
                        <td
                          className={cn(
                            "bg-sage-500/10 px-2 py-1.5 text-right tabular-nums font-semibold",
                            type.amount,
                            curPct == null ? "text-text-soft" : "text-green-900",
                          )}
                        >
                          {formatPct(curPct)}
                        </td>
                        <td
                          className={cn(
                            "bg-cream-100/80 px-2 py-1.5 text-right tabular-nums",
                            type.amount,
                            prevPct == null ? "text-text-soft" : "text-text-muted",
                          )}
                        >
                          {formatPct(prevPct)}
                        </td>
                        <td
                          className={cn(
                            "px-2 py-1.5 text-right tabular-nums font-medium",
                            type.amount,
                            deltaPp == null
                              ? "text-text-soft"
                              : deltaPp > 0.05
                                ? "text-terracotta-600"
                                : deltaPp < -0.05
                                  ? "text-sage-500"
                                  : "text-text-muted",
                          )}
                        >
                          {deltaPp == null
                            ? "—"
                            : `${deltaPp > 0 ? "+" : ""}${deltaPp.toFixed(1)} pp`}
                        </td>
                      </>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
