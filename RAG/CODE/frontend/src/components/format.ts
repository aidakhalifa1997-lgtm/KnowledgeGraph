// Formats d'affichage communs (français).

const dateFormatter = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });
const dateTimeFormatter = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });
const numberFormatter = new Intl.NumberFormat("fr-FR");

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(d.getTime()) ? value : dateFormatter.format(d);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : dateTimeFormatter.format(d);
}

export const formatNumber = (n: number) => numberFormatter.format(n);

export const formatPercent = (ratio: number, digits = 0) =>
  `${(ratio * 100).toFixed(digits).replace(".", ",")} %`;

export const formatMs = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1).replace(".", ",")} s` : `${Math.round(ms)} ms`);
