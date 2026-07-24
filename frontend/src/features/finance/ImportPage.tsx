import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP } from "@/lib/utils";

type Bank = {
  id: string;
  name: string;
  importer: string;
  active: boolean;
};

type ImportResult = {
  dry_run: boolean;
  rows_total: number;
  rows_valid: number;
  rows_new: number;
  rows_duplicated: number;
  rows_errors: number;
  errors: string[];
  preview: Array<{
    date: string;
    value: string;
    item: string;
    concept: string;
    duplicate: boolean;
  }>;
};

export function ImportPage() {
  const [bankSlug, setBankSlug] = useState("bancolombia");
  const [file, setFile] = useState<File | null>(null);
  const [last, setLast] = useState<ImportResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const banks = useQuery({
    queryKey: ["finance-banks"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ results: Bank[] } | Bank[]>("/finance/banks/?active=true");
      return Array.isArray(data) ? data : data.results || [];
    },
  });

  const importable = (banks.data || []).filter((b) => b.importer);

  const run = useMutation({
    mutationFn: async (dryRun: boolean) => {
      if (!file) throw new Error("Selecciona un archivo CSV");
      const fd = new FormData();
      fd.append("file", file);
      fd.append("dry_run", dryRun ? "true" : "false");
      const { data } = await apiClient.post<ImportResult>(
        `/finance/bank-import/${bankSlug}/`,
        fd,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return data;
    },
    onSuccess: (data) => {
      setLast(data);
      setMessage(
        data.dry_run
          ? `Vista previa: ${data.rows_new} nuevos, ${data.rows_duplicated} duplicados, ${data.rows_errors} errores`
          : `Importados ${data.rows_new} movimientos (${data.rows_duplicated} ya existían)`,
      );
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al importar";
      setMessage(String(detail));
    },
  });

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Finanzas"
        title="Carga de extractos"
        actions={
          <Link
            to="/finance/movements"
            className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
          >
            Ir a clasificar
          </Link>
        }
      />

      {message ? <Alert>{message}</Alert> : null}

      <div className="grid gap-3 lg:grid-cols-2">
        {importable.map((b) => (
          <button
            key={b.id}
            type="button"
            onClick={() => setBankSlug(b.importer || b.name.toLowerCase())}
            className={`rounded-2xl border p-4 text-left transition ${
              bankSlug === b.importer || bankSlug === b.name.toLowerCase()
                ? "border-green-900 bg-cream-100"
                : "border-line bg-cream-50 hover:bg-cream-100"
            }`}
          >
            <p className="font-serif text-xl text-green-900">{b.name}</p>
            <p className="mt-1 text-xs text-text-muted">Parser · {b.importer}</p>
          </button>
        ))}
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs grow">
            <span className="label-caps text-text-muted">Archivo CSV</span>
            <input
              type="file"
              accept=".csv,text/csv,text/plain"
              className="mt-1 block w-full text-sm"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
          <Button
            type="button"
            variant="outline"
            disabled={!file || run.isPending}
            onClick={() => run.mutate(true)}
          >
            Previsualizar
          </Button>
          <Button type="button" disabled={!file || run.isPending} onClick={() => run.mutate(false)}>
            Confirmar importación
          </Button>
        </div>

        {last ? (
          <div className="mt-5 space-y-3">
            <div className="flex flex-wrap gap-2">
              <Badge variant="sage">Nuevos {last.rows_new}</Badge>
              <Badge variant="terracotta">Duplicados {last.rows_duplicated}</Badge>
              <Badge variant="wine">Errores {last.rows_errors}</Badge>
              {last.dry_run ? <Badge variant="dark">Dry-run</Badge> : null}
            </div>
            <div className="overflow-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-line label-caps text-text-muted">
                    <th className="px-2 py-2">Fecha</th>
                    <th className="px-2 py-2">Tipo</th>
                    <th className="px-2 py-2 text-right">Valor</th>
                    <th className="px-2 py-2">Concepto</th>
                    <th className="px-2 py-2">Dup</th>
                  </tr>
                </thead>
                <tbody>
                  {last.preview.slice(0, 40).map((r, i) => (
                    <tr key={i} className="border-b border-line/50">
                      <td className="px-2 py-1.5">{r.date}</td>
                      <td className="px-2 py-1.5">{r.item}</td>
                      <td className="px-2 py-1.5 text-right">{formatCOP(Number(r.value))}</td>
                      <td className="px-2 py-1.5 max-w-[320px] truncate">{r.concept}</td>
                      <td className="px-2 py-1.5">{r.duplicate ? "sí" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {last.errors?.length ? (
              <ul className="text-xs text-wine-900">
                {last.errors.slice(0, 10).map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
