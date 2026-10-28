import { fmt, parseYmd } from "@/lib/utils";

/** A date n days on, by calendar parts (no UTC drift). */
export function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

/** "Tue 3 Nov" for a YYYY-MM-DD. */
export function rowDate(s: string | null | undefined): string {
  const d = parseYmd(s || "");
  return d ? d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) : "—";
}

/** Quantity: whole stays whole, else up to 2 decimals. */
export function q(n: unknown): string {
  const v = Number(n);
  return (Number.isFinite(v) ? v : 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

/** Money to 2 decimals; null (pay hidden) is a dash. */
export function money(n: number | null | undefined): string {
  return n == null ? "—" : fmt(n);
}
