import { useCallback, useEffect, useMemo, useState } from "react";
import { AccentScope, CalendarGrid, CalendarLegend } from "@/components/avocado/calendar-grid";
import { NoForecastTable, NoPickDateTable } from "@/components/avocado/calendar-tables";
import { dayMonth, fmtKgTonnes, fmtNum, fmtUnit, type CellUnit } from "@/components/avocado/calendar-format";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { Bar, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { TogglePill } from "@/components/TogglePill";
import { useToast } from "@/components/Toast";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { getHarvestCalendar, type HarvestCalendar as CalendarData } from "@/lib/avocado-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";

const UNITS: { id: CellUnit; label: string }[] = [
  { id: "tonnes", label: "Tonnes" },
  { id: "crates", label: "Crates" },
  { id: "kg", label: "Kg" },
];

export function HarvestCalendar() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [data, setData] = useState<CalendarData | null>(null);
  const [loading, setLoading] = useState(true);
  const [farm, setFarm] = useState("");
  const [year, setYear] = useState("");
  const [unit, setUnit] = useState<CellUnit>("tonnes");

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getHarvestCalendar({ farm: farm || undefined, planting_year: year ? Number(year) : undefined });
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as CalendarData);
  }, [farm, year, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const series = useMemo(() => (data?.weeks ?? []).map((w) => ({ week: w.week, value: w.kg })), [data]);
  const years = useMemo(() => (data?.filters.planting_years ?? []).map(String), [data]);

  const peak = k?.peak_week;
  const win = k?.in_window;
  const now = k?.pickable_now;
  const nod = k?.no_pick_date;

  return (
    <PageShell
      title={viewLabel("harvest-calendar", crop)}
      eyebrow={crop.name}
      description="One row a block, one column a week starting Monday. Locked weeks are blocks still under the dry matter minimum."
      actions={
        <>
          <FilterSelect label="Farm" value={farm} onChange={setFarm} options={data?.filters.farms ?? []} allLabel="All farms" />
          <FilterSelect label="Planting year" value={year} onChange={setYear} options={years} allLabel="All years" />
          <ClearFiltersPill
            active={!!farm || !!year}
            onClear={() => {
              setFarm("");
              setYear("");
            }}
          />
          <div role="group" aria-label="Cells show" className="flex items-center gap-1.5">
            <span className="hidden text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--sd-quiet)] md:inline">Cells show</span>
            {UNITS.map((u) => (
              <TogglePill key={u.id} pressed={unit === u.id} onPressedChange={() => setUnit(u.id)}>
                {u.label}
              </TogglePill>
            ))}
          </div>
          <RefreshButton onClick={load} loading={loading} label="the calendar" />
        </>
      }
    >
      <AccentScope accent={accent} className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard
          loading={first}
          label="Peak week"
          value={peak ? `Wk ${peak.iso_week}` : "—"}
          hint={peak ? `${fmtUnit(peak.kg, peak.crates, unit)} · week of ${dayMonth(peak.week)}` : "no weeks placed yet"}
          series={series}
          deltaLabel="vs prev week"
        />
        <KpiCard
          loading={first}
          label="In window"
          value={win ? fmtUnit(win.kg, win.crates, unit) : "—"}
          hint={win?.from_iso_week ? `weeks ${win.from_iso_week} to ${win.to_iso_week} of ${data?.pick_weeks ?? 0} picking weeks` : "nothing dated"}
        />
        <KpiCard
          loading={first}
          label="Pickable now"
          value={now ? `${fmtNum(now.blocks)} of ${fmtNum(now.of)}` : "—"}
          hint={now ? `blocks at or above ${now.minimum_pct}% dry matter` : ""}
          tone={now && now.blocks > 0 ? "good" : "default"}
        />
        <KpiCard
          loading={first}
          label="No pick date"
          value={nod ? fmtKgTonnes(nod.kg) : "—"}
          hint={nod ? `${fmtNum(nod.blocks)} blocks waiting on a dry matter sample` : ""}
          tone={nod && nod.blocks > 0 ? "warning" : "default"}
        />
      </AccentScope>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Which block, which week</CardTitle>
            <CardDescription>
              Hatched weeks are locked, the block is under {data?.minimum_pct ?? 24}% dry matter. Dotted rows have never been sampled: a missing
              measurement, not a verdict.
            </CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="space-y-3 px-5 pb-6" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <Bar key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <>
            <CalendarGrid data={data} unit={unit} accent={accent} />
            <CalendarLegend data={data} accent={accent} unit={unit} />
          </>
        )}
      </Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>No pick date</CardTitle>
              <CardDescription>
                Forecast fruit that cannot be placed in a week, because the block has no dry matter reading to date it. Sample these and they join the calendar.
              </CardDescription>
            </CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : <NoPickDateTable rows={data.no_pick_date} />}
        </Card>
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>No forecast</CardTitle>
              <CardDescription>No kilograms this season: too young to bear, or no planting year so no yield curve applies.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : <NoForecastTable rows={data.no_forecast} />}
        </Card>
      </div>
    </PageShell>
  );
}
