import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { dayTime, fmtNum, METRIC_LABEL, TONE } from "@/components/aquaculture/format";
import { Chip, Empty } from "@/components/aquaculture/ui";
import { WaterCard } from "@/components/aquaculture/water-card";
import { DoChart, POND_COLORS, PondLegend, TempChart } from "@/components/aquaculture/water-charts";
import { WaterReadingDialog } from "@/components/aquaculture/water-dialog";
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
import { getWaterQuality, type Bands, type WaterQualityPage } from "@/lib/aquaculture-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { todayISO, ymd } from "@/lib/utils";

function defaultRange(): DateRange {
  const to = todayISO();
  const d = new Date(`${to}T00:00:00`);
  d.setDate(d.getDate() - 13);
  return { from: ymd(d), to };
}

/** The safe ranges in words; only the limits the manager has set. */
function safeBands(b: Bands): string {
  const parts = [
    b.do_min != null ? `oxygen at least ${b.do_min} mg/L` : "",
    b.ph_min != null && b.ph_max != null ? `pH ${b.ph_min} to ${b.ph_max}` : "",
    b.temp_min != null && b.temp_max != null ? `${b.temp_min} to ${b.temp_max} °C` : "",
    b.ammonia_max != null ? `ammonia under ${b.ammonia_max} mg/L` : "",
  ].filter(Boolean);
  return parts.length ? `Safe bands: ${parts.join(" · ")}` : "No safe water bands set on the crop or its varieties yet";
}

export function WaterQuality() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [data, setData] = useState<WaterQualityPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [pond, setPond] = useState("");
  const [recording, setRecording] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getWaterQuality({ from_date: range.from, to_date: range.to, unit: pond || undefined });
    setLoading(false);
    if (isError(r)) return void toast(r.error, "error");
    setData(r as WaterQualityPage);
  }, [range, pond, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const dirty = !!pond || range.from !== defaultRange().from || range.to !== defaultRange().to;
  const colorOf = useMemo(() => {
    const all = data?.form.ponds ?? [];
    return (unit: string) => POND_COLORS[Math.max(all.findIndex((p) => p.unit === unit), 0) % POND_COLORS.length];
  }, [data]);
  const withData = (data?.ponds ?? []).filter((p) => p.readings > 0);
  const lowDo = k && k.lowest_do_mg_l.value != null && data && data.bands.do_min != null && Number(k.lowest_do_mg_l.value) < data.bands.do_min;

  return (
    <PageShell
      title={viewLabel("water-quality", crop)}
      eyebrow={crop.name}
      description={data ? safeBands(data.bands) : undefined}
      actions={
        <>
          <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
          <FilterSelect label="Pond" value={pond} onChange={setPond} options={(data?.form.ponds ?? []).map((p) => ({ value: p.unit, label: p.label }))} allLabel="All ponds" />
          <ClearFiltersPill active={dirty} onClear={() => { setPond(""); setRange(defaultRange()); }} />
          <RefreshButton onClick={load} loading={loading} label="the readings" />
          <ToolbarButton onClick={() => setRecording(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Record a reading
          </ToolbarButton>
        </>
      }
    >
      <KpiGrid cols={4}>
        <KpiCard loading={first} label="Ponds in band" value={k ? `${k.ponds_in_band.value} of ${k.ponds_in_band.of}` : "—"} hint="latest reading inside every safe band" tone={k && k.ponds_in_band.value !== k.ponds_in_band.of ? "warning" : "good"} />
        <KpiCard loading={first} label="Alerts" value={k ? Number(k.alerts.value) : "—"} hint="out-of-band measurements in the period" series={k?.alerts.series} goodDirection="down" deltaLabel="vs prev day" tone={k && Number(k.alerts.value) > 0 ? "critical" : "default"} />
        <KpiCard loading={first} label="Lowest oxygen" value={k?.lowest_do_mg_l.value != null ? `${fmtNum(Number(k.lowest_do_mg_l.value), 1)} mg/L` : "—"} hint={data?.bands.do_min != null ? `safe is ${data.bands.do_min} or more` : undefined} series={k?.lowest_do_mg_l.series} goodDirection="up" deltaLabel="vs prev day" tone={lowDo ? "critical" : "default"} />
        <KpiCard loading={first} label="Average temperature" value={k?.avg_temp_c.value != null ? `${fmtNum(Number(k.avg_temp_c.value), 1)} °C` : "—"} hint={`${k?.readings.value ?? 0} readings`} series={k?.avg_temp_c.series} deltaLabel="vs prev day" />
      </KpiGrid>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="water-cards">
        {first || !data
          ? [0, 1, 2].map((i) => (
              <Card key={i} className="space-y-3 p-5" aria-busy="true">
                <Bar className="h-5 w-28" />
                <Bar className="h-12 w-full" />
                <Bar className="h-[70px] w-full" />
              </Card>
            ))
          : data.ponds.map((p) => <WaterCard key={p.unit} pond={p} bands={p.bands ?? data.bands} color={colorOf(p.unit)} />)}
      </div>
      {data && !data.ponds.length && <div className="mt-4"><Empty>No ponds are set up for this crop.</Empty></div>}

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Dissolved oxygen</CardTitle>
              <CardDescription>mg/L by reading. Below the shaded line fish are stressed; a night low is the usual cause of a die-off.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-6"><Bar className="h-[220px] w-full" /></div> : (
            <>
              <PondLegend ponds={withData} />
              <div className="px-3 pb-3"><DoChart ponds={withData} bands={data.bands} /></div>
            </>
          )}
        </Card>
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Temperature</CardTitle>
              <CardDescription>°C by reading. The shaded band is the safe range.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-6"><Bar className="h-[220px] w-full" /></div> : (
            <>
              <PondLegend ponds={withData} />
              <div className="px-3 pb-3"><TempChart ponds={withData} bands={data.bands} /></div>
            </>
          )}
        </Card>
      </div>

      <Card className="mt-4 overflow-hidden" data-testid="alerts">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Alerts</CardTitle>
            <CardDescription>Every out-of-band measurement in the period, newest first.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : data.alerts.length ? (
          <ul className="divide-y divide-[var(--sd-line-soft)] px-5 pb-3 text-[13px]">
            {data.alerts.map((a, i) => (
              <li key={`${a.pond}-${a.at}-${a.metric}-${i}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
                <Chip className={TONE.bad}>{METRIC_LABEL[a.metric] ?? a.metric}</Chip>
                <span className="font-semibold">{a.pond_name}</span>
                <span className="text-[var(--sd-muted)]">{a.message}</span>
                <span className="ml-auto text-[12px] text-[var(--sd-quiet)]">{dayTime(a.at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">No alerts. Every reading in this period was inside the safe bands.</p>
        )}
      </Card>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Recent readings</CardTitle>
            <CardDescription>The latest 60. Values outside their band are in red.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : data.readings.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>When</th><th className={TH}>Pond</th>
                  <th className={THR}>Oxygen</th><th className={THR}>pH</th><th className={THR}>Temp</th>
                  <th className={THR}>Ammonia</th><th className={THR}>Nitrite</th><th className={THR}>Secchi</th><th className={TH}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {data.readings.map((r) => {
                  const bad = new Set<string>(r.flags.map((f) => f.metric));
                  const c = (key: string, v: number | null, d: number) => (
                    <td className={`${TDR} ${bad.has(key) ? "font-semibold text-[var(--sd-data-red)]" : ""}`}>{v == null ? "—" : fmtNum(v, d)}</td>
                  );
                  return (
                    <tr key={r.name} className={BODY_ROW}>
                      <td className={TD}>{dayTime(r.at)}</td>
                      <td className={`${TD} font-semibold`}>{data.ponds.find((p) => p.unit === r.pond)?.label ?? r.pond}</td>
                      {c("do", r.dissolved_oxygen_mg_l, 1)}{c("ph", r.ph, 1)}{c("temp", r.temperature_c, 1)}
                      {c("ammonia", r.ammonia_mg_l, 2)}{c("nitrite", r.nitrite_mg_l, 2)}{c("secchi", r.secchi_cm, 0)}
                      <td className={`${TD} text-[var(--sd-muted)]`}>{r.notes ?? ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">No readings in this period. Use Record a reading to add one.</p>
        )}
      </Card>

      {data && <WaterReadingDialog open={recording} onOpenChange={setRecording} form={data.form} bands={data.bands} defaultPond={pond} onSaved={load} />}
    </PageShell>
  );
}
