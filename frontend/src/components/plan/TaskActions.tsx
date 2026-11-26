import { useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { DatePicker } from "@/components/DatePicker";
import { BlockNotice, OverrideReasonDialog } from "@/components/rules/RuleParts";
import { addDays, rowDate } from "@/components/plan/fmt";
import { ruleFailure, type RuleFailure } from "@/lib/rules";
import { useToast } from "@/components/Toast";
import { deletePlanTask, forwardPlanTasks, movePlanTask, postponePlanTask, type PlanTask } from "@/lib/api";
import { isError, type Envelope } from "@/lib/frappe";
import { parseYmd, ymd } from "@/lib/utils";

type Mode = "move" | "postpone" | "delete";

const ITEM =
  "flex w-full items-center rounded-[var(--sd-radius)] px-2.5 py-2 text-left text-[13px] text-[var(--sd-ink)] hover:bg-[var(--sd-bg-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 aria-disabled:cursor-not-allowed aria-disabled:text-[var(--sd-muted)] aria-disabled:hover:bg-transparent";

/** The "..." menu at the end of a plan task row: change date, postpone, delete. */
export function TaskActions({
  plan,
  task,
  weekStart,
  onDone,
  canReschedule = true,
  canApprove = false,
}: {
  plan: string;
  task: PlanTask;
  weekStart: Date;
  onDone: () => void;
  /** Change date, postpone and delete (Production Plan Editor). */
  canReschedule?: boolean;
  /** A manager may approve and forward a task that awaits approval. */
  canApprove?: boolean;
}) {
  const toast = useToast();
  const [menu, setMenu] = useState(false);
  const [mode, setMode] = useState<Mode | null>(null);
  const finished = task.status === "Done" || task.status === "Skipped";
  const hasWork = (task.work?.length ?? 0) > 0;

  function open(m: Mode) {
    setMenu(false);
    setMode(m);
  }
  async function approveForward() {
    setMenu(false);
    const r = await forwardPlanTasks(plan, task.name ? [task.name] : undefined);
    if (isError(r)) toast(r.error, "error");
    else {
      toast("Approved and forwarded to the supervisor.");
      onDone();
    }
  }
  function done() {
    setMode(null);
    onDone();
  }

  return (
    <>
      <Popover open={menu} onOpenChange={setMenu}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label="Task actions"
            className="mr-1 flex size-8 shrink-0 items-center justify-center rounded-[var(--sd-radius)] text-[var(--sd-muted)] transition-colors hover:bg-[var(--sd-bg-soft)] hover:text-[var(--sd-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            <MoreHorizontal className="size-4" aria-hidden />
          </button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-56 p-1.5" role="menu">
          {canApprove && !!task.awaiting_approval && (
            <button type="button" role="menuitem" className={ITEM} onClick={() => void approveForward()}>
              Approve &amp; forward
            </button>
          )}
          {canReschedule && !finished && (
            <button type="button" role="menuitem" className={ITEM} onClick={() => open("move")}>
              Change date
            </button>
          )}
          {canReschedule && !finished && (
            <button type="button" role="menuitem" className={ITEM} onClick={() => open("postpone")}>
              Postpone
            </button>
          )}
          {canReschedule && <button
            type="button"
            role="menuitem"
            className={ITEM}
            aria-disabled={hasWork || undefined}
            title={hasWork ? "Work is recorded; mark it Skipped instead" : undefined}
            onClick={() => !hasWork && open("delete")}
          >
            Delete
          </button>}
        </PopoverContent>
      </Popover>
      {mode === "move" && <ChangeDateDialog plan={plan} task={task} weekStart={weekStart} onClose={() => setMode(null)} onDone={done} />}
      {mode === "postpone" && <PostponeDialog plan={plan} task={task} onClose={() => setMode(null)} onDone={done} />}
      {mode === "delete" && <DeleteTaskDialog plan={plan} task={task} onClose={() => setMode(null)} onDone={done} />}
    </>
  );
}

interface DialogProps {
  plan: string;
  task: PlanTask;
  onClose: () => void;
  onDone: () => void;
}

/** Shared submit state: busy, inline error, and the activity-rule envelope. */
function useAction(run: (overrideReason: string | null) => Promise<Envelope<unknown>>, onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [rule, setRule] = useState<RuleFailure | null>(null);

  async function submit(overrideReason?: string) {
    setBusy(true);
    setFailure(null);
    setRule(null);
    const r = await run(overrideReason ?? null);
    setBusy(false);
    if (isError(r)) {
      const rf = ruleFailure(r);
      if (rf) setRule(rf);
      else setFailure(r.error);
      return;
    }
    onDone();
  }
  return { busy, failure, rule, setRule, submit };
}

function Failure({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px] text-[var(--sd-ink)]">
      {text}
    </p>
  );
}

function Footer({ busy, onClose, children }: { busy: boolean; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="flex justify-end gap-2">
      <Button variant="outline" onClick={onClose} disabled={busy}>
        Cancel
      </Button>
      {children}
    </div>
  );
}

function Shell({
  title,
  description,
  busy,
  onClose,
  rule,
  onCancelRule,
  onOverride,
  children,
}: {
  title: string;
  description: string;
  busy: boolean;
  onClose: () => void;
  rule: RuleFailure | null;
  onCancelRule: () => void;
  onOverride: (reason: string) => void;
  children: React.ReactNode;
}) {
  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-md" aria-describedby="task-action-desc">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription id="task-action-desc">{description}</DialogDescription>
        </DialogHeader>
        {children}
      </DialogContent>
      {rule?.status === "Warn" && (
        <OverrideReasonDialog breaches={rule.breaches} busy={busy} onCancel={onCancelRule} onConfirm={onOverride} />
      )}
    </Dialog>
  );
}

export function ChangeDateDialog({ plan, task, weekStart, onClose, onDone }: DialogProps & { weekStart: Date }) {
  const min = ymd(weekStart);
  const max = ymd(addDays(weekStart, 6));
  const [date, setDate] = useState(task.due_date);
  const inWeek = date >= min && date <= max;
  const { busy, failure, rule, setRule, submit } = useAction((o) => movePlanTask(plan, task.name ?? "", date, o), onDone);

  return (
    <Shell
      title="Change date"
      description={`${task.operation_name} · currently ${rowDate(task.due_date)}. It stays in this week.`}
      busy={busy}
      onClose={onClose}
      rule={rule}
      onCancelRule={() => setRule(null)}
      onOverride={(r) => void submit(r)}
    >
      <div className="flex flex-col gap-1.5">
        <Label>New date</Label>
        <DatePicker value={date} onChange={(d) => { setDate(d); setRule(null); }} min={min} max={max} aria-label="New date" />
        {!inWeek && <p className="text-[12.5px] text-[var(--sd-muted)]">Pick a day in this week. To move it to another week, postpone it.</p>}
      </div>
      {rule?.status === "Block" && <BlockNotice breaches={rule.breaches} />}
      <Failure text={failure} />
      <Footer busy={busy} onClose={onClose}>
        <Button onClick={() => void submit()} disabled={busy || !inWeek || rule?.status === "Block"}>
          {busy ? "Moving…" : "Move task"}
        </Button>
      </Footer>
    </Shell>
  );
}

export function PostponeDialog({ plan, task, onClose, onDone }: DialogProps) {
  const due = parseYmd(task.due_date);
  const min = due ? ymd(addDays(due, 1)) : task.due_date;
  const [date, setDate] = useState(min);
  const [reason, setReason] = useState("");
  const later = date >= min;
  const ready = later && reason.trim().length > 0;
  const { busy, failure, rule, setRule, submit } = useAction(
    (o) => postponePlanTask(plan, task.name ?? "", date, reason.trim(), o),
    onDone,
  );

  return (
    <Shell
      title="Postpone task"
      description={`${task.operation_name} · due ${rowDate(task.due_date)}. Postponed tasks stay flagged Late.`}
      busy={busy}
      onClose={onClose}
      rule={rule}
      onCancelRule={() => setRule(null)}
      onOverride={(r) => void submit(r)}
    >
      <div className="flex flex-col gap-1.5">
        <Label>New date</Label>
        <DatePicker value={date} onChange={(d) => { setDate(d); setRule(null); }} min={min} aria-label="New date" />
        {!later && <p className="text-[12.5px] text-[var(--sd-muted)]">Pick a day after the current due date.</p>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="postpone-reason">Reason</Label>
        <Textarea id="postpone-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is it being postponed?" />
      </div>
      {rule?.status === "Block" && <BlockNotice breaches={rule.breaches} />}
      <Failure text={failure} />
      <Footer busy={busy} onClose={onClose}>
        <Button onClick={() => void submit()} disabled={busy || !ready || rule?.status === "Block"}>
          {busy ? "Postponing…" : "Postpone task"}
        </Button>
      </Footer>
    </Shell>
  );
}

export function DeleteTaskDialog({ plan, task, onClose, onDone }: DialogProps) {
  const [reason, setReason] = useState("");
  const { busy, failure, submit } = useAction(() => deletePlanTask(plan, task.name ?? "", reason.trim()), onDone);

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-md" aria-describedby="task-delete-desc">
        <DialogHeader>
          <DialogTitle>Delete task</DialogTitle>
          <DialogDescription id="task-delete-desc">
            {task.operation_name} · due {rowDate(task.due_date)}. This removes it from the plan.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="delete-reason">Reason</Label>
          <Textarea id="delete-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is it being deleted?" />
        </div>
        <Failure text={failure} />
        <Footer busy={busy} onClose={onClose}>
          <Button variant="destructive" onClick={() => void submit()} disabled={busy || !reason.trim()}>
            {busy ? "Deleting…" : "Delete task"}
          </Button>
        </Footer>
      </DialogContent>
    </Dialog>
  );
}
