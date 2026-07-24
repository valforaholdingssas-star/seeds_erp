import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatCOP(value: number) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(value);
}

/** Compact money for charts: $1,2M · $45K · $980 */
export function formatCompactCOP(value: number) {
  const sign = value < 0 ? "-" : "";
  const n = Math.abs(value);
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `${sign}$${m >= 10 ? m.toFixed(0) : m.toFixed(1).replace(".", ",")}M`;
  }
  if (n >= 1_000) {
    const k = n / 1_000;
    return `${sign}$${k >= 100 ? k.toFixed(0) : k.toFixed(0)}K`;
  }
  return `${sign}$${Math.round(n).toLocaleString("es-CO")}`;
}

/** Channel sale date (closed_at), Bogotá-friendly medium style. */
export function formatSaleDate(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("es-CO", {
    timeZone: "America/Bogota",
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(d);
}
