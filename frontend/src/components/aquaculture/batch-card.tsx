import { Card } from "@/components/ui/card";
import type { PondBatch } from "@/lib/aquaculture-api";
import { bandTone, type Bands } from "@/lib/bands";
import { cn } from "@/lib/utils";
import { GrowthChart } from "./growth-chart";
import { ageLabel, dayMonth, fmtGrams, fmtKg, fmtNum, fmtPct, TONE } from "./format";
import { Chip, Fact } from "./ui";

function statusChip(b: PondBatch) {
  if (b.status === "Harvested") return <Chip className={TONE.quiet}>Harvested {dayMonth(b.harvest_date)}</Chip>;
  if (b.status === "Closed") return <Chip className={TONE.quiet}>Closed</Chip>;
  if (b.on_track === false) return <Chip className={TONE.warn} title="At the current growth rate the fish reach the target weight more than a week after the target date">Behind target</Chip>;
  if (b.on_track) return <Chip className={TONE.ok}>On track</Chip>;
  return <Chip className={TONE.quiet}>{b.growth_curve.length < 2 ? "Not sampled yet" : "No projection"}</Chip>;
}

export function BatchCard({
  b,
  accent,
  bands,
  staleDays,
  onSample,
  onHarvest,
}: {
  b: PondBatch;
  accent: string;
  bands?: Bands;
  staleDays: number | null;
  onSample: (b: PondBatch) => void;
  onHarvest: (b: PondBatch) => void;
}) {
  const growing = b.status === "Growing";
  const lowSurvival = bandTone(bands, "Fish survival", b.survival_pct) === "critical";
  const staleSample = growing && staleDays != null && (b.sample_age_days == null || b.sample_age_days > staleDays);
  return (
    <Card className="flex flex-col gap-3 p-5" data-testid={`batch-card-${b.pond_name}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold">{b.pond_name}</div>
          <div className="text-[12px] text-[var(--sd-quiet)]">
            {b.species} · {fmtNum(b.stocked)} stocked {dayMonth(b.stocking_date)} · {ageLabel(b.days_in_water)} in water
          </div>
        </div>
        {statusChip(b)}
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-[34px] font-semibold leading-none tabular-nums" style={{ color: accent }}>{fmtNum(b.live)}</span>
        <span className="text-[12px] text-[var(--sd-quiet)]">{growing ? "fish alive" : `fish left · ${fmtNum(b.harvested)} harvested`}</span>
      </div>

      <GrowthChart b={b} accent={accent} />

      <div className="grid grid-cols-3 gap-3">
        <Fact label="Avg weight" value={fmtGrams(b.avg_weight_g)} hint={b.last_sampled ? `Sampled ${dayMonth(b.last_sampled)}` : "Weight at stocking; no sample yet"} tone={staleSample ? "warn" : undefined} />
        <Fact label="Biomass" value={growing ? fmtKg(b.biomass_kg) : fmtKg(b.harvest_kg)} hint={growing ? "Live fish times average weight" : "Harvested"} />
        <Fact label="Survival" value={fmtPct(b.survival_pct)} tone={lowSurvival ? "bad" : undefined} hint={`${fmtNum(b.dead)} died since stocking`} />
        <Fact label="FCR" value={fmtNum(b.fcr, 2)} hint="Kg of feed per kg gained" tone={b.fcr != null && b.fcr > 1.8 ? "warn" : undefined} />
        <Fact label="Feed to date" value={fmtKg(b.feed_kg)} hint={`${fmtKg(b.feed_7d_kg)} in the last 7 days`} />
        <Fact label="Growth" value={b.growth_g_day != null ? `${fmtNum(b.growth_g_day, 1)} g/day` : "—"} hint="Over the last four samples" />
      </div>

      <div className={cn("rounded-xl bg-[var(--sd-bg-soft)] px-3 py-2 text-[12px] text-[var(--sd-muted)]")} data-testid="projection">
        {growing
          ? b.projected_harvest_date
            ? `Reaches ${b.target_weight_g} g around ${dayMonth(b.projected_harvest_date)}${b.target_date ? ` · target ${dayMonth(b.target_date)}` : ""}${b.projected_weight_g ? ` · ${fmtGrams(b.projected_weight_g)} on the target date` : ""}`
            : b.target_weight_g
              ? "Sample the fish to project a harvest date."
              : "No target weight set."
          : `Harvested ${fmtKg(b.harvest_kg)}${b.fcr ? ` · FCR ${fmtNum(b.fcr, 2)}` : ""}`}
      </div>

      {growing && (
        <div className="flex gap-2 pt-1">
          <button type="button" className="rounded-full px-3 py-1.5 text-[12px] font-medium text-[var(--sd-ink)] shadow-[var(--sd-shadow-1)] hover:shadow-[var(--sd-shadow-2)]" onClick={() => onSample(b)}>
            Record sample
          </button>
          <button type="button" className="rounded-full px-3 py-1.5 text-[12px] font-medium text-[var(--sd-ink)] shadow-[var(--sd-shadow-1)] hover:shadow-[var(--sd-shadow-2)]" onClick={() => onHarvest(b)}>
            Record harvest
          </button>
        </div>
      )}
    </Card>
  );
}
