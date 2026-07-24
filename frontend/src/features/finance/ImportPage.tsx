import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCOP, formatSaleDate } from "@/lib/utils";

type BankCoverage = {
  date_from: string | null;
  date_to: string | null;
  movements: number;
};

type LastImport = {
  batch_id: string;
  uploaded_at: string;
  filename: string;
  date_from: string | null;
  date_to: string | null;
  rows_created: number;
  rows_duplicated: number;
  rows_total: number;
};

type Bank = {
  id: string;
  name: string;
  importer: string;
  active: boolean;
  last_import: LastImport | null;
  coverage: BankCoverage | null;
};

type ImportResult = {
  dry_run: boolean;
  date_from?: string | null;
  date_to?: string | null;
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

function rangeLabel(from: string | null | undefined, to: string | null | undefined) {
  if (!from && !to) return null;
  if (from && to && from === to) return formatSaleDate(from);
  if (from && to) return `${formatSaleDate(from)} → ${formatSaleDate(to)}`;
  return formatSaleDate(from || to);
}

export function ImportPage() {
  const qc = useQueryClient();
  const [bankSlug, setBankSlug] = useState("bancolombia");
  const [file, setFile] = useState<File | null>(null);
  const [last, setLast] = useState<ImportResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const banks = useQuery({
    queryKey: ["finance-banks"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ results: Bank[] } | Bank[]>(
        "/finance/banks/?active=true",
      );
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
      const range = rangeLabel(data.date_from, data.date_to);
      setMessage(
        data.dry_run
          ? `Vista previa${range ? ` · ${range}` : ""}: ${data.rows_new} nuevos, ${data.rows_duplicated} duplicados, ${data.rows_errors} errores`
          : `Importados ${data.rows_new} movimientos${range ? ` (${range})` : ""} · ${data.rows_duplicated} ya existían`,
      );
      if (!data.dry_run) {
        void qc.invalidateQueries({ queryKey: ["finance-banks"] });
      }
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
        {importable.map((b) => {
          const selected =
            bankSlug === b.importer || bankSlug === b.name.toLowerCase();
          const lastRange = rangeLabel(b.last_import?.date_from, b.last_import?.date_to);
          const covRange = rangeLabel(b.coverage?.date_from, b.coverage?.date_to);
          return (
            <button
              key={b.id}
              type="button"
              onClick={() => setBankSlug(b.importer || b.name.toLowerCase())}
              className={`rounded-2xl border p-4 text-left transition ${
                selected
                  ? "border-green-900 bg-cream-100"
                  : "border-line bg-cream-50 hover:bg-cream-100"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="font-serif text-xl text-green-900">{b.name}</p>
                {b.last_import ? (
                  <Badge variant="sage">Con datos</Badge>
                ) : (
                  <Badge variant="terracotta">Sin cargas</Badge>
                )}
              </div>
              <p className="mt-1 text-xs text-text-muted">Parser · {b.importer}</p>

              <div className="mt-3 space-y-1.5 border-t border-line/70 pt-3 text-xs text-green-900">
                {b.last_import ? (
                  <>
                    <p>
                      <span className="label-caps text-text-muted">Último reporte · </span>
                      {lastRange || "sin fechas en el archivo"}
                    </p>
                    <p className="text-text-muted">
                      Subido {formatSaleDate(b.last_import.uploaded_at)}
                      {b.last_import.filename ? ` · ${b.last_import.filename}` : ""}
                    </p>
                    <p className="text-text-muted">
                      {b.last_import.rows_created} nuevos · {b.last_import.rows_duplicated}{" "}
                      duplicados
                    </p>
                  </>
                ) : (
                  <p className="text-text-muted">Aún no hay extractos confirmados para este banco.</p>
                )}
                {covRange ? (
                  <p className="pt-1">
                    <span className="label-caps text-text-muted">Cobertura en ERP · </span>
                    {covRange}
                    {b.coverage?.movements != null ? (
                      <span className="text-text-muted"> · {b.coverage.movements} movs.</span>
                    ) : null}
                  </p>
                ) : null}
              </div>
            </button>
          );
        })}
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
              {last.date_from || last.date_to ? (
                <Badge variant="dark">
                  {rangeLabel(last.date_from, last.date_to)}
                </Badge>
              ) : null}
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
