import { AccentScope } from "@/components/avocado/calendar-grid";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { Chip } from "@/components/avocado/calendar-grid";
import { dayMonth, fmtNum } from "@/components/avocado/calendar-format";
import { BlockCard } from "@/components/avocado/drymatter-card";
import { RecordSampleDialog } from "@/components/avocado/drymatter-dialog";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { Bar, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { getDryMatter, type DryMatterPage } from "@/lib/avocado-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { cn } from "@/lib/utils";

export function DryMatter() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [data, setData] = useState<DryMatterPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [farm, setFarm] = useState("");
  const [block, setBlock] = useState("");
  const [recording, setRecording] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getDryMatter({ farm: farm || undefined, block: block || undefined });
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as DryMatterPage);
  }, [farm, block, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const s = data?.summary;
  const blocks = useMemo(
    () => (data?.blocks ?? []).filter((b) => !block || b.block === block),
    [data, block],
  );
  const blockOptions = useMemo(
    () => (data?.form.blocks ?? []).map((b) => ({ value: b.block, label: b.block })),
    [data],
  );

  return (
    <PageShell
      title={viewLabel("dry-matter", crop)}
      eyebrow={crop.name}
      description={data ? `Week ${data.form.week_number} · export window ${data.minimum_pct} to ${data.maximum_pct}% dry matter` : undefined}
      actions={
        <>
          <FilterSelect label="Farm" value={farm} onChange={(v) => { setFarm(v); setBlock(""); }} options={data?.farms ?? []} allLabel="All farms" />
          <FilterSelect label="Block" value={block} onChange={setBlock} options={blockOptions} allLabel="All blocks" />
          <ClearFiltersPill active={!!farm || !!block} onClear={() => { setFarm(""); setBlock(""); }} />
          <RefreshButton onClick={load} loading={loading} label="the tests" />
          <ToolbarButton onClick={() => setRecording(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Record a sample
          </ToolbarButton>
        </>
      }
    >
      <AccentScope accent={accent} className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        <KpiCard loading={first} label="Due for sampling" value={s?.due ?? "—"} hint={data?.retest_days ? `in or past the sampling stage, no test in ${data.retest_days} days` : "in or past the sampling stage"} tone={s?.due ? "warning" : "default"} />
        <KpiCard loading={first} label="Ready" value={s ? `${fmtNum(s.ready)} of ${fmtNum(s.blocks)}` : "—"} hint={data ? `blocks at or above ${data.minimum_pct}%` : ""} tone={s?.ready ? "good" : "default"} />
        <KpiCard loading={first} label="Rising" value={s?.rising ?? "—"} hint="under the floor and gaining" />
        <KpiCard loading={first} label="Stale" value={s?.stale ?? "—"} hint="last reading too old to trust" tone={s?.stale ? "warning" : "default"} />
        <KpiCard loading={first} label="Never sampled" value={s?.never_sampled ?? "—"} hint="no reading for the block or its planting year" tone={s?.never_sampled ? "warning" : "default"} />
      </AccentScope>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="dm-cards">
        {first || !data
          ? [0, 1, 2].map((i) => (
              <Card key={i} className="space-y-3 p-5" aria-busy="true">
                <Bar className="h-5 w-32" />
                <Bar className="h-9 w-24" />
                <Bar className="h-[110px] w-full" />
              </Card>
            ))
          : blocks.map((b) => <BlockCard key={b.block} b={b} minimum={data!.minimum_pct} accent={accent} />)}
      </div>
      {data && !blocks.length && (
        <p className="mt-4 rounded-2xl bg-[var(--sd-card)] px-5 py-10 text-center text-[13px] text-[var(--sd-quiet)] shadow-[var(--sd-shadow-1)]">
          No blocks to show. Choose another farm, or check the blocks have a planting year.
        </p>
      )}

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Earlier tests</CardTitle>
            <CardDescription>
              One row a visit. Two visits a fortnight apart let the forecast measure how fast a block is gaining, instead of assuming the estate's usual rate.
            </CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div>
        ) : data.recent_visits.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Date</th>
                  <th className={THR}>Week</th>
                  <th className={TH}>Where</th>
                  <th className={TH}>Stage</th>
                  <th className={THR}>Sizes</th>
                  <th className={THR}>Avg dry matter</th>
                  <th className={TH}>Verdict</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_visits.map((v, i) => (
                  <tr key={`${v.test_date}-${v.where}-${i}`} className={BODY_ROW}>
                    <td className={cn(TD, "font-semibold")}>{dayMonth(v.test_date)}</td>
                    <td className={TDR}>{v.week_number ?? "—"}</td>
                    <td className={TD}>
                      {v.where}
                      {v.measured_on === "area" && (
                        <Chip className="ml-2 bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]">area, not a block</Chip>
                      )}
                    </td>
                    <td className={cn(TD, "text-[var(--sd-muted)]")} data-testid="dm-visit-stage">{v.stage || "—"}</td>
                    <td className={TDR}>{v.sizes.length}</td>
                    <td className={cn(TDR, "font-semibold")}>{v.average_dry_matter.toFixed(1)}%</td>
                    <td className={TD}>
                      <Chip className={v.ready ? "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]" : "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]"}>
                        {v.ready ? "Ready" : "Not yet"}
                      </Chip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">
            {block ? `No test recorded for ${block} yet.` : "No tests recorded yet. Use Record a sample to add one."}
          </p>
        )}
      </Card>

      {data && (
        <RecordSampleDialog open={recording} onOpenChange={setRecording} form={data.form} defaultBlock={block} onSaved={load} />
      )}
    </PageShell>
  );
}
