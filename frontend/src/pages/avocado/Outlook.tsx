import { useCallback, useEffect, useRef, useState } from "react";
import { FilterSelect } from "@/components/FilterSelect";
import { AccentScope } from "@/components/avocado/calendar-grid";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import {
  AlertsList,
  DeliveredBySeason,
  DryMatterCard,
  LossesCard,
  OutlookKpis,
  PickersCard,
  UndatedChip,
} from "@/components/avocado/outlook-cards";
import { SectionCard } from "@/components/avocado/forecast-ui";
import { PillEditor } from "@/components/avocado/forecast-ui";
import { OrchardMap } from "@/components/avocado/outlook-map";
import { SeasonTimeline } from "@/components/avocado/outlook-timeline";
import { BlocksTreemap } from "@/components/avocado/outlook-treemap";
import { Bar, ChartSkeleton } from "@/components/Loading";
import { getSeasonOutlook, savePricePerKg, type SeasonOutlook } from "@/lib/avocado-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { qty } from "@/lib/format";

function CardSkeleton({ title, height }: { title: string; height: number }) {
  return (
    <SectionCard title={title}>
      <ChartSkeleton height={height} />
    </SectionCard>
  );
}

/** Season Outlook: when the crop arrives, where it grows, who has to pick it. */
export function Outlook() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [data, setData] = useState<SeasonOutlook | null>(null);
  const [loading, setLoading] = useState(true);
  const [farm, setFarm] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  // Typed in the toolbar for this view only: the estate's price and crew come from settings and harvest teams.
  const [priceTry, setPriceTry] = useState<number | undefined>();
  const [crewTry, setCrewTry] = useState<number | undefined>();
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    const r = await getSeasonOutlook({ farm: farm || undefined, price_per_kg: priceTry, crew_available: crewTry });
    if (mine !== seq.current) return;
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as SeasonOutlook);
  }, [farm, priceTry, crewTry, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveWith(write: () => Promise<{ error?: string } | unknown>, done: string): Promise<boolean> {
    const r = await write();
    if (isError(r as never)) {
      toast((r as { error: string }).error, "error");
      return false;
    }
    toast(done);
    await load();
    return true;
  }

  const h = data?.header;
  const sub = h
    ? h.blocks
      ? `${data!.crop} crop forecast · ${qty(h.blocks)} blocks · ${h.stale_readings} stale · ${h.weeks_dated} weeks dated${
          h.biennial_factor === 1 ? " · on year" : h.biennial_factor ? ` · off year ×${h.biennial_factor}` : ""
        }`
      : "Nothing to forecast yet"
    : undefined;

  const actions = (
    <>
      {data && data.farms.length > 0 && (
        <FilterSelect label="Farm" value={farm} onChange={setFarm} options={data.farms} allLabel="All farms" />
      )}
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
            onSaveEstate={crop.boot.can_manage ? (n) => saveWith(() => savePricePerKg(n), "Estate price saved.") : undefined}
          />
          <PillEditor
            label="Crew available"
            display={qty(data.crew_available)}
            value={data.crew_available}
            unit="pickers"
            onSave={(n) => {
              setCrewTry(n);
              return true;
            }}
          />
        </>
      )}
      <RefreshButton onClick={() => void load()} loading={loading} label="the season outlook" />
    </>
  );

  return (
    <PageShell
      title={viewLabel("outlook", crop)}
      eyebrow={crop.name}
      actions={actions}
      description={sub ?? <Bar className="inline-block h-3.5 w-72 align-middle" />}
    >
      <AccentScope accent={accent} className="flex flex-col gap-6">
        <OutlookKpis data={data} />
        {!data ? (
          <>
            <CardSkeleton title="Season timeline" height={240} />
            <CardSkeleton title="Orchard" height={320} />
            <CardSkeleton title="Blocks" height={300} />
          </>
        ) : (
          <>
            <UndatedChip data={data} />
            <SeasonTimeline data={data} />
            <OrchardMap data={data} selected={selected} onSelect={setSelected} />
            <BlocksTreemap data={data} selected={selected} onSelect={setSelected} />
            <div className="grid gap-6 lg:grid-cols-3">
              <DryMatterCard data={data} />
              <PickersCard data={data} />
              <LossesCard losses={data.losses} block={selected} />
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              <AlertsList alerts={data.alerts} />
              <DeliveredBySeason rows={data.delivered_by_season} />
            </div>
          </>
        )}
      </AccentScope>
    </PageShell>
  );
}
