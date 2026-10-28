import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { FilterSelect } from "@/components/FilterSelect";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { WeekPicker } from "@/components/WeekPicker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { listCommitments, saveCommitment, type Row } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { kes, qty, shortDate } from "@/lib/format";
import { cn, ymd } from "@/lib/utils";
import { currentIsoWeek, weekStart, type IsoWeek } from "@/lib/weeks";
import { BODY_ROW, EmptyRows, Field, HEAD_ROW, TH, THR } from "./records";

const STATUSES = ["Open", "Confirmed", "Delivered", "Cancelled"];

const STATUS_CLASS: Record<string, string> = {
  Open: "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]",
  Confirmed: "bg-[rgba(63,143,79,0.10)] text-[var(--sd-sev-moderate)]",
  Delivered: "bg-[rgba(63,143,79,0.10)] text-[var(--sd-sev-moderate)]",
  Cancelled: "bg-[rgba(196,48,43,0.09)] text-[var(--sd-sev-critical)]",
};

export function CommitmentsPanel({
  crop,
  uom,
  canEdit,
  canSeePay,
  onSaved,
}: {
  crop: string;
  uom: string;
  canEdit: boolean;
  canSeePay: boolean;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    const r = await listCommitments(crop);
    if (isError(r)) {
      toast(r.error, "error");
      setRows([]);
      return;
    }
    setRows(r.rows ?? []);
  }, [crop, toast]);

  useEffect(() => {
    setRows(null);
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-3">
      {canEdit && (
        <div className="flex justify-end">
          <Button size="sm" className="rounded-full" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> New commitment
          </Button>
        </div>
      )}
      {!rows ? (
        <RowsSkeleton rows={4} />
      ) : rows.length === 0 ? (
        <EmptyRows>No buyer commitments yet.</EmptyRows>
      ) : (
        <div className="max-h-[min(52vh,440px)] overflow-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
          <table className="w-full min-w-[40rem] text-[13px]">
            <thead>
              <tr className={HEAD_ROW}>
                <th className={TH}>Customer</th>
                <th className={TH}>Week starting</th>
                <th className={THR}>Committed ({uom})</th>
                {canSeePay && <th className={THR}>Price / {uom}</th>}
                <th className={TH}>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const status = String(r.status ?? "");
                return (
                  <tr key={String(r.name ?? i)} className={BODY_ROW}>
                    <td className="px-3 py-2.5 font-medium text-[var(--sd-ink)]">{String(r.customer ?? "")}</td>
                    <td className="px-3 py-2.5 tabular-nums">
                      {shortDate(r.week_start as string)}
                      {r.iso_week ? <span className="ml-1.5 text-[11px] text-[var(--sd-quiet)]">W{String(r.iso_week).padStart(2, "0")}</span> : null}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{qty(Number(r.committed_qty))}</td>
                    {canSeePay && <td className="px-3 py-2.5 text-right tabular-nums">{kes(r.price_per_uom as number | null)}</td>}
                    <td className="px-3 py-2.5">
                      <span className={cn("inline-flex rounded-[var(--sd-radius-pill)] px-2.5 py-1 text-[11px] font-medium", STATUS_CLASS[status] ?? STATUS_CLASS.Open)}>
                        {status || "—"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {open && (
        <CommitmentDialog
          crop={crop}
          uom={uom}
          canSeePay={canSeePay}
          onClose={() => setOpen(false)}
          onSaved={() => {
            setOpen(false);
            void load();
            onSaved();
          }}
        />
      )}
    </div>
  );
}

function CommitmentDialog({
  crop,
  uom,
  canSeePay,
  onClose,
  onSaved,
}: {
  crop: string;
  uom: string;
  canSeePay: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [customer, setCustomer] = useState("");
  const [week, setWeek] = useState<IsoWeek>(currentIsoWeek());
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [status, setStatus] = useState("Open");
  const [saving, setSaving] = useState(false);

  const valid = customer.trim() !== "" && Number(quantity) > 0;

  async function save() {
    setSaving(true);
    const r = await saveCommitment({
      crop,
      customer: customer.trim(),
      week_start: ymd(weekStart(week)),
      committed_qty: Number(quantity),
      price_per_uom: price === "" ? undefined : Number(price),
      status,
    });
    setSaving(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast("Commitment saved.");
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New commitment</DialogTitle>
          <DialogDescription>Record how much a buyer has agreed to take in a given week.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Customer" htmlFor="commit-customer">
              <Input id="commit-customer" value={customer} onChange={(e) => setCustomer(e.target.value)} />
            </Field>
          </div>
          <Field label="Week">
            <WeekPicker value={week} onChange={setWeek} className="self-start" />
          </Field>
          <Field label="Status">
            <FilterSelect aria-label="Status" value={status} options={STATUSES.map((s) => ({ value: s, label: s }))} onChange={setStatus} />
          </Field>
          <Field label={`Committed quantity (${uom})`} htmlFor="commit-qty">
            <Input id="commit-qty" type="number" min="0" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </Field>
          {canSeePay && (
            <Field label={`Price per ${uom} (KES, optional)`} htmlFor="commit-price">
              <Input id="commit-price" type="number" min="0" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
            </Field>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" disabled={!valid || saving} onClick={save}>
            {saving ? "Saving…" : "Save commitment"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
