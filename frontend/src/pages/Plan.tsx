import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ListPlus, Wand2 } from "lucide-react";
import { Figure, FigureRow } from "@/components/Figure";
import { FilterSelect } from "@/components/FilterSelect";
import { RowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { WeekPicker } from "@/components/WeekPicker";
import { AddTaskDialog, type OperationOption } from "@/components/plan/AddTaskDialog";
import { AvatarStack, DeviationBadge, StatusPill } from "@/components/plan/badges";
import { addDays, money, q, rowDate } from "@/components/plan/fmt";
import { TickOffDialog } from "@/components/plan/TickOffDialog";
import {
  generatePlanWeek,
  getPlan,
  listOperations,
  listUnits,
  listValueAdders,
  type Plan as PlanData,
  type PlanTask,
  type UnitRow,
  type ValueAdder,
} from "@/lib/api";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { currentIsoWeek, weekStart, type IsoWeek } from "@/lib/weeks";
import { cn, ymd } from "@/lib/utils";

const CARD = "rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)]";

/** The week's work, by unit, with a tick-off for each task. */
export function Plan() {
  const crop = useCurrentCrop();
  const { boot } = crop;
  const toast = useToast();
  const [week, setWeek] = useState<IsoWeek>(currentIsoWeek);
  const [farm, setFarm] = useState(boot.farms[0] ?? "");
  const [plan, setPlan] = useState<PlanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [ops, setOps] = useState<OperationOption[]>([]);
  const [people, setPeople] = useState<ValueAdder[]>([]);
  const [generating, setGenerating] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const seq = useRef(0);

  const load = useCallback(
    async (quiet = false) => {
      if (!farm) {
        setLoading(false);
        return;
      }
      const mine = ++seq.current;
      if (!quiet) {
        setLoading(true);
        setError(null);
      }
      const r = await getPlan(crop.name, farm, week.year, week.week);
      if (mine !== seq.current) return; // a newer week/farm was asked for
      if (isError(r)) {
        if (!quiet) setError(r.error);
      } else {
        setPlan(r);
        setError(null);
      }
      setLoading(false);
    },
    [crop.name, farm, week.year, week.week],
  );

  useEffect(() => {
    void load();
  }, [load]);

  // Lookups for the dialogs; the page does not wait on them.
  useEffect(() => {
    let live = true;
    void listUnits(crop.name).then((r) => live && !isError(r) && setUnits(r.units));
    void listOperations(crop.name).then(
      (r) => live && !isError(r) && setOps(r.rows as unknown as OperationOption[]),
    );
    void listValueAdders().then((r) => live && !isError(r) && setPeople(r.people));
    return () => {
      live = false;
    };
  }, [crop.name]);

  const tasks = useMemo(() => plan?.tasks ?? [], [plan]);
  const unitByName = useMemo(() => new Map(units.map((u) => [u.name, u])), [units]);

  const groups = useMemo(() => {
    const m = new Map<string, PlanTask[]>();
    for (const t of tasks) {
      const list = m.get(t.unit);
      if (list) list.push(t);
      else m.set(t.unit, [t]);
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));
  }, [tasks]);

  const stats = useMemo(() => {
    const done = tasks.filter((t) => t.status === "Done").length;
    const labour = tasks.reduce((s, t) => s + t.work.reduce((x, w) => x + (w.pay_value ?? 0), 0), 0);
    return {
      total: tasks.length,
      done,
      pct: tasks.length ? Math.round((done / tasks.length) * 100) : 0,
      deviations: tasks.filter((t) => t.deviation).length,
      labour,
    };
  }, [tasks]);

  const supervisors = useMemo(() => {
    const m = new Map<string, string>();
    for (const t of tasks) if (t.supervisor) m.set(t.supervisor, t.supervisor_name || t.supervisor);
    return [...m].map(([value, label]) => ({ value, label }));
  }, [tasks]);

  async function generate() {
    setGenerating(true);
    const r = await generatePlanWeek(crop.name, farm, week.year, week.week);
    setGenerating(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(
      r.created ? `${r.created} task${r.created === 1 ? "" : "s"} added` : "No new tasks: the protocols are already planned",
      r.created ? "ok" : "info",
    );
    void load(true);
  }

  // The returned task replaces its row at once; the quiet refetch then brings
  // the per-row work entries (the save returns only their names).
  function applySaved(task: PlanTask) {
    setPlan((p) =>
      p
        ? { ...p, tasks: p.tasks.map((t) => (t.name === task.name ? { ...t, ...task, work: task.work ?? t.work } : t)) }
        : p,
    );
    toast(`${task.operation_name} saved`);
    setPicked(null);
    void load(true);
  }

  const selected = tasks.find((t) => t.name === picked) ?? null;
  const unitLabel = crop.unit_label || "Unit";
  const weekLabel = `W${String(week.week).padStart(2, "0")} ${week.year}`;
  const farmOptions = boot.farms.map((f) => ({ value: f, label: f }));

  const actions = (
    <>
      <WeekPicker value={week} onChange={setWeek} />
      <FilterSelect value={farm} options={farmOptions} onChange={setFarm} placeholder="Farm" aria-label="Farm" />
      {boot.can_plan && (
        <>
          <Button variant="outline" onClick={generate} disabled={generating || !farm}>
            <Wand2 className="h-4 w-4" strokeWidth={1.75} />
            {generating ? "Generating…" : "Generate from protocols"}
          </Button>
          <Button onClick={() => setAdding(true)} disabled={!farm}>
            <ListPlus className="h-4 w-4" strokeWidth={1.75} />
            Add task
          </Button>
        </>
      )}
    </>
  );

  let body: React.ReactNode;
  if (!farm) {
    body = <Empty title="No farm to plan for">Add a farm to this crop's settings and it will appear here.</Empty>;
  } else if (loading) {
    body = (
      <div className={cn(CARD, "px-4 py-4")}>
        <RowsSkeleton rows={6} />
      </div>
    );
  } else if (error) {
    body = (
      <Empty title="Could not load the plan">
        {error}
        <Button variant="outline" onClick={() => void load()}>
          Try again
        </Button>
      </Empty>
    );
  } else if (!tasks.length) {
    body = (
      <Empty title={`Nothing planned for ${weekLabel}`}>
        {boot.can_plan
          ? "Generate the week from the crop's protocols, or add a task by hand."
          : "No tasks have been planned for this week yet."}
        {boot.can_plan && (
          <Button onClick={generate} disabled={generating}>
            <Wand2 className="h-4 w-4" strokeWidth={1.75} />
            {generating ? "Generating…" : "Generate from protocols"}
          </Button>
        )}
      </Empty>
    );
  } else {
    body = (
      <div className="flex flex-col gap-4">
        {groups.map(([unit, list]) => {
          const u = unitByName.get(unit);
          const done = list.filter((t) => t.status === "Done").length;
          return (
            <section key={unit} className={CARD} aria-label={unit}>
              <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 pb-2 pt-3.5">
                <h2 className="text-[15px] font-semibold tracking-tight text-[var(--sd-ink)]">{unit}</h2>
                <span className="min-w-0 flex-1 truncate text-[12.5px] text-[var(--sd-muted)]">
                  {[u ? `${q(u.area_ha)} ha` : null, u?.item].filter(Boolean).join(" · ")}
                </span>
                <span className="text-[12.5px] tabular-nums text-[var(--sd-muted)]">
                  {done}/{list.length} done
                </span>
              </header>
              <ul className="divide-y divide-[var(--sd-line-soft)] px-1.5 pb-1.5">
                {list.map((t) => (
                  <li key={t.name ?? `${t.operation}-${t.due_date}`}>
                    <button
                      type="button"
                      onClick={() => setPicked(t.name ?? null)}
                      className="flex w-full flex-wrap items-center gap-x-3 gap-y-1.5 rounded-[var(--sd-radius)] px-2.5 py-2.5 text-left transition-colors hover:bg-[var(--sd-bg-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                    >
                      <span className="min-w-[10rem] flex-1 truncate text-[13.5px] font-medium text-[var(--sd-ink)]">
                        {t.operation_name}
                      </span>
                      <span className="text-[13px] tabular-nums text-[var(--sd-muted)]">
                        {q(t.planned_qty)} → <span className="text-[var(--sd-ink)]">{q(t.done_qty)}</span> {t.uom}
                      </span>
                      <span className="w-24 text-[12.5px] tabular-nums text-[var(--sd-muted)]">{rowDate(t.due_date)}</span>
                      <StatusPill status={t.status} />
                      <DeviationBadge deviation={t.deviation} />
                      <span className="ml-auto">
                        <AvatarStack names={t.work.map((w) => w.employee_name || w.employee)} />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    );
  }

  const showSummary = !!farm && !loading && !error && tasks.length > 0;

  return (
    <PageShell
      title="Weekly Plan"
      eyebrow={crop.name}
      actions={actions}
      description={`${rowDate(plan?.week_start ?? ymd(weekStart(week)))} to ${rowDate(
        plan?.week_end ?? ymd(addDays(weekStart(week), 6)),
      )}. Tap a task to record the work.`}
    >
      {showSummary && (
        <FigureRow>
          <Figure label="Tasks" value={String(stats.total)} hint={`${stats.done} done`} />
          <Figure label="Done" value={`${stats.pct}%`} />
          <Figure label="Deviations" value={String(stats.deviations)} />
          {boot.can_see_pay && <Figure label="Labour" value={money(stats.labour)} hint="KES" />}
        </FigureRow>
      )}
      {body}
      {selected && plan?.plan && (
        <TickOffDialog
          key={selected.name}
          plan={plan.plan}
          task={selected}
          people={people}
          canSeePay={boot.can_see_pay}
          onClose={() => setPicked(null)}
          onSaved={applySaved}
        />
      )}
      {adding && (
        <AddTaskDialog
          crop={crop.name}
          farm={farm}
          year={week.year}
          week={week.week}
          weekStart={weekStart(week)}
          unitLabel={unitLabel}
          units={units}
          operations={ops}
          supervisors={supervisors}
          onClose={() => setAdding(false)}
          onAdded={() => {
            setAdding(false);
            toast("Task added");
            void load(true);
          }}
        />
      )}
    </PageShell>
  );
}

function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className={cn(CARD, "flex flex-col items-start gap-3 px-5 py-6 text-[13px] text-[var(--sd-muted)]")}>
      <h2 className="text-[16px] font-semibold text-[var(--sd-ink)]">{title}</h2>
      {children}
    </div>
  );
}
