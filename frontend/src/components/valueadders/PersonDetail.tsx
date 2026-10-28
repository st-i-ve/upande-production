import { useEffect, useState } from "react";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { RowsSkeleton } from "@/components/Loading";
import { PendingChip } from "@/components/plan/QtyBar";
import { q, rowDate } from "@/components/plan/fmt";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { isError } from "@/lib/frappe";
import { formatUoms, kes, mergeUoms } from "@/lib/format";
import { getValueAdderDetail, type ValueAdderDetail, type WorkBreakdown } from "@/lib/overview-api";
import { weeklySeries } from "@/components/valueadders/series";

function Breakdown({ title, rows, canPay, label }: { title: string; rows: WorkBreakdown[]; canPay: boolean; label?: (k: string) => string }) {
  if (!rows.length) return null;
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-[13px] font-semibold text-[var(--sd-ink)]">{title}</h3>
      <div className="overflow-auto">
        <table className="w-full min-w-[360px] text-[13px]">
          <thead>
            <tr className={THEAD_ROW}>
              <th className={TH}>{title.replace(/^By /, "")}</th>
              <th className={THR}>Hours</th>
              <th className={THR}>Qty</th>
              {canPay && <th className={THR}>Pay</th>}
              <th className={THR}>Entries</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className={BODY_ROW}>
                <td className={TD}>{label ? label(r.key) : r.key}</td>
                <td className={TDR}>{q(r.hours)}</td>
                <td className={TDR}>{formatUoms(r.qty_by_uom)}</td>
                {canPay && <td className={TDR}>{kes(r.pay_value)}</td>}
                <td className={TDR}>{r.entries}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Side panel for one value adder over the page's date range. */
export function PersonDetail({
  crop,
  employee,
  name,
  from,
  to,
  canPay,
  onClose,
}: {
  crop: string;
  employee: string;
  name: string;
  from: string;
  to: string;
  canPay: boolean;
  onClose: () => void;
}) {
  const [data, setData] = useState<ValueAdderDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    setLoading(true);
    void getValueAdderDetail(crop, employee, from, to).then((r) => {
      if (!live) return;
      setLoading(false);
      if (isError(r)) setFailed(true);
      else setData(r as ValueAdderDetail);
    });
    return () => {
      live = false;
    };
  }, [crop, employee, from, to]);

  const sum = (pick: (r: WorkBreakdown) => number) => (data ? data.by_day.reduce((s, r) => s + pick(r), 0) : 0);
  const pay = data && canPay ? data.by_day.reduce((s, r) => s + (r.pay_value ?? 0), 0) : null;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="left-auto right-0 top-0 h-full max-h-none w-full max-w-[600px] translate-x-0 translate-y-0 content-start overflow-y-auto sm:rounded-none sm:rounded-l-[var(--sd-radius-card)]">
        <DialogHeader>
          <DialogTitle className="text-[22px] tracking-tight">{name}</DialogTitle>
          <DialogDescription className="flex items-center gap-2">
            <span>
              {rowDate(from)} to {rowDate(to)}
            </span>
            {data && data.pending_entries > 0 && <PendingChip>{data.pending_entries} awaiting approval</PendingChip>}
          </DialogDescription>
        </DialogHeader>
        {loading && !data ? (
          <RowsSkeleton rows={8} />
        ) : failed || !data ? (
          <p className="text-[13px] text-[var(--sd-muted)]">This person's work could not be loaded.</p>
        ) : (
          <>
            <KpiGrid cols={2}>
              <KpiCard label="Hours" value={q(sum((r) => r.hours))} series={weeklySeries(data.by_day, (r) => r.hours)} goodDirection="up" />
              <KpiCard label="Quantity" value={formatUoms(mergeUoms(data.by_day.map((r) => r.qty_by_uom)))} hint="per unit of measure" />
              {canPay && <KpiCard label="Earned" value={kes(pay)} series={weeklySeries(data.by_day, (r) => r.pay_value ?? 0)} />}
              <KpiCard label="Days worked" value={data.by_day.length} hint={`${sum((r) => r.entries)} entries`} />
            </KpiGrid>
            <Breakdown title="By operation" rows={data.by_operation} canPay={canPay} />
            <Breakdown title="By unit" rows={data.by_unit} canPay={canPay} />
            <Breakdown title="By day" rows={[...data.by_day].reverse()} canPay={canPay} label={rowDate} />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
