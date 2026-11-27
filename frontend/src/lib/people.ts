import { addDays } from "@/components/plan/fmt";
import { parseYmd, todayISO, ymd } from "@/lib/utils";

/** The last four weeks up to today: the server's default too. */
export function lastFourWeeks(): { from: string; to: string } {
  const to = todayISO();
  return { from: ymd(addDays(parseYmd(to)!, -28)), to };
}

/** A number for display, one decimal at most; an em dash when there is none. */
export function fmt(v: number | null | undefined, unit = ""): string {
  return v == null ? "—" : `${Number(v).toLocaleString("en-US", { maximumFractionDigits: 1 })}${unit}`;
}

/** "3 Nov": the Monday a week starts on. */
export function weekLabel(monday: string): string {
  const d = parseYmd(monday);
  return d ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : monday;
}

export function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}
