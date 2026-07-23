import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";

type IvaSummary = {
  from: string | null;
  to: string | null;
  sales: { iva_generated: string; net_value: string; total_value: string; count: number };
  invoices: { iva: string; total: string; count: number };
};

export function IvaPage() {
  const today = new Date().toISOString().slice(0, 10);
  const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    .toISOString()
    .slice(0, 10);
  const [from, setFrom] = useState(monthStart);
  const [to, setTo] = useState(today);

  const summary = useQuery({
    queryKey: ["iva-summary", from, to],
    queryFn: async () => {
      const { data } = await apiClient.get<IvaSummary>(
        `/accounting/iva/summary/?from=${from}&to=${to}`,
      );
      return data;
    },
  });

  const s = summary.data;

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Contabilidad"
        title="IVA"
        actions={
          <>
            <Link
              to="/accounting"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Facturas
            </Link>
          </>
        }
      />

      <Card tone="cream" className="grid max-w-xl gap-4 sm:grid-cols-2">
        <div>
          <FieldLabel>Desde</FieldLabel>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div>
          <FieldLabel>Hasta</FieldLabel>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </Card>

      <div className="grid gap-5 md:grid-cols-2">
        <Card className="seeds-panel">
          <p className="label-caps text-text-muted">Ventas activas</p>
          <p className="mt-3 font-serif text-4xl text-green-900">
            {formatCOP(Number(s?.sales.iva_generated || 0))}
          </p>
          <p className="mt-2 text-sm text-text-muted">
            IVA generado · {s?.sales.count ?? 0} pedidos · neto{" "}
            {formatCOP(Number(s?.sales.net_value || 0))}
          </p>
        </Card>
        <Card tone="dark" className="seeds-panel-dark">
          <p className="relative z-10 label-caps text-text-on-dark-muted">Facturas</p>
          <p className="relative z-10 mt-3 font-serif text-4xl">
            {formatCOP(Number(s?.invoices.iva || 0))}
          </p>
          <p className="relative z-10 mt-2 text-sm text-text-on-dark-muted">
            IVA en facturas · {s?.invoices.count ?? 0} docs · total{" "}
            {formatCOP(Number(s?.invoices.total || 0))}
          </p>
        </Card>
      </div>
    </div>
  );
}
