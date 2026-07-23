import { useQuery } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import { DataTable } from "@/components/data/DataTable";
import { Button } from "@/components/ui/Button";
import { FieldLabel, Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

type GeoRow = {
  id: string;
  municipality: string;
  municipality_code: string;
  department: string;
  department_iso: string;
  search: string;
};

type Paginated<T> = { count: number; results: T[] };

export function GeoPage() {
  const [q, setQ] = useState("Bogotá");

  const catalog = useQuery({
    queryKey: ["geo-catalog"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<GeoRow> | GeoRow[]>("/geo/catalog/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const resolve = useQuery({
    queryKey: ["geo-resolve", q],
    queryFn: async () => {
      const { data } = await apiClient.get<{ query: string; matches: GeoRow[] }>(
        "/geo/catalog/resolve/",
        { params: { q } },
      );
      return data;
    },
    enabled: q.trim().length > 0,
  });

  const columns = useMemo<ColumnDef<GeoRow, unknown>[]>(
    () => [
      { accessorKey: "municipality", header: "Municipio" },
      { accessorKey: "municipality_code", header: "DANE" },
      { accessorKey: "department", header: "Departamento" },
      {
        accessorKey: "department_iso",
        header: "ISO",
        cell: ({ getValue }) => <Badge variant="sage">{String(getValue())}</Badge>,
      },
    ],
    [],
  );

  return (
    <div className="space-y-8">
      <header>
        <p className="label-caps text-text-muted">Geografía</p>
        <h1 className="mt-2 font-serif text-4xl tracking-tight text-green-900">
          Catálogo DANE
        </h1>
        <p className="mt-2 max-w-xl text-text-muted">
          Resolución exacta → difusa (pg_trgm). El formateo con IA llega en logística.
        </p>
      </header>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[240px] flex-1">
            <FieldLabel>Probar resolución</FieldLabel>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ciudad…" />
          </div>
          <Button type="button" variant="outline" onClick={() => resolve.refetch()}>
            Resolver
          </Button>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {(resolve.data?.matches || []).map((m) => (
            <Badge key={m.id} variant="dark">
              {m.municipality} · {m.municipality_code} · {m.department_iso}
            </Badge>
          ))}
          {resolve.data && resolve.data.matches.length === 0 ? (
            <p className="text-sm text-terracotta-600">Sin coincidencias (o ciudad bloqueada).</p>
          ) : null}
        </div>
      </Card>

      <DataTable
        data={catalog.data || []}
        columns={columns}
        searchableKeys={["municipality", "department", "municipality_code", "department_iso"]}
        emptyTitle="Catálogo vacío"
        emptyDescription="Ejecuta seed_geo en el backend para cargar municipios frecuentes."
      />
    </div>
  );
}
