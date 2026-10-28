import type { MiteStatus, QueenStatus } from "@/lib/apiary-api";
import { cn } from "@/lib/utils";

export function Chip({ children, className, title }: { children: React.ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-[var(--sd-radius-pill)] px-2 py-0.5 text-[11px] font-medium tabular-nums",
        className,
      )}
    >
      {children}
    </span>
  );
}

export const TONE = {
  ok: "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]",
  warn: "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]",
  bad: "bg-[var(--sd-alert-error)] text-[var(--sd-data-red)]",
  quiet: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
};

export const QUEEN_LABEL: Record<QueenStatus, string> = {
  queenright: "Queenright",
  weak: "Some queenless",
  queenless: "Queenless",
  none: "Not inspected",
};
export const QUEEN_TONE: Record<QueenStatus, string> = {
  queenright: TONE.ok,
  weak: TONE.warn,
  queenless: TONE.bad,
  none: TONE.quiet,
};
export const MITE_LABEL: Record<MiteStatus, string> = { ok: "Mites low", watch: "Mites rising", high: "Treat now", none: "No count" };
export const MITE_TONE: Record<MiteStatus, string> = { ok: TONE.ok, watch: TONE.warn, high: TONE.bad, none: TONE.quiet };
export const MITE_COLOR: Record<MiteStatus, string> = {
  ok: "var(--sd-data-green)",
  watch: "var(--sd-target)",
  high: "var(--sd-data-red)",
  none: "var(--sd-quiet)",
};

export const fmt = (n: number | null | undefined, d = 0) =>
  n == null || !Number.isFinite(n) ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export function dayMonth(ymd: string | null | undefined): string {
  if (!ymd) return "—";
  const d = new Date(`${ymd}T00:00:00`);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export const dayMonthYear = (ymd: string) =>
  new Date(`${ymd}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10.5px] font-medium uppercase tracking-[0.12em] text-[var(--sd-quiet)]">{label}</div>
      <div className="mt-0.5 text-[13px] font-semibold tabular-nums">{value}</div>
    </div>
  );
}

export function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">{children}</p>;
}

/** Today minus n days, YYYY-MM-DD. */
export function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
