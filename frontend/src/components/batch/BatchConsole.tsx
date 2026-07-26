import { useBatchConsole } from "@/features/batch/batchStore";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

const statusBadge: Record<string, "sage" | "wine" | "terracotta" | "dark" | "rose"> = {
  SUCCESS: "sage",
  FAILED: "wine",
  RUNNING: "terracotta",
  PENDING: "rose",
  SKIPPED: "dark",
};

export function BatchConsole() {
  const { open, minimized, batch, polling, setMinimized, close } = useBatchConsole();
  if (!open || !batch) return null;

  if (minimized) {
    return (
      <button
        type="button"
        onClick={() => setMinimized(false)}
        className="fixed bottom-6 right-6 z-40 rounded-[999px] bg-green-900 px-5 py-3 label-caps text-text-on-dark shadow-lg"
      >
        Lote {batch.done}/{batch.total}
        {polling ? " · en curso" : " · listo"}
      </button>
    );
  }

  return (
    <aside
      className={cn(
        "fixed bottom-0 right-0 z-40 flex h-[min(70vh,520px)] w-full max-w-md flex-col",
        "rounded-tl-[32px] border border-line bg-cream-100 shadow-[var(--shadow-2)]",
      )}
    >
      <header className="flex items-center justify-between border-b border-line px-5 py-4">
        <div>
          <p className="label-caps text-text-muted">{batch.job_type}</p>
          <p className="font-serif text-xl text-green-900">
            {batch.success} ok · {batch.failed} fallidas · {batch.done}/{batch.total}
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={() => setMinimized(true)}>
            Min
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={close}>
            Cerrar
          </Button>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <ul className="space-y-2">
          {(batch.items || []).map((item) => (
            <li
              key={item.id}
              className="rounded-[16px] border border-line bg-warm-white px-3 py-2 text-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-green-900">
                  {String(
                    item.result?.name ||
                      item.result?.tracking_number ||
                      item.result?.number ||
                      item.ref_id,
                  )}
                </span>
                <Badge variant={statusBadge[item.status] || "dark"}>{item.status}</Badge>
              </div>
              {item.error ? (
                <p className="mt-1 text-xs text-wine-900">{item.error}</p>
              ) : item.result && Object.keys(item.result).length > 0 ? (
                <p className="mt-1 text-xs text-text-muted">
                  {String(
                    item.result.alegra_id ||
                      item.result.tracking_number ||
                      item.result.number ||
                      item.result.status ||
                      item.result.order_id ||
                      "",
                  )}
                </p>
              ) : null}
            </li>
          ))}
          {!batch.items?.length && (
            <p className="py-8 text-center text-sm text-text-soft">
              {batch.total === 0
                ? "Sin ítems (revisa credenciales Woo / rango vacío)."
                : "Cargando ítems…"}
            </p>
          )}
        </ul>
      </div>
      {polling && (
        <p className="border-t border-line px-5 py-2 text-xs text-text-muted">
          Actualizando cada 2s…
        </p>
      )}
    </aside>
  );
}
