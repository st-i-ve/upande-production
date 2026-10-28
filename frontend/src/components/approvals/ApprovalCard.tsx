import { useState } from "react";
import { CheckCircle2, Loader2, RotateCcw, Undo2 } from "lucide-react";
import { CheckCircle } from "@/components/ui/check-circle";
import { Input } from "@/components/ui/input";
import { StepLine } from "@/components/approvals/StepLine";
import type { ApprovalGroup, ResubmitEdit } from "@/lib/approvals-api";
import { kes, shortDate, trimQty } from "@/lib/format";
import { cn } from "@/lib/utils";

const PILL = "inline-flex h-8 items-center gap-1.5 rounded-full px-3.5 text-[12px] font-medium transition-colors disabled:opacity-50";

/** One supervisor submission: where, what, who, how it moves the plan, and the keyed rows. */
export function ApprovalCard({
  group: g,
  showPay,
  selectable,
  selected,
  busy,
  onSelect,
  onApprove,
  onSendBack,
  onResubmit,
}: {
  group: ApprovalGroup;
  showPay: boolean;
  selectable: boolean;
  selected: boolean;
  busy: boolean;
  onSelect: (next: boolean) => void;
  onApprove: () => void;
  onSendBack: () => void;
  onResubmit: (edits: ResubmitEdit[]) => void;
}) {
  const [draft, setDraft] = useState<Record<string, { qty: string; hours: string }>>({});
  const sentBack = g.status === "Sent Back";
  const plan = g.plan_week ? `Week ${g.plan_week}${g.plan_year ? `, ${g.plan_year}` : ""}` : g.unplanned ? "Unplanned" : null;
  const val = (name: string, field: "qty" | "hours", orig: number | null) =>
    draft[name]?.[field] ?? (orig == null ? "" : String(orig));
  const set = (name: string, field: "qty" | "hours", v: string, e: { qty: number; hours: number | null }) =>
    setDraft((d) => ({
      ...d,
      [name]: { qty: d[name]?.qty ?? String(e.qty), hours: d[name]?.hours ?? (e.hours == null ? "" : String(e.hours)), [field]: v },
    }));

  const edits = (): ResubmitEdit[] =>
    g.entries.flatMap((e) => {
      const d = draft[e.name];
      if (!d) return [];
      const q = Number(d.qty);
      const h = d.hours === "" ? null : Number(d.hours);
      const out: ResubmitEdit = { name: e.name };
      if (Number.isFinite(q) && q !== e.qty) out.qty = q;
      if (h !== e.hours && (h === null || Number.isFinite(h))) out.hours = h;
      return out.qty !== undefined || out.hours !== undefined ? [out] : [];
    });

  return (
    <article
      data-testid={`approval-card-${g.key}`}
      className={cn(
        "scp-card-in rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)] transition-shadow",
        selected && "ring-2 ring-[var(--sd-ink)]",
      )}
    >
      <header className="flex flex-wrap items-start gap-x-4 gap-y-2 px-5 pt-4">
        {selectable && (
          <CheckCircle
            className="mt-1"
            checked={selected}
            onCheckedChange={onSelect}
            label={`Select ${g.unit_name} ${g.operation_name}`}
          />
        )}
        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-semibold tracking-tight text-[var(--sd-ink)]">
            {g.unit_name} <span className="font-normal text-[var(--sd-muted)]">·</span> {g.operation_name}
          </h3>
          <p className="mt-0.5 text-[12px] text-[var(--sd-quiet)]">
            {[plan, shortDate(g.work_date)].filter(Boolean).join(" · ")}
          </p>
        </div>
        <div className="text-right text-[12px]">
          <div className="font-medium text-[var(--sd-ink)]">{g.submitted_by_name || g.submitted_by}</div>
          <div
            data-testid="age"
            className={cn("mt-0.5", g.stale ? "font-semibold text-[var(--sd-data-red)]" : "text-[var(--sd-quiet)]")}
          >
            {g.age_days === 0 ? "Keyed today" : `${g.age_days} day${g.age_days === 1 ? "" : "s"} waiting`}
            {g.stale && " · stale"}
          </div>
        </div>
      </header>

      <div className="px-5 pt-3">
        <StepLine planned={g.task_planned_qty} done={g.task_done_qty} pending={g.total_qty} uom={g.uom} />
      </div>

      {sentBack && g.review_note && (
        <p
          data-testid="review-note"
          className="mx-5 mt-3 rounded-[var(--sd-radius)] bg-[var(--sd-alert-warn)] px-3 py-2 text-[12.5px] text-[var(--sd-ink)]"
        >
          <b className="font-semibold">Sent back:</b> {g.review_note}
        </p>
      )}

      <div className="overflow-x-auto px-5 pt-3">
        <table className="w-full min-w-[420px] text-[12.5px]">
          <thead>
            <tr className="text-left text-[10.5px] uppercase tracking-wider text-[var(--sd-quiet)]">
              <th className="pb-1.5 pr-3 font-medium">Value adder</th>
              <th className="pb-1.5 pr-3 text-right font-medium">Qty{g.uom ? ` (${g.uom})` : ""}</th>
              <th className="pb-1.5 pr-3 text-right font-medium">Hours</th>
              {showPay && <th className="pb-1.5 pr-3 text-right font-medium">Rate</th>}
              {showPay && <th className="pb-1.5 text-right font-medium">Pay</th>}
            </tr>
          </thead>
          <tbody>
            {g.entries.map((e) => (
              <tr key={e.name} className="border-t border-[var(--sd-line)]">
                <td className="py-1.5 pr-3 text-[var(--sd-ink)]">{e.employee_name || e.employee}</td>
                {sentBack ? (
                  <>
                    <td className="py-1 pr-3 text-right">
                      <Input
                        aria-label={`Qty for ${e.employee_name || e.employee}`}
                        inputMode="decimal"
                        className="ml-auto h-8 w-20 text-right"
                        value={val(e.name, "qty", e.qty)}
                        onChange={(ev) => set(e.name, "qty", ev.target.value, e)}
                      />
                    </td>
                    <td className="py-1 pr-3 text-right">
                      <Input
                        aria-label={`Hours for ${e.employee_name || e.employee}`}
                        inputMode="decimal"
                        className="ml-auto h-8 w-20 text-right"
                        value={val(e.name, "hours", e.hours)}
                        onChange={(ev) => set(e.name, "hours", ev.target.value, e)}
                      />
                    </td>
                  </>
                ) : (
                  <>
                    <td className="py-1.5 pr-3 text-right">{trimQty(e.qty)}</td>
                    <td className="py-1.5 pr-3 text-right">{e.hours == null ? "—" : trimQty(e.hours)}</td>
                  </>
                )}
                {showPay && <td className="py-1.5 pr-3 text-right text-[var(--sd-muted)]">{kes(e.rate)}</td>}
                {showPay && <td className="py-1.5 text-right">{kes(e.pay_value)}</td>}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-[var(--sd-line)] font-semibold text-[var(--sd-ink)]">
              <td className="py-1.5 pr-3">Total</td>
              <td className="py-1.5 pr-3 text-right">{trimQty(g.total_qty)}</td>
              <td className="py-1.5 pr-3" />
              {showPay && <td className="py-1.5 pr-3" />}
              {showPay && <td className="py-1.5 text-right" data-testid="total-pay">{kes(g.total_pay)}</td>}
            </tr>
          </tfoot>
        </table>
      </div>

      {g.note && <p className="mx-5 mt-2 text-[12px] italic text-[var(--sd-muted)]">Plan note: {g.note}</p>}

      <footer className="flex items-center justify-end gap-2 px-5 pb-4 pt-3">
        {g.status === "Pending" && (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={onSendBack}
              className={cn(PILL, "bg-[rgba(10,10,10,0.05)] text-[var(--sd-ink)] hover:bg-[rgba(10,10,10,0.09)]")}
            >
              <Undo2 className="h-3.5 w-3.5" /> Send back
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onApprove}
              className={cn(PILL, "bg-[var(--sd-ink)] text-[var(--sd-card)] hover:opacity-90")}
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />} Approve
            </button>
          </>
        )}
        {sentBack && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onResubmit(edits())}
            className={cn(PILL, "bg-[var(--sd-ink)] text-[var(--sd-card)] hover:opacity-90")}
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />} Resubmit
          </button>
        )}
        {g.status === "Approved" && (
          <span className="text-[12px] text-[var(--sd-quiet)]">
            Approved{g.reviewed_by ? ` by ${g.reviewed_by}` : ""}
          </span>
        )}
      </footer>
    </article>
  );
}
