import { useCallback, useEffect, useMemo, useState } from "react";
import { fmtKgTonnes, fmtNum, dayMonth } from "@/components/avocado/calendar-format";
import { AccentScope } from "@/components/avocado/calendar-grid";
import { PillNumber } from "@/components/avocado/picking-crew";
import { PickingChart } from "@/components/avocado/picking-chart";
import { RatesTable, RejectedTable, UnscheduledTable, WeekDetail } from "@/components/avocado/picking-detail";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { Bar, ChartSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle, CardTools } from "@/components/ui/card";
import { getPickingPlan, saveCrewAvailable, type PickingPlan as PlanData } from "@/lib/avocado-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { kes } from "@/lib/format";

const toNum = (s: string): number | undefined => {
  if (s.trim() === "") return undefined;
  const n = Number(s);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
};

export function PickingPlan() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [data, setData] = useState<PlanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [farm, setFarm] = useState("");
  const [crewDraft, setCrewDraft] = useState("");
  const [days, setDays] = useState("");
  const [pay, setPay] = useState("");
  const [crewOverride, setCrewOverride] = useState<number | undefined>();
  const [daysQ, setDaysQ] = useState<number | undefined>();
  const [payQ, setPayQ] = useState<number | undefined>();
  const [week, setWeek] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getPickingPlan({ farm: farm || undefined, crew_available: crewOverride, days_per_week: daysQ, pay_per_day: payQ });
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    const d = r as PlanData;
    setData(d);
    setCrewDraft(String(d.crew_available));
    setDays(String(d.days_per_week));
    if (d.pay_per_day_kes) setPay(String(d.pay_per_day_kes));
  }, [farm, crewOverride, daysQ, payQ, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const saveCrew = async () => {
    const n = toNum(crewDraft);
    if (n === undefined || !Number.isInteger(n)) {
      toast("Crew available must be a whole number of people.", "error");
      return;
    }
    setSaving(true);
    const r = await saveCrewAvailable(n);
    setSaving(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`Crew available saved: ${n} pickers.`);
    // The saved figure is now the plan's: re-read with it.
    if (crewOverride === n) void load();
    else setCrewOverride(n);
  };

  const first = firstLoad(loading, !!data);
  const canPay = !!data?.can_see_pay;
  const crewDirty = !!data && crewDraft !== String(data.crew_available);
  const selected = week || data?.focus_week || data?.weeks[0]?.week || "";
  const detail = useMemo(() => data?.weeks.find((w) => w.week === selected) ?? data?.week_detail ?? null, [data, selected]);
  const weekOptions = useMemo(
    () => (data?.weeks ?? []).map((w) => ({ value: w.week, label: `Week of ${dayMonth(w.week)}` })),
    [data],
  );
  const k = data?.kpis;
  const series = (data?.weeks ?? []).map((w) => ({ week: w.week, value: w.pickers_needed }));

  return (
    <PageShell
      title={viewLabel("picking-plan", crop)}
      eyebrow={crop.name}
      description="Each block's kilograms divided by that block's own picking rate. Bars over the crew line are the weeks worth a meeting."
      actions={
        <>
          <FilterSelect label="Farm" value={farm} onChange={setFarm} options={data?.farms ?? []} allLabel="All farms" />
          <PillNumber label="Crew available" value={crewDraft} onChange={setCrewDraft} width="w-12">
            {crewDirty && (
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  void saveCrew();
                }}
                disabled={saving}
                className="rounded-full bg-foreground px-2.5 py-0.5 text-[11px] font-semibold text-background disabled:opacity-50"
              >
                Save
              </button>
            )}
          </PillNumber>
          <PillNumber label="Days a week" value={days} onChange={setDays} onCommit={() => setDaysQ(toNum(days))} min={1} max={7} width="w-8" />
          {canPay && <PillNumber label="Pay a day (KES)" value={pay} onChange={setPay} onCommit={() => setPayQ(toNum(pay))} width="w-16" placeholder="set rate" />}
          <ClearFiltersPill active={!!farm} onClear={() => setFarm("")} />
          <RefreshButton onClick={load} loading={loading} label="the plan" />
        </>
      }
    >
      <AccentScope accent={accent} className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard
          loading={first}
          label="Peak crew"
          value={k?.peak_week.pickers != null ? fmtNum(k.peak_week.pickers) : "—"}
          hint={k?.peak_week.week ? `pickers, week of ${dayMonth(k.peak_week.week)}` : "no weeks planned yet"}
          series={series}
          goodDirection="down"
        />
        <KpiCard
          loading={first}
          label="Weeks short"
          value={k?.weeks_short.weeks ?? 0}
          hint={
            k?.weeks_short.weeks
              ? `first ${dayMonth(k.weeks_short.first_week)}, worst ${fmtNum(k.weeks_short.worst_shortfall_pickers)} short`
              : data && data.crew_available > 0
                ? "the crew covers every week"
                : "set the crew available to compare"
          }
          tone={k?.weeks_short.weeks ? "critical" : data?.crew_available ? "good" : "default"}
        />
        <KpiCard
          loading={first}
          label="Picker days"
          value={k?.picker_days.total != null ? fmtNum(k.picker_days.total) : "—"}
          hint={`${k?.picker_days.days_per_week ?? days} days a week${canPay && k?.wage_bill_kes != null ? ` · wage bill ${kes(k.wage_bill_kes)}` : ""}`}
        />
        <KpiCard
          loading={first}
          label="Cannot staff yet"
          value={k ? fmtKgTonnes(k.cannot_staff.kg) : "—"}
          hint={k ? `${fmtNum(k.cannot_staff.blocks)} blocks with no pick date` : ""}
          tone={k?.cannot_staff.blocks ? "warning" : "default"}
        />
      </AccentScope>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Week by week</CardTitle>
            <CardDescription>Pickers needed against the crew you have. Click a bar to open that week.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="px-5 pb-6"><ChartSkeleton height={280} /></div>
        ) : data.weeks.length ? (
          <PickingChart weeks={data.weeks} crew={data.crew_available} selected={selected} onSelect={setWeek} accent={accent} />
        ) : (
          <p className="px-5 py-10 text-center text-[13px] text-[var(--sd-quiet)]">
            No picking weeks yet. A week needs a forecast and a dry matter reading that dates its pick.
          </p>
        )}
      </Card>

      {data && detail && (
        <Card className="mt-4 overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Week detail</CardTitle>
              <CardDescription>Rates and basis per block, and how many people the week is short or has spare.</CardDescription>
            </CardHeading>
            <CardTools>
              <FilterSelect label="Week" value={detail.week} onChange={setWeek} options={weekOptions} />
            </CardTools>
          </CardHeaderRow>
          <WeekDetail week={detail} canSeePay={canPay} />
        </Card>
      )}

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Picking rate</CardTitle>
              <CardDescription>Kilograms taken off divided by the pickers who took them. A property of the block, not of the picker. Nobody is ranked on it.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : <RatesTable rates={data.rates} />}
        </Card>
        <Card className="overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Cannot staff yet</CardTitle>
              <CardDescription>Fruit with no pick date, because the block has no dry matter sample. Sample these and they join the plan.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : <UnscheduledTable rows={data.unscheduled} />}
        </Card>
      </div>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Refused records</CardTitle>
            <CardDescription>Harvest records whose picker count cannot be one day's work. Left out of the rates rather than averaged in, because one bad row would set the crew for a whole season.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div> : <RejectedTable rows={data.rejected_records} />}
      </Card>
    </PageShell>
  );
}
