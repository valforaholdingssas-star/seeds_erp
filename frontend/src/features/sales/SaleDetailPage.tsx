import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP, formatSaleDate } from "@/lib/utils";
import { formatSaleItemLine } from "@/lib/kitTypes";

type SaleDetail = {
  id: string;
  source: string;
  external_id: string;
  customer_name: string;
  email: string;
  phone: string;
  id_number: string;
  address_raw: string;
  city_raw: string;
  state_raw: string;
  amount_products: string;
  amount_shipping: string;
  total_value: string;
  iva_generated: string;
  net_value: string;
  payment_account: string;
  payment_method_detail: { id: string; name: string } | null;
  income_source: string;
  status: string;
  state: string;
  deal_name: string;
  stage: string;
  closed_at: string | null;
  symptoms: string;
  order_notes: string;
  age: string;
  requires_shipping: boolean;
  fulfillment_type: "ENVIA" | "DOMICILIO" | "OFICINA";
  withdrawn_reason: string;
  seller_detail: { id: string; name: string } | null;
  items: { id: string; color: string; tipo: string; quantity: number; product_name: string }[];
  shipment: {
    id: string;
    status: string;
    tracking_number: string;
    label_url: string;
    shipping_cost: string | null;
    warning: boolean;
    do_not_ship: boolean;
    city_mirror: string;
    address_mirror: string;
  } | null;
  invoice: {
    id: string;
    status: string;
    number: string;
    total: string;
    iva: string;
    pdf_url: string;
  } | null;
};

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="label-caps text-text-muted">{label}</p>
      <p className="mt-1 text-green-900">{value || "—"}</p>
    </div>
  );
}

export function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const sale = useQuery({
    queryKey: ["sale", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<SaleDetail>(`/sales/${id}/`);
      return data;
    },
  });

  const withdraw = useMutation({
    mutationFn: async () => {
      await apiClient.post(`/sales/${id}/withdraw/`, { reason: "desde detalle" });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sale", id] });
      qc.invalidateQueries({ queryKey: ["sales"] });
    },
  });

  if (sale.isLoading) {
    return <p className="text-text-muted">Cargando venta…</p>;
  }

  if (sale.isError || !sale.data) {
    return (
      <Alert variant="error">
        No encontramos esa venta.{" "}
        <Link to="/sales" className="underline">
          Volver
        </Link>
      </Alert>
    );
  }

  const s = sale.data;

  return (
    <div className="space-y-3" data-testid="sale-detail">
      <PageHeader
        eyebrow="Ventas"
        title={s.customer_name || s.external_id}
        actions={
          <>
            <Link
              to="/sales"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Volver
            </Link>
            {s.state === "ACTIVE" ? (
              <Button
                type="button"
                variant="primary-wine"
                size="xs"
                onClick={() => withdraw.mutate()}
                disabled={withdraw.isPending}
              >
                Retirar
              </Button>
            ) : null}
          </>
        }
      />

      <p className="text-sm text-text-muted">
        {s.external_id} · {s.source}
      </p>

      <div className="flex flex-wrap gap-2">
        <Badge variant="dark">{s.source}</Badge>
        <Badge variant="sage">{s.status}</Badge>
        <Badge variant={s.state === "ACTIVE" ? "sage" : "terracotta"}>{s.state}</Badge>
        <Badge
          variant={
            s.fulfillment_type === "ENVIA"
              ? "dark"
              : s.fulfillment_type === "DOMICILIO"
                ? "terracotta"
                : "sage"
          }
        >
          {s.fulfillment_type === "ENVIA"
            ? "Envia"
            : s.fulfillment_type === "DOMICILIO"
              ? "Domicilio (sin Envia)"
              : "Oficina"}
        </Badge>
        {s.seller_detail ? <Badge variant="dark">{s.seller_detail.name}</Badge> : null}
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="seeds-panel space-y-4 lg:col-span-2">
          <h2 className="font-serif text-2xl text-green-900">Cliente</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nombre" value={s.customer_name} />
            <Field label="Fecha de venta" value={formatSaleDate(s.closed_at)} />
            <Field label="Documento" value={s.id_number} />
            <Field label="Email" value={s.email} />
            <Field label="Teléfono" value={s.phone} />
            <Field label="Ciudad" value={[s.city_raw, s.state_raw].filter(Boolean).join(", ")} />
            <Field label="Dirección" value={s.address_raw} />
          </div>
        </Card>

        <Card tone="dark" className="seeds-panel-dark space-y-4">
          <p className="relative z-10 label-caps text-text-on-dark-muted">Fiscal</p>
          <p className="relative z-10 font-serif text-4xl">{formatCOP(Number(s.total_value))}</p>
          <div className="relative z-10 space-y-2 text-sm text-text-on-dark-muted">
            <p>Productos · {formatCOP(Number(s.amount_products))}</p>
            <p>Envío · {formatCOP(Number(s.amount_shipping))}</p>
            <p>IVA · {formatCOP(Number(s.iva_generated))}</p>
            <p>Neto · {formatCOP(Number(s.net_value))}</p>
            <p>Cuenta · {s.payment_method_detail?.name || s.payment_account || "—"}</p>
          </div>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="font-serif text-2xl text-green-900">Kits</h2>
          {s.items?.length ? (
            <ul className="space-y-2">
              {s.items.map((it) => (
                <li
                  key={it.id}
                  className="flex items-center justify-between rounded-[16px] border border-line px-4 py-3"
                >
                  <span>{formatSaleItemLine(it)}</span>
                  <Badge variant="sage">{it.color}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-text-muted">Sin kits desglosados.</p>
          )}
        </Card>

        <Card className="space-y-3">
          <h2 className="font-serif text-2xl text-green-900">Notas</h2>
          <Field label="Deal" value={s.deal_name} />
          <Field label="Síntomas" value={s.symptoms} />
          <Field label="Edad" value={s.age} />
          <Field label="Notas" value={s.order_notes} />
          {s.withdrawn_reason ? (
            <Field label="Retiro" value={s.withdrawn_reason} />
          ) : null}
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-serif text-2xl text-green-900">Envío</h2>
            <Link to="/logistics" className="label-caps text-sage-500">
              Ir a logística
            </Link>
          </div>
          {s.shipment ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Estado" value={<Badge variant="dark">{s.shipment.status}</Badge>} />
              <Field label="Guía" value={s.shipment.tracking_number} />
              <Field label="Ciudad" value={s.shipment.city_mirror} />
              <Field label="Dirección" value={s.shipment.address_mirror} />
              <Field
                label="Costo"
                value={
                  s.shipment.shipping_cost
                    ? formatCOP(Number(s.shipment.shipping_cost))
                    : "—"
                }
              />
              {s.shipment.label_url ? (
                <div>
                  <p className="label-caps text-text-muted">Etiqueta</p>
                  <a
                    href={s.shipment.label_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-block text-sm text-sage-600 underline underline-offset-2 hover:text-green-900"
                  >
                    Abrir PDF
                  </a>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-text-muted">
              {s.fulfillment_type === "ENVIA"
                ? "Aún sin registro de envío."
                : s.fulfillment_type === "DOMICILIO"
                  ? "Domicilio fuera de Envia: no genera guía."
                  : "Visita a oficina: no genera guía."}
            </p>
          )}
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-serif text-2xl text-green-900">Factura</h2>
            <Link to="/accounting" className="label-caps text-sage-500">
              Ir a facturas
            </Link>
          </div>
          {s.invoice ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Estado" value={<Badge variant="dark">{s.invoice.status}</Badge>} />
              <Field label="Número" value={s.invoice.number} />
              <Field label="Total" value={formatCOP(Number(s.invoice.total))} />
              <Field label="IVA" value={formatCOP(Number(s.invoice.iva))} />
              {s.invoice.pdf_url ? (
                <a
                  href={s.invoice.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                  className="label-caps text-terracotta-600 underline sm:col-span-2"
                >
                  Ver PDF
                </a>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-text-muted">Sin factura asociada aún.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
