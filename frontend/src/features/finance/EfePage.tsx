import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";

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

export function EfePage() {
  const yearNow = new Date().getFullYear();
  const [year, setYear] = useState(yearNow);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const efe = useQuery({
    queryKey: ["finance-efe", year],
    queryFn: async () => {
      const { data } = await apiClient.get<EfeMatrix>(`/finance/efe/?year=${year}`);
      return data;
    },
  });

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

  const months = efe.data?.months || [];

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Finanzas"
        title="Modelo financiero (EFE)"
        actions={
          <div className="flex flex-wrap items-center gap-2">
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

      <Card className="overflow-auto">
        {efe.isLoading ? (
          <p className="text-sm text-text-muted">Cargando EFE…</p>
        ) : (
          <table className="min-w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-[10px] label-caps text-text-muted">
                <th className="sticky left-0 bg-cream-50 px-2 py-2">Cuenta</th>
                {months.map((m) => (
                  <th key={m} className="px-2 py-2 text-right">
                    {m.slice(5)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((line) => (
                <tr
                  key={line.code}
                  className={`border-b border-line/60 ${line.is_leaf ? "" : "bg-cream-100/40 font-medium"}`}
                >
                  <td className="sticky left-0 bg-inherit px-2 py-1.5 whitespace-nowrap">
                    <button
                      type="button"
                      className="text-left text-green-900"
                      style={{ paddingLeft: `${line.depth * 12}px` }}
                      onClick={() => {
                        if (line.is_leaf) return;
                        setCollapsed((c) => ({ ...c, [line.code]: !c[line.code] }));
                      }}
                    >
                      {!line.is_leaf ? (collapsed[line.code] ? "▸ " : "▾ ") : ""}
                      {line.full_label}
                      {!line.is_leaf ? (
                        <Badge variant="sage" className="ml-2">
                          {line.kind}
                        </Badge>
                      ) : null}
                    </button>
                  </td>
                  {months.map((m) => {
                    const v = Number(line.real[m] || 0);
                    return (
                      <td key={m} className="px-2 py-1.5 text-right tabular-nums text-green-900">
                        {v ? formatCOP(v) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
