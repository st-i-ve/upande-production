import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import type { PickingPlan, PlanWeek } from "@/lib/avocado-api";
import { kes } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Chip } from "./calendar-grid";
import { dayMonth, fmtKgTonnes, fmtNum } from "./calendar-format";
import { statusText } from "./picking-chart";

const Empty = ({ children }: { children: React.ReactNode }) => (
  <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">{children}</p>
);

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="min-w-[110px]">
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--sd-quiet)]">{label}</div>
      <div className={cn("mt-1 text-[22px] font-semibold leading-none tracking-[-0.02em] tabular-nums", tone)}>{value}</div>
    </div>
  );
}

export function WeekDetail({ week, canSeePay }: { week: PlanWeek; canSeePay: boolean }) {
  const tone =
    week.status === "short" ? "text-[var(--sd-data-red)]" : week.status === "spare" ? "text-[var(--sd-data-green)]" : undefined;
  return (
    <div data-testid="week-detail">
      <div className="flex flex-wrap gap-x-8 gap-y-4 px-5 pb-4">
        <Stat label="Picked" value={fmtKgTonnes(week.kg)} />
        <Stat label="Crates" value={fmtNum(week.crates)} />
        <Stat label="Pickers needed" value={fmtNum(week.pickers_needed)} />
        <Stat label="Available" value={week.crew_available ? fmtNum(week.crew_available) : "—"} />
        <Stat label="Crew" value={statusText(week)} tone={tone} />
        <Stat label="Picker days" value={fmtNum(week.picker_days)} />
        {canSeePay && <Stat label="Wages" value={kes(week.wage_cost)} />}
        {canSeePay && week.cost_per_kg != null && <Stat label="Per kg" value={`KES ${week.cost_per_kg.toFixed(2)}`} />}
      </div>
      {week.pct_kg_measured != null && (
        <p className="px-5 pb-3 text-[12px] text-[var(--sd-quiet)]">
          {fmtNum(week.pct_kg_measured)}% of this week's kilograms use a block's own measured picking rate, the rest the estate's.
        </p>
      )}
      <ScrollTable>
        <table className="w-full text-[13px]">
          <thead className={STICKY_HEAD}>
            <tr className={THEAD_ROW}>
              <th className={TH}>Block</th>
              <th className={THR}>Kg</th>
              <th className={THR}>Crates</th>
              <th className={THR}>Kg per picker day</th>
              <th className={TH}>Rate basis</th>
              <th className={THR}>Picker days</th>
              <th className={THR}>Pickers</th>
            </tr>
          </thead>
          <tbody>
            {week.by_block.map((b) => (
              <tr key={b.block} className={BODY_ROW}>
                <td className={cn(TD, "font-semibold")}>{b.block}</td>
                <td className={TDR}>{fmtNum(b.kg)}</td>
                <td className={TDR}>{fmtNum(b.crates)}</td>
                <td className={TDR}>{fmtNum(b.kg_per_picker_day)}</td>
                <td className={TD}>
                  <Chip className={b.measured ? "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]" : "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]"} title={b.rate_basis}>
                    {b.measured ? "Measured" : "Estate rate"}
                  </Chip>
                </td>
                <td className={TDR}>{fmtNum(b.picker_days, 1)}</td>
                <td className={TDR}>{fmtNum(b.pickers_needed, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollTable>
    </div>
  );
}

export function RatesTable({ rates }: { rates: PickingPlan["rates"] }) {
  if (!rates.blocks.length && !rates.estate) return <Empty>No harvest records yet, so every block uses the estate's usual rate.</Empty>;
  return (
    <ScrollTable>
      <table className="w-full text-[13px]">
        <thead className={STICKY_HEAD}>
          <tr className={THEAD_ROW}>
            <th className={TH}>Block</th>
            <th className={THR}>Kg per picker day</th>
            <th className={TH}>Basis</th>
            <th className={THR}>Records</th>
          </tr>
        </thead>
        <tbody>
          {rates.estate && (
            <tr className={cn(BODY_ROW, "bg-[var(--sd-bg-soft)]")}>
              <td className={cn(TD, "font-semibold")}>Estate</td>
              <td className={TDR}>{fmtNum(rates.estate.kg_per_picker_day)}</td>
              <td className={cn(TD, "text-[var(--sd-muted)]")}>{rates.estate.basis}</td>
              <td className={TDR}>{fmtNum(rates.estate.events)}</td>
            </tr>
          )}
          {rates.blocks.map((r) => (
            <tr key={r.block} className={BODY_ROW}>
              <td className={cn(TD, "font-semibold")}>{r.block}</td>
              <td className={TDR}>{fmtNum(r.kg_per_picker_day)}</td>
              <td className={cn(TD, "text-[var(--sd-muted)]")}>{r.basis}</td>
              <td className={TDR}>{fmtNum(r.events)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollTable>
  );
}

export function UnscheduledTable({ rows }: { rows: PickingPlan["unscheduled"] }) {
  if (!rows.length) return <Empty>Every forecast block has a pick date. Nothing waiting.</Empty>;
  return (
    <ScrollTable>
      <table className="w-full text-[13px]">
        <thead className={STICKY_HEAD}>
          <tr className={THEAD_ROW}>
            <th className={TH}>Block</th>
            <th className={THR}>Forecast</th>
            <th className={TH}>Why</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((u) => (
            <tr key={u.block} className={BODY_ROW}>
              <td className={cn(TD, "font-semibold")}>{u.block}</td>
              <td className={TDR}>{fmtKgTonnes(u.expected_kg)}</td>
              <td className={cn(TD, "text-[var(--sd-muted)]")}>{u.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollTable>
  );
}

export function RejectedTable({ rows }: { rows: PickingPlan["rejected_records"] }) {
  if (!rows.length) return <Empty>Every harvest record reads like a real day's picking.</Empty>;
  return (
    <ScrollTable>
      <table className="w-full text-[13px]">
        <thead className={STICKY_HEAD}>
          <tr className={THEAD_ROW}>
            <th className={TH}>Block</th>
            <th className={TH}>Date</th>
            <th className={THR}>Implied kg per picker</th>
            <th className={TH}>Why refused</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.block}-${r.date}-${i}`} className={BODY_ROW}>
              <td className={cn(TD, "font-semibold")}>{r.block}</td>
              <td className={TD}>{dayMonth(r.date)}</td>
              <td className={TDR}>{fmtNum(r.implied_rate)}</td>
              <td className={cn(TD, "text-[var(--sd-muted)]")}>{r.why}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollTable>
  );
}
