import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonVariants } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn, formatCOP } from "@/lib/utils";

type GoalRow = {
  seller_id: string;
  seller_name: string;
  months: Record<string, string | null>;
  year_total: string;
};

type GoalsPayload = {
  year: number;
  sellers: GoalRow[];
  saved?: number;
  deleted?: number;
};

const MONTH_LABELS = [
  "Ene",
  "Feb",
  "Mar",
  "Abr",
  "May",
  "Jun",
  "Jul",
  "Ago",
  "Sep",
  "Oct",
  "Nov",
  "Dic",
];

function money(v: string | null | undefined) {
  if (v == null || v === "") return "—";
  return formatCOP(Number(v));
}

export function SalesGoalsPage() {
  const qc = useQueryClient();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const goals = useQuery({
    queryKey: ["seller-monthly-goals", year],
    queryFn: async () => {
      const { data } = await apiClient.get<GoalsPayload>(`/sales/goals/?year=${year}`);
      return data;
    },
  });

  const cellKey = (sellerId: string, month: number) => `${sellerId}:${month}`;

  const dirtyItems = useMemo(() => {
    const items: Array<{ seller_id: string; month: number; amount: string | null }> = [];
    for (const [key, value] of Object.entries(drafts)) {
      const [sellerId, monthStr] = key.split(":");
      const month = Number(monthStr);
      const original =
        goals.data?.sellers.find((s) => s.seller_id === sellerId)?.months[String(month)] ??
        null;
      const normalized = value.trim() === "" ? null : value.trim();
      const origNorm = original == null ? null : String(Number(original));
      const nextNorm = normalized == null ? null : String(Number(normalized));
      if (origNorm !== nextNorm && !(Number.isNaN(Number(normalized)) && normalized != null)) {
        items.push({
          seller_id: sellerId,
          month,
          amount: normalized,
        });
      }
    }
    return items;
  }, [drafts, goals.data]);

  const save = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.put<GoalsPayload>("/sales/goals/", {
        year,
        items: dirtyItems,
      });
      return data;
    },
    onSuccess: (data) => {
      setDrafts({});
      setError(null);
      setMsg(
        `Metas ${year} guardadas` +
          (data.saved != null ? ` · ${data.saved} celdas` : "") +
          (data.deleted ? ` · ${data.deleted} vaciadas` : ""),
      );
      void qc.invalidateQueries({ queryKey: ["seller-monthly-goals", year] });
    },
    onError: () => setError("No se pudieron guardar las metas."),
  });

  const displayValue = (row: GoalRow, month: number) => {
    const key = cellKey(row.seller_id, month);
    if (key in drafts) return drafts[key];
    const v = row.months[String(month)];
    return v == null ? "" : String(Number(v));
  };

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Comercial"
        title="Metas de ventas"
        actions={
          <Link
            to="/sellers"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            Vendedores
          </Link>
        }
      />

      <Alert variant="info">
        Define la meta mensual (COP) de cada comercial. En Métricas se compara venta vs meta del
        mes filtrado. Vaciar una celda quita la meta de ese mes (cae al default global si aplica).
      </Alert>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {msg ? <Alert variant="success">{msg}</Alert> : null}

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <FieldLabel>Año</FieldLabel>
          <Input
            type="number"
            className="w-28"
            value={year}
            onChange={(e) => {
              setYear(Number(e.target.value) || currentYear);
              setDrafts({});
              setMsg(null);
            }}
          />
        </div>
        <Button
          type="button"
          disabled={save.isPending || dirtyItems.length === 0}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Guardando…" : `Guardar cambios (${dirtyItems.length})`}
        </Button>
      </div>

      <Card className="overflow-x-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-text-muted">
              <th className="sticky left-0 bg-warm-white px-3 py-2 font-medium">Comercial</th>
              {MONTH_LABELS.map((label) => (
                <th key={label} className="px-2 py-2 text-center font-medium">
                  {label}
                </th>
              ))}
              <th className="px-3 py-2 text-right font-medium">Total año</th>
            </tr>
          </thead>
          <tbody>
            {(goals.data?.sellers || []).map((row) => (
              <tr key={row.seller_id} className="border-b border-border/60">
                <td className="sticky left-0 bg-warm-white px-3 py-2 font-medium text-green-900">
                  {row.seller_name}
                </td>
                {MONTH_LABELS.map((_, idx) => {
                  const month = idx + 1;
                  return (
                    <td key={month} className="px-1 py-1">
                      <input
                        className="w-[6.5rem] rounded-lg border border-border bg-cream-50 px-2 py-1.5 text-right text-xs tabular-nums"
                        inputMode="decimal"
                        placeholder="—"
                        value={displayValue(row, month)}
                        onChange={(e) =>
                          setDrafts((d) => ({
                            ...d,
                            [cellKey(row.seller_id, month)]: e.target.value,
                          }))
                        }
                      />
                    </td>
                  );
                })}
                <td className="px-3 py-2 text-right tabular-nums text-text-muted">
                  {money(row.year_total)}
                </td>
              </tr>
            ))}
            {!goals.data?.sellers?.length ? (
              <tr>
                <td colSpan={14} className="px-3 py-8 text-center text-text-muted">
                  No hay comerciales activos (se excluyen ECOMMERCE / Ecommerce 2 / FERIAS).
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
