import { useEffect, useMemo, useState } from "react";
import { BarChart3, ChevronLeft, Download, Layers, MapPinned, Settings2, UserPlus } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { Figure, FigureRow } from "@/components/Figure";
import { FilterSelect } from "@/components/FilterSelect";
import { firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ToolbarButton } from "@/components/ToolbarButton";
import { AddLabourersDialog } from "@/components/casuallabourers/AddLabourersDialog";
import { LabourerDialog } from "@/components/casuallabourers/LabourerDialog";
import { CompareDialog } from "@/components/people/CompareDialog";
import { KpiRadar, type RadarAxis } from "@/components/people/KpiRadar";
import { PersonList, type PersonListItem } from "@/components/people/PersonList";
import { PersonPortrait } from "@/components/people/PersonPortrait";
import { FlagsCard, MedianTable, PickPrompt, RecordSkeleton, ShareBars, WeekStrip, type MedianRow } from "@/components/people/RecordParts";
import { rowDate } from "@/components/plan/fmt";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { fmt, lastFourWeeks } from "@/lib/people";
import { labourerPeople, type LabourerPeople, type LabourerPerson } from "@/lib/people-api";
import { todayISO } from "@/lib/utils";

const defaultRange = (): DateRange => lastFourWeeks();

const MEDIAN_ROWS: MedianRow[] = [
  { key: "days_worked", label: "Days worked", lowerIsBetter: false },
  { key: "tasks", label: "Tasks worked on" },
  { key: "output_vs_peers", label: "Output against peers on the same activity", unit: "%", lowerIsBetter: false },
  { key: "sent_back_pct", label: "Work sent back", unit: "%", lowerIsBetter: true },
  { key: "attendance_pct", label: "Working days worked", unit: "%", lowerIsBetter: false },
];

const SCORE_KEYS = ["attendance", "output", "quality"] as const;

function csvCell(v: unknown): string {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** The radar is three scores, each 0-100 and outward is better. */
function axesOf(p: LabourerPerson): RadarAxis[] {
  const m = p.metrics;
  const v = (k: (typeof SCORE_KEYS)[number]) => (p.scores[k] == null ? null : (p.scores[k] as number) / 100);
  return [
    { key: "attendance", label: "Attendance", value: v("attendance"), readout: `${fmt(m.days_worked)} days, ${fmt(m.attendance_pct, "%")} of working days` },
    { key: "output", label: "Output", value: v("output"), readout: m.output_vs_peers == null ? "—" : `${fmt(m.output_vs_peers, "%")} of peers on the same work` },
    { key: "quality", label: "Right first time", value: v("quality"), readout: m.sent_back_pct == null ? "—" : `${fmt(m.sent_back_pct, "%")} sent back` },
  ];
}

/** Casual labour: a roster beside the picked person's record, benchmarked against the farm median. Add labourers,
 *  and Manage (targets, supervisor, crew, active, remove) from the record. No pay is shown here. */
export function CasualLabourers() {
  const crop = useCurrentCrop();
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [status, setStatus] = useState("1");
  const [supervisor, setSupervisor] = useState("");
  const [data, setData] = useState<LabourerPeople | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [comparing, setComparing] = useState(false);
  const [managing, setManaging] = useState<LabourerPerson | null>(null);
  const [adding, setAdding] = useState(false);
  const { from, to } = range;

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    void labourerPeople(crop.name, from, to).then((r) => {
      if (!live) return;
      setLoading(false);
      if (isError(r)) setError(r.error);
      else setData(r);
    });
    return () => {
      live = false;
    };
  }, [crop.name, from, to, tick]);

  const shown = useMemo(
    () =>
      (data?.people ?? [])
        .filter((p) => (status === "" ? true : String(p.active ? 1 : 0) === status))
        .filter((p) => !supervisor || p.supervisor === supervisor),
    [data, status, supervisor],
  );
  const byId = useMemo(() => new Map(shown.map((p) => [p.employee, p])), [shown]);
  // One entry per supervisor id on the roster; two people with one name stay apart.
  const supervisors = useMemo(() => {
    const byKey = new Map<string, string>();
    for (const p of data?.people ?? []) if (p.supervisor) byKey.set(p.supervisor, p.supervisor_name || p.supervisor);
    const names = [...byKey.values()];
    return [...byKey]
      .map(([value, name]) => ({ value, label: names.filter((n) => n === name).length > 1 ? `${name} (${value})` : name }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [data]);
  useEffect(() => {
    setSelectedId((cur) => (cur && byId.has(cur) ? cur : shown[0]?.employee ?? null));
  }, [byId, shown]);
  const selected = selectedId ? byId.get(selectedId) ?? null : null;
  const waiting = firstLoad(loading, !!data);
  const dirty = status !== "1" || !!supervisor || from !== defaultRange().from || to !== defaultRange().to;
  const reload = () => setTick((t) => t + 1);

  const items: PersonListItem[] = shown.map((p) => ({
    id: p.employee,
    name: p.employee_name,
    image: p.image,
    inactive: !p.active,
    keywords: `${p.crew ?? ""} ${p.supervisor_name ?? ""}`,
    sub: [p.supervisor_name || "No supervisor", p.last_worked ? `last worked ${rowDate(p.last_worked)}` : "not worked yet", p.active ? null : "Inactive"].filter(Boolean).join(" · "),
    figure: fmt(p.metrics.days_worked),
    figureHint: "days",
  }));
  const benchmark = SCORE_KEYS.map((k) => {
    const m = data?.medians[k];
    return m == null ? null : m / 100;
  });

  function exportCsv() {
    const head = ["Labourer", "Employee", "Active", "Crew", "Supervisor", "Last worked", "Days worked", "Tasks", "Output per day", "Unit", "Output against peers %", "Sent back %"];
    const lines = [
      head,
      ...shown.map((p) => [
        p.employee_name, p.employee, p.active ? "Yes" : "No", p.crew ?? "", p.supervisor_name ?? "", p.last_worked ?? "",
        p.metrics.days_worked ?? "", p.metrics.tasks ?? "", p.metrics.output_per_day ?? "", p.output_uom ?? "", p.metrics.output_vs_peers ?? "", p.metrics.sent_back_pct ?? "",
      ]),
    ];
    const blob = new Blob([lines.map((l) => l.map(csvCell).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `casual-labourers-${from}-to-${to}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

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
        allLabel="All labourers"
      />
      {supervisors.length > 0 && <FilterSelect label="Supervisor" value={supervisor} onChange={setSupervisor} options={supervisors} allLabel="All supervisors" />}
      <ClearFiltersPill
        active={dirty}
        onClear={() => {
          setStatus("1");
          setSupervisor("");
          setRange(defaultRange());
        }}
      />
      <ToolbarButton onClick={() => setAdding(true)}>
        <UserPlus className="h-4 w-4" strokeWidth={1.75} />
        Add labourers
      </ToolbarButton>
      <ToolbarButton onClick={exportCsv} disabled={!shown.length}>
        <Download className="h-4 w-4" strokeWidth={1.75} />
        Export CSV
      </ToolbarButton>
      <RefreshButton onClick={reload} loading={loading} label="casual labourers" />
    </>
  );

  const m = selected?.metrics;
  const uom = selected?.output_uom ?? "";
  return (
    <PageShell
      title="Casual Labourers"
      eyebrow={crop.name}
      actions={actions}
      description="Each casual labourer's days, output and returns over the period, against the farm median."
    >
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
                <PersonList items={items} selectedId={selected?.employee ?? null} onSelect={setSelectedId} label="Find a labourer" noun="labourers" loading={waiting} />
                {!waiting && !items.length && (
                  <p className="mt-2 text-[12.5px] text-[var(--sd-muted)]">
                    {data?.people.length ? "No labourers match these filters." : "No casual labourers on the roster yet. Use Add labourers to choose them from the Employee list."}
                  </p>
                )}
              </CardContent>
            </Card>
          </aside>

          {selected && m && data ? (
            <div className="flex min-w-0 flex-col gap-5" data-testid="labourer-record">
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="flex items-center gap-1.5 self-start text-[12.5px] font-medium text-[var(--sd-muted)] hover:text-[var(--sd-ink)] xl:hidden"
              >
                <ChevronLeft className="h-4 w-4" />
                All labourers
              </button>
              <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,280px)]">
                <div className="flex min-w-0 flex-col gap-5">
                  <FigureRow>
                    <Figure label="Days worked" value={fmt(m.days_worked)} hint={`of ${data.workdays} working days`} />
                    <Figure label="Tasks" value={fmt(m.tasks)} hint="tasks worked on" />
                    <Figure label="Output / day" value={fmt(m.output_per_day)} unit={uom || undefined} hint={m.output_vs_peers == null ? "no peers on the same work" : `${fmt(m.output_vs_peers, "%")} of peers`} />
                    <Figure label="Sent back" value={fmt(m.sent_back_pct, "%")} hint={`${fmt(m.sent_back)} of ${fmt(m.entries)} entries`} />
                  </FigureRow>
                  <div className="-mt-2 flex flex-wrap items-center gap-3">
                    <Button variant="outline" size="sm" disabled={shown.length < 2} onClick={() => setComparing(true)}>
                      <BarChart3 className="mr-1.5 h-3.5 w-3.5" />
                      Compare
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setManaging(selected)}>
                      <Settings2 className="mr-1.5 h-3.5 w-3.5" />
                      Manage
                    </Button>
                  </div>

                  <MedianTable
                    rows={MEDIAN_ROWS}
                    mine={m}
                    medians={data.medians}
                    name={selected.employee_name}
                    description={`Median of the ${shown.filter((p) => p.active && p.metrics.days_worked).length} active labourers who worked in the period.`}
                  />
                  <FlagsCard flags={selected.flags} description="Sent-back work not yet corrected, and long absences." />
                  <ShareBars title="Where they worked" description="Share of their entries by block." rows={selected.where_blocks} icon={MapPinned} empty="No work in this period." />
                  <ShareBars title="What they did" description="Share of their entries by activity." rows={selected.where_activities} icon={Layers} empty="No work in this period." />
                  <WeekStrip
                    weeks={data.weeks}
                    description="Days worked and output per week."
                    series={[
                      { key: "days", label: "Days worked", values: selected.weekly.map((w) => w.days), color: "var(--sd-data-green)" },
                      { key: "output", label: uom ? `Output (${uom})` : "Output", values: selected.weekly.map((w) => w.output), color: "var(--sd-data-indigo)" },
                    ]}
                  />
                </div>

                <div className="flex min-w-0 flex-col gap-5 lg:sticky lg:top-6 lg:self-start">
                  <PersonPortrait
                    id={selected.employee}
                    name={selected.employee_name}
                    image={selected.image}
                    pill={selected.active ? undefined : "Inactive"}
                    facts={[
                      { label: "Supervisor", value: selected.supervisor_name || "—" },
                      { label: "Crew", value: selected.crew || "—" },
                      { label: "Last worked", value: selected.last_worked ? rowDate(selected.last_worked) : "—" },
                      { label: "Entries", value: fmt(m.entries) },
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
            <PickPrompt label={shown.length ? "Pick a labourer" : "No labourers to show"} />
          )}
        </div>
      )}

      {selected && data && (
        <CompareDialog
          open={comparing}
          onOpenChange={setComparing}
          subject={{ id: selected.employee, name: selected.employee_name, image: selected.image, sub: selected.supervisor_name || "" }}
          pool={shown.map((p) => ({ id: p.employee, name: p.employee_name, image: p.image, sub: p.supervisor_name || "" }))}
          axesFor={(id) => axesOf(byId.get(id)!)}
          benchmark={benchmark}
          benchmarkReadouts={benchmark.map((x) => (x == null ? "—" : fmt(x * 100)))}
          benchmarkLabel="Farm median"
        />
      )}
      {managing && (
        <LabourerDialog
          crop={crop.name}
          employee={managing.employee}
          name={managing.employee_name}
          from={from}
          to={to}
          canPay={false}
          accent={crop.accent_color || "#3f7d3a"}
          onClose={() => setManaging(null)}
          onChanged={reload}
        />
      )}
      <AddLabourersDialog open={adding} onOpenChange={setAdding} onAdded={reload} />
    </PageShell>
  );
}
