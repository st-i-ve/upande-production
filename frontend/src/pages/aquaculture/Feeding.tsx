import { useCallback, useEffect, useState } from "react";
import { Plus, Skull } from "lucide-react";
import { CAUSE_COLOR, CausesChart, FeedMortalityChart } from "@/components/aquaculture/feeding-charts";
import { FeedingDialog, MortalityDialog } from "@/components/aquaculture/feeding-dialogs";
import { dayMonth, fmtKg, fmtNum, fmtPct, TONE } from "@/components/aquaculture/format";
import { Chip, Empty, Fact } from "@/components/aquaculture/ui";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { Bar, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { useToast } from "@/components/Toast";
import { ToolbarButton } from "@/components/ToolbarButton";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { getFeedingMortality, type FeedingMortalityPage } from "@/lib/aquaculture-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { todayISO, ymd } from "@/lib/utils";

function defaultRange(): DateRange {
  const to = todayISO();
  const d = new Date(`${to}T00:00:00`);
  d.setDate(d.getDate() - 27);
  return { from: ymd(d), to };
}

export function Feeding() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#2b6f9e";
  const [data, setData] = useState<FeedingMortalityPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [pond, setPond] = useState("");
  const [feeding, setFeeding] = useState(false);
  const [dying, setDying] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getFeedingMortality({ from_date: range.from, to_date: range.to, unit: pond || undefined });
    setLoading(false);
    if (isError(r)) return void toast(r.error, "error");
    setData(r as FeedingMortalityPage);
  }, [range, pond, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const label = (unit: string) => data?.form.ponds.find((p) => p.unit === unit)?.label ?? unit;
  const dirty = !!pond || range.from !== defaultRange().from || range.to !== defaultRange().to;

  return (
    <PageShell
      title={viewLabel("feeding", crop)}
      eyebrow={crop.name}
      description="Feed and deaths by day. A spike in deaths with a feed drop is usually oxygen: check the water quality page for the same dates."
      actions={
        <>
          <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
          <FilterSelect label="Pond" value={pond} onChange={setPond} options={(data?.form.ponds ?? []).map((p) => ({ value: p.unit, label: p.label }))} allLabel="All ponds" />
          <ClearFiltersPill active={dirty} onClear={() => { setPond(""); setRange(defaultRange()); }} />
          <RefreshButton onClick={load} loading={loading} label="feeding and mortality" />
          <ToolbarButton onClick={() => setFeeding(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Record feeding
          </ToolbarButton>
          <ToolbarButton onClick={() => setDying(true)} disabled={!data}>
            <Skull className="h-4 w-4" />
            Record mortality
          </ToolbarButton>
        </>
      }
    >
      <KpiGrid cols={4}>
        <KpiCard loading={first} label="Feed fed" value={k ? fmtKg(Number(k.feed_kg.value)) : "—"} hint="in the period" series={k?.feed_kg.series} deltaLabel="vs prev day" />
        <KpiCard loading={first} label="Feed a day" value={k ? fmtKg(Number(k.feed_kg_per_day.value)) : "—"} hint="average across the period" />
        <KpiCard loading={first} label="Fish died" value={k ? fmtNum(Number(k.dead.value)) : "—"} hint="in the period" series={k?.dead.series} goodDirection="down" deltaLabel="vs prev day" tone={k && Number(k.dead.value) > 0 ? "warning" : "default"} />
        <KpiCard loading={first} label="Hardest hit" value={k?.worst_pond.value ?? "—"} hint={k?.worst_pond.value ? `${fmtNum(k.worst_pond.dead)} fish lost` : "no deaths recorded"} tone={k?.worst_pond.value ? "critical" : "default"} />
      </KpiGrid>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card className="overflow-hidden xl:col-span-2">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Feed against mortality</CardTitle>
              <CardDescription>Bars are kilograms fed (left axis); the red line is fish that died (right axis).</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          <div className="px-3 pb-3">{first || !data ? <Bar className="h-[260px] w-full" /> : <FeedMortalityChart daily={data.daily} accent={accent} />}</div>
        </Card>
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Causes of death</CardTitle>
              <CardDescription>Fish lost in the period, by recorded cause.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          <div className="px-3 pb-3">
            {first || !data ? <Bar className="h-[200px] w-full" /> : data.causes.length ? <CausesChart causes={data.causes} /> : (
              <p className="px-2 py-10 text-center text-[13px] text-[var(--sd-quiet)]">No deaths recorded in this period.</p>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="feeding-ponds">
        {first || !data
          ? [0, 1, 2].map((i) => (
              <Card key={i} className="space-y-3 p-5" aria-busy="true"><Bar className="h-5 w-28" /><Bar className="h-16 w-full" /></Card>
            ))
          : data.ponds.map((p) => (
              <Card key={p.unit} className="flex flex-col gap-3 p-5" data-testid={`feed-pond-${p.label}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="text-[15px] font-semibold">{p.label}</div>
                  {p.top_cause && <Chip className={TONE.quiet} title="Most common cause of death in the period"><span className="mr-1.5 h-2 w-2 rounded-full" style={{ background: CAUSE_COLOR[p.top_cause] }} />{p.top_cause}</Chip>}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Fact label="Fed" value={fmtKg(p.feed_kg)} hint={`${fmtKg(p.feed_kg_per_day)} a day`} />
                  <Fact label="A day" value={fmtKg(p.feed_kg_per_day)} />
                  <Fact label="Died" value={fmtNum(p.dead)} tone={p.mortality_pct != null && p.mortality_pct >= 2 ? "bad" : undefined} />
                  <Fact label="Of stocked" value={fmtPct(p.mortality_pct, 2)} hint="Share of the growing batch's fingerlings" />
                </div>
              </Card>
            ))}
      </div>
      {data && !data.ponds.length && <div className="mt-4"><Empty>No ponds are set up for this crop.</Empty></div>}

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading><CardTitle>Feeding log</CardTitle><CardDescription>Latest entries in the period.</CardDescription></CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : data.feed_log.length ? (
            <ScrollTable>
              <table className="w-full text-[13px]">
                <thead className={STICKY_HEAD}>
                  <tr className={THEAD_ROW}><th className={TH}>Date</th><th className={TH}>Pond</th><th className={TH}>Feed</th><th className={THR}>Kg</th><th className={THR}>Times</th></tr>
                </thead>
                <tbody>
                  {data.feed_log.map((r) => (
                    <tr key={r.name} className={BODY_ROW}>
                      <td className={TD}>{dayMonth(r.feed_date)}</td>
                      <td className={`${TD} font-semibold`}>{label(r.pond)}</td>
                      <td className={`${TD} text-[var(--sd-muted)]`}>{r.feed_type ?? "—"}</td>
                      <td className={TDR}>{fmtNum(r.kg_fed, 1)}</td>
                      <td className={TDR}>{r.times_fed || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollTable>
          ) : <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">No feeding recorded in this period.</p>}
        </Card>
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading><CardTitle>Mortality log</CardTitle><CardDescription>Latest entries in the period.</CardDescription></CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : data.mortality_log.length ? (
            <ScrollTable>
              <table className="w-full text-[13px]">
                <thead className={STICKY_HEAD}>
                  <tr className={THEAD_ROW}><th className={TH}>Date</th><th className={TH}>Pond</th><th className={THR}>Fish</th><th className={TH}>Cause</th><th className={TH}>Notes</th></tr>
                </thead>
                <tbody>
                  {data.mortality_log.map((r) => (
                    <tr key={r.name} className={BODY_ROW}>
                      <td className={TD}>{dayMonth(r.mortality_date)}</td>
                      <td className={`${TD} font-semibold`}>{label(r.pond)}</td>
                      <td className={TDR}>{fmtNum(r.dead_count)}</td>
                      <td className={TD}>{r.cause}</td>
                      <td className={`${TD} text-[var(--sd-muted)]`}>{r.notes ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollTable>
          ) : <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">No deaths recorded in this period.</p>}
        </Card>
      </div>

      {data && (
        <>
          <FeedingDialog open={feeding} onOpenChange={setFeeding} form={data.form} defaultPond={pond} onSaved={load} />
          <MortalityDialog open={dying} onOpenChange={setDying} form={data.form} defaultPond={pond} onSaved={load} />
        </>
      )}
    </PageShell>
  );
}
