/** Display labels for sale channels in Comercial. */
export const SOURCE_LABELS: Record<string, string> = {
  ECOMMERCE: "Ecommerce",
  SHOPIFY: "Ecommerce 2",
  KOMMO: "Kommo",
  FERIAS: "Ferias",
  MANUAL: "Manual",
};

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return "—";
  return SOURCE_LABELS[source] || source;
}
