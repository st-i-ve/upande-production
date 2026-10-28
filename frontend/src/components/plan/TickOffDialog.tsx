import { useMemo, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchPicker } from "@/components/ui/search-picker";
import { Textarea } from "@/components/ui/textarea";
import { BlockNotice, OverrideReasonDialog, RuleFlag } from "@/components/rules/RuleParts";
import { ruleFailure, type RuleFailure } from "@/lib/rules";
import { STATUSES, StatusPill } from "@/components/plan/badges";
import { recordTaskWork, type PlanTask, type ValueAdder } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { money, q as fmtQty, rowDate as shortDate } from "@/components/plan/fmt";
import { cn, num } from "@/lib/utils";

interface EntryRow {
  key: number;
  employee: string;
  qty: string;
  hours: string;
}

/**
 * Tick a task off: set its status, and record who did how much. Several value
 * adders can be added before saving; a status-only save (no rows) is fine and
 * creates no work. The pay figure is a preview of qty x rate; the server's own
 * sum is what is stored.
 */
export function TickOffDialog({
  plan,
  task,
  people,
  canSeePay,
  onClose,
  onSaved,
}: {
  plan: string;
  task: PlanTask;
  people: ValueAdder[];
  canSeePay: boolean;
  onClose: () => void;
  onSaved: (task: PlanTask) => void;
}) {
  const [status, setStatus] = useState(task.status || "Open");
  const [rows, setRows] = useState<EntryRow[]>([]);
  const [note, setNote] = useState(task.note ?? "");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [rule, setRule] = useState<RuleFailure | null>(null);
  const seq = useRef(0);

  const options = useMemo(
    () => people.map((p) => ({ value: p.name, label: p.employee_name || p.name })),
    [people],
  );
  const rate = canSeePay ? task.rate : null;
  const uom = task.uom ?? "";

  const patch = (key: number, p: Partial<EntryRow>) =>
    setRows((all) => all.map((r) => (r.key === key ? { ...r, ...p } : r)));

  // A row is saved when it names a person; it must carry a quantity (hours are optional).
  const filled = rows.filter((r) => r.employee);
  const bad = filled.some((r) => num(r.qty) <= 0);
  const preview = rate == null ? null : filled.reduce((s, r) => s + num(r.qty) * rate, 0);

  async function save(overrideReason?: string) {
    setBusy(true);
    setFailure(null);
    setRule(null);
    const entries = filled.map((r) => ({ employee: r.employee, qty: num(r.qty), hours: num(r.hours) }));
    const r = await recordTaskWork(plan, task.name as string, status, entries, note, null, overrideReason ?? null);
    setBusy(false);
    if (isError(r)) {
      const rf = ruleFailure(r);
      if (rf) setRule(rf);
      else setFailure(r.error);
      return;
    }
    onSaved(r.task);
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-xl" aria-describedby="tick-desc">
        <DialogHeader>
          <DialogTitle>{task.operation_name}</DialogTitle>
          <DialogDescription id="tick-desc">
            {task.unit} · due {shortDate(task.due_date)} · planned {fmtQty(task.planned_qty)} {uom}, done{" "}
            {fmtQty(task.done_qty)} {uom}
          </DialogDescription>
        </DialogHeader>

        {task.rule_status && task.rule_status !== "OK" && (
          <div className="flex items-start gap-2 rounded-[var(--sd-radius)] bg-[var(--sd-amber-bg)] px-3 py-2 text-[12.5px] text-[var(--sd-ink)]">
            <RuleFlag status={task.rule_status} />
            <span className="whitespace-pre-line">{[task.rule_notes, task.override_reason ? `Reason given: ${task.override_reason}` : ""].filter(Boolean).join("\n")}</span>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <Label>Status</Label>
          <div role="radiogroup" aria-label="Status" className="flex flex-wrap gap-1 rounded-full bg-[var(--sd-bg-soft)] p-1 shadow-[var(--sd-shadow-inset)]">
            {STATUSES.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={status === s}
                onClick={() => setStatus(s)}
                className={cn(
                  "h-8 flex-1 whitespace-nowrap rounded-full px-3 text-[12.5px] font-medium transition-colors",
                  status === s
                    ? "bg-[var(--sd-card)] text-[var(--sd-ink)] shadow-[var(--sd-shadow-1)]"
                    : "text-[var(--sd-muted)] hover:text-[var(--sd-ink)]",
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {task.work.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <Label>Recorded so far</Label>
            <ul className="divide-y divide-[var(--sd-line-soft)] rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-3.5 shadow-[var(--sd-shadow-inset)]">
              {task.work.map((w) => (
                <li key={w.name} className="flex items-center gap-3 py-2 text-[13px] tabular-nums">
                  <span className="min-w-0 flex-1 truncate text-[var(--sd-ink)]">{w.employee_name || w.employee}</span>
                  <span className="text-[var(--sd-muted)]">
                    {fmtQty(w.qty)} {uom}
                  </span>
                  <span className="w-14 text-right text-[var(--sd-muted)]">{fmtQty(w.hours)} h</span>
                  {canSeePay && <span className="w-20 text-right text-[var(--sd-ink)]">{money(w.pay_value)}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-col gap-2">
          <Label>Add value adders</Label>
          {rows.map((r) => {
            const line = rate == null ? null : num(r.qty) * rate;
            return (
              <div key={r.key} className="flex items-center gap-2" data-testid="entry-row">
                <div className="min-w-0 flex-1">
                  <SearchPicker
                    value={r.employee}
                    options={options}
                    onChange={(v) => patch(r.key, { employee: v })}
                    placeholder="Choose a person"
                    label="Value adder"
                  />
                </div>
                <Input
                  inputMode="decimal"
                  aria-label={`Quantity${uom ? ` (${uom})` : ""}`}
                  placeholder={uom || "Qty"}
                  className="w-20 tabular-nums"
                  value={r.qty}
                  onChange={(e) => patch(r.key, { qty: e.target.value })}
                />
                <Input
                  inputMode="decimal"
                  aria-label="Hours"
                  placeholder="Hours"
                  className="w-20 tabular-nums"
                  value={r.hours}
                  onChange={(e) => patch(r.key, { hours: e.target.value })}
                />
                {line != null && (
                  <span className="w-20 shrink-0 text-right text-[12.5px] tabular-nums text-[var(--sd-muted)]">
                    {money(line)}
                  </span>
                )}
                <button
                  type="button"
                  aria-label="Remove"
                  className="shrink-0 rounded-full p-1 text-[var(--sd-quiet)] hover:text-[var(--sd-sev-critical)]"
                  onClick={() => setRows((all) => all.filter((x) => x.key !== r.key))}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            );
          })}
          <div className="flex items-center justify-between gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRows((all) => [...all, { key: ++seq.current, employee: "", qty: "", hours: "" }])}
            >
              <Plus className="h-3.5 w-3.5" /> Add value adder
            </Button>
            {preview != null && filled.length > 0 && (
              <span className="text-[13px] tabular-nums text-[var(--sd-muted)]">
                Pay preview <span className="font-semibold text-[var(--sd-ink)]">{money(preview)}</span>
              </span>
            )}
          </div>
          {bad && <p className="text-[12px] text-[var(--sd-amber)]">Give each person the quantity they did.</p>}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="tick-note">Note</Label>
          <Textarea id="tick-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Anything the next shift should know" />
        </div>

        {rule?.status === "Block" && <BlockNotice breaches={rule.breaches} />}
        {failure && (
          <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px] text-[var(--sd-ink)]">
            {failure}
          </p>
        )}

        <div className="flex items-center justify-between gap-3">
          <StatusPill status={task.status} />
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button onClick={() => void save()} disabled={busy || bad || rule?.status === "Block"}>
              {busy ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      </DialogContent>
      {rule?.status === "Warn" && (
        <OverrideReasonDialog breaches={rule.breaches} busy={busy} onCancel={() => setRule(null)} onConfirm={(reason) => void save(reason)} />
      )}
    </Dialog>
  );
}
