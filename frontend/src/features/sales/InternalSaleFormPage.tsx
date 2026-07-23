import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { KIT_TYPES } from "@/lib/kitTypes";

type Mode = "ferias" | "manual";

type Seller = { id: string; name: string; is_system: boolean };
type PaymentMethod = { id: string; name: string; active: boolean };

const FULFILLMENT_OPTIONS = [
  {
    value: "ENVIA",
    label: "Envia (genera guía)",
    hint: "Sale en logística y crea guía con Envia.",
  },
  {
    value: "DOMICILIO",
    label: "Domicilio fuera de Envia",
    hint: "Entrega local/propia. No genera guía.",
  },
  {
    value: "OFICINA",
    label: "Visita / recoger en oficina",
    hint: "El cliente pasa por oficina. No genera guía.",
  },
] as const;

export function InternalSaleFormPage({ mode }: { mode: Mode }) {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    customer_name: "",
    email: "",
    phone: "",
    id_number: "",
    address_raw: "",
    city_raw: "",
    state_raw: "",
    total_value: "",
    amount_shipping: "0",
    payment_method: "",
    fulfillment_type: "ENVIA",
    qty_dorados: "0",
    qty_plateados: "0",
    tipo_dorados: "",
    tipo_plateados: "",
    commercial_raw: mode === "ferias" ? "FERIAS" : "",
    order_notes: "",
  });

  const sellers = useQuery({
    queryKey: ["sellers-mini"],
    enabled: mode === "manual",
    queryFn: async () => {
      const { data } = await apiClient.get<{ results: Seller[] } | Seller[]>("/sellers/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const paymentMethods = useQuery({
    queryKey: ["payment-methods-active"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ results: PaymentMethod[] } | PaymentMethod[]>(
        "/payment-methods/",
        { params: { active_only: "1" } },
      );
      return Array.isArray(data) ? data : data.results;
    },
  });

  const create = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        payment_method: form.payment_method || null,
        payment_account: undefined,
        total_value: form.total_value,
        amount_shipping: form.amount_shipping || "0",
        qty_dorados: Number(form.qty_dorados || 0),
        qty_plateados: Number(form.qty_plateados || 0),
      };
      const path = mode === "ferias" ? "/sales/ferias/" : "/sales/manual/";
      await apiClient.post(path, payload);
    },
    onSuccess: () => navigate("/sales"),
    onError: () =>
      setError("No se pudo guardar. Revisa cliente, ciudad/dirección y cantidades."),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  const title = mode === "ferias" ? "Venta de feria" : "Venta manual";

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <Link to="/sales" className="label-caps text-text-muted hover:text-green-900">
          ← Consolidado
        </Link>
        <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">{title}</h1>
        <p className="mt-2 text-text-muted">
          Se escribe en origen y se promueve al consolidado si el estado es válido.
        </p>
      </header>

      <Card>
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <FieldLabel>Cliente</FieldLabel>
            <Input
              required
              value={form.customer_name}
              onChange={(e) => setForm((f) => ({ ...f, customer_name: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel>Email</FieldLabel>
            <Input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel>Teléfono</FieldLabel>
            <Input
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel>Cédula</FieldLabel>
            <Input
              value={form.id_number}
              onChange={(e) => setForm((f) => ({ ...f, id_number: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel>Medio de pago</FieldLabel>
            <Select
              required
              value={form.payment_method}
              onChange={(e) => setForm((f) => ({ ...f, payment_method: e.target.value }))}
            >
              <option value="">Selecciona…</option>
              {(paymentMethods.data || []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <FieldLabel>Tipo de entrega</FieldLabel>
            <Select
              required
              value={form.fulfillment_type}
              onChange={(e) =>
                setForm((f) => ({ ...f, fulfillment_type: e.target.value }))
              }
            >
              {FULFILLMENT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
            <p className="mt-2 text-sm text-text-muted">
              {
                FULFILLMENT_OPTIONS.find((o) => o.value === form.fulfillment_type)
                  ?.hint
              }
            </p>
          </div>
          <div className="md:col-span-2">
            <FieldLabel>Dirección</FieldLabel>
            <Input
              value={form.address_raw}
              onChange={(e) => setForm((f) => ({ ...f, address_raw: e.target.value }))}
              required={form.fulfillment_type === "ENVIA"}
              placeholder={
                form.fulfillment_type === "ENVIA"
                  ? "Obligatoria para Envia"
                  : "Opcional"
              }
            />
          </div>
          <div>
            <FieldLabel>Ciudad</FieldLabel>
            <Input
              value={form.city_raw}
              onChange={(e) => setForm((f) => ({ ...f, city_raw: e.target.value }))}
              required={form.fulfillment_type === "ENVIA"}
            />
          </div>
          <div>
            <FieldLabel>Depto / municipio</FieldLabel>
            <Input
              value={form.state_raw}
              onChange={(e) => setForm((f) => ({ ...f, state_raw: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel>Valor total</FieldLabel>
            <Input
              required
              type="number"
              min="0"
              step="0.01"
              value={form.total_value}
              onChange={(e) => setForm((f) => ({ ...f, total_value: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel>Transporte</FieldLabel>
            <Input
              type="number"
              min="0"
              step="0.01"
              value={form.amount_shipping}
              onChange={(e) => setForm((f) => ({ ...f, amount_shipping: e.target.value }))}
            />
          </div>
          <div className="md:col-span-2 rounded-[24px] border border-line bg-cream-100/50 p-4">
            <p className="label-caps text-text-muted">Kits</p>
            <p className="mt-1 text-sm text-text-muted">
              Primero el tipo (10, 20 o 30 semillas), luego cuántos kits de ese tipo en
              dorado o plateado.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-3 rounded-[20px] border border-line bg-warm-white p-4">
                <p className="font-medium text-green-900">Dorados</p>
                <div>
                  <FieldLabel>Tipo de kit</FieldLabel>
                  <Select
                    value={form.tipo_dorados}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, tipo_dorados: e.target.value }))
                    }
                  >
                    <option value="">Selecciona…</option>
                    {KIT_TYPES.map((k) => (
                      <option key={k.value} value={k.value}>
                        {k.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <FieldLabel>Cantidad de kits</FieldLabel>
                  <Input
                    type="number"
                    min="0"
                    value={form.qty_dorados}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, qty_dorados: e.target.value }))
                    }
                  />
                </div>
              </div>
              <div className="space-y-3 rounded-[20px] border border-line bg-warm-white p-4">
                <p className="font-medium text-green-900">Plateados</p>
                <div>
                  <FieldLabel>Tipo de kit</FieldLabel>
                  <Select
                    value={form.tipo_plateados}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, tipo_plateados: e.target.value }))
                    }
                  >
                    <option value="">Selecciona…</option>
                    {KIT_TYPES.map((k) => (
                      <option key={k.value} value={k.value}>
                        {k.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <FieldLabel>Cantidad de kits</FieldLabel>
                  <Input
                    type="number"
                    min="0"
                    value={form.qty_plateados}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, qty_plateados: e.target.value }))
                    }
                  />
                </div>
              </div>
            </div>
          </div>
          {mode === "manual" ? (
            <div className="md:col-span-2">
              <FieldLabel>Vendedor</FieldLabel>
              <Select
                required
                value={form.commercial_raw}
                onChange={(e) => setForm((f) => ({ ...f, commercial_raw: e.target.value }))}
              >
                <option value="">Selecciona…</option>
                {(sellers.data || [])
                  .filter((s) => !s.is_system)
                  .map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name}
                    </option>
                  ))}
              </Select>
            </div>
          ) : null}
          <div className="md:col-span-2">
            <FieldLabel>Notas</FieldLabel>
            <Textarea
              value={form.order_notes}
              onChange={(e) => setForm((f) => ({ ...f, order_notes: e.target.value }))}
            />
          </div>
          {error ? (
            <div className="md:col-span-2">
              <Alert variant="error">{error}</Alert>
            </div>
          ) : null}
          <div className="md:col-span-2 flex gap-3">
            <Button type="button" variant="ghost" onClick={() => navigate("/sales")}>
              Cancelar
            </Button>
            <Button type="submit" disabled={create.isPending}>
              Guardar venta
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
