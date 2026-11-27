import { useEffect, useMemo, useState } from "react";
import { BarChart3, ChevronLeft, MapPinned, UserCog, UserPlus } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { Figure, FigureRow } from "@/components/Figure";
import { FilterSelect } from "@/components/FilterSelect";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ToolbarButton } from "@/components/ToolbarButton";
import { CompareDialog } from "@/components/people/CompareDialog";
import { KpiRadar, type RadarAxis } from "@/components/people/KpiRadar";
import { PersonList, type PersonListItem } from "@/components/people/PersonList";
import { PersonPortrait } from "@/components/people/PersonPortrait";
import { FlagsCard, MedianTable, PickPrompt, RecordSkeleton, ShareBars, WeekStrip, type MedianRow } from "@/components/people/RecordParts";
import { SupervisorDialog } from "@/components/supervisors/SupervisorDialog";
import { SupervisorForm } from "@/components/supervisors/SupervisorForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { firstLoad } from "@/components/Loading";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { fmt, lastFourWeeks } from "@/lib/people";
import { supervisorPeople, type SupervisorPeople, type SupervisorPerson } from "@/lib/people-api";
import { assistantsWithoutManager, type AssistantWithoutManager, type SupervisorDetail } from "@/lib/supervisors-api";
import { todayISO } from "@/lib/utils";
import { currentIsoWeek } from "@/lib/weeks";

const defaultRange = (): DateRange => lastFourWeeks();

const MEDIAN_ROWS: MedianRow[] = [
  { key: "assigned", label: "Tasks assigned" },
  { key: "on_time_pct", label: "Done on time", unit: "%", lowerIsBetter: false },
  { key: "late_pct", label: "Postponed or late", unit: "%", lowerIsBetter: true },
  { key: "logs_per_day", label: "Progress logs / active day", lowerIsBetter: false },
  { key: "sent_back_pct", label: "Labour sent back", unit: "%", lowerIsBetter: true },
  { key: "check_days", label: "Days to check labour", lowerIsBetter: true },
];

const SCORE_KEYS = ["on_time", "steady", "logging", "returns", "check_speed"] as const;

/** The radar is the five scores, each 0-100 and outward is better. */
function axesOf(p: SupervisorPerson): RadarAxis[] {
  const m = p.metrics;
  const v = (k: (typeof SCORE_KEYS)[number]) => (p.scores[k] == null ? null : (p.scores[k] as number) / 100);
  return [
    { key: "on_time", label: "On time", value: v("on_time"), readout: `${fmt(m.on_time_pct, "%")} done on time` },
    { key: "steady", label: "Not postponed", value: v("steady"), readout: `${fmt(m.late_pct, "%")} postponed or late` },
    { key: "logging", label: "Logging", value: v("logging"), readout: `${fmt(m.logs_per_day)} logs / active day` },
    { key: "returns", label: "Labour right", value: v("returns"), readout: m.sent_back == null ? "—" : `${m.sent_back} sent back` },
    { key: "check_speed", label: "Check speed", value: v("check_speed"), readout: m.check_days == null ? "—" : `${fmt(m.check_days)} days to check` },
  ];
}

/** Supervisors: a roster beside the picked supervisor's record, benchmarked against the farm median.
 *  Managers add and edit supervisors here (Add supervisor; Details and edit on the record). */
export function Supervisors() {
  const crop = useCurrentCrop();
  const canManage = !!(crop.boot.can_manage ?? crop.boot.can_plan);
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [status, setStatus] = useState("1");
  const [data, setData] = useState<SupervisorPeople | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [orphans, setOrphans] = useState<AssistantWithoutManager[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [comparing, setComparing] = useState(false);
  const [detail, setDetail] = useState<SupervisorPerson | null>(null);
  const [form, setForm] = useState<{ existing: SupervisorDetail["supervisor"] | null } | null>(null);
  const { from, to } = range;

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    void supervisorPeople(crop.name, from, to).then((r) => {
      if (!live) return;
      setLoading(false);
      if (isError(r)) setError(r.error);
      else setData(r);
    });
    return () => {
      live = false;
    };
  }, [crop.name, from, to, tick]);

  // Managers see which assistant managers have no manager: their work goes to every manager until it is set.
  useEffect(() => {
    if (!canManage) return;
    let live = true;
    void assistantsWithoutManager().then((r) => {
      if (live && !isError(r)) setOrphans(r);
    });
    return () => {
      live = false;
    };
  }, [canManage, tick]);

  const shown = useMemo(() => (data?.people ?? []).filter((p) => (status === "" ? true : String(p.active ? 1 : 0) === status)), [data, status]);
  const byId = useMemo(() => new Map(shown.map((p) => [p.employee, p])), [shown]);
  // Open on the first of the roster; keep the pick while it stays in the list.
  useEffect(() => {
    setSelectedId((cur) => (cur && byId.has(cur) ? cur : shown[0]?.employee ?? null));
  }, [byId, shown]);
  const selected = selectedId ? byId.get(selectedId) ?? null : null;
  const waiting = firstLoad(loading, !!data);
  const dirty = status !== "1" || from !== defaultRange().from || to !== defaultRange().to;
  const reload = () => setTick((t) => t + 1);

  const items: PersonListItem[] = shown.map((p) => ({
    id: p.employee,
    name: p.employee_name,
    image: p.image,
    inactive: !p.active,
    keywords: `${p.farm ?? ""} ${p.phone ?? ""}`,
    sub: [p.farm || crop.name, `${p.blocks} ${p.blocks === 1 ? "block" : "blocks"}${p.activities ? `, ${p.activities} ${p.activities === 1 ? "activity" : "activities"}` : ""}`, p.overseer ? "Overseer" : null, p.active ? null : "Inactive"]
      .filter(Boolean)
      .join(" · "),
    figure: p.metrics.on_time_pct == null ? undefined : `${fmt(p.metrics.on_time_pct)}%`,
    figureHint: p.metrics.on_time_pct == null ? undefined : "on time",
  }));

  const benchmark = SCORE_KEYS.map((k) => {
    const m = data?.medians[k];
    return m == null ? null : m / 100;
  });

  const actions = (
    <>
      <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
      <FilterSelect
        label="Status"
        value={status}
        onChange={setStatus}
        options={[
          { value: "1", label: "Active" },
          { value: "0", label: "Inactive" },
        ]}
        allLabel="All supervisors"
      />
      <ClearFiltersPill
        active={dirty}
        onClear={() => {
          setStatus("1");
          setRange(defaultRange());
        }}
      />
      {canManage && (
        <ToolbarButton onClick={() => setForm({ existing: null })}>
          <UserPlus className="h-4 w-4" strokeWidth={1.75} />
          Add supervisor
        </ToolbarButton>
      )}
      <RefreshButton onClick={reload} loading={loading} label="supervisors" />
    </>
  );

  const m = selected?.metrics;
  return (
    <PageShell
      title="Supervisors"
      eyebrow={crop.name}
      actions={actions}
      description="Each supervisor's tasks, logging and crew over the period, against the farm median."
    >
      {orphans.length > 0 && (
        <div role="status" data-testid="assistants-without-manager" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-warn)] px-4 py-3 text-[13px] text-[var(--sd-ink)]">
          <p className="font-medium">Assistant managers with no manager</p>
          <p className="mt-0.5 text-[var(--sd-muted)]">Set Reports To on their employee record so their work reaches a manager's team.</p>
          <ul className="mt-1.5 list-disc pl-5">
            {orphans.map((a) => (
              <li key={a.user}>{a.full_name}{a.employee ? ` (${a.employee})` : ""}</li>
            ))}
          </ul>
        </div>
      )}
      {error ? (
        <div className="flex flex-col items-start gap-3 text-[13px] text-[var(--sd-muted)]">
          {error}
          <ToolbarButton onClick={reload}>Try again</ToolbarButton>
        </div>
      ) : (
        <div className="relative grid min-w-0 gap-5 xl:grid-cols-[minmax(0,300px)_minmax(0,1fr)]" aria-busy={waiting || undefined}>
          <aside className={selected ? "hidden min-w-0 xl:sticky xl:top-6 xl:block xl:self-start" : "min-w-0 xl:sticky xl:top-6 xl:self-start"}>
            <Card>
              <CardContent className="p-4">
                <PersonList items={items} selectedId={selected?.employee ?? null} onSelect={setSelectedId} label="Find a supervisor" noun="supervisors" loading={waiting} />
                {!waiting && !items.length && (
                  <p className="mt-2 text-[12.5px] text-[var(--sd-muted)]">
                    {data?.people.length ? "No supervisors match these filters." : "No supervisors yet. Use Add supervisor to choose them from the Employee list."}
                  </p>
                )}
              </CardContent>
            </Card>
          </aside>

          {selected && m && data ? (
            <div className="flex min-w-0 flex-col gap-5" data-testid="supervisor-record">
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="flex items-center gap-1.5 self-start text-[12.5px] font-medium text-[var(--sd-muted)] hover:text-[var(--sd-ink)] xl:hidden"
              >
                <ChevronLeft className="h-4 w-4" />
                All supervisors
              </button>
              <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,280px)]">
                <div className="flex min-w-0 flex-col gap-5">
                  <FigureRow>
                    <Figure label="Tasks assigned" value={fmt(m.assigned)} hint={`${fmt(m.done)} done`} />
                    <Figure label="Done on time" value={fmt(m.on_time_pct, "%")} hint="of tasks due so far" />
                    <Figure label="Postponed or late" value={fmt(m.late_pct, "%")} hint="of tasks assigned" />
                  </FigureRow>
                  <FigureRow>
                    <Figure label="Logs / active day" value={fmt(m.logs_per_day)} hint={`${fmt(m.logs)} logs on ${fmt(m.active_days)} days`} />
                    <Figure label="Labour sent back" value={m.sent_back == null ? "—" : fmt(m.sent_back)} hint={m.sent_back_pct == null ? "crew figures are private" : `${fmt(m.sent_back_pct, "%")} of ${fmt(m.entries)} entries`} />
                    <Figure label="Days to check" value={fmt(m.check_days)} hint="labour recorded to Checked" />
                  </FigureRow>
                  <div className="-mt-2 flex flex-wrap items-center gap-3">
                    <Button variant="outline" size="sm" disabled={shown.length < 2} onClick={() => setComparing(true)}>
                      <BarChart3 className="mr-1.5 h-3.5 w-3.5" />
                      Compare
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setDetail(selected)}>
                      <UserCog className="mr-1.5 h-3.5 w-3.5" />
                      {data.can_manage ? "Details and edit" : "Details"}
                    </Button>
                  </div>

                  <MedianTable
                    rows={MEDIAN_ROWS}
                    mine={m}
                    medians={data.medians}
                    name={selected.employee_name}
                    description={`Median of the ${shown.filter((p) => p.active && p.metrics.assigned).length} active supervisors with tasks in the period.`}
                  />
                  <FlagsCard flags={selected.flags} description="Overdue work, labour waiting on their check, open tasks with no progress." />
                  <ShareBars title="Where they worked" description="Share of their tasks by block." rows={selected.where} icon={MapPinned} empty="No tasks in this period." />
                  <WeekStrip
                    weeks={data.weeks}
                    description="Tasks done and progress logs per week."
                    series={[
                      { key: "done", label: "Tasks done", values: selected.weekly.map((w) => w.done), color: "var(--sd-data-green)" },
                      { key: "logs", label: "Progress logs", values: selected.weekly.map((w) => w.logs), color: "var(--sd-data-indigo)" },
                    ]}
                  />
                </div>

                <div className="flex min-w-0 flex-col gap-5 lg:sticky lg:top-6 lg:self-start">
                  <PersonPortrait
                    id={selected.employee}
                    name={selected.employee_name}
                    image={selected.image}
                    pill={selected.overseer ? "Overseer" : selected.active ? undefined : "Inactive"}
                    facts={[
                      { label: "Farm", value: selected.farm || "—" },
                      { label: "Phone", value: selected.phone || "—" },
                      { label: "This week", value: `${selected.blocks} ${selected.blocks === 1 ? "block" : "blocks"}` },
                      { label: "Crew", value: String(selected.crew) },
                    ]}
                  />
                  <Card>
                    <CardHeader className="pb-0">
                      <CardTitle className="text-[14px]">Score parts</CardTitle>
                      <CardDescription>Outward is better on every axis.</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <KpiRadar axes={axesOf(selected)} benchmark={benchmark} label="Score parts" />
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          ) : waiting ? (
            <RecordSkeleton />
          ) : (
            <PickPrompt label={shown.length ? "Pick a supervisor" : "No supervisors to show"} />
          )}
        </div>
      )}

      {selected && data && (
        <CompareDialog
          open={comparing}
          onOpenChange={setComparing}
          subject={{ id: selected.employee, name: selected.employee_name, image: selected.image, sub: selected.farm || "" }}
          pool={shown.map((p) => ({ id: p.employee, name: p.employee_name, image: p.image, sub: p.farm || "" }))}
          axesFor={(id) => axesOf(byId.get(id)!)}
          benchmark={benchmark}
          benchmarkReadouts={benchmark.map((x) => (x == null ? "—" : fmt(x * 100)))}
          benchmarkLabel="Farm median"
        />
      )}
      {detail && (
        <SupervisorDialog
          employee={detail.employee}
          name={detail.employee_name}
          crop={crop.name}
          year={currentIsoWeek().year}
          week={currentIsoWeek().week}
          reloadKey={tick}
          onClose={() => setDetail(null)}
          onEdit={(d) => setForm({ existing: d.supervisor })}
        />
      )}
      {canManage && (
        <SupervisorForm
          open={!!form}
          onOpenChange={(o) => !o && setForm(null)}
          existing={form?.existing ?? null}
          crops={crop.boot.crops.map((c) => c.name)}
          farms={crop.boot.farms}
          onSaved={reload}
        />
      )}
    </PageShell>
  );
}
