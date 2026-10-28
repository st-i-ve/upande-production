/** Number and date formatting shared by the production pages.
 *  A fixed locale so a figure reads the same on every machine on the farm. */

const LOCALE = "en-US";

/** Thousands separators, no decimals unless asked: 12,345 */
export function qty(n: number | null | undefined, decimals = 0): string {
  if (n == null || !Number.isFinite(Number(n))) return "—";
  return Number(n).toLocaleString(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Kenyan shillings, whole shillings: KES 1,234,567. null (hidden pay) is a dash. */
export function kes(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(Number(n))) return "—";
  return `KES ${qty(n, 0)}`;
}

/** Hectares with one decimal: 12.3 */
export function ha(n: number | null | undefined): string {
  return qty(n, 1);
}

/** 2026-03-09 -> 9 Mar 2026. Anything unparseable comes back as a dash. */
export function shortDate(ymd: string | null | undefined): string {
  if (!ymd) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ymd);
  if (!m) return "—";
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
