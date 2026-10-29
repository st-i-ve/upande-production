import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { bandTone } from "@/lib/bands";
import { BatchCard } from "@/components/aquaculture/batch-card";
import { HarvestDialog, SamplingDialog, StockingDialog } from "@/components/aquaculture/batch-dialogs";
import { ageLabel, dayMonth, fmtGrams, fmtKg, fmtNum, fmtPct, TONE } from "@/components/aquaculture/format";
import { Chip, Empty } from "@/components/aquaculture/ui";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { Bar, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { useToast } from "@/components/Toast";
import { ToolbarButton } from "@/components/ToolbarButton";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { getPondBatches, type PondBatch, type PondBatchesPage } from "@/lib/aquaculture-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";

const STATUSES = ["Growing", "Harvested", "Closed"];

export function PondBatches() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#2b6f9e";
  const [data, setData] = useState<PondBatchesPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [pond, setPond] = useState("");
  const [status, setStatus] = useState("");
  const [stocking, setStocking] = useState(false);
  const [sampling, setSampling] = useState<PondBatch | null>(null);
  const [harvesting, setHarvesting] = useState<PondBatch | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getPondBatches({ status: status || undefined, unit: pond || undefined });
    setLoading(false);
    if (isError(r)) return void toast(r.error, "error");
    setData(r as PondBatchesPage);
  }, [status, pond, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const batches = data?.batches ?? [];
  const growing = batches.filter((b) => b.status === "Growing").length;

  return (
    <PageShell
      title={viewLabel("pond-batches", crop)}
      eyebrow={crop.name}
      description="A batch is one stocking of a pond. Fish have no crop cycles: stock, sample, feed, then harvest."
      actions={
        <>
          <FilterSelect label="Pond" value={pond} onChange={setPond} options={(data?.form.ponds ?? []).map((p) => ({ value: p.unit, label: p.label }))} allLabel="All ponds" />
          <FilterSelect label="Status" value={status} onChange={setStatus} options={STATUSES} allLabel="Any status" />
          <ClearFiltersPill active={!!pond || !!status} onClear={() => { setPond(""); setStatus(""); }} />
          <RefreshButton onClick={load} loading={loading} label="the batches" />
          <ToolbarButton onClick={() => setStocking(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Stock a pond
          </ToolbarButton>
        </>
      }
    >
      <KpiGrid cols={4}>
        <KpiCard loading={first} label="Fish alive" value={k ? fmtNum(Number(k.live_fish.value)) : "—"} hint={`${k?.growing.value ?? 0} growing batches`} series={k?.live_fish.series} goodDirection="up" deltaLabel="vs last week" />
        <KpiCard loading={first} label="Biomass" value={k ? fmtKg(Number(k.biomass_kg.value)) : "—"} hint="live fish times average weight" series={k?.biomass_kg.series} goodDirection="up" deltaLabel="vs last week" />
        <KpiCard loading={first} label="FCR" value={k ? fmtNum(k.fcr.value as number | null, 2) : "—"} hint="kg of feed per kg gained, growing batches" series={k?.fcr.series} goodDirection="down" deltaLabel="vs last week" tone={k && Number(k.fcr.value) > 1.8 ? "warning" : "default"} />
        <KpiCard loading={first} label="Survival" value={k ? fmtPct(k.survival_pct.value as number | null) : "—"} hint="of fingerlings stocked, growing batches" series={k?.survival_pct.series} goodDirection="up" deltaLabel="vs last week" tone={k && k.survival_pct.value != null ? bandTone(data?.bands, "Fish survival", Number(k.survival_pct.value)) === "critical" ? "critical" : "default" : "default"} />
      </KpiGrid>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="batch-cards">
        {first || !data
          ? [0, 1, 2].map((i) => (
              <Card key={i} className="space-y-3 p-5" aria-busy="true">
                <Bar className="h-5 w-32" />
                <Bar className="h-9 w-24" />
                <Bar className="h-[150px] w-full" />
              </Card>
            ))
          : batches.map((b) => <BatchCard key={b.name} b={b} accent={accent} bands={data?.bands} staleDays={data?.sample_stale_days ?? null} onSample={setSampling} onHarvest={setHarvesting} />)}
      </div>
      {data && !batches.length && (
        <div className="mt-4">
          <Empty>{pond || status ? "No batch matches these filters." : "No pond has been stocked yet. Use Stock a pond to start a batch."}</Empty>
        </div>
      )}

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>All batches</CardTitle>
            <CardDescription>{growing} growing. FCR is feed divided by weight gained, including fish already harvested.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div>
        ) : batches.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Pond</th>
                  <th className={TH}>Species</th>
                  <th className={TH}>Stocked</th>
                  <th className={THR}>In water</th>
                  <th className={THR}>Alive</th>
                  <th className={THR}>Survival</th>
                  <th className={THR}>Avg weight</th>
                  <th className={THR}>Biomass</th>
                  <th className={THR}>Feed</th>
                  <th className={THR}>FCR</th>
                  <th className={TH}>Harvest</th>
                  <th className={TH}>Status</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.name} className={BODY_ROW} data-testid={`batch-row-${b.pond_name}`}>
                    <td className={`${TD} font-semibold`}>{b.pond_name}</td>
                    <td className={TD}>{b.species}</td>
                    <td className={TD}>{dayMonth(b.stocking_date)} · {fmtNum(b.stocked)}</td>
                    <td className={TDR}>{ageLabel(b.days_in_water)}</td>
                    <td className={TDR}>{fmtNum(b.live)}</td>
                    <td className={TDR}>{fmtPct(b.survival_pct)}</td>
                    <td className={TDR}>{fmtGrams(b.avg_weight_g)}</td>
                    <td className={TDR}>{b.status === "Growing" ? fmtKg(b.biomass_kg) : "—"}</td>
                    <td className={TDR}>{fmtKg(b.feed_kg)}</td>
                    <td className={TDR}>{fmtNum(b.fcr, 2)}</td>
                    <td className={TD}>
                      {b.status === "Harvested"
                        ? `${fmtKg(b.harvest_kg)} · ${dayMonth(b.harvest_date)}`
                        : b.projected_harvest_date
                          ? `~${dayMonth(b.projected_harvest_date)}`
                          : "—"}
                    </td>
                    <td className={TD}>
                      <Chip className={b.status === "Growing" ? (b.on_track === false ? TONE.warn : TONE.ok) : TONE.quiet}>{b.status}</Chip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">Nothing to list.</p>
        )}
      </Card>

      {data && <StockingDialog open={stocking} onOpenChange={setStocking} form={data.form} onSaved={load} />}
      <SamplingDialog open={!!sampling} onOpenChange={(o) => !o && setSampling(null)} batch={sampling} onSaved={load} />
      <HarvestDialog open={!!harvesting} onOpenChange={(o) => !o && setHarvesting(null)} batch={harvesting} onSaved={load} />
    </PageShell>
  );
}
