/** The pieces of a person's record shared by the Supervisors and Casual Labourers pages. */
import type { LucideIcon } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { PersonFlag, ShareRow } from "@/lib/people-api";
import { fmt, weekLabel } from "@/lib/people";
import { cn } from "@/lib/utils";

export function median(values: (number | null | undefined)[]): number | null {
  const xs = values.filter((v): v is number => v != null).sort((a, b) => a - b);
  if (!xs.length) return null;
  const m = Math.floor(xs.length / 2);
  return xs.length % 2 ? xs[m]! : (xs[m - 1]! + xs[m]!) / 2;
}

export interface MedianRow {
  key: string;
  label: string;
  unit?: string;
  /** true: lower is better; false: higher is better; undefined: no judgement */
  lowerIsBetter?: boolean;
}

/** One person's figures beside the farm median; a figure on the wrong side of it is red. */
export function MedianTable({
  rows,
  mine,
  medians,
  name,
  description,
}: {
  rows: MedianRow[];
  mine: Record<string, number | null | undefined>;
  medians: Record<string, number | null | undefined>;
  name: string;
  description: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Against the farm median</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <table className="w-full border-collapse text-[13px]" aria-label="Against the farm median">
          <thead>
            <tr className="border-b border-[var(--sd-line)] text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--sd-quiet)]">
              <th className="py-2 pr-3">Measure</th>
              <th className="py-2 pr-3 text-right">{name.split(" ")[0]}</th>
              <th className="py-2 text-right">Farm median</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const a = mine[r.key];
              const b = medians[r.key];
              const worse = a != null && b != null && r.lowerIsBetter !== undefined ? (r.lowerIsBetter ? a > b : a < b) : false;
              return (
                <tr key={r.key} className="border-b border-[var(--sd-line-soft)] last:border-0">
                  <td className="py-2 pr-3 text-[var(--sd-muted)]">{r.label}</td>
                  <td className={cn("py-2 pr-3 text-right tabular-nums", worse ? "text-[var(--sd-sev-critical)]" : "text-[var(--sd-ink)]")}>{fmt(a, r.unit)}</td>
                  <td className="py-2 text-right tabular-nums text-[var(--sd-quiet)]">{fmt(b, r.unit)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

export function FlagsCard({ flags, description }: { flags: PersonFlag[]; description: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Flags</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        {flags.length ? (
          <ul className="flex flex-col gap-2" aria-label="Flags">
            {flags.map((f) => (
              <li key={f.kind} className="flex flex-wrap items-baseline gap-2 text-[13px]">
                <span className="rounded-full px-2 py-px text-[11px] font-medium text-[var(--sd-data-red)] shadow-[inset_0_0_0_1px_var(--sd-data-red)]">{f.label}</span>
                <span className="text-[var(--sd-muted)]">{f.detail}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-[var(--sd-muted)]">No flags.</p>
        )}
      </CardContent>
    </Card>
  );
}

/** "Where they worked": each row's share of the person's work as a bar. */
export function ShareBars({ title, description, rows, icon: Icon, empty }: { title: string; description: string; rows: ShareRow[]; icon: LucideIcon; empty: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        {rows.length ? (
          <ul className="flex flex-col gap-2" aria-label={title}>
            {rows.map((r) => (
              <li key={r.key} className="flex items-center gap-3 text-[12.5px]">
                <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--sd-quiet)]" />
                <span className="w-40 shrink-0 truncate text-[var(--sd-ink)]" title={r.label}>{r.label}</span>
                <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--sd-bg-soft)]">
                  <span className="block h-full rounded-full bg-[var(--sd-ink)]" style={{ width: `${r.share ?? 0}%` }} />
                </span>
                <span className="w-12 shrink-0 text-right tabular-nums text-[var(--sd-muted)]">{Math.round(r.share ?? 0)}%</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-[var(--sd-muted)]">{empty}</p>
        )}
      </CardContent>
    </Card>
  );
}

export interface WeekSeries {
  key: string;
  label: string;
  values: number[];
  color: string;
}

/** Week by week: one small bar chart per series over the ISO weeks of the range. */
export function WeekStrip({ weeks, series, description }: { weeks: string[]; series: WeekSeries[]; description: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Week by week</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 pt-0">
        {series.map((s) => {
          const max = Math.max(1, ...s.values);
          return (
            <div key={s.key}>
              <p className="mb-1.5 text-[11.5px] font-medium text-[var(--sd-muted)]">{s.label}</p>
              <div className="flex h-16 items-end gap-1.5" role="img" aria-label={s.label}>
                {weeks.map((w, i) => (
                  <div key={w} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                    <span className="w-full rounded-t-[3px]" style={{ height: `${Math.max(4, (48 * (s.values[i] ?? 0)) / max)}px`, background: s.color }} title={`${weekLabel(w)}: ${fmt(s.values[i])}`} />
                    <span className="text-[10px] tabular-nums text-[var(--sd-quiet)]">{weekLabel(w)}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

/** A record frame while the first load is pending. */
export function RecordSkeleton() {
  return (
    <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,280px)]" aria-busy data-skeleton="record">
      <div className="flex min-w-0 flex-col gap-5">
        <div className="h-24 animate-pulse rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)]" />
        <div className="h-56 animate-pulse rounded-[var(--sd-radius-card)] bg-[var(--sd-bg-soft)]" />
      </div>
      <div className="aspect-[4/5] animate-pulse rounded-[var(--sd-radius-card)] bg-[var(--sd-bg-soft)]" />
    </div>
  );
}

export function PickPrompt({ label }: { label: string }) {
  return (
    <Card className="hidden xl:block">
      <CardContent className="flex min-h-[420px] flex-col items-center justify-center gap-2 text-center">
        <p className="text-[15px] font-medium text-[var(--sd-ink)]">{label}</p>
        <p className="max-w-[36ch] text-[13px] text-[var(--sd-muted)]">Search by name or ID. Their figures open here, beside the farm median.</p>
      </CardContent>
    </Card>
  );
}
