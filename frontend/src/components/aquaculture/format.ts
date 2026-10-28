/** Figures shared by the aquaculture pages. Units live in the names. */

const N = (n: number, d = 0) => n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmtNum = (n: number | null | undefined, d = 0) => (n == null || !Number.isFinite(n) ? "—" : N(n, d));
export const fmtPct = (n: number | null | undefined, d = 1) => (n == null || !Number.isFinite(n) ? "—" : `${N(n, d)}%`);

/** 1,234 kg -> "1.2 t" from a tonne up. */
export function fmtKg(kg: number | null | undefined): string {
  if (kg == null || !Number.isFinite(kg)) return "—";
  return Math.abs(kg) >= 1000 ? `${N(kg / 1000, 1)} t` : `${N(kg, kg < 100 ? 1 : 0)} kg`;
}

export function fmtGrams(g: number | null | undefined): string {
  if (g == null || !Number.isFinite(g)) return "—";
  return `${N(g, g < 100 ? 1 : 0)} g`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-10-28" -> "28 Oct" */
export function dayMonth(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [, m, d] = iso.slice(0, 10).split("-").map(Number);
  return m && d ? `${d} ${MONTHS[m - 1]}` : "—";
}

/** "2026-10-28 06:00" -> "28 Oct 06:00" */
export function dayTime(at: string): string {
  return `${dayMonth(at)} ${at.slice(11, 16)}`.trim();
}

export function ageLabel(days: number): string {
  if (days < 14) return `${days} d`;
  return `${Math.floor(days / 7)} wk ${days % 7} d`;
}

export const METRIC_LABEL: Record<string, string> = {
  do: "Dissolved oxygen",
  ph: "pH",
  temp: "Temperature",
  ammonia: "Ammonia",
  nitrite: "Nitrite",
};

/** A number from an input; null when blank or not finite. */
export function numOf(v: string): number | null {
  if (!v.trim()) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export const TONE = {
  ok: "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]",
  warn: "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]",
  bad: "bg-[var(--sd-alert-error)] text-[var(--sd-data-red)]",
  quiet: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
} as const;
