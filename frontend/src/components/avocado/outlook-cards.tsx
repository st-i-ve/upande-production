import { KpiCard, KpiGrid } from "@/components/KpiCard";
import type { LossView, OutlookAlert, OutlookKpi, SeasonOutlook } from "@/lib/avocado-api";
import { kes, qty } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ACCENT, Chip, EmptyNote, SectionCard, ShareBar, dayMonth, kesShort, pct1, tonnes } from "./forecast-ui";

// -- KPI cards ---------------------------------------------------------------------

const KPI_TITLES: Record<OutlookKpi["key"], string> = {
  season_crop: "Forecast for the season, calibrated against what was delivered so far.",
  crop_value: "Forecast kilograms at the price in the toolbar. Nothing here is invoiced.",
  ready_to_pick: "A block is ready when a sample that is still current puts it at or above the dry matter floor. A stale sample cannot say.",
  crew_next_week: "Pickers the first dated week needs, at each block's own measured kilograms per picker-day.",
  estimate_accuracy: "Fitted, not proven. One season is thin evidence.",
  stale_readings: "A dry matter sample older than six weeks describes fruit that has already been picked, so it cannot date a harvest.",
};

function Meter({ pct, tone }: { pct: number; tone?: "bad" | "warn" }) {
  return (
    <div className="absolute inset-x-6 bottom-4" aria-hidden>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--sd-ink)]/[0.07]">
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{
            width: `${Math.max(0, Math.min(100, pct))}%`,
            background: tone === "bad" ? "var(--sd-sev-critical)" : tone === "warn" ? "var(--sd-sev-high)" : ACCENT,
          }}
        />
      </div>
    </div>
  );
}

function cardFor(k: OutlookKpi): { value: string; hint: string; tone: "default" | "warning" | "critical" | "good"; meterTone?: "bad" | "warn" } {
  switch (k.key) {
    case "season_crop":
      return { value: k.value == null ? "—" : tonnes(k.value), hint: k.note, tone: "default" };
    case "crop_value":
      return { value: kesShort(k.value), hint: k.note, tone: "default" };
    case "ready_to_pick":
      return { value: k.value == null ? "—" : `${qty(k.value)} ${k.value === 1 ? "block" : "blocks"}`, hint: k.note, tone: k.value ? "good" : "default" };
    case "crew_next_week":
      return {
        value: k.value == null ? "—" : `${qty(k.value)} pickers`,
        hint: k.note,
        tone: k.short ? "critical" : "default",
        meterTone: k.short ? "bad" : undefined,
      };
    case "estimate_accuracy":
      return {
        value: k.value == null ? "—" : pct1(k.value),
        hint: k.note,
        tone: k.value == null ? "default" : k.value >= 90 ? "good" : "warning",
        meterTone: k.value != null && k.value < 90 ? "warn" : undefined,
      };
    case "stale_readings":
      return {
        value: `${qty(k.value ?? 0)}${k.of ? ` of ${k.of}` : ""}`,
        hint: k.note,
        tone: k.value ? "warning" : "good",
        meterTone: k.value ? "warn" : undefined,
      };
  }
}

export function OutlookKpis({ data }: { data: SeasonOutlook | null }) {
  if (!data) {
    return (
      <KpiGrid cols={3}>
        {["Season crop", "Crop value", "Ready to pick", "Crew next week", "Estimate accuracy", "Stale readings"].map((l) => (
          <KpiCard key={l} label={l} value="" loading className="min-h-[148px]" />
        ))}
      </KpiGrid>
    );
  }
  return (
    <KpiGrid cols={3} className="lg:grid-cols-3">
      {data.kpis.map((k) => {
        const c = cardFor(k);
        return (
          <div key={k.key} className="relative" title={KPI_TITLES[k.key]} data-testid={`kpi-${k.key}`}>
            <KpiCard
              label={k.label}
              value={c.value}
              hint={c.hint}
              tone={c.tone}
              className="h-full pb-10"
            />
            {k.meter_pct != null && <Meter pct={k.meter_pct} tone={c.meterTone} />}
          </div>
        );
      })}
    </KpiGrid>
  );
}

// -- Dry matter --------------------------------------------------------------------

export function DryMatterCard({ data }: { data: SeasonOutlook }) {
  const dm = data.dry_matter;
  const scaleMax = Math.max(30, ...dm.cohorts.map((c) => c.dry_matter_pct + 2));
  const floorLeft = (dm.minimum_pct / scaleMax) * 100;
  return (
    <SectionCard testId="outlook-drymatter" title="Dry matter" description={`${dm.minimum_pct}% floor. Fruit below it cannot ship, whatever it weighs.`}>
      {!dm.cohorts.length ? (
        <EmptyNote>
          <b className="text-[var(--sd-text)]">No samples</b> — dry matter has never been recorded.
        </EmptyNote>
      ) : (
        <ul className="flex flex-col gap-4">
          {dm.cohorts.map((c) => {
            const ready = c.dry_matter_pct >= dm.minimum_pct;
            return (
              <li key={String(c.planting_year)} className="text-[13px]">
                <div className="mb-1.5 flex items-baseline justify-between gap-3">
                  <span className="font-medium">
                    {c.planting_year ?? "Unknown"} planting <span className="font-normal text-[var(--sd-quiet)]">· {c.blocks.join(", ")} · {tonnes(c.expected_kg)}</span>
                  </span>
                  <span className="font-semibold tabular-nums">{qty(c.dry_matter_pct, 1)}%</span>
                </div>
                <div className="relative h-2.5 rounded-full bg-[var(--sd-ink)]/[0.06]">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${(c.dry_matter_pct / scaleMax) * 100}%`, background: ready ? ACCENT : "var(--sd-sev-high)" }}
                  />
                  <i className="absolute -top-1 h-[18px] w-0.5 bg-[var(--sd-ink)]" style={{ left: `${floorLeft}%` }} title={`${dm.minimum_pct}% floor`} />
                </div>
                <div className="mt-1.5 text-[12px] text-[var(--sd-quiet)]">
                  {ready
                    ? "At the floor now"
                    : c.weeks_to_minimum != null
                      ? `${qty(c.short_pct, 1)} points short, gaining ${qty(c.gain_pct_per_week, 2)} a week · opens ${dayMonth(c.open_date)} (${qty(c.weeks_to_minimum, 1)} weeks)`
                      : "Not rising, so no opening date yet"}
                  {c.stale_blocks > 0 && ` · ${c.stale_blocks} stale`}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {dm.blocks.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--sd-line-soft)] pt-3">
          {dm.blocks.map((b) => (
            <Chip key={b.block} kind={b.stale ? "warn" : b.ready ? "good" : ""}>
              {b.block} {qty(b.dry_matter_pct, 1)}%{b.stale ? " · stale" : b.ready ? " · ready" : b.ready_date ? ` · ${dayMonth(b.ready_date)}` : ""}
            </Chip>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

// -- Pickers -----------------------------------------------------------------------

export function PickersCard({ data }: { data: SeasonOutlook }) {
  const p = data.pickers;
  const rows = p.rows;
  const hi = Math.max(1, p.crew_available, ...rows.map((r) => r.pickers_needed));
  const peak = rows.length ? Math.max(...rows.map((r) => r.pickers_needed)) : 0;
  return (
    <SectionCard testId="outlook-pickers" title="Pickers" description={`${qty(p.crew_available)} on the books, ${p.days_per_week} days a week.`}>
      {!rows.length ? (
        <EmptyNote>
          <b className="text-[var(--sd-text)]">No week to staff</b> —{" "}
          {data.undated.kg ? `${tonnes(data.undated.kg)} waiting on a pick date.` : "nothing scheduled."}
        </EmptyNote>
      ) : (
        <>
          <div className="relative flex h-[140px] items-end gap-1.5 border-b border-[var(--sd-line)] pt-4">
            {p.crew_available > 0 && (
              <div
                className="pointer-events-none absolute inset-x-0 border-t border-dashed border-[var(--sd-ink)]"
                style={{ bottom: `${(p.crew_available / hi) * 100}%` }}
              >
                <span className="absolute right-0 -top-4 text-[11px] font-semibold">crew {qty(p.crew_available)}</span>
              </div>
            )}
            {rows.map((r) => {
              const over = p.crew_available > 0 && r.pickers_needed > p.crew_available;
              return (
                <div
                  key={r.week}
                  className="flex-1 rounded-t-[4px]"
                  style={{ height: `${Math.max(2, (r.pickers_needed / hi) * 100)}%`, background: over ? "var(--sd-sev-critical)" : ACCENT }}
                  title={`${dayMonth(r.week)} · ${qty(r.pickers_needed, 1)} pickers · ${tonnes(r.kg)}${over ? ` · ${qty(r.shortfall ?? 0)} short` : ""}`}
                  data-short={over || undefined}
                />
              );
            })}
          </div>
          <div className="mt-1 flex justify-between text-[11px] text-[var(--sd-quiet)]">
            <span>{dayMonth(rows[0].week)}</span>
            <span>{dayMonth(rows[rows.length - 1].week)}</span>
          </div>
          <p className="mt-2 text-[13px] text-[var(--sd-text)]">
            <b className="tabular-nums">{p.weeks_short}</b> {p.weeks_short === 1 ? "week" : "weeks"} short of {rows.length} · peak {Math.round(peak)} pickers
          </p>
        </>
      )}
    </SectionCard>
  );
}

// -- Losses ------------------------------------------------------------------------

export function LossesCard({ losses, block }: { losses: LossView; block: string | null }) {
  const all = losses.rows;
  const rows = (block ? all.filter((r) => r.block === block) : all).slice(0, 7);
  const hi = Math.max(1, ...rows.map((r) => r.lost_kg));
  return (
    <SectionCard
      testId="outlook-losses"
      title="Lost to sick trees"
      description={losses.lost_kg ? `${tonnes(losses.lost_kg)} total${losses.lost_value_kes ? ` · ${kes(losses.lost_value_kes)}` : ""}` : undefined}
    >
      {!rows.length ? (
        <EmptyNote>
          <b className="text-[var(--sd-text)]">{all.length ? "0" : "0 kg"}</b> — {all.length ? "lost on this block." : "no sick trees or gaps recorded."}
        </EmptyNote>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {rows.map((r) => (
            <li key={r.block} className="grid grid-cols-[4.5rem_1fr_auto] items-center gap-3 text-[13px]" title={`${qty(r.sick_trees)} sick, ${qty(r.gaps)} gaps${r.lost_value_kes ? ` · ${kes(r.lost_value_kes)}` : ""}`}>
              <span className="truncate font-medium">{r.block}</span>
              <ShareBar pct={(r.lost_kg / hi) * 100} tone="bad" />
              <span className="tabular-nums text-[var(--sd-muted)]">{tonnes(r.lost_kg)}</span>
            </li>
          ))}
        </ul>
      )}
      {all.length > 0 && <p className="mt-3 text-[12px] text-[var(--sd-quiet)]">across {all.length} {all.length === 1 ? "block" : "blocks"}</p>}
    </SectionCard>
  );
}

// -- Undated, alerts, delivered ------------------------------------------------------

export function UndatedChip({ data }: { data: SeasonOutlook }) {
  const u = data.undated;
  if (!u.kg && !u.stale_blocks.length) return null;
  return (
    <div data-testid="outlook-undated" className="flex flex-wrap items-center gap-2 rounded-[var(--sd-radius-lg)] bg-[var(--sd-alert-warn)] px-4 py-3 text-[13px]">
      <Chip kind="warn">{tonnes(u.kg)} undated</Chip>
      <span className="text-[var(--sd-text)]">
        {u.blocks.length} {u.blocks.length === 1 ? "block" : "blocks"} with no pick week
        {u.blocks.length > 0 && <span className="text-[var(--sd-quiet)]"> ({u.blocks.map((b) => `${b.block}: ${b.reason}`).join("; ")})</span>}
        {u.stale_blocks.length > 0 && (
          <span className="text-[var(--sd-quiet)]">
            {" "}· stale: {u.stale_blocks.map((s) => `${s.block} (${s.sample_age_weeks} weeks old, ${s.needs})`).join("; ")}
          </span>
        )}
      </span>
    </div>
  );
}

export function AlertsList({ alerts }: { alerts: OutlookAlert[] }) {
  return (
    <SectionCard testId="outlook-alerts" title="Needs attention" description="Only what is actually wrong, five at most.">
      {!alerts.length ? (
        <EmptyNote>
          <b className="text-[var(--sd-text)]">Nothing wrong</b> — every reading is current and the crew covers the plan.
        </EmptyNote>
      ) : (
        <ul className="flex flex-col divide-y divide-[var(--sd-line-soft)]">
          {alerts.map((a) => (
            <li key={a.key} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0 text-[13px]">
              <i
                className={cn(
                  "mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full",
                  a.kind === "neg" ? "bg-[var(--sd-sev-critical)]" : a.kind === "warn" ? "bg-[var(--sd-sev-high)]" : "bg-[var(--sd-series-4)]",
                )}
              />
              <span>
                <b className="tabular-nums">{qty(a.count)}</b> {a.label}
                <span className="block text-[12px] text-[var(--sd-quiet)]">{a.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

export function DeliveredBySeason({ rows }: { rows: SeasonOutlook["delivered_by_season"] }) {
  const hi = Math.max(1, ...rows.map((r) => r.kg));
  return (
    <SectionCard testId="outlook-delivered" title="Delivered by season" description="Kilograms delivered per season from the yield history; avocados alternate on and off years.">
      {!rows.length ? (
        <EmptyNote>No delivered kilograms on file yet.</EmptyNote>
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((r) => (
            <li key={r.year} className="grid grid-cols-[3.5rem_1fr_auto] items-center gap-3 text-[13px]">
              <span className="font-medium tabular-nums">{r.year}</span>
              <ShareBar pct={(r.kg / hi) * 100} tone={r.on_year ? undefined : "muted"} />
              <span className="flex items-center gap-2 tabular-nums">
                {tonnes(r.kg)}
                <Chip kind={r.on_year ? "good" : ""}>{r.on_year ? "on year" : "off year"}</Chip>
              </span>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
