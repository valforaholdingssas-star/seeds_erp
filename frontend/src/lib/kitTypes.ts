/** Tipos de kit Seeds: tamaño (10/20/30) × color × cantidad de kits. */

export const KIT_TYPES = [
  { value: "KIT_10", label: "Kit de 10 semillas", seeds: 10 },
  { value: "KIT_20", label: "Kit de 20 semillas", seeds: 20 },
  { value: "KIT_30", label: "Kit de 30 semillas", seeds: 30 },
] as const;

export type KitTypeValue = (typeof KIT_TYPES)[number]["value"];

const ALIASES: Record<string, KitTypeValue> = {
  kit_10: "KIT_10",
  kit10: "KIT_10",
  "10": "KIT_10",
  "kit de 10": "KIT_10",
  "kit de 10 semillas": "KIT_10",
  "10 semillas": "KIT_10",
  "kit 10": "KIT_10",
  kit_20: "KIT_20",
  kit20: "KIT_20",
  "20": "KIT_20",
  "kit de 20": "KIT_20",
  "kit de 20 semillas": "KIT_20",
  "20 semillas": "KIT_20",
  "kit 20": "KIT_20",
  kit_30: "KIT_30",
  kit30: "KIT_30",
  "30": "KIT_30",
  "kit de 30": "KIT_30",
  "kit de 30 semillas": "KIT_30",
  "30 semillas": "KIT_30",
  "kit 30": "KIT_30",
  KIT_10: "KIT_10",
  KIT_20: "KIT_20",
  KIT_30: "KIT_30",
};

export function normalizeKitType(raw?: string | null): string {
  if (!raw?.trim()) return "";
  const text = raw.trim();
  if (text === "KIT_10" || text === "KIT_20" || text === "KIT_30") return text;
  const key = text.toLowerCase().replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
  const compact = key.replace(/\s/g, "");
  if (ALIASES[key]) return ALIASES[key];
  if (ALIASES[compact]) return ALIASES[compact];
  const m = key.match(/\b(10|20|30)\b/);
  if (m) return ALIASES[m[1]];
  return text;
}

export function kitTypeLabel(code?: string | null): string {
  const n = normalizeKitType(code);
  return KIT_TYPES.find((k) => k.value === n)?.label || code || "";
}

export function formatSaleItemLine(item: {
  quantity: number;
  color?: string;
  tipo?: string;
}): string {
  const qty = item.quantity || 0;
  const kit = kitTypeLabel(item.tipo);
  const color =
    item.color === "DORADO"
      ? "Dorado"
      : item.color === "PLATEADO"
        ? "Plateado"
        : item.color || "";
  if (kit && color) return `${qty}× ${kit} · ${color}`;
  if (kit) return `${qty}× ${kit}`;
  if (color) return `${qty}× ${color}`;
  return String(qty);
}
