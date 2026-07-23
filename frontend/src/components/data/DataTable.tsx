import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
} from "@tanstack/react-table";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Download, Filter, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { FieldLabel, Input } from "@/components/ui/Input";

export type ColumnFilterSpec = {
  key: string;
  label: string;
  type?: "text" | "select";
  options?: string[];
};

export type DataTableProps<T> = {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  searchableKeys?: (keyof T)[];
  columnFilters?: ColumnFilterSpec[];
  emptyTitle?: string;
  emptyDescription?: string;
  onSelectionChange?: (rows: T[]) => void;
  bulkActions?: ReactNode;
  exportFilename?: string;
  /** Acciones extra a la derecha de la barra (antes de filtros/export) */
  toolbarActions?: ReactNode;
  hint?: string;
};

export function DataTable<T extends { id: string }>({
  data,
  columns,
  searchableKeys = [],
  columnFilters = [],
  emptyTitle = "Sin resultados",
  emptyDescription = "Ajusta los filtros o espera a que lleguen datos.",
  onSelectionChange,
  bulkActions,
  exportFilename,
  toolbarActions,
  hint,
}: DataTableProps<T>) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [draftFilters, setDraftFilters] = useState<Record<string, string>>({});
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((v) => v.trim()).length,
    [filters],
  );

  const filtered = useMemo(() => {
    let rows = data;
    if (query.trim() && searchableKeys.length) {
      const q = query.toLowerCase();
      rows = rows.filter((row) =>
        searchableKeys.some((key) =>
          String(row[key] ?? "")
            .toLowerCase()
            .includes(q),
        ),
      );
    }
    for (const [key, value] of Object.entries(filters)) {
      if (!value.trim()) continue;
      const v = value.toLowerCase();
      rows = rows.filter((row) => {
        const raw = (row as Record<string, unknown>)[key];
        if (typeof raw === "boolean") {
          return String(raw) === v;
        }
        return String(raw ?? "")
          .toLowerCase()
          .includes(v);
      });
    }
    return rows;
  }, [data, query, searchableKeys, filters]);

  const table = useReactTable({
    data: filtered,
    columns,
    state: { rowSelection },
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  });

  const selected = table.getSelectedRowModel().rows.map((r) => r.original);

  useEffect(() => {
    onSelectionChange?.(selected);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowSelection, filtered]);

  function openFilters() {
    setDraftFilters(filters);
    setFiltersOpen(true);
  }

  function applyFilters() {
    setFilters(draftFilters);
    setFiltersOpen(false);
  }

  function clearFilters() {
    setDraftFilters({});
    setFilters({});
    setFiltersOpen(false);
  }

  function exportCsv() {
    if (!filtered.length) return;
    const keys = Object.keys(filtered[0] as object).filter((k) => k !== "items");
    const lines = [
      keys.join(","),
      ...filtered.map((row) =>
        keys
          .map((k) => {
            const raw = String((row as Record<string, unknown>)[k] ?? "");
            return `"${raw.replaceAll('"', '""')}"`;
          })
          .join(","),
      ),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportFilename || "seeds-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      {/* Barra de herramientas */}
      <div className="flex flex-col gap-3 rounded-[28px] border border-line bg-warm-white/90 p-3 shadow-[var(--shadow-1)] sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4">
        <div className="relative min-w-0 flex-1">
          <Search
            strokeWidth={1.5}
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-soft"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar…"
            aria-label="Buscar"
            className="w-full rounded-[999px] border border-line bg-cream-100/80 py-2.5 pl-10 pr-4 text-sm text-text-dark outline-none transition-all focus:border-green-900/30 focus:ring-2 focus:ring-sage-500/25"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {toolbarActions}
          {columnFilters.length > 0 ? (
            <Button type="button" size="sm" variant="primary-dark" onClick={openFilters}>
              <Filter strokeWidth={1.5} className="h-3.5 w-3.5" />
              Filtros
              {activeFilterCount > 0 ? (
                <span className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-text-on-dark/20 px-1.5 text-[10px]">
                  {activeFilterCount}
                </span>
              ) : null}
            </Button>
          ) : null}
          {exportFilename !== undefined ? (
            <Button type="button" size="sm" variant="outline" onClick={exportCsv}>
              <Download strokeWidth={1.5} className="h-3.5 w-3.5" />
              Exportar
            </Button>
          ) : null}
          <span className="hidden label-caps text-text-soft sm:inline">
            {filtered.length} reg.
          </span>
        </div>
      </div>

      {activeFilterCount > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {columnFilters.map((f) => {
            const val = filters[f.key];
            if (!val?.trim()) return null;
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilters((prev) => ({ ...prev, [f.key]: "" }))}
                className="inline-flex items-center gap-1.5 rounded-full border border-line bg-cream-100 px-3 py-1.5 text-[10px] label-caps text-green-900 transition-colors hover:bg-warm-white"
              >
                {f.label}: {val}
                <X strokeWidth={1.5} className="h-3 w-3 text-text-soft" />
              </button>
            );
          })}
          <button
            type="button"
            onClick={clearFilters}
            className="label-caps text-text-soft hover:text-green-900"
          >
            Limpiar filtros
          </button>
        </div>
      ) : null}

      {hint ? <p className="text-sm text-text-muted">{hint}</p> : null}

      {selected.length > 0 && bulkActions ? (
        <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-[24px] border border-green-900/15 bg-green-900 px-5 py-3 text-text-on-dark shadow-[var(--shadow-2)]">
          <span className="label-caps text-text-on-dark-muted">{selected.length} seleccionados</span>
          <span className="spark" aria-hidden>
            ✦
          </span>
          <div className="flex flex-wrap gap-2">{bulkActions}</div>
          <button
            type="button"
            className="ml-auto label-caps text-text-on-dark-muted hover:text-text-on-dark"
            onClick={() => setRowSelection({})}
          >
            Limpiar
          </button>
        </div>
      ) : null}

      <div className="seeds-panel overflow-hidden rounded-[28px] border border-line shadow-[var(--shadow-1)]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] border-collapse text-left text-sm">
            <thead className="bg-green-900/[0.04]">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-line">
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className="whitespace-nowrap label-caps px-4 py-3.5 font-medium text-text-muted"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="px-6 py-16 text-center">
                    <p className="font-serif text-2xl text-green-900">{emptyTitle}</p>
                    <p className="mt-2 text-text-muted">{emptyDescription}</p>
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className={cn(
                      "border-b border-line/70 transition-colors duration-[160ms] ease-soft hover:bg-green-900/[0.025]",
                      row.getIsSelected() && "bg-sage-500/10",
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className="whitespace-nowrap px-4 py-3.5 align-middle text-text-dark"
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Popup de filtros */}
      {filtersOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
          <button
            type="button"
            className="absolute inset-0 bg-green-950/40 backdrop-blur-[2px]"
            aria-label="Cerrar filtros"
            onClick={() => setFiltersOpen(false)}
          />
          <div className="relative z-10 w-full max-w-lg animate-[fade-up_280ms_var(--ease-soft)] rounded-t-[32px] border border-line bg-cream-100 p-6 shadow-[var(--shadow-3)] sm:rounded-[32px] sm:p-8">
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <p className="label-caps text-text-muted">Tabla</p>
                <h2 className="mt-1 font-serif text-3xl text-green-900">Filtros</h2>
                <p className="mt-1 text-sm text-text-muted">
                  Aplica y cierra. Los activos quedan como chips arriba.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setFiltersOpen(false)}
                className="rounded-full border border-line p-2 text-green-900 hover:bg-warm-white"
                aria-label="Cerrar"
              >
                <X strokeWidth={1.5} className="h-4 w-4" />
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {columnFilters.map((f) => (
                <div key={f.key} className={f.type === "select" ? "" : "sm:col-span-2"}>
                  <FieldLabel>{f.label}</FieldLabel>
                  {f.type === "select" && f.options ? (
                    <select
                      className="w-full rounded-[16px] border border-line bg-warm-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-sage-500/25"
                      value={draftFilters[f.key] || ""}
                      onChange={(e) =>
                        setDraftFilters((prev) => ({ ...prev, [f.key]: e.target.value }))
                      }
                    >
                      <option value="">Todos</option>
                      {f.options.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      value={draftFilters[f.key] || ""}
                      onChange={(e) =>
                        setDraftFilters((prev) => ({ ...prev, [f.key]: e.target.value }))
                      }
                      placeholder={`Filtrar ${f.label.toLowerCase()}…`}
                    />
                  )}
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={clearFilters}>
                Limpiar
              </Button>
              <Button type="button" className="ml-auto" onClick={applyFilters}>
                Aplicar filtros
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
