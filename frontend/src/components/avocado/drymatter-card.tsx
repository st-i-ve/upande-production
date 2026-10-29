import type { DryMatterBlock, DryMatterState } from "@/lib/avocado-api";
import { Card } from "@/components/ui/card";
import { Chip } from "./calendar-grid";
import { dayMonth, fmtNum } from "./calendar-format";
import { TrendChart } from "./drymatter-chart";

export const STATE_LABEL: Record<DryMatterState, string> = {
  ready: "Ready",
  rising: "Rising",
  stale: "Stale",
  never_sampled: "Never sampled",
};

const STATE_TONE: Record<DryMatterState, string> = {
  ready: "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]",
  rising: "bg-[var(--sd-alert-info)] text-[var(--sd-muted)] ring-1 ring-[var(--sd-line)]",
  stale: "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]",
  never_sampled: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
};

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10.5px] font-medium uppercase tracking-[0.12em] text-[var(--sd-quiet)]">{label}</div>
      <div className="mt-0.5 text-[13px] font-semibold tabular-nums">{value}</div>
    </div>
  );
}

const SAMPLING_LABEL: Record<string, string> = {
  due: "Due for sampling",
  recent: "Sampled recently",
  not_yet: "Not yet sampling",
  no_cycle: "No open cycle",
};

const SAMPLING_TONE: Record<string, string> = {
  due: "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]",
  recent: "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]",
  not_yet: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
  no_cycle: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
};

export function BlockCard({ b, minimum, accent }: { b: DryMatterBlock; minimum: number; accent: string }) {
  const gain = b.gain_pct_per_week;
  return (
    <Card className="flex flex-col gap-3 p-5" data-testid={`dm-card-${b.block}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold">{b.block}</div>
          <div className="text-[12px] text-[var(--sd-quiet)]">
            {b.farm || "no farm"} · {b.planting_year ?? "no year"}
          </div>
        </div>
        <Chip className={STATE_TONE[b.state]}>{STATE_LABEL[b.state]}</Chip>
      </div>

      <div className="flex items-end gap-2">
        <span className="text-[34px] font-semibold leading-none tracking-[-0.03em] tabular-nums" style={b.state === "ready" ? { color: accent } : undefined}>
          {b.dry_matter_pct != null ? `${b.dry_matter_pct.toFixed(1)}%` : "—"}
        </span>
        <span className="pb-0.5 text-[12px] text-[var(--sd-quiet)]">
          {b.dry_matter_pct == null
            ? "dry matter"
            : b.short_pct
              ? `${b.short_pct.toFixed(1)} points under the ${minimum}% floor`
              : `above the ${minimum}% floor`}
        </span>
      </div>

      <TrendChart points={b.trend} minimum={minimum} accent={accent} label={`Dry matter trend for ${b.block}`} />

      <div className="grid grid-cols-3 gap-3">
        <Fact label="Gain a week" value={gain != null ? `${gain >= 0 ? "+" : ""}${gain.toFixed(2)} pts` : "—"} />
        <Fact
          label={b.state === "ready" ? "Ready since" : "To minimum"}
          value={
            b.state === "ready"
              ? "now"
              : b.weeks_to_minimum != null
                ? `${fmtNum(b.weeks_to_minimum, 1)} wk${b.ready_date ? ` · ${dayMonth(b.ready_date)}` : ""}`
                : "—"
          }
        />
        <Fact label="Last test" value={b.sample_date ? `${dayMonth(b.sample_date)}${b.sample_age_weeks != null ? ` · ${fmtNum(b.sample_age_weeks)} wk ago` : ""}` : "never"} />
      </div>

      <div className="flex flex-wrap items-center gap-1.5 text-[12px] text-[var(--sd-muted)]">
        {b.measured_on === "cohort" && (
          <Chip className="bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]" title="Inherited from a planting-year test, not taken on this block.">
            planting-area reading
          </Chip>
        )}
        {b.sampling && (
          <Chip
            data-testid={`dm-sampling-${b.block}`}
            className={SAMPLING_TONE[b.sampling]}
            title={b.sample_from_stage ? `Sampling is due from ${b.sample_from_stage}` : "Sampling is due from the start"}
          >
            {SAMPLING_LABEL[b.sampling]}
            {b.sampling === "not_yet" && b.sample_from_stage ? `: from ${b.sample_from_stage}` : ""}
          </Chip>
        )}
        {b.stage && <span data-testid={`dm-stage-${b.block}`}>Stage: {b.stage}</span>}
        {b.samples > 0 && <span>{b.samples} test{b.samples === 1 ? "" : "s"}</span>}
        {b.gain_basis && <span>· {b.gain_basis}</span>}
      </div>
      {b.needs && <p className="rounded-xl bg-[var(--sd-bg-soft)] px-3 py-2 text-[12.5px] text-[var(--sd-muted)]">{b.needs}</p>}
    </Card>
  );
}
