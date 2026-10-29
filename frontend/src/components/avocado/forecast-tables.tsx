import { useState } from "react";
import { Pencil } from "lucide-react";
import { compact, niceTicks, useWidth } from "@/components/forecast/chart-utils";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { STICKY_HEAD, ScrollTable } from "@/components/ScrollTable";
import { Input } from "@/components/ui/input";
import type { BlockRow, CurveRow, ForecastMode, ForecastView, ProductionForecast } from "@/lib/avocado-api";
import { kes, qty } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ACCENT, Chip, EmptyNote, Legend, SectionCard, ShareBar, dayMonth, pct1, tonnes } from "./forecast-ui";

// -- Yield curve ----------------------------------------------------------------------

const CURVE_H = 200;

export function YieldCurveCard({ rows }: { rows: CurveRow[] }) {
  const [ref, width] = useWidth(300, 700);
  const pad = { top: 14, right: 8, bottom: 26, left: 40 };
  const has = rows.some((r) => r.kg_per_tree > 0);
  const hi = Math.max(1, ...rows.map((r) => r.kg_per_tree));
  const ticks = niceTicks(0, hi, 4);
  const top = ticks[ticks.length - 1] || hi;
  const plotW = Math.max(1, width - pad.left - pad.right);
  const plotH = CURVE_H - pad.top - pad.bottom;
  const band = plotW / Math.max(1, rows.length);
  const y = (v: number) => pad.top + plotH - (v / top) * plotH;
  return (
    <SectionCard
      testId="forecast-curve"
      title="Yield curve"
      description="Kilograms picked divided by trees picked, straight off the harvest logs. Age bands the estate has never harvested stay a typed estimate."
    >
      {!rows.length || !has ? (
        <EmptyNote>No yield curve yet — one harvest against a block with a planting year starts it.</EmptyNote>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          <div>
            <div ref={ref} className="w-full">
              <svg width={width} height={CURVE_H} role="img" aria-label="Kilograms per tree by tree age">
                {ticks.map((t) => (
                  <g key={t}>
                    <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} stroke="var(--sd-line)" />
                    <text x={pad.left - 6} y={y(t) + 3.5} textAnchor="end" fontSize="10.5" fill="var(--sd-quiet)">{compact(t)}</text>
                  </g>
                ))}
                {rows.map((r, i) => {
                  const measured = r.basis === "harvested";
                  const bw = Math.max(3, band * 0.7);
                  return (
                    <g key={r.label}>
                      <rect
                        x={pad.left + i * band + (band - bw) / 2}
                        y={y(r.kg_per_tree)}
                        width={bw}
                        height={Math.max(0, pad.top + plotH - y(r.kg_per_tree))}
                        rx={3}
                        fill={ACCENT}
                        fillOpacity={measured ? 1 : 0.35}
                      >
                        <title>{`Age ${r.label}: ${qty(r.kg_per_tree, 1)} kg/tree (${r.basis})`}</title>
                      </rect>
                      <text x={pad.left + i * band + band / 2} y={CURVE_H - 8} textAnchor="middle" fontSize="10.5" fill="var(--sd-quiet)">{r.label}</text>
                    </g>
                  );
                })}
              </svg>
            </div>
            <Legend items={[{ color: ACCENT, label: "Measured (harvested)" }, { color: ACCENT, label: "Estate history", dashed: true }]} />
          </div>
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead>
                <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
                  <th className={TH}>Tree age</th>
                  <th className={THR}>kg / tree</th>
                  <th className={TH}>Basis</th>
                  <th className={THR}>Harvests</th>
                  <th className={THR}>Trees</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.label} className={BODY_ROW}>
                    <td className={`${TD} font-medium`}>{r.label}</td>
                    <td className={TDR}>{qty(r.kg_per_tree, 1)}</td>
                    <td className={TD}><Chip kind={r.basis === "harvested" ? "good" : ""}>{r.basis}</Chip></td>
                    <td className={TDR}>{qty(r.harvests)}</td>
                    <td className={TDR}>{qty(r.trees)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        </div>
      )}
    </SectionCard>
  );
}

// -- Blocks ----------------------------------------------------------------------------

function ForecastCell({ row, editable, onSave }: { row: BlockRow; editable: boolean; onSave: (kg: number) => Promise<boolean> }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  if (!editable) return <>{qty(row.expected_kg)}</>;
  if (!editing) {
    return (
      <button
        type="button"
        aria-label={`Edit forecast for ${row.block}`}
        onClick={() => {
          setText(String(row.expected_kg || ""));
          setEditing(true);
        }}
        className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 hover:bg-[var(--sd-ink)]/[0.06]"
      >
        {qty(row.expected_kg)}
        <Pencil className="h-3 w-3 text-[var(--sd-quiet)]" aria-hidden />
      </button>
    );
  }
  const n = Number(text);
  const valid = text.trim() !== "" && Number.isFinite(n) && n >= 0;
  async function commit() {
    if (!valid) return;
    if (n === row.expected_kg) return setEditing(false);
    setBusy(true);
    const ok = await onSave(n);
    setBusy(false);
    if (ok) setEditing(false);
  }
  return (
    <Input
      autoFocus
      type="number"
      min={0}
      aria-label={`Forecast kg for ${row.block}`}
      value={text}
      disabled={busy}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") void commit();
        if (e.key === "Escape") setEditing(false);
      }}
      onBlur={() => setEditing(false)}
      className="ml-auto h-8 w-28 text-right tabular-nums"
    />
  );
}

export function BlocksCard({
  view,
  mode,
  canEdit = true,
  onEdit,
}: {
  view: ForecastView;
  mode: ForecastMode;
  canEdit?: boolean;
  onEdit: (block: string, kg: number) => Promise<boolean>;
}) {
  const manual = mode === "manual" && canEdit;
  const hi = Math.max(1, ...view.top_blocks.map((b) => b.expected_kg));
  return (
    <SectionCard
      testId="forecast-blocks"
      title="Blocks"
      description={
        manual
          ? "Sized on bearing trees, never planted trees. Click a forecast to type your own figure for the block."
          : "Sized on bearing trees, never planted trees. A block bearing nothing forecasts nothing."
      }
    >
      {!view.block_rows.length ? (
        <EmptyNote>No block has a live tree count yet — fill in live and bearing trees.</EmptyNote>
      ) : (
        <div className="flex flex-col gap-6">
          {view.top_blocks.length > 0 && (
            <ul className="flex flex-col gap-2.5" aria-label="Heaviest blocks">
              {view.top_blocks.map((b) => (
                <li key={b.block} className="grid grid-cols-[5rem_1fr_auto] items-center gap-3 text-[13px]">
                  <span className="truncate font-medium">{b.block}</span>
                  <ShareBar pct={(b.expected_kg / hi) * 100} />
                  <span className="tabular-nums text-[var(--sd-muted)]">
                    {tonnes(b.expected_kg)} · {qty(b.kg_per_tree, 1)} kg/tree
                  </span>
                </li>
              ))}
            </ul>
          )}
          <ScrollTable tall>
            <table className="w-full text-[13px]">
              <thead>
                <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
                  <th className={TH}>Block</th>
                  <th className={TH}>Farm</th>
                  <th className={THR}>Age</th>
                  <th className={THR}>Live</th>
                  <th className={THR}>Bearing</th>
                  <th className={TH}>Bearing %</th>
                  <th className={THR}>kg / tree</th>
                  <th className={TH}>Basis</th>
                  <th className={THR}>Forecast (kg)</th>
                  <th className={THR}>Value</th>
                </tr>
              </thead>
              <tbody>
                {view.block_rows.map((r) => (
                  <tr key={r.block} className={BODY_ROW}>
                    <td className={`${TD} font-medium`}>{r.block}{r.variety ? <span className="ml-1.5 font-normal text-[var(--sd-quiet)]">{r.variety}</span> : null}</td>
                    <td className={TD}>{r.farm ?? "—"}</td>
                    <td className={TDR}>{r.age ?? "—"}</td>
                    <td className={TDR}>{qty(r.live_trees)}</td>
                    <td className={TDR}>{qty(r.bearing_trees)}</td>
                    <td className={TD}>
                      <div className="flex items-center gap-2">
                        <ShareBar pct={r.pct_bearing} className="w-16" />
                        <span className="tabular-nums text-[var(--sd-quiet)]">{pct1(r.pct_bearing)}</span>
                      </div>
                    </td>
                    <td className={TDR}>{qty(r.kg_per_tree, 1)}</td>
                    <td className={`${TD} max-w-[18rem] truncate text-[var(--sd-muted)]`} title={r.basis}>{r.basis}</td>
                    <td className={`${TDR} font-medium`}>
                      <ForecastCell row={r} editable={manual} onSave={(kg) => onEdit(r.block, kg)} />
                    </td>
                    <td className={TDR}>{r.value_kes == null ? "—" : kes(r.value_kes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        </div>
      )}
    </SectionCard>
  );
}

// -- Pick schedule ---------------------------------------------------------------------------

export function ScheduleCard({ s }: { s: ProductionForecast["schedule"] }) {
  const peak = Math.max(1, ...s.weeks.map((w) => w.kg));
  return (
    <SectionCard
      testId="forecast-schedule"
      title="Pick schedule"
      description={`Each block's kilograms from the week its dry matter crosses ${s.minimum_pct}%, spread over ${s.pick_weeks} picks. Unsampled blocks are listed below, not dropped into week one.`}
    >
      {!s.weeks.length ? (
        <EmptyNote>
          Nothing dated — a pick week needs one dry matter sample on the block.
          {s.unscheduled_kg ? ` ${tonnes(s.unscheduled_kg)} of forecast is waiting on one.` : ""}
        </EmptyNote>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap gap-2">
            <Chip kind="good">{tonnes(s.scheduled_kg)} dated</Chip>
            <Chip>{tonnes(s.next_6_weeks_kg)} in the next 6 weeks</Chip>
            {Object.entries(s.kg_by_basis).map(([k, v]) => (
              <Chip key={k}>{tonnes(v)} by {k}{s.blocks_by_basis[k] ? ` · ${s.blocks_by_basis[k]} ${s.blocks_by_basis[k] === 1 ? "block" : "blocks"}` : ""}</Chip>
            ))}
            {s.unscheduled_kg > 0 && <Chip kind="warn">{tonnes(s.unscheduled_kg)} undated</Chip>}
          </div>
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead>
                <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
                  <th className={TH}>Week of</th>
                  <th className={THR}>Kilograms</th>
                  <th className={TH}>Share of peak</th>
                  <th className={THR}>Value</th>
                </tr>
              </thead>
              <tbody>
                {s.weeks.map((w) => (
                  <tr key={w.week} className={BODY_ROW}>
                    <td className={`${TD} font-medium`}>{dayMonth(w.week)} <span className="text-[var(--sd-quiet)]">wk {w.iso_week}</span></td>
                    <td className={`${TDR} font-medium`}>{qty(w.kg)}</td>
                    <td className={TD}><ShareBar pct={(w.kg / peak) * 100} className="w-44" /></td>
                    <td className={TDR}>{w.value_kes == null ? "—" : qty(w.value_kes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
          {s.scheduled_blocks.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className={THEAD_ROW}>
                    <th className={TH}>Block</th>
                    <th className={TH}>Starts</th>
                    <th className={THR}>Picks</th>
                    <th className={THR}>Expected</th>
                    <th className={TH}>Dated on</th>
                  </tr>
                </thead>
                <tbody>
                  {s.scheduled_blocks.map((b) => (
                    <tr key={b.block} className={BODY_ROW} title={b.basis}>
                      <td className={`${TD} font-medium`}>{b.block}</td>
                      <td className={TD}>{dayMonth(b.start)}</td>
                      <td className={TDR}>{b.weeks} weeks</td>
                      <td className={TDR}>{tonnes(b.expected_kg)}</td>
                      <td className={TD}><Chip kind={b.measured_on === "dry matter" ? "good" : "warn"}>{b.measured_on}</Chip></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {s.unscheduled.length > 0 && (
            <div className="rounded-[var(--sd-radius-lg)] bg-[var(--sd-alert-warn)] px-4 py-3 text-[13px]">
              <b>Not on the schedule:</b>{" "}
              {s.unscheduled.map((u) => `${u.block} (${tonnes(u.expected_kg)}, ${u.reason})`).join(" · ")}
            </div>
          )}
        </div>
      )}
    </SectionCard>
  );
}

// -- Losses -------------------------------------------------------------------------------------

export function LossesTableCard({ losses }: { losses: ProductionForecast["losses"] }) {
  return (
    <SectionCard
      testId="forecast-losses"
      title="Losses"
      description="Sick trees and gaps priced at the kilograms that block's own age band delivers."
      tools={losses.lost_kg > 0 ? <Chip kind="neg">{tonnes(losses.lost_kg)}{losses.lost_value_kes ? ` · ${kes(losses.lost_value_kes)}` : ""}</Chip> : undefined}
    >
      {!losses.rows.length ? (
        <EmptyNote>Nothing to price — fill in sick trees and trees to infill on the block.</EmptyNote>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className={THEAD_ROW}>
                <th className={TH}>Block</th>
                <th className={TH}>Farm</th>
                <th className={THR}>Age</th>
                <th className={THR}>Sick</th>
                <th className={THR}>Gaps</th>
                <th className={THR}>% sick</th>
                <th className={THR}>kg / tree</th>
                <th className={THR}>Lost kg</th>
                <th className={THR}>Lost value</th>
              </tr>
            </thead>
            <tbody>
              {losses.rows.map((r) => (
                <tr key={r.block} className={BODY_ROW}>
                  <td className={`${TD} font-medium`}>{r.block}</td>
                  <td className={TD}>{r.farm ?? "—"}</td>
                  <td className={TDR}>{r.age ?? "—"}</td>
                  <td className={TDR}>{qty(r.sick_trees)}</td>
                  <td className={TDR}>{qty(r.gaps)}</td>
                  <td className={TDR}>{pct1(r.pct_sick)}</td>
                  <td className={TDR}>{qty(r.kg_per_tree, 1)}</td>
                  <td className={`${TDR} font-medium text-[var(--sd-sev-critical)]`}>{qty(r.lost_kg)}</td>
                  <td className={TDR}>{r.lost_value_kes == null ? "—" : kes(r.lost_value_kes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

// -- Maturity and gaps -----------------------------------------------------------------------------

export function MaturityCard({ m }: { m: ProductionForecast["maturity"] }) {
  return (
    <SectionCard
      testId="forecast-maturity"
      title="Maturity"
      description={`Dry matter against the ${m.minimum_pct}% export minimum. Below it the fruit cannot ship, whatever it weighs.`}
    >
      {!m.blocks.length ? (
        <EmptyNote>No dry matter samples yet — under {m.minimum_pct}% the fruit cannot ship.</EmptyNote>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className={THEAD_ROW}>
                <th className={TH}>Block</th>
                <th className={TH}>Sampled</th>
                <th className={THR}>Dry matter</th>
                <th className={THR}>Short by</th>
                <th className={TH}>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {m.blocks.map((b) => (
                <tr key={b.block} className={BODY_ROW}>
                  <td className={`${TD} font-medium`}>{b.block}</td>
                  <td className={TD}>{dayMonth(b.sample_date)}</td>
                  <td className={`${TDR} font-medium`}>{qty(b.dry_matter_pct, 1)}%</td>
                  <td className={TDR}>{b.shortfall_pct ? `${qty(b.shortfall_pct, 1)}%` : "—"}</td>
                  <td className={TD}><Chip kind={b.ready ? "good" : "warn"}>{b.ready ? "Pickable" : "Not yet"}</Chip></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

export function DataGapsCard({ gaps }: { gaps: ProductionForecast["data_gaps"] }) {
  return (
    <SectionCard
      testId="forecast-gaps"
      title="Data gaps"
      description="Reported, not patched. A forecast that invents the missing half is worse than one that says what it does not know."
    >
      {!gaps.length ? (
        <EmptyNote>Nothing missing — every block has trees, an age and a cultivar.</EmptyNote>
      ) : (
        <ul className="flex flex-col divide-y divide-[var(--sd-line-soft)]">
          {gaps.map((g) => (
            <li key={g.issue} className="py-2.5 text-[13px] first:pt-0 last:pb-0">
              <b>{g.issue}</b> — {g.count} {g.count === 1 ? "block" : "blocks"}:{" "}
              <span className="text-[var(--sd-muted)]">
                {g.blocks.slice(0, 6).join(", ")}
                {g.blocks.length > 6 ? ` and ${g.blocks.length - 6} more` : ""}
              </span>
              <span className="block text-[12px] text-[var(--sd-quiet)]">{g.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
