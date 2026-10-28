import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ListPlus, Wand2 } from "lucide-react";
import { ActivityDot } from "@/components/ActivityDot";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { FilterSelect } from "@/components/FilterSelect";
import { RowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { useToast } from "@/components/Toast";
import { ToolbarButton } from "@/components/ToolbarButton";
import { Button } from "@/components/ui/button";
import { WeekPicker } from "@/components/WeekPicker";
import { AddTaskDialog, type OperationOption } from "@/components/plan/AddTaskDialog";
import { AvatarStack, DeviationBadge, STATUSES, StatusPill } from "@/components/plan/badges";
import { PendingChip, QtyBar } from "@/components/plan/QtyBar";
import { addDays, q, rowDate } from "@/components/plan/fmt";
import { RuleFlag } from "@/components/rules/RuleParts";
import { ProtocolCheckPanel } from "@/components/plan/ProtocolCheckPanel";
import { TickOffDialog } from "@/components/plan/TickOffDialog";
import {
  generatePlanWeek,
  getPlan,
  listOperations,
  listUnits,
  listValueAdders,
  type Plan as PlanData,
  type SkippedStep,
  type PlanTask,
  type UnitRow,
  type ValueAdder,
} from "@/lib/api";
import { protocolCheck, type ProtocolCheck } from "@/lib/varieties-api";
import { cropUsesCycles, useCurrentCrop } from "@/lib/crops";
import { formatUoms, kes, sumByUom } from "@/lib/format";
import { isError } from "@/lib/frappe";
import { currentIsoWeek, weekStart, type IsoWeek } from "@/lib/weeks";
import { cn, ymd } from "@/lib/utils";

const NOT_DONE = ["Open", "In Progress", "Partly Done"];
const CARD = "rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)]";

/** The week's work, by unit, with a tick-off for each task. */
export function Plan() {
  const crop = useCurrentCrop();
  const { boot } = crop;
  const accent = crop.accent_color || "#3f7d3a";
  const toast = useToast();
  const [week, setWeek] = useState<IsoWeek>(currentIsoWeek);
  const [farm, setFarm] = useState(boot.farms[0] ?? "");
  const [opFilter, setOpFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [plan, setPlan] = useState<PlanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [ops, setOps] = useState<OperationOption[]>([]);
  const [people, setPeople] = useState<ValueAdder[]>([]);
  const [generating, setGenerating] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [check, setCheck] = useState<ProtocolCheck | null>(null);
  const [skipped, setSkipped] = useState<SkippedStep[]>([]);
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
    setSkipped([]);
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

  const usesCycles = cropUsesCycles(crop);
  // Protocol steps due this week that an activity rule would stop; a failure just hides the panel.
  useEffect(() => {
    let live = true;
    setCheck(null);
    if (usesCycles) {
      void (async () => {
        try {
          const r = await protocolCheck(crop.name, week.year, week.week);
          if (live && !isError(r)) setCheck(r);
        } catch {
          /* no panel */
        }
      })();
    }
    return () => {
      live = false;
    };
  }, [crop.name, usesCycles, week.year, week.week, plan]);

  const allTasks = useMemo(() => plan?.tasks ?? [], [plan]);
  const tasks = useMemo(
    () =>
      allTasks.filter(
        (t) =>
          (!opFilter || t.operation_name === opFilter) &&
          (!statusFilter || (statusFilter === "Awaiting approval" ? (t.pending_qty ?? 0) > 0 : t.status === statusFilter)),
      ),
    [allTasks, opFilter, statusFilter],
  );
  const opOptions = useMemo(() => [...new Set(allTasks.map((t) => t.operation_name))].sort(), [allTasks]);
  const hasPending = allTasks.some((t) => (t.pending_qty ?? 0) > 0);
  const statusOptions = hasPending ? [...STATUSES, "Awaiting approval"] : [...STATUSES];
  const dirty = !!opFilter || !!statusFilter;
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
    // Quantities live in each task's own UOM (Hectare, Tree, Crate...): total them per UOM, never across.
    return {
      planned: sumByUom(tasks, (t) => ({ uom: t.uom, qty: t.planned_qty })),
      doneQty: sumByUom(tasks, (t) => ({ uom: t.uom, qty: t.done_qty })),
      pendingQty: sumByUom(tasks, (t) => ({ uom: t.uom, qty: t.pending_qty })),
      pendingTasks: tasks.filter((t) => (t.pending_qty ?? 0) > 0).length,
      overdue: tasks.filter((t) => NOT_DONE.includes(t.status) && t.due_date < ymd(new Date())).length,
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
    setSkipped(r.skipped ?? []);
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
      <FilterSelect label="Farm" value={farm} options={farmOptions} onChange={setFarm} />
      <FilterSelect label="Operation" value={opFilter} options={opOptions} onChange={setOpFilter} allLabel="All operations" />
      <FilterSelect label="Status" value={statusFilter} options={statusOptions} onChange={setStatusFilter} allLabel="All statuses" />
      <ClearFiltersPill
        active={dirty}
        onClear={() => {
          setOpFilter("");
          setStatusFilter("");
        }}
      />
      {boot.can_plan && (
        <>
          {cropUsesCycles(crop) && (
            <ToolbarButton onClick={generate} disabled={generating || !farm}>
              <Wand2 className="h-4 w-4" strokeWidth={1.75} />
              {generating ? "Generating…" : "Generate from protocols"}
            </ToolbarButton>
          )}
          <ToolbarButton onClick={() => setAdding(true)} disabled={!farm}>
            <ListPlus className="h-4 w-4" strokeWidth={1.75} />
            Add task
          </ToolbarButton>
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
  } else if (allTasks.length && !tasks.length) {
    body = (
      <Empty title="No tasks match these filters">
        <Button variant="outline" onClick={() => { setOpFilter(""); setStatusFilter(""); }}>
          Clear filters
        </Button>
      </Empty>
    );
  } else if (!tasks.length) {
    body = (
      <Empty title={`Nothing planned for ${weekLabel}`}>
        {boot.can_plan
          ? cropUsesCycles(crop)
            ? "Generate the week from the crop's protocols, or add a task by hand."
            : "Add a task by hand."
          : "No tasks have been planned for this week yet."}
        {boot.can_plan && cropUsesCycles(crop) && (
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
                <span className="w-24">
                  {/* Tasks, not quantities: a unit's tasks are in different UOMs. */}
                  <QtyBar
                    planned={list.length}
                    done={done}
                    pending={list.filter((t) => t.status !== "Done" && (t.pending_qty ?? 0) > 0).length}
                    color={accent}
                  />
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
                        <ActivityDot color={t.color} label={t.operation_name} />
                        {t.operation_name}
                      </span>
                      <span className="flex w-44 flex-col gap-1">
                        <span className="text-[13px] tabular-nums text-[var(--sd-muted)]">
                          <span className="text-[var(--sd-ink)]">{q(t.done_qty)}</span>
                          {(t.pending_qty ?? 0) > 0 && <span className="text-[var(--sd-amber)]"> +{q(t.pending_qty)}</span>} / {q(t.planned_qty)} {t.uom}
                        </span>
                        <QtyBar planned={t.planned_qty} done={t.done_qty} pending={t.pending_qty ?? 0} color={accent} className="h-1.5" />
                      </span>
                      <span className="w-24 text-[12.5px] tabular-nums text-[var(--sd-muted)]">{rowDate(t.due_date)}</span>
                      <StatusPill status={t.status} />
                      <DeviationBadge deviation={t.deviation} />
                      <RuleFlag status={t.rule_status} notes={t.rule_notes} overrideReason={t.override_reason} />
                      {(t.pending_qty ?? 0) > 0 && <PendingChip>Awaiting approval</PendingChip>}
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

  const opLabel = (name: string) => ops.find((o) => o.name === name)?.operation_name || name;
  const skippedPanel = skipped.length > 0 && (
    <div role="status" data-testid="skipped-steps" className="mb-4 rounded-[var(--sd-radius-lg)] bg-[var(--sd-alert-error)] px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-[13.5px] font-semibold text-[var(--sd-ink)]">
          {skipped.length} protocol step{skipped.length === 1 ? "" : "s"} not planned: an activity rule blocks {skipped.length === 1 ? "it" : "them"}
        </h2>
        <button type="button" className="text-[12px] text-[var(--sd-muted)] underline" onClick={() => setSkipped([])}>
          Dismiss
        </button>
      </div>
      <ul className="flex flex-col gap-1">
        {skipped.map((s) => (
          <li key={s.protocol_ref} className="text-[13px] text-[var(--sd-ink)]">
            <span className="font-medium">{s.unit}</span> · {opLabel(s.operation)} · due {rowDate(s.due_date)}
            <span className="block text-[12.5px] text-[var(--sd-muted)]">{s.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );

  const showSummary = !!farm && !error && (loading ? false : allTasks.length > 0);

  return (
    <PageShell
      title="Weekly Plan"
      eyebrow={crop.name}
      actions={actions}
      description={`${rowDate(plan?.week_start ?? ymd(weekStart(week)))} to ${rowDate(
        plan?.week_end ?? ymd(addDays(weekStart(week), 6)),
      )}. Tap a task to record the work.`}
    >
      {(showSummary || (loading && !!farm && !plan)) && (
        <div className="mb-4">
          <KpiGrid cols={boot.can_see_pay ? 5 : 4}>
            <KpiCard
              label="Tasks done"
              value={`${stats.pct}%`}
              hint={`${stats.done} of ${stats.total} tasks`}
              tone={stats.total > 0 && stats.done === stats.total ? "good" : "default"}
              loading={firstLoad(loading, !!plan)}
            />
            <KpiCard
              label="Quantity done"
              value={formatUoms(stats.doneQty)}
              hint={`of ${formatUoms(stats.planned)} planned${stats.pendingQty.some((x) => x.qty > 0) ? ` · ${formatUoms(stats.pendingQty)} awaiting approval` : ""}`}
              loading={firstLoad(loading, !!plan)}
            />
            <KpiCard
              label={stats.pendingTasks || hasPending ? "Awaiting approval" : "Overdue"}
              value={stats.pendingTasks || hasPending ? stats.pendingTasks : stats.overdue}
              hint={stats.pendingTasks || hasPending ? "tasks with unapproved work" : "open tasks past their due date"}
              tone={(stats.pendingTasks || stats.overdue) > 0 ? "warning" : "good"}
              loading={firstLoad(loading, !!plan)}
            />
            <KpiCard
              label="Deviations"
              value={stats.deviations}
              hint="late, partial or skipped"
              tone={stats.deviations > 0 ? "warning" : "default"}
              loading={firstLoad(loading, !!plan)}
            />
            {boot.can_see_pay && (
              <KpiCard label="Labour" value={kes(stats.labour)} hint="approved work" loading={firstLoad(loading, !!plan)} />
            )}
          </KpiGrid>
        </div>
      )}
      {skippedPanel}
      <ProtocolCheckPanel check={check} />
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
          usesCycles={cropUsesCycles(crop)}
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
