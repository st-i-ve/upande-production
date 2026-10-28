import { addDays } from "date-fns";
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

/** Shade for a slice by how much of the period target it received. */
export function mmColor(pct: number, accent: string): string {
  if (pct < 50) return "#c0392b";
  if (pct < 90) return "#e0a030";
  // On target is a calm green, not the crop accent: F&V's accent is an orange that reads as a
  // warning next to the under-target red.
  if (pct <= 125) return ON_TARGET;
  return "#3b7ea1";
}

export const ON_TARGET = "#3f8f5a";

export const MM_LEGEND = [
  { label: "Under 50% of target", color: "#c0392b" },
  { label: "50-90%", color: "#e0a030" },
  { label: "On target (90-125%)", color: ON_TARGET },
  { label: "Over 125%", color: "#3b7ea1" },
];

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
