import type { GradeBucket } from "@/lib/fv-api";
import { fmtNum, gradeColor } from "./fv-format";

export function GradeLegend({ grades, accent }: { grades: string[]; accent: string }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 px-5 pb-3 text-[12px]" data-testid="grade-legend">
      {grades.map((g) => (
        <span key={g} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: gradeColor(grades, g, accent) }} />
          {g}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-[var(--sd-data-red)] opacity-70" />
        Rejects
      </span>
    </div>
  );
}

/** One horizontal stacked bar per bucket (crop item or block): grades, then rejects, as shares of what was received. */
export function GradeBars({ rows, grades, accent, testId }: { rows: GradeBucket[]; grades: string[]; accent: string; testId: string }) {
  if (!rows.length) {
    return <p className="px-5 pb-6 text-[13px] text-[var(--sd-quiet)]">Nothing graded in this period.</p>;
  }
  return (
    <ul className="flex flex-col gap-3 px-5 pb-5" data-testid={testId}>
      {rows.map((r) => {
        const total = r.graded_kg + r.rejects_kg || 1;
        return (
          <li key={r.key} data-testid={`${testId}-${r.key}`}>
            <div className="flex items-baseline justify-between gap-3 text-[13px]">
              <span className="font-medium">{r.key}</span>
              <span className="tabular-nums text-[var(--sd-quiet)]">
                {fmtNum(r.graded_kg)} kg · {fmtNum(r.class1_pct, 0)}% class 1 · {fmtNum(r.reject_pct, 1)}% rejects
              </span>
            </div>
            <div className="mt-1.5 flex h-5 overflow-hidden rounded-md bg-[var(--sd-line-soft)]" role="img" aria-label={`${r.key} grade split`}>
              {grades.map((g) => {
                const kg = r.grades[g] ?? 0;
                return kg > 0 ? (
                  <span key={g} title={`${g}: ${fmtNum(kg)} kg`} style={{ width: `${(kg / total) * 100}%`, background: gradeColor(grades, g, accent) }} />
                ) : null;
              })}
              {r.rejects_kg > 0 && (
                <span title={`Rejects: ${fmtNum(r.rejects_kg)} kg`} className="bg-[var(--sd-data-red)] opacity-70" style={{ width: `${(r.rejects_kg / total) * 100}%` }} />
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
