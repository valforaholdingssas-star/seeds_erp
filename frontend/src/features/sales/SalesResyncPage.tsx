import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { useBatchConsole } from "@/features/batch/batchStore";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";

type Channel = "woo" | "shopify";

export function SalesResyncPage() {
  const openBatch = useBatchConsole((s) => s.openBatch);
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
  const [channel, setChannel] = useState<Channel>("woo");
  const [after, setAfter] = useState(weekAgo);
  const [before, setBefore] = useState(today);
  const [status, setStatus] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const resync = useMutation({
    mutationFn: async () => {
      const path =
        channel === "shopify" ? "/sales/shopify/resync/" : "/sales/ecommerce/resync/";
      const body =
        channel === "shopify"
          ? {
              after,
              before,
              financial_status: status || undefined,
            }
          : {
              after,
              before,
              status: status || undefined,
            };
      const { data } = await apiClient.post<{
        id: string;
        total: number;
        status: string;
      }>(path, body);
      return data;
    },
    onSuccess: (data) => {
      setError(null);
      const label = channel === "shopify" ? "Shopify" : "WooCommerce";
      setMsg(
        data.total === 0
          ? `Sin órdenes en el rango (o ${label} sin credenciales).`
          : `Resync ${label} iniciado: ${data.total} órdenes.`,
      );
      if (data.total > 0) void openBatch(data.id);
    },
    onError: () =>
      setError(
        channel === "shopify"
          ? "No se pudo iniciar el resync. Revisa credenciales Shopify."
          : "No se pudo iniciar el resync. Revisa credenciales Woo.",
      ),
  });

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Ventas"
        title="Resync ecommerce"
        actions={
          <>
            <Link
              to="/sales"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Volver
            </Link>
          </>
        }
      />

      {error && <Alert variant="error">{error}</Alert>}
      {msg && <Alert variant="info">{msg}</Alert>}

      <Card tone="cream" className="max-w-xl space-y-4">
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={channel === "woo" ? "primary-dark" : "ghost"}
            onClick={() => {
              setChannel("woo");
              setStatus("");
              setMsg(null);
              setError(null);
            }}
          >
            WooCommerce
          </Button>
          <Button
            type="button"
            size="sm"
            variant={channel === "shopify" ? "primary-dark" : "ghost"}
            onClick={() => {
              setChannel("shopify");
              setStatus("");
              setMsg(null);
              setError(null);
            }}
          >
            Shopify
          </Button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel>Desde</FieldLabel>
            <Input type="date" value={after} onChange={(e) => setAfter(e.target.value)} />
          </div>
          <div>
            <FieldLabel>Hasta</FieldLabel>
            <Input type="date" value={before} onChange={(e) => setBefore(e.target.value)} />
          </div>
        </div>
        <div>
          <FieldLabel>
            {channel === "shopify"
              ? "Estado financiero (opcional)"
              : "Estado Woo (opcional)"}
          </FieldLabel>
          <Input
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            placeholder={
              channel === "shopify"
                ? "paid,pending,refunded,…"
                : "processing,completed,…"
            }
          />
        </div>
        <Button type="button" disabled={resync.isPending} onClick={() => resync.mutate()}>
          {resync.isPending ? "Consultando…" : "Reconciliar rango"}
        </Button>
      </Card>
    </div>
  );
}
