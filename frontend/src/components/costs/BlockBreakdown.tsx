import { useEffect, useState } from "react";
import { RowsSkeleton } from "@/components/Loading";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { blockBreakdown, type BlockBreakdown as Breakdown } from "@/lib/blockcost-api";
import { isError } from "@/lib/frappe";
import { formatUoms, ha, kes, qty } from "@/lib/format";
import { cn } from "@/lib/utils";

const TH = "px-2 py-2 font-medium";
const TD = "px-2 py-2 tabular-nums";

function Section({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="text-[14px] font-semibold text-[var(--sd-ink)]">{title}</h3>
      <p className="mb-2 text-[12px] text-[var(--sd-quiet)]">{hint}</p>
      {children}
    </section>
  );
}

const Empty = ({ children }: { children: string }) => <p className="py-3 text-[13px] text-[var(--sd-muted)]">{children}</p>;

/**
 * What is happening on one block over the period: labour by activity, inputs by item (with
 * quantity, UOM, amount, per ha and the planned protocol quantity), other expenses by account,
 * totals, and the ERP budget against what has been spent this year.
 */
export function BlockBreakdown({
  unit,
  from,
  to,
  canSeePay,
  onClose,
}: {
  unit: string;
  from: string;
  to: string;
  canSeePay: boolean;
  onClose: () => void;
}) {
  const [data, setData] = useState<Breakdown | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setData(null);
    setFailure(null);
    void blockBreakdown(unit, from, to).then((r) => {
      if (!live) return;
      if (isError(r)) setFailure(r.error);
      else setData(r);
    });
    return () => {
      live = false;
    };
  }, [unit, from, to]);

  const budget = data?.budget;
  const over = !!budget?.erp_budget && (budget.actual_this_fy ?? 0) > budget.erp_budget;
  const hasPlanned = !!data?.inputs.some((i) => i.planned_qty != null);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="left-auto right-0 top-0 h-full max-h-none w-full max-w-[720px] translate-x-0 translate-y-0 content-start overflow-y-auto sm:rounded-none sm:rounded-l-[var(--sd-radius-card)]">
        <DialogHeader>
          <DialogTitle className="text-[22px] tracking-tight">{unit}</DialogTitle>
          <DialogDescription>
            What went into this block, {from} to {to}.
            {data?.area_ha ? ` ${ha(data.area_ha)} ha.` : ""}
          </DialogDescription>
        </DialogHeader>

        {failure ? (
          <p role="alert" className="text-[13px] text-[var(--sd-muted)]">{failure}</p>
        ) : !data ? (
          <RowsSkeleton rows={8} />
        ) : (
          <>
            <KpiGrid cols={2}>
              {canSeePay && <KpiCard label="Total" value={kes(data.totals.total)} hint="labour + inputs + other" goodDirection="down" />}
              {canSeePay && <KpiCard label="Per ha" value={data.totals.per_ha != null ? kes(data.totals.per_ha) : "—"} hint="over the block's area" goodDirection="down" />}
              <KpiCard
                label="ERP budget"
                value={budget?.erp_budget ? kes(budget.erp_budget) : "—"}
                hint={
                  budget?.erp_budget
                    ? `${kes(budget.actual_this_fy)} spent this year${over ? " — over budget" : ""}`
                    : "no ERPNext budget on this cost centre"
                }
                tone={over ? "critical" : undefined}
              />
            </KpiGrid>

            <Section title="Labour by activity" hint="Approved work by casual workers, from their recorded pay.">
              {data.labour.length === 0 ? (
                <Empty>No labour in this period.</Empty>
              ) : (
                <table className="w-full text-[13px]" data-testid="breakdown-labour">
                  <thead>
                    <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                      <th className={TH}>Activity</th>
                      <th className={cn(TH, "text-right")}>Quantity</th>
                      <th className={cn(TH, "text-right")}>Workers</th>
                      {canSeePay && <th className={cn(TH, "text-right")}>Pay</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {data.labour.map((l) => (
                      <tr key={l.operation} className="border-b border-[var(--sd-line-soft)] last:border-0">
                        <td className="px-2 py-2 text-[var(--sd-ink)]">{l.operation}</td>
                        <td className={cn(TD, "text-right")}>{formatUoms(l.qty_by_uom) || "—"}</td>
                        <td className={cn(TD, "text-right")}>{qty(l.workers)}</td>
                        {canSeePay && <td className={cn(TD, "text-right")}>{kes(l.pay)}</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            <Section title="Inputs by item" hint="Stock issued to this block's cost centre (fertiliser, chemicals, other).">
              {data.inputs.length === 0 ? (
                <Empty>No inputs issued in this period.</Empty>
              ) : (
                <table className="w-full text-[13px]" data-testid="breakdown-inputs">
                  <thead>
                    <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                      <th className={TH}>Item</th>
                      <th className={cn(TH, "text-right")}>Quantity</th>
                      <th className={cn(TH, "text-right")}>Per ha</th>
                      {hasPlanned && <th className={cn(TH, "text-right")}>Planned</th>}
                      {canSeePay && <th className={cn(TH, "text-right")}>Amount</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {data.inputs.map((i) => (
                      <tr key={i.item_code} data-testid={`input-${i.item_code}`} className="border-b border-[var(--sd-line-soft)] last:border-0">
                        <td className="px-2 py-2">
                          <div className="text-[var(--sd-ink)]">{i.item_name || i.item_code}</div>
                          {i.item_group && <div className="text-[11px] text-[var(--sd-quiet)]">{i.item_group}</div>}
                        </td>
                        <td className={cn(TD, "text-right")}>{qty(i.qty, 2)} {i.uom}</td>
                        <td className={cn(TD, "text-right")} data-testid={`per-ha-${i.item_code}`}>
                          {i.per_ha != null ? `${qty(i.per_ha, 2)} ${i.uom}/ha` : "—"}
                        </td>
                        {hasPlanned && (
                          <td className={cn(TD, "text-right text-[var(--sd-muted)]")}>{i.planned_qty != null ? `${qty(i.planned_qty, 2)} ${i.uom}` : "—"}</td>
                        )}
                        {canSeePay && <td className={cn(TD, "text-right")}>{kes(i.amount)}</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            <Section title="Other expenses by account" hint="Other ledger expenses posted to this cost centre.">
              {data.other.length === 0 ? (
                <Empty>No other expenses in this period.</Empty>
              ) : (
                <table className="w-full text-[13px]" data-testid="breakdown-other">
                  <tbody>
                    {data.other.map((o) => (
                      <tr key={o.account} className="border-b border-[var(--sd-line-soft)] last:border-0">
                        <td className="px-2 py-2 text-[var(--sd-ink)]">{o.account}</td>
                        {canSeePay && <td className={cn(TD, "text-right")}>{kes(o.amount)}</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            {canSeePay && (
              <Section title="Totals" hint="Over the period.">
                <table className="w-full text-[13px]" data-testid="breakdown-totals">
                  <tbody>
                    {(
                      [
                        ["Labour", data.totals.labour],
                        ["Inputs", data.totals.inputs],
                        ["Other", data.totals.other],
                      ] as const
                    ).map(([label, v]) => (
                      <tr key={label} className="border-b border-[var(--sd-line-soft)]">
                        <td className="px-2 py-2 text-[var(--sd-muted)]">{label}</td>
                        <td className={cn(TD, "text-right")}>{kes(v)}</td>
                      </tr>
                    ))}
                    <tr className="font-medium text-[var(--sd-ink)]">
                      <td className="px-2 py-2">Total</td>
                      <td className={cn(TD, "text-right")}>{kes(data.totals.total)}</td>
                    </tr>
                  </tbody>
                </table>
              </Section>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
