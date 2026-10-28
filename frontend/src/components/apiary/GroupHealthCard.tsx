import { Card } from "@/components/ui/card";
import type { HiveGroupStatus } from "@/lib/apiary-api";
import { MiteChart } from "./charts";
import { Chip, dayMonth, Fact, fmt, MITE_COLOR, MITE_LABEL, MITE_TONE, QUEEN_LABEL, QUEEN_TONE, TONE } from "./ui";

/** One hive group: mite load against the threshold, queen status, brood and stores from the latest inspection. */
export function GroupHealthCard({ g, threshold, accent }: { g: HiveGroupStatus; threshold: number; accent: string }) {
  const mites = g.mites_per_100;
  const pct = mites != null ? Math.min(100, (mites / (threshold * 2)) * 100) : 0;
  const sick = g.disease_signs && g.disease_signs !== "None";
  return (
    <Card className="flex flex-col gap-3 p-5" data-testid={`hg-card-${g.unit}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold">{g.label}</div>
          <div className="text-[12px] text-[var(--sd-quiet)]">
            {g.last_date ? `Inspected ${dayMonth(g.last_date)} · ${g.days_since} days ago` : "No inspection in this period"}
          </div>
        </div>
        <Chip className={QUEEN_TONE[g.queen_status]} title={g.colonies ? `${g.queenright} of ${g.colonies} colonies have a laying queen` : undefined}>
          {QUEEN_LABEL[g.queen_status]}
        </Chip>
      </div>

      <div>
        <div className="flex items-end gap-2">
          <span className="text-[34px] font-semibold leading-none tracking-[-0.03em] tabular-nums" style={{ color: MITE_COLOR[g.mite_status] }} data-testid="hg-mites">
            {mites != null ? fmt(mites, 1) : "—"}
          </span>
          <span className="pb-0.5 text-[12px] text-[var(--sd-quiet)]">mites per 100 bees · limit {threshold}</span>
          <Chip className={`ml-auto ${MITE_TONE[g.mite_status]}`}>{MITE_LABEL[g.mite_status]}</Chip>
        </div>
        <div className="relative mt-2 h-1.5 rounded-full bg-[var(--sd-bg-soft)]" role="img" aria-label={`Mite load ${mites ?? "unknown"} against a limit of ${threshold}`}>
          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: MITE_COLOR[g.mite_status] }} />
          <i className="absolute -top-0.5 h-2.5 w-px bg-[var(--sd-ink)]" style={{ left: "50%" }} title={`Threshold ${threshold}`} />
        </div>
      </div>

      <MiteChart points={g.trend} threshold={threshold} accent={accent} label={`Mite load trend for ${g.label}`} />

      <div className="grid grid-cols-3 gap-3">
        <Fact label="Colonies" value={g.colonies != null ? `${g.queenright}/${g.colonies} queenright` : "—"} />
        <Fact label="Brood" value={g.brood_pattern ?? "—"} />
        <Fact label="Temper" value={g.temperament ?? "—"} />
        <Fact label="Frames brood" value={fmt(g.frames_brood, 1)} />
        <Fact label="Frames honey" value={fmt(g.frames_honey, 1)} />
        <Fact label="Frames stores" value={fmt(g.frames_stores, 1)} />
      </div>
      {sick && <Chip className={`self-start ${TONE.warn}`}>{g.disease_signs}</Chip>}
    </Card>
  );
}
