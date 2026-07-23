import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type PageHeaderProps = {
  /** Ruta corta, ej. "Logística / Envíos" */
  eyebrow?: string;
  title: string;
  actions?: ReactNode;
  className?: string;
};

/**
 * Cabecera densa de módulo (~1 fila). Sin card ni descripción:
 * prioriza viewport para la tabla.
 */
export function PageHeader({ eyebrow, title, actions, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        "flex min-h-9 flex-wrap items-center justify-between gap-x-4 gap-y-2",
        className,
      )}
    >
      <div className="flex min-w-0 items-baseline gap-2.5">
        {eyebrow ? (
          <p className="hidden label-caps shrink-0 text-text-soft sm:inline">{eyebrow}</p>
        ) : null}
        {eyebrow ? <span className="hidden text-text-soft/40 sm:inline" aria-hidden>·</span> : null}
        <h1 className="truncate font-serif text-[1.35rem] leading-none tracking-tight text-green-900 sm:text-2xl">
          {title}
        </h1>
      </div>
      {actions ? (
        <div className="flex max-w-full flex-nowrap items-center gap-1.5 overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {actions}
        </div>
      ) : null}
    </header>
  );
}
