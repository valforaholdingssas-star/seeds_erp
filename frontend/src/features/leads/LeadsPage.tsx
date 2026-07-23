import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, type FormEvent } from "react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { KanbanBoard, type KanbanItem } from "@/components/kanban/KanbanBoard";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";

type LeadStatus = "NUEVO" | "CONTACTADO" | "CALIFICADO" | "CONVERTIDO" | "DESCARTADO";

type Lead = {
  id: string;
  name: string;
  email: string;
  phone: string;
  city: string;
  source: string;
  status: LeadStatus;
  seller: string | null;
  seller_name: string | null;
  notes: string;
};

type Paginated<T> = { count: number; results: T[] };
type Board = { columns: Record<string, Lead[]>; count: number };

const STATUSES: LeadStatus[] = [
  "NUEVO",
  "CONTACTADO",
  "CALIFICADO",
  "CONVERTIDO",
  "DESCARTADO",
];

const ALLOWED: Record<LeadStatus, LeadStatus[]> = {
  NUEVO: ["CONTACTADO", "CALIFICADO", "DESCARTADO", "CONVERTIDO"],
  CONTACTADO: ["CALIFICADO", "DESCARTADO", "CONVERTIDO", "NUEVO"],
  CALIFICADO: ["CONVERTIDO", "DESCARTADO", "CONTACTADO"],
  CONVERTIDO: ["DESCARTADO"],
  DESCARTADO: ["NUEVO", "CONTACTADO"],
};

const statusBadge: Record<LeadStatus, "sage" | "terracotta" | "wine" | "dark" | "rose"> = {
  NUEVO: "rose",
  CONTACTADO: "sage",
  CALIFICADO: "dark",
  CONVERTIDO: "sage",
  DESCARTADO: "wine",
};

export function LeadsPage() {
  const qc = useQueryClient();
  const [view, setView] = useState<"kanban" | "tabla">("kanban");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    city: "",
    source: "manual",
    notes: "",
  });

  const leads = useQuery({
    queryKey: ["leads"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Lead> | Lead[]>("/leads/?page_size=200");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const board = useQuery({
    queryKey: ["leads-board"],
    queryFn: async () => {
      const { data } = await apiClient.get<Board>("/leads/board/");
      return data;
    },
  });

  const create = useMutation({
    mutationFn: async () => {
      await apiClient.post("/leads/", {
        ...form,
        name: form.name.trim(),
        status: "NUEVO",
      });
    },
    onSuccess: () => {
      setForm({ name: "", email: "", phone: "", city: "", source: "manual", notes: "" });
      setError(null);
      qc.invalidateQueries({ queryKey: ["leads"] });
      qc.invalidateQueries({ queryKey: ["leads-board"] });
    },
    onError: () => setError("No se pudo crear el lead."),
  });

  const move = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: LeadStatus }) => {
      await apiClient.post(`/leads/${id}/transition/`, { status });
    },
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["leads"] });
      qc.invalidateQueries({ queryKey: ["leads-board"] });
    },
    onError: () => setError("Transición no permitida para ese lead."),
  });

  const columns = useMemo<ColumnDef<Lead, unknown>[]>(
    () => [
      { accessorKey: "name", header: "Nombre" },
      { accessorKey: "city", header: "Ciudad" },
      { accessorKey: "source", header: "Fuente" },
      {
        accessorKey: "status",
        header: "Estado",
        cell: ({ row }) => (
          <Badge variant={statusBadge[row.original.status]}>{row.original.status}</Badge>
        ),
      },
      {
        accessorKey: "seller_name",
        header: "Vendedor",
        cell: ({ row }) => row.original.seller_name || "—",
      },
      { accessorKey: "email", header: "Email" },
      { accessorKey: "phone", header: "Teléfono" },
    ],
    [],
  );

  const kanbanItems = useMemo<KanbanItem[]>(() => {
    const cols = board.data?.columns || {};
    return STATUSES.flatMap((status) =>
      (cols[status] || []).map((lead) => ({
        id: lead.id,
        columnId: status,
        title: lead.name,
        subtitle: `${lead.city || "Sin ciudad"} · ${lead.source}`,
      })),
    );
  }, [board.data]);

  const kanbanColumns = useMemo(
    () =>
      STATUSES.map((status) => ({
        id: status,
        label: status,
        badge: <Badge variant={statusBadge[status]}>{status}</Badge>,
      })),
    [],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("El nombre es obligatorio.");
      return;
    }
    create.mutate();
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-caps text-text-muted">Comercial</p>
          <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">Leads</h1>
          <p className="mt-2 max-w-xl text-text-muted">
            Arrastra tarjetas entre columnas. Las transiciones inválidas se rechazan al soltar.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={view === "kanban" ? "primary-dark" : "outline"}
            size="sm"
            onClick={() => setView("kanban")}
          >
            Kanban
          </Button>
          <Button
            type="button"
            variant={view === "tabla" ? "primary-dark" : "outline"}
            size="sm"
            onClick={() => setView("tabla")}
          >
            Tabla
          </Button>
        </div>
      </header>

      {error && <Alert variant="error">{error}</Alert>}

      <Card tone="cream" className="max-w-3xl">
        <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <FieldLabel htmlFor="lead-name">Nombre</FieldLabel>
            <Input
              id="lead-name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Nombre del lead"
            />
          </div>
          <div>
            <FieldLabel htmlFor="lead-email">Email</FieldLabel>
            <Input
              id="lead-email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel htmlFor="lead-phone">Teléfono</FieldLabel>
            <Input
              id="lead-phone"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel htmlFor="lead-city">Ciudad</FieldLabel>
            <Input
              id="lead-city"
              value={form.city}
              onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
            />
          </div>
          <div>
            <FieldLabel htmlFor="lead-source">Fuente</FieldLabel>
            <Input
              id="lead-source"
              value={form.source}
              onChange={(e) => setForm((f) => ({ ...f, source: e.target.value }))}
            />
          </div>
          <div className="sm:col-span-2 flex justify-end">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Guardando…" : "Agregar lead"}
            </Button>
          </div>
        </form>
      </Card>

      {view === "kanban" ? (
        <KanbanBoard
          columns={kanbanColumns}
          items={kanbanItems}
          canDrop={(item, to) => {
            const from = item.columnId as LeadStatus;
            const target = to as LeadStatus;
            return from === target || (ALLOWED[from] || []).includes(target);
          }}
          onMove={(id, to) => move.mutate({ id, status: to as LeadStatus })}
        />
      ) : (
        <DataTable
          data={leads.data || []}
          columns={columns}
          searchableKeys={["name", "email", "city", "source", "status"]}
          emptyTitle="Sin leads"
          emptyDescription="Crea el primero con el formulario de arriba."
        />
      )}
    </div>
  );
}
