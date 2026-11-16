import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { kes, shortDate, trimQty } from "@/lib/format";
import { isError } from "@/lib/frappe";
import {
  approvePayRun,
  cancelPayRun,
  downloadCsv,
  markPayRunPaid,
  payRunCsv,
  payRunDetail,
  refreshPayRun,
  type PayRunDetail,
  type PayRunStatus,
} from "@/lib/labourpay-api";
import { cn, todayISO } from "@/lib/utils";

const CHIP: Record<PayRunStatus, string> = {
  Draft: "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]",
  Approved: "bg-[var(--sd-alert-info)] text-[var(--sd-ink)]",
  Paid: "bg-[var(--sd-pistachio)] text-[var(--sd-ink)]",
  Cancelled: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)] line-through",
};

export function StatusChip({ status }: { status: PayRunStatus }) {
  return <span className={cn("rounded-full px-2 py-0.5 text-[11.5px] font-medium", CHIP[status])}>{status}</span>;
}

/**
 * One pay run: its lines (days, entries, quantity and amount per person) and the buttons its state
 * allows. Draft: refresh, approve, delete. Approved: mark paid, cancel. Any state: download CSV.
 * `readOnly` (Work Management drives pay) leaves only the download.
 */
export function PayRunDialog({
  name,
  initial,
  readOnly,
  onClose,
  onChanged,
}: {
  name: string;
  initial?: PayRunDetail | null;
  readOnly?: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [run, setRun] = useState<PayRunDetail | null>(initial ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [reference, setReference] = useState("");
  const [paidOn, setPaidOn] = useState(todayISO());

  useEffect(() => {
    if (initial) return;
    let live = true;
    void payRunDetail(name).then((r) => {
      if (!live) return;
      if (isError(r)) setError(r.error);
      else setRun(r);
    });
    return () => {
      live = false;
    };
  }, [name, initial]);

  async function act(key: string, fn: () => Promise<unknown>, done: string, close = false) {
    setBusy(key);
    const r = (await fn()) as PayRunDetail | { error: string; status?: string };
    setBusy(null);
    if (isError(r as never)) return void toast((r as { error: string }).error, "error");
    toast(done);
    onChanged();
    if (close || (r as { status?: string }).status === "Deleted") return onClose();
    setRun(r as PayRunDetail);
    setPaying(false);
  }

  async function csv() {
    setBusy("csv");
    const r = await payRunCsv(name);
    setBusy(null);
    if (isError(r)) return void toast(r.error, "error");
    downloadCsv(r.filename, r.csv);
  }

  const total = run?.total_amount ?? run?.lines.reduce((t, l) => t + (l.amount ?? 0), 0) ?? 0;
  const draft = run?.status === "Draft";
  const approved = run?.status === "Approved";

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-4xl" aria-describedby="pr-desc">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3 text-[20px] tracking-tight">
            {name}
            {run && <StatusChip status={run.status} />}
          </DialogTitle>
          <DialogDescription id="pr-desc">
            {run
              ? `${shortDate(run.from_date)} to ${shortDate(run.to_date)}${run.farm ? ` · ${run.farm}` : ""}${run.paid_on ? ` · paid ${shortDate(run.paid_on)}` : ""}${run.payment_reference ? ` · ${run.payment_reference}` : ""}`
              : "Loading the pay run…"}
          </DialogDescription>
        </DialogHeader>

        {error ? (
          <p role="alert" className="text-[13px] text-[var(--sd-muted)]">{error}</p>
        ) : !run ? null : run.lines.length === 0 ? (
          <p className="text-[13px] text-[var(--sd-muted)]">
            No approved, unpaid work falls in this period.{draft ? " Refresh after more work is approved." : ""}
          </p>
        ) : (
          <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                  <th className="px-3 py-2 font-medium">Employee</th>
                  <th className="px-3 py-2 text-right font-medium">Days</th>
                  <th className="px-3 py-2 text-right font-medium">Entries</th>
                  <th className="px-3 py-2 text-right font-medium">Qty</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {run.lines.map((l) => (
                  <tr key={l.employee} className="border-b border-[var(--sd-line-soft)]">
                    <td className="px-3 py-2 font-medium text-[var(--sd-ink)]">{l.employee_name || l.employee}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{l.days}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{l.entries}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{trimQty(l.qty)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{kes(l.amount)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-semibold">
                  <td className="px-3 py-2">Total · {run.total_people} {run.total_people === 1 ? "person" : "people"}</td>
                  <td colSpan={3} />
                  <td className="px-3 py-2 text-right tabular-nums" data-testid="pr-total">{kes(total)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}

        {paying && approved && (
          <div className="grid gap-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] p-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pr-ref">Payment reference</Label>
              <Input id="pr-ref" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="e.g. MPESA batch number" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pr-paid-on">Paid on</Label>
              <DatePicker id="pr-paid-on" aria-label="Paid on" value={paidOn} onChange={setPaidOn} max={todayISO()} />
            </div>
            <div className="flex justify-end gap-2 sm:col-span-2">
              <Button variant="outline" onClick={() => setPaying(false)} disabled={!!busy}>
                Cancel
              </Button>
              <Button disabled={!!busy} onClick={() => void act("paid", () => markPayRunPaid(name, reference.trim() || undefined, paidOn || undefined), "Marked as paid.")}>
                {busy === "paid" ? "Saving…" : "Confirm paid"}
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button variant="outline" onClick={() => void csv()} disabled={!!busy || !run}>
            <Download className="mr-1.5 h-4 w-4" /> Download CSV
          </Button>
          {run && !readOnly && (
            <div className="flex flex-wrap gap-2">
              {draft && (
                <>
                  <Button
                    variant="outline"
                    disabled={!!busy}
                    onClick={() => {
                      if (window.confirm(`Delete draft ${name}?`)) void act("delete", () => cancelPayRun(name), "Draft deleted.", true);
                    }}
                  >
                    Delete
                  </Button>
                  <Button variant="outline" disabled={!!busy} onClick={() => void act("refresh", () => refreshPayRun(name), "Pay run refreshed.")}>
                    {busy === "refresh" ? "Refreshing…" : "Refresh"}
                  </Button>
                  <Button disabled={!!busy || run.lines.length === 0} onClick={() => void act("approve", () => approvePayRun(name), "Pay run approved. Its work is locked.")}>
                    {busy === "approve" ? "Approving…" : "Approve"}
                  </Button>
                </>
              )}
              {approved && !paying && (
                <>
                  <Button
                    variant="outline"
                    disabled={!!busy}
                    onClick={() => {
                      if (window.confirm(`Cancel ${name}? Its work goes back to unpaid.`)) void act("cancel", () => cancelPayRun(name), "Pay run cancelled.");
                    }}
                  >
                    Cancel pay run
                  </Button>
                  <Button disabled={!!busy} onClick={() => setPaying(true)}>
                    Mark paid
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
