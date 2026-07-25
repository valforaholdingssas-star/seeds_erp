import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";

type DryRun = {
  headers: string[];
  mapping: Record<string, string | null>;
  total: number;
  valid: number;
  invalid: number;
  rows: Array<{ row: number; ok: boolean; errors: string[]; data?: { external_id: string } }>;
};

type CommitResult = {
  created: number;
  updated: number;
  skipped: number;
  rejected: number;
};

const SAMPLE = `external_id,source,customer_name,city_raw,total_value,qty_dorados,commercial_raw,status,guia,costo_guia,fecha_envio
CSV-DEMO-1,KOMMO,Ana Demo,Bogotá,189000,1,COMERCIAL 1,completed,76116478969,18500,2026-01-15
CSV-DEMO-2,MANUAL,Luis Demo,Medellín,250000,2,VENDEDORA 1,completed,76116478000,15200,2026-01-16
CSV-BAD,,Sin Nombre,,abc,0,,completed,,,
`;

export function SalesImportPage() {
  const [csv, setCsv] = useState(SAMPLE);
  const [file, setFile] = useState<File | null>(null);
  const [dry, setDry] = useState<DryRun | null>(null);
  const [commit, setCommit] = useState<CommitResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onDuplicate, setOnDuplicate] = useState<"skip" | "update">("skip");

  async function postImport(dryRun: boolean) {
    if (file) {
      const form = new FormData();
      form.append("file", file);
      form.append("dry_run", String(dryRun));
      form.append("on_duplicate", onDuplicate);
      if (!dryRun && dry?.mapping) {
        form.append("mapping", JSON.stringify(dry.mapping));
      }
      const { data } = await apiClient.post("/sales/import/", form);
      return data;
    }
    const { data } = await apiClient.post("/sales/import/", {
      csv,
      dry_run: dryRun,
      on_duplicate: onDuplicate,
      mapping: dry?.mapping,
    });
    return data;
  }

  const dryRunMut = useMutation({
    mutationFn: async () => postImport(true) as Promise<DryRun>,
    onSuccess: (data) => {
      setDry(data);
      setCommit(null);
      setError(null);
    },
    onError: () => setError("No se pudo validar el archivo."),
  });

  const confirm = useMutation({
    mutationFn: async () => postImport(false) as Promise<CommitResult>,
    onSuccess: (data) => {
      setCommit(data);
      setError(null);
    },
    onError: () => setError("No se pudo importar."),
  });

  function onFile(picked: File | null) {
    if (!picked) return;
    const name = picked.name.toLowerCase();
    setDry(null);
    setCommit(null);
    if (name.endsWith(".xlsx") || name.endsWith(".xlsm")) {
      setFile(picked);
      setCsv("");
      return;
    }
    setFile(null);
    const reader = new FileReader();
    reader.onload = () => {
      setCsv(String(reader.result || ""));
    };
    reader.readAsText(picked);
  }

  return (
    <div className="space-y-3">
      <PageHeader
        eyebrow="Ventas"
        title="Importar CSV / XLSX"
        actions={
          <>
            <Link
              to="/sales"
              className="inline-flex min-h-7 items-center rounded-[999px] border border-line px-3 text-[10px] label-caps"
            >
              Volver a ventas
            </Link>
          </>
        }
      />

      {error && <Alert variant="error">{error}</Alert>}

      <Card tone="cream" className="seeds-panel space-y-4">
        <p className="text-sm text-text-muted">
          Compatible con el export de Excel (Deal ID, NÚMERO DE GUÍA, TRASPORTE, ENVIADO, etc.).
          Filas sin valor se omiten. Con guía se marca <strong>ENVIADO</strong> sin regenerar Envia ni
          descontar inventario.
        </p>
        <div className="flex flex-wrap gap-3">
          <label className="inline-flex min-h-11 cursor-pointer items-center rounded-[999px] border border-line px-6 label-caps">
            Elegir archivo
            <input
              type="file"
              accept=".csv,.xlsx,.xlsm,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="hidden"
              onChange={(e) => onFile(e.target.files?.[0] || null)}
            />
          </label>
          {file ? (
            <Badge variant="sage">Excel · {file.name}</Badge>
          ) : (
            <Badge variant="dark">Texto CSV</Badge>
          )}
          <select
            className="rounded-[999px] border border-line bg-warm-white px-4 py-2 text-sm"
            value={onDuplicate}
            onChange={(e) => setOnDuplicate(e.target.value as "skip" | "update")}
          >
            <option value="skip">Duplicados: saltar</option>
            <option value="update">Duplicados: actualizar</option>
          </select>
          <Button
            type="button"
            variant="outline"
            onClick={() => dryRunMut.mutate()}
            disabled={dryRunMut.isPending || (!csv.trim() && !file)}
          >
            {dryRunMut.isPending ? "Validando…" : "Dry-run"}
          </Button>
          <Button
            type="button"
            disabled={!dry || dry.valid === 0 || confirm.isPending}
            onClick={() => confirm.mutate()}
          >
            {confirm.isPending ? "Importando…" : `Confirmar ${dry?.valid || 0} válidas`}
          </Button>
        </div>
        {!file ? (
          <textarea
            className="min-h-56 w-full rounded-[20px] border border-line bg-warm-white px-4 py-3 font-mono text-xs outline-none focus:ring-2 focus:ring-sage-500/30"
            value={csv}
            onChange={(e) => {
              setCsv(e.target.value);
              setFile(null);
              setDry(null);
              setCommit(null);
            }}
          />
        ) : (
          <p className="rounded-[20px] border border-dashed border-line bg-warm-white/70 px-4 py-6 text-sm text-text-muted">
            El archivo Excel se envía al servidor en dry-run/confirm. Quita el archivo para editar
            CSV a mano.
            <button
              type="button"
              className="ml-2 label-caps text-terracotta-600 underline"
              onClick={() => {
                setFile(null);
                setCsv(SAMPLE);
              }}
            >
              Quitar Excel
            </button>
          </p>
        )}
      </Card>

      {dry && (
        <Card tone="warm-white">
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge variant="dark">{dry.total} filas</Badge>
            <Badge variant="sage">{dry.valid} válidas</Badge>
            <Badge variant="wine">{dry.invalid} inválidas</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line label-caps text-text-muted">
                  <th className="py-2 pr-4">Fila</th>
                  <th className="py-2 pr-4">Estado</th>
                  <th className="py-2">Detalle</th>
                </tr>
              </thead>
              <tbody>
                {dry.rows.slice(0, 40).map((r) => (
                  <tr key={r.row} className="border-b border-line/60">
                    <td className="py-2 pr-4">{r.row}</td>
                    <td className="py-2 pr-4">
                      {r.ok ? (
                        <Badge variant="sage">OK</Badge>
                      ) : (
                        <Badge variant="wine">Error</Badge>
                      )}
                    </td>
                    <td className="py-2 text-text-muted">
                      {r.ok ? r.data?.external_id : (r.errors || []).join("; ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {commit && (
        <Alert variant="success">
          Importadas: {commit.created} creadas · {commit.updated} actualizadas ·{" "}
          {commit.skipped} saltadas · {commit.rejected} rechazadas.
        </Alert>
      )}
    </div>
  );
}
