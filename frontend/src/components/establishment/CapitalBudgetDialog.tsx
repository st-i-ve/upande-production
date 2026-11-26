import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { DraftBar } from "@/components/DraftBar";
import { RowsSkeleton } from "@/components/Loading";
import { ScrollTable } from "@/components/ScrollTable";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Picker } from "@/components/ui/picker";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDraftFields } from "@/hooks/useDialogDraft";
import {
  getUnitCapitalBudget,
  saveUnitCapitalBudget,
  type UnitBudget,
} from "@/lib/establishment-api";
import { isError } from "@/lib/frappe";
import { kes } from "@/lib/format";
import { num } from "@/lib/utils";

interface EditRow {
  operation: string;
  basis: "Per ha" | "Total";
  amount: string;
  note: string;
}

const BASES = ["Per ha", "Total"];

function CapitalBudgetForm({
  unit,
  budget,
  operations,
  canWrite,
  onSaved,
}: {
  unit: string;
  budget: UnitBudget;
  operations: string[];
  canWrite: boolean;
  onSaved: (b: UnitBudget) => void;
}) {
  const [rows, setRows] = useState<EditRow[]>(() =>
    budget.rows.map((r) => ({ operation: r.operation, basis: r.basis, amount: String(r.amount ?? ""), note: r.note ?? "" })),
  );
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const draft = useDraftFields({ key: `capital-budget:${unit}`, open: canWrite, enabled: canWrite, fields: { rows: [rows, setRows] } });

  const patch = (i: number, p: Partial<EditRow>) => setRows((x) => x.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const taken = new Set(rows.map((r) => r.operation));
  const options = (own: string) => [...new Set([...operations, ...(own ? [own] : [])])].filter((o) => o === own || !taken.has(o));
  const spentOf = (op: string) => budget.rows.find((r) => r.operation === op)?.spent;

  async function save() {
    setBusy(true);
    setFailure(null);
    const r = await saveUnitCapitalBudget(
      unit,
      rows.filter((x) => x.operation).map((x) => ({ operation: x.operation, basis: x.basis, amount: num(x.amount) ?? 0, note: x.note || null })),
    );
    setBusy(false);
    if (isError(r)) return setFailure(r.error);
    draft.clear();
    onSaved(r);
  }

  if (!canWrite) {
    return budget.rows.length === 0 ? (
      <p className="py-4 text-center text-[13px] text-[var(--sd-muted)]">No capital budget on this block.</p>
    ) : (
      <ScrollTable>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Activity</TableHead>
              <TableHead>Basis</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead className="text-right">Budget</TableHead>
              <TableHead className="text-right">Spent</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {budget.rows.map((r) => (
              <TableRow key={r.operation} data-testid={`budget-${r.operation}`}>
                <TableCell className="font-medium">{r.operation_name || r.operation}</TableCell>
                <TableCell>{r.basis}</TableCell>
                <TableCell className="text-right tabular-nums">{kes(r.amount)}</TableCell>
                <TableCell className="text-right tabular-nums">{kes(r.effective)}</TableCell>
                <TableCell className="text-right tabular-nums">{kes(r.spent)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ScrollTable>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <DraftBar restored={draft.restored} onDiscard={draft.discard} />
      {rows.length === 0 && <p className="py-2 text-center text-[13px] text-[var(--sd-muted)]">No capital budget on this block yet.</p>}
      {rows.length > 0 && (
        <ScrollTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Activity</TableHead>
                <TableHead>Basis</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead className="text-right">Budget</TableHead>
                <TableHead className="text-right">Spent</TableHead>
                <TableHead>Note</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => {
                const saved = budget.rows.find((b) => b.operation === r.operation);
                const unchanged = saved && saved.basis === r.basis && String(saved.amount ?? "") === r.amount;
                return (
                  <TableRow key={i}>
                    <TableCell className="min-w-[10rem]">
                      <Picker label={`Activity ${i + 1}`} value={r.operation} onChange={(v) => patch(i, { operation: v })} options={options(r.operation)} placeholder="Choose an activity" />
                    </TableCell>
                    <TableCell className="min-w-[7rem]">
                      <Picker label={`Basis ${i + 1}`} value={r.basis} onChange={(v) => patch(i, { basis: v as EditRow["basis"] })} options={BASES} />
                    </TableCell>
                    <TableCell>
                      <Input aria-label={`Amount ${i + 1}`} inputMode="decimal" className="ml-auto h-8 w-28 text-right tabular-nums" value={r.amount} onChange={(e) => patch(i, { amount: e.target.value })} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums" data-testid={`effective-${i}`}>
                      {unchanged ? kes(saved.effective) : "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{r.operation && spentOf(r.operation) != null ? kes(spentOf(r.operation)) : "—"}</TableCell>
                    <TableCell>
                      <Input aria-label={`Note ${i + 1}`} className="h-8" value={r.note} onChange={(e) => patch(i, { note: e.target.value })} />
                    </TableCell>
                    <TableCell>
                      <Button size="sm" variant="ghost" aria-label={`Remove activity ${i + 1}`} onClick={() => setRows((x) => x.filter((_, j) => j !== i))}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </ScrollTable>
      )}
      {failure && (
        <p role="alert" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px] font-medium text-[var(--sd-ink)]">
          {failure}
        </p>
      )}
      <div className="flex justify-between gap-2">
        <Button variant="outline" onClick={() => setRows((x) => [...x, { operation: "", basis: "Per ha", amount: "", note: "" }])} disabled={busy}>
          <Plus className="h-4 w-4" /> Add activity
        </Button>
        <Button onClick={() => void save()} disabled={busy}>
          {busy ? "Saving…" : "Save budget"}
        </Button>
      </div>
    </div>
  );
}

/**
 * One block's capital budget: its rows, the amount each comes to on the block's area, and what has been
 * spent. Managers edit; the server decides what is allowed and its refusal shows inline.
 */
export function CapitalBudgetDialog({
  unit,
  operations,
  canWrite,
  onClose,
  onSaved,
}: {
  unit: string;
  /** Capital operations of the crop that may be budgeted. */
  operations: string[];
  canWrite: boolean;
  onClose: () => void;
  onSaved?: () => void;
}) {
  const [budget, setBudget] = useState<UnitBudget | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void getUnitCapitalBudget(unit).then((r) => {
      if (!live) return;
      if (isError(r)) setFailure(r.error);
      else setBudget(r);
    });
    return () => {
      live = false;
    };
  }, [unit]);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto" aria-describedby="capbud-desc">
        <DialogHeader>
          <DialogTitle>Capital budget · {unit}</DialogTitle>
          <DialogDescription id="capbud-desc">
            What setting up this block is budgeted to cost. Per ha rows are multiplied by the block's area{budget?.area_ha != null ? ` (${budget.area_ha} ha)` : ""}.
          </DialogDescription>
        </DialogHeader>
        {failure && (
          <p role="alert" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px] font-medium text-[var(--sd-ink)]">
            {failure}
          </p>
        )}
        {!budget && !failure && <RowsSkeleton rows={3} />}
        {budget && (
          <>
            <CapitalBudgetForm
              unit={unit}
              budget={budget}
              operations={operations}
              canWrite={canWrite}
              onSaved={(b) => {
                setBudget(b);
                onSaved?.();
              }}
            />
            <div className="flex justify-between text-[13px] text-[var(--sd-muted)]" data-testid="budget-totals">
              <span>Total budget {kes(budget.total_budget)}</span>
              <span>Spent {kes(budget.total_spent)}</span>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
