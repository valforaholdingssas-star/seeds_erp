import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
  type Table,
} from "@tanstack/react-table";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
  /**
   * Server-side search: parent owns the query and fetches from the API.
   * When set, the table does NOT filter rows locally by the search box.
   */
  searchQuery?: string;
  onSearchQueryChange?: (value: string) => void;
  /** Total matches from the API (shown in toolbar). Defaults to current page length. */
  searchTotalCount?: number;
};

function SelectAllHeader<T>({ table }: { table: Table<T> }) {
  const allSelected = table.getIsAllRowsSelected();
  const someSelected = table.getIsSomeRowsSelected();
  return (
    <input
      type="checkbox"
      aria-label="Seleccionar todos"
      title="Seleccionar todos"
      checked={allSelected}
      ref={(el) => {
        if (el) el.indeterminate = someSelected && !allSelected;
      }}
      onChange={table.getToggleAllRowsSelectedHandler()}
      className="h-4 w-4 accent-green-900"
      onClick={(e) => e.stopPropagation()}
    />
  );
}

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
  searchQuery,
  onSearchQueryChange,
  searchTotalCount,
}: DataTableProps<T>) {
  const serverSearch = typeof onSearchQueryChange === "function";
  const [localQuery, setLocalQuery] = useState("");
  const query = serverSearch ? (searchQuery ?? "") : localQuery;
  const setQuery = serverSearch ? onSearchQueryChange! : setLocalQuery;
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [draftFilters, setDraftFilters] = useState<Record<string, string>>({});
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const lastEmittedIds = useRef<string>("");
  const onSelectionChangeRef = useRef(onSelectionChange);
  onSelectionChangeRef.current = onSelectionChange;

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((v) => v.trim()).length,
    [filters],
  );

  // Parents often pass searchableKeys inline; stabilize by value to avoid
  // filtered→onSelectionChange→re-render loops that freeze the table.
  const searchableKeySig = searchableKeys.map(String).join("\0");
  const stableSearchKeys = useMemo(
    () => searchableKeySig.split("\0").filter(Boolean) as (keyof T)[],
    [searchableKeySig],
  );

  const filtered = useMemo(() => {
    let rows = data;
    // Local text search only when the parent is not driving server search.
    if (!serverSearch && query.trim() && stableSearchKeys.length) {
      const q = query.toLowerCase();
      rows = rows.filter((row) =>
        stableSearchKeys.some((key) =>
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
  }, [data, query, stableSearchKeys, filters, serverSearch]);

  // Drop selection for rows no longer visible after filter/search.
  useEffect(() => {
    const visible = new Set(filtered.map((r) => r.id));
    setRowSelection((prev) => {
      const next: RowSelectionState = {};
      let changed = false;
      for (const [id, on] of Object.entries(prev)) {
        if (on && visible.has(id)) next[id] = true;
        else if (on) changed = true;
      }
      if (!changed && Object.keys(next).length === Object.keys(prev).length) {
        return prev;
      }
      return next;
    });
  }, [filtered]);

  const resolvedColumns = useMemo(() => {
    return columns.map((col) => {
      if (col.id !== "select") return col;
      return {
        ...col,
        header: ({ table }: { table: Table<T> }) => <SelectAllHeader table={table} />,
        size: 40,
      } as ColumnDef<T, unknown>;
    });
  }, [columns]);

  const table = useReactTable({
    data: filtered,
    columns: resolvedColumns,
    state: { rowSelection },
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  });

  const selected = table.getSelectedRowModel().rows.map((r) => r.original);
  const selectedIdsSig = selected.map((r) => r.id).sort().join(",");

  useEffect(() => {
    if (selectedIdsSig === lastEmittedIds.current) return;
    lastEmittedIds.current = selectedIdsSig;
    onSelectionChangeRef.current?.(selected);
    // selected is derived from rowSelection; only emit when ids actually change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIdsSig, rowSelection]);

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
    <div className="space-y-3">
      {/* Barra compacta — no full-bleed */}
      <div className="relative z-20 flex justify-start">
        <div className="inline-flex max-w-full flex-nowrap items-center gap-1.5 rounded-[999px] border border-line/80 bg-warm-white/70 py-1 pl-1 pr-2 shadow-[var(--shadow-1)] backdrop-blur-sm sm:gap-2 sm:pr-3">
          <div className="relative w-[min(100%,14rem)] shrink-0 sm:w-56">
            <Search
              strokeWidth={1.5}
              className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-soft"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar…"
              aria-label="Buscar"
              className="w-full rounded-[999px] border-0 bg-cream-100/70 py-1.5 pl-9 pr-3 text-sm text-text-dark outline-none transition-all placeholder:text-text-soft focus:bg-cream-100 focus:ring-2 focus:ring-sage-500/20"
            />
          </div>

          <div className="flex flex-nowrap items-center gap-1.5">
            {toolbarActions}
            {columnFilters.length > 0 ? (
              <Button type="button" size="xs" variant="primary-dark" onClick={openFilters}>
                <Filter strokeWidth={1.5} className="h-3 w-3" />
                Filtros
                {activeFilterCount > 0 ? (
                  <span className="ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-text-on-dark/20 px-1 text-[9px]">
                    {activeFilterCount}
                  </span>
                ) : null}
              </Button>
            ) : null}
            {exportFilename !== undefined ? (
              <Button type="button" size="xs" variant="outline" onClick={exportCsv}>
                <Download strokeWidth={1.5} className="h-3 w-3" />
                Exportar
              </Button>
            ) : null}
            <span className="hidden whitespace-nowrap px-1 label-caps text-text-soft sm:inline">
              {(serverSearch ? (searchTotalCount ?? data.length) : filtered.length)}{" "}
              reg.
            </span>
          </div>
        </div>
      </div>

      {activeFilterCount > 0 ? (
        <div className="relative z-20 flex flex-wrap items-center gap-2">
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
        <div className="relative z-20 flex flex-wrap items-center gap-3 rounded-[24px] border border-green-900/15 bg-green-900 px-5 py-3 text-text-on-dark shadow-[var(--shadow-2)]">
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

      <div className="seeds-panel relative z-0 overflow-hidden rounded-[28px] border border-line shadow-[var(--shadow-1)]">
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
                  <td colSpan={resolvedColumns.length} className="px-6 py-16 text-center">
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
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Filtros de tabla"
            className="relative z-10 w-full max-w-lg animate-[fade-up_280ms_var(--ease-soft)] rounded-t-[32px] border border-line bg-cream-100 p-6 shadow-[var(--shadow-3)] sm:rounded-[32px] sm:p-8"
            onClick={(e) => e.stopPropagation()}
          >
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
