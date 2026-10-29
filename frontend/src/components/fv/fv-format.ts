import { addDays } from "date-fns";
import type { Band } from "@/lib/bands";
import { todayISO, ymd } from "@/lib/utils";

/** Default window for both pages: the last six weeks, from a Monday. */
export function defaultRange(): { from: string; to: string } {
  const now = new Date();
  const monday = addDays(now, -((now.getDay() + 6) % 7) - 35);
  return { from: ymd(monday), to: todayISO() };
}

export const fmtNum = (n: number, d = 0) =>
  n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmtKg = (n: number) => `${fmtNum(n)} kg`;

/** "12 Oct" from YYYY-MM-DD or a datetime. */
export function dayMonth(s: string): string {
  const d = new Date(s.slice(0, 10) + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function hhmm(s: string): string {
  return s.slice(11, 16);
}

export function weeklySeries<T extends { week: string }>(rows: T[], pick: (r: T) => number) {
  return rows.map((r) => ({ week: r.week, value: pick(r) }));
}

export const ON_TARGET = "#3f8f5a";

/** Shades by position in the "Irrigation % of target" bands: under, low, on target, over. */
const BAND_SHADES = ["#c0392b", "#e0a030", ON_TARGET, "#3b7ea1"];
const NO_BAND = "#c4c7cc";

/** Shade for a slice by how much of the period target it received (on target is a calm green, not the crop
 *  accent: F&V's accent is an orange that reads as a warning next to the under-target red). */
export function mmColor(pct: number, rows: Band[] | undefined): string {
  const i = (rows ?? []).findIndex((b) => pct >= b.min && (b.max == null || pct < b.max));
  return i < 0 ? NO_BAND : BAND_SHADES[i % BAND_SHADES.length];
}

/** The legend rows, labelled by the bands the server sent. */
export function mmLegend(rows: Band[] | undefined): { label: string; color: string }[] {
  return (rows ?? []).map((b, i) => ({ label: b.label, color: BAND_SHADES[i % BAND_SHADES.length] }));
}

/** First grade is the crop accent; the rest step through neutral warm tones. */
export function gradeColor(grades: string[], grade: string, accent: string): string {
  const palette = [accent, "#c9a227", "#d9822b", "#8a8f98", "#c4c7cc", "#7b6a8a"];
  const i = grades.indexOf(grade);
  return palette[(i < 0 ? 0 : i) % palette.length];
}

export const FAULT_COLOR: Record<string, string> = {
  "Tower misalignment": "#c0392b",
  "Pressure drop": "#e0a030",
  Power: "#7b6a8a",
  Stuck: "#c0392b",
};
