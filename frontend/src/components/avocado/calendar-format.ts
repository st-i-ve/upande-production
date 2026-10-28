/** Figures shared by the avocado calendar, picking and dry matter pages. Units live in the names. */

export type CellUnit = "tonnes" | "crates" | "kg";

const N = (n: number, d = 0) =>
  n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmtNum = (n: number | null | undefined, d = 0) => (n == null || !Number.isFinite(n) ? "—" : N(n, d));

/** 12,300 kg -> "12.3 t"; under a tonne stays in kg. */
export function fmtKgTonnes(kg: number | null | undefined): string {
  if (kg == null || !Number.isFinite(kg)) return "—";
  return Math.abs(kg) >= 1000 ? `${N(kg / 1000, 1)} t` : `${N(kg)} kg`;
}

/** A figure in the unit the toolbar picked, with its unit suffix. */
export function fmtUnit(kg: number, crates: number, unit: CellUnit): string {
  if (unit === "crates") return `${N(crates)} crates`;
  if (unit === "kg") return `${N(kg)} kg`;
  return `${N(kg / 1000, 1)} t`;
}

/** Compact figure for a grid cell (no suffix). */
export function cellFigure(kg: number, crates: number, unit: CellUnit): string {
  if (!kg) return "";
  if (unit === "crates") return N(crates);
  if (unit === "kg") return N(kg);
  const t = kg / 1000;
  return N(t, t < 10 ? 2 : 1);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** 2026-10-26 -> "26 Oct". */
export function dayMonth(ymd: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ymd ?? "");
  return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]}` : "—";
}

/** The Monday on or before a local date, as YYYY-MM-DD. */
export function mondayOf(d: Date = new Date()): string {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  const p = (n: number) => String(n).padStart(2, "0");
  return `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}`;
}

/** Accent tint for heat shade 0-5 (accent mixed into white). */
export function shadeColor(accent: string, shade: number): string {
  const pct = [0, 14, 30, 50, 74, 100][Math.max(0, Math.min(5, shade))];
  return `color-mix(in srgb, ${accent} ${pct}%, white)`;
}
