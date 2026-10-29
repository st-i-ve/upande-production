import { useCallback, useEffect, useRef, useState } from "react";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { Bar, ChartSkeleton } from "@/components/Loading";
import { AccentScope } from "@/components/avocado/calendar-grid";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { TogglePill } from "@/components/TogglePill";
import { useToast } from "@/components/Toast";
import { EstimateCard, PlantingYearCard, SeasonBudgetCard } from "@/components/avocado/forecast-budget";
import { BlocksCard, DataGapsCard, LossesTableCard, MaturityCard, ScheduleCard, YieldCurveCard } from "@/components/avocado/forecast-tables";
import { PillEditor, SectionCard, kesShort, pct1, tonnes } from "@/components/avocado/forecast-ui";
import {
  getProductionForecast,
  saveManualForecast,
  savePricePerKg,
  setForecastMode,
  type ForecastMode,
  type KpiCard as KpiData,
  type ProductionForecast,
} from "@/lib/avocado-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { qty } from "@/lib/format";

function display(c: KpiData): string {
  if (c.value == null) return "—";
  if (c.of != null) return `${qty(c.value)} of ${qty(c.of)}`;
  if (c.unit === "kg") return tonnes(c.value);
  if (c.unit === "KES") return kesShort(c.value);
  if (c.unit === "%") return pct1(c.value);
  return qty(c.value);
}

function KpiRow({ data, mode }: { data: ProductionForecast | null; mode: ForecastMode }) {
  if (!data) {
    return (
      <KpiGrid cols={4}>
        {["Forecast", "Grade 1", "Value", "Bearing"].map((l) => (
          <KpiCard key={l} label={l} value="" loading className="min-h-[148px]" />
        ))}
      </KpiGrid>
    );
  }
  return (
    <KpiGrid cols={4} className="lg:grid-cols-4">
      {data.views[mode].cards.map((c) => (
        <KpiCard
          key={c.key}
          label={c.label}
          value={display(c)}
          hint={c.key === "losing" && c.lost_kes ? `${c.hint} · ${kesShort(c.lost_kes)}` : c.hint}
          tone={c.key === "losing" && c.value ? "critical" : c.key === "grade_1" ? "good" : "default"}
          className="h-full"
        />
      ))}
    </KpiGrid>
  );
}

function ModeNote({ data, mode }: { data: ProductionForecast; mode: ForecastMode }) {
  if (mode === "automatic")
    return (
      <>
        Showing the <b>system-calculated</b> forecast — from tree counts, block ages and dry matter samples.
      </>
    );
  const n = data.manual_note.entries;
  return n ? (
    <>
      Showing <b>{n} manually entered</b> block {n === 1 ? "forecast" : "forecasts"} of {data.manual_note.blocks_total} orchard blocks. Switch to Automatic for the estate's calculated forecast.
    </>
  ) : (
    <>
      No manual forecasts have been entered yet for this season — click a block's forecast in the table to type one. Switch to Automatic to see the calculated forecast.
    </>
  );
}

/** Block Forecast: the season's crop by block, calculated or typed, against budget and what was delivered. */
export function BlockForecast() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const canEdit = !!(crop.boot.can_plan || crop.boot.can_manage);
  const [data, setData] = useState<ProductionForecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [farm, setFarm] = useState("");
  const [season, setSeason] = useState("");
  const [mode, setMode] = useState<ForecastMode>("automatic");
  // Typed in the toolbar for this view only; the estate price is the crop's setting.
  const [priceTry, setPriceTry] = useState<number | undefined>();
  const modeSet = useRef(false);
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    const r = await getProductionForecast({ farm: farm || undefined, season: season ? Number(season) : undefined, price_per_kg: priceTry });
    if (mine !== seq.current) return;
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    const d = r as ProductionForecast;
    setData(d);
    if (!modeSet.current) {
      modeSet.current = true;
      setMode(d.mode);
    }
  }, [farm, season, priceTry, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // Both views are already in hand: switching never re-asks the server for the forecast,
  // it only remembers the choice.
  async function pickMode(next: ForecastMode) {
    if (next === mode) return;
    const prev = mode;
    setMode(next);
    const r = await setForecastMode(next);
    if (isError(r)) {
      setMode(prev);
      toast(r.error, "error");
    }
  }

  async function saveEstatePrice(n: number) {
    const r = await savePricePerKg(n);
    if (isError(r)) {
      toast(r.error, "error");
      return false;
    }
    toast("Estate price saved.");
    await load();
    return true;
  }

  async function editBlock(block: string, kg: number) {
    const r = await saveManualForecast({ orchard_block: block, expected_kg: kg, season: data?.season });
    if (isError(r)) {
      toast(r.error, "error");
      return false;
    }
    toast(`Forecast for ${block} saved.`);
    await load();
    return true;
  }

  const view = data?.views[mode];
  const modeLabel = mode === "manual" ? "Manual" : "Automatic";

  const actions = (
    <>
      <TogglePill pressed={mode === "manual"} onPressedChange={() => void pickMode("manual")}>
        Manual
      </TogglePill>
      <TogglePill pressed={mode === "automatic"} onPressedChange={() => void pickMode("automatic")}>
        Automatic
      </TogglePill>
      {data && (
        <>
          <PillEditor
            label="Price / kg"
            display={`KES ${qty(data.price_per_kg)}`}
            value={data.price_per_kg}
            unit="KES"
            onSave={(n) => {
              setPriceTry(n);
              return true;
            }}
            onSaveEstate={crop.boot.can_manage ? saveEstatePrice : undefined}
          />
          <FilterSelect
            label="Season"
            value={String(data.season)}
            onChange={setSeason}
            options={data.seasons.map(String)}
          />
          {data.farms.length > 0 && <FilterSelect label="Farm" value={farm} onChange={setFarm} options={data.farms} allLabel="All farms" />}
        </>
      )}
      <RefreshButton onClick={() => void load()} loading={loading} label="the forecast" />
    </>
  );

  return (
    <PageShell
      title={viewLabel("block-forecast", crop)}
      eyebrow={crop.name}
      actions={actions}
      description={data ? <ModeNote data={data} mode={mode} /> : <Bar className="inline-block h-3.5 w-80 align-middle" />}
    >
      <AccentScope accent={accent} className="flex flex-col gap-6">
        <KpiRow data={data} mode={mode} />
        {!data || !view ? (
          <>
            <SectionCard title="Season budget"><ChartSkeleton height={180} /></SectionCard>
            <SectionCard title="Blocks"><ChartSkeleton height={280} /></SectionCard>
          </>
        ) : (
          <>
            <SeasonBudgetCard
              budget={data.budget}
              forecastKg={view.total_kg}
              vsBudget={view.vs_budget}
              modeLabel={modeLabel}
              canEdit={canEdit}
              onSaved={() => void load()}
            />
            <EstimateCard e={data.estimate_vs_delivered} />
            <PlantingYearCard rows={data.by_planting_year} />
            <YieldCurveCard rows={data.yield_curve} />
            <BlocksCard view={view} mode={mode} canEdit={canEdit} onEdit={editBlock} />
            <ScheduleCard s={data.schedule} />
            <div className="grid gap-6 xl:grid-cols-2">
              <MaturityCard m={data.maturity} />
              <DataGapsCard gaps={data.data_gaps} />
            </div>
            <LossesTableCard losses={data.losses} />
          </>
        )}
      </AccentScope>
    </PageShell>
  );
}
