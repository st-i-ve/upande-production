import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import type { HarvestCalendar } from "@/lib/avocado-api";
import { cn } from "@/lib/utils";
import { Chip } from "./calendar-grid";
import { fmtKgTonnes, fmtNum } from "./calendar-format";

const NO_DATE_REASON: Record<string, { label: string; tone: string; title: string }> = {
  never_sampled: {
    label: "Never sampled",
    tone: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
    title: "No dry matter reading for this block or its planting year.",
  },
  stale_sample: {
    label: "Stale sample",
    tone: "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]",
    title: "The last reading is too old to date the pick. Sample again.",
  },
  not_rising: {
    label: "Not rising",
    tone: "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]",
    title: "Sampled, but dry matter is not rising, so no date can be projected.",
  },
};

const NO_FORECAST_REASON: Record<string, { label: string; tone: string; title: string }> = {
  not_bearing: {
    label: "Not bearing",
    tone: "bg-[var(--sd-alert-info)] text-[var(--sd-muted)]",
    title: "Too young to bear fruit this season.",
  },
  no_planting_year: {
    label: "No planting year",
    tone: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
    title: "Without a planting year no yield curve applies.",
  },
};

export function NoPickDateTable({ rows }: { rows: HarvestCalendar["no_pick_date"] }) {
  if (!rows.length) return <Empty>Nothing waiting on the lab.</Empty>;
  return (
    <ScrollTable>
      <table className="w-full text-[13px]">
        <thead className={STICKY_HEAD}>
          <tr className={THEAD_ROW}>
            <th className={TH}>Block</th>
            <th className={TH}>Farm</th>
            <th className={THR}>Forecast</th>
            <th className={TH}>Missing</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const why = NO_DATE_REASON[r.reason] ?? NO_DATE_REASON.never_sampled;
            return (
              <tr key={r.block} className={BODY_ROW}>
                <td className={cn(TD, "font-semibold")}>{r.block}</td>
                <td className={TD}>{r.farm || "—"}</td>
                <td className={TDR}>{fmtKgTonnes(r.expected_kg)}</td>
                <td className={TD}>
                  <Chip className={why.tone} title={why.title}>
                    {why.label}
                  </Chip>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollTable>
  );
}

export function NoForecastTable({ rows }: { rows: HarvestCalendar["no_forecast"] }) {
  if (!rows.length) return <Empty>Every block carries a forecast.</Empty>;
  return (
    <ScrollTable>
      <table className="w-full text-[13px]">
        <thead className={STICKY_HEAD}>
          <tr className={THEAD_ROW}>
            <th className={TH}>Block</th>
            <th className={TH}>Farm</th>
            <th className={THR}>Planted</th>
            <th className={THR}>Bearing trees</th>
            <th className={TH}>Why</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const why = NO_FORECAST_REASON[r.reason] ?? NO_FORECAST_REASON.not_bearing;
            return (
              <tr key={r.block} className={BODY_ROW}>
                <td className={cn(TD, "font-semibold")}>{r.block}</td>
                <td className={TD}>{r.farm || "—"}</td>
                <td className={TDR}>{r.planting_year ?? "—"}</td>
                <td className={TDR}>{fmtNum(r.bearing_trees)}</td>
                <td className={TD}>
                  <Chip className={why.tone} title={why.title}>
                    {why.label}
                  </Chip>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollTable>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">{children}</p>;
}
