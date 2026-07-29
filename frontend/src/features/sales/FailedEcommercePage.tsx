import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonVariants } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn, formatCOP } from "@/lib/utils";

type FollowUpStatus = "POR_CONTACTAR" | "CONTACTADO" | "EN_SEGUIMIENTO" | "CERRADO";

type FailedOrder = {
  id: string;
  channel: "ECOMMERCE" | "SHOPIFY";
  external_id: string;
  status: string;
  deal_name: string;
  closed_at: string | null;
  total_value: string;
  amount_shipping: string;
  payment_account: string;
  customer_name: string;
  email: string;
  phone: string;
  id_number: string;
  address_raw: string;
  city_raw: string;
  state_raw: string;
  qty_dorados: number;
  qty_plateados: number;
  order_notes: string;
  follow_up_status: FollowUpStatus;
  follow_up_notes: string;
  contacted_at: string | null;
  contacted_by_name: string;
  created_at: string | null;
};

type Payload = {
  count: number;
  counts: { total: number; por_contactar: number; contactados: number };
  results: FailedOrder[];
};

const FOLLOW_UPS: FollowUpStatus[] = [
  "POR_CONTACTAR",
  "CONTACTADO",
  "EN_SEGUIMIENTO",
  "CERRADO",
];

const followBadge: Record<FollowUpStatus, "rose" | "sage" | "dark" | "wine"> = {
  POR_CONTACTAR: "rose",
  CONTACTADO: "sage",
  EN_SEGUIMIENTO: "dark",
  CERRADO: "wine",
};

function money(v: string | number | null | undefined) {
  if (v == null || v === "") return "—";
  return formatCOP(Number(v));
}

function fmtDate(v: string | null) {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleString("es-CO", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return v;
  }
}

export function FailedEcommercePage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"por_contactar" | "contactados" | "todos">("por_contactar");
  const [channel, setChannel] = useState<"" | "ECOMMERCE" | "SHOPIFY">("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState<FailedOrder | null>(null);
  const [notes, setNotes] = useState("");
  const [followStatus, setFollowStatus] = useState<FollowUpStatus>("CONTACTADO");

  const contactedParam =
    tab === "por_contactar" ? "0" : tab === "contactados" ? "1" : undefined;

  const list = useQuery({
    queryKey: ["sales-failed-ecommerce", tab, channel, search],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (channel) params.set("channel", channel);
      if (contactedParam) params.set("contacted", contactedParam);
      if (search.trim()) params.set("search", search.trim());
      if (tab === "por_contactar") params.set("follow_up_status", "POR_CONTACTAR");
      const { data } = await apiClient.get<Payload>(
        `/sales/failed-ecommerce/?${params.toString()}`,
      );
      return data;
    },
  });

  const saveMut = useMutation({
    mutationFn: async (payload: {
      id: string;
      channel: string;
      follow_up_status: FollowUpStatus;
      follow_up_notes: string;
      mark_contacted: boolean;
    }) => {
      const { data } = await apiClient.patch<FailedOrder>(
        `/sales/failed-ecommerce/${payload.id}/`,
        {
          channel: payload.channel,
          follow_up_status: payload.follow_up_status,
          follow_up_notes: payload.follow_up_notes,
          mark_contacted: payload.mark_contacted,
        },
      );
      return data;
    },
    onSuccess: () => {
      setOkMsg("Seguimiento actualizado.");
      setError(null);
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["sales-failed-ecommerce"] });
    },
    onError: () => setError("No se pudo guardar el seguimiento."),
  });

  const columns = useMemo<ColumnDef<FailedOrder, unknown>[]>(
    () => [
      {
        accessorKey: "closed_at",
        header: "Fecha",
        cell: ({ row }) => fmtDate(row.original.closed_at || row.original.created_at),
      },
      {
        accessorKey: "channel",
        header: "Canal",
        cell: ({ row }) => (
          <Badge variant="terracotta">
            {row.original.channel === "SHOPIFY" ? "Shopify" : "Woo"}
          </Badge>
        ),
      },
      { accessorKey: "external_id", header: "Pedido" },
      {
        accessorKey: "status",
        header: "Estado tienda",
        cell: ({ row }) => <Badge variant="wine">{row.original.status}</Badge>,
      },
      { accessorKey: "customer_name", header: "Cliente" },
      { accessorKey: "phone", header: "Teléfono" },
      { accessorKey: "email", header: "Email" },
      { accessorKey: "id_number", header: "Cédula" },
      {
        id: "city",
        header: "Ciudad",
        cell: ({ row }) =>
          [row.original.city_raw, row.original.state_raw].filter(Boolean).join(", ") || "—",
      },
      {
        accessorKey: "total_value",
        header: "Valor",
        cell: ({ row }) => money(row.original.total_value),
      },
      {
        accessorKey: "follow_up_status",
        header: "Seguimiento",
        cell: ({ row }) => (
          <Badge variant={followBadge[row.original.follow_up_status]}>
            {row.original.follow_up_status.replaceAll("_", " ")}
          </Badge>
        ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              setEditing(row.original);
              setNotes(row.original.follow_up_notes || "");
              setFollowStatus(
                row.original.follow_up_status === "POR_CONTACTAR"
                  ? "CONTACTADO"
                  : row.original.follow_up_status,
              );
              setOkMsg(null);
              setError(null);
            }}
          >
            Gestionar
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Comercial"
        title="Ecommerce fallidos"
        actions={
          <Link to="/sales" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
            Ir a ventas
          </Link>
        }
      />

      <Alert variant="caution">
        Pedidos de WooCommerce / Shopify que <strong>no llegaron a ventas</strong> (pendiente,
        fallido, cancelado, on-hold…). Úsalos para que la vendedora contacte al cliente y deje
        registro.
      </Alert>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {okMsg ? <Alert variant="success">{okMsg}</Alert> : null}

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["por_contactar", "Por contactar"],
              ["contactados", "Ya contactados"],
              ["todos", "Todos"],
            ] as const
          ).map(([key, label]) => (
            <Button
              key={key}
              type="button"
              size="sm"
              variant={tab === key ? "primary-dark" : "ghost"}
              onClick={() => setTab(key)}
            >
              {label}
              {key === "por_contactar" && list.data?.counts
                ? ` (${list.data.counts.por_contactar})`
                : ""}
              {key === "contactados" && list.data?.counts
                ? ` (${list.data.counts.contactados})`
                : ""}
            </Button>
          ))}
        </div>
        <div>
          <FieldLabel>Canal</FieldLabel>
          <select
            className="rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
            value={channel}
            onChange={(e) => setChannel(e.target.value as typeof channel)}
          >
            <option value="">Todos</option>
            <option value="ECOMMERCE">WooCommerce</option>
            <option value="SHOPIFY">Shopify</option>
          </select>
        </div>
        <div className="min-w-[220px] flex-1">
          <FieldLabel>Buscar</FieldLabel>
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Nombre, teléfono, email, cédula, pedido…"
          />
        </div>
      </div>

      {editing ? (
        <Card className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="font-serif text-lg text-green-900">
                {editing.customer_name || "Sin nombre"} · #{editing.external_id}
              </p>
              <p className="text-sm text-text-muted">
                {editing.channel === "SHOPIFY" ? "Shopify" : "Woo"} · {editing.status} ·{" "}
                {money(editing.total_value)}
              </p>
            </div>
            <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(null)}>
              Cerrar
            </Button>
          </div>
          <div className="grid gap-2 text-sm md:grid-cols-2">
            <p>
              <span className="text-text-muted">Teléfono:</span>{" "}
              {editing.phone ? (
                <a className="underline" href={`tel:${editing.phone}`}>
                  {editing.phone}
                </a>
              ) : (
                "—"
              )}
            </p>
            <p>
              <span className="text-text-muted">Email:</span>{" "}
              {editing.email ? (
                <a className="underline" href={`mailto:${editing.email}`}>
                  {editing.email}
                </a>
              ) : (
                "—"
              )}
            </p>
            <p>
              <span className="text-text-muted">Cédula:</span> {editing.id_number || "—"}
            </p>
            <p>
              <span className="text-text-muted">Ciudad:</span>{" "}
              {[editing.city_raw, editing.state_raw].filter(Boolean).join(", ") || "—"}
            </p>
            <p className="md:col-span-2">
              <span className="text-text-muted">Dirección:</span> {editing.address_raw || "—"}
            </p>
            <p className="md:col-span-2">
              <span className="text-text-muted">Kits:</span> {editing.qty_dorados} dorados ·{" "}
              {editing.qty_plateados} plateados
            </p>
            {editing.order_notes ? (
              <p className="md:col-span-2">
                <span className="text-text-muted">Nota pedido:</span> {editing.order_notes}
              </p>
            ) : null}
            {editing.contacted_at ? (
              <p className="md:col-span-2 text-xs text-text-muted">
                Contactado {fmtDate(editing.contacted_at)}
                {editing.contacted_by_name ? ` por ${editing.contacted_by_name}` : ""}
              </p>
            ) : null}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <FieldLabel>Estado de seguimiento</FieldLabel>
              <select
                className="w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
                value={followStatus}
                onChange={(e) => setFollowStatus(e.target.value as FollowUpStatus)}
              >
                {FOLLOW_UPS.map((s) => (
                  <option key={s} value={s}>
                    {s.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <FieldLabel>Notas de contacto</FieldLabel>
              <textarea
                className="min-h-[88px] w-full rounded-xl border border-border bg-warm-white px-3 py-2 text-sm"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Qué dijo el cliente, compromiso, próximo paso…"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={saveMut.isPending}
              onClick={() =>
                saveMut.mutate({
                  id: editing.id,
                  channel: editing.channel,
                  follow_up_status: followStatus,
                  follow_up_notes: notes,
                  mark_contacted: true,
                })
              }
            >
              {saveMut.isPending ? "Guardando…" : "Marcar contactado y guardar"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={saveMut.isPending}
              onClick={() =>
                saveMut.mutate({
                  id: editing.id,
                  channel: editing.channel,
                  follow_up_status: followStatus,
                  follow_up_notes: notes,
                  mark_contacted: false,
                })
              }
            >
              Solo guardar notas / estado
            </Button>
          </div>
        </Card>
      ) : null}

      <DataTable
        columns={columns}
        data={list.data?.results || []}
        emptyDescription="No hay pedidos fallidos con estos filtros."
      />
    </div>
  );
}
