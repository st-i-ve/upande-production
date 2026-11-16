import { useCallback, useEffect, useState } from "react";
import { Lock, Plus } from "lucide-react";
import { FilterSelect } from "@/components/FilterSelect";
import { TableRowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ToolbarButton } from "@/components/ToolbarButton";
import { NewPayRunDialog } from "@/components/labourpay/NewPayRunDialog";
import { PayRunDialog, StatusChip } from "@/components/labourpay/PayRunDialog";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import { useCurrentCrop } from "@/lib/crops";
import { kes, shortDate } from "@/lib/format";
import { isError } from "@/lib/frappe";
import { listPayRuns, type PayRunDetail, type PayRunSummary } from "@/lib/labourpay-api";
import { useLabourMode } from "@/lib/use-labour-mode";

const STATUSES = ["Draft", "Approved", "Paid", "Cancelled"];
const TH = "px-4 py-2.5 font-medium";
const NUM = "px-4 py-2.5 text-right tabular-nums";

/**
 * Built-in pay runs: gather a period's approved work, approve it, then mark it paid. When Work
 * Management drives labour, pay is handled there and this page only lists what exists.
 */
export function PayRuns() {
  const crop = useCurrentCrop();
  const canSeePay = crop.boot.can_see_pay;
  const canManage = crop.boot.can_manage;
  const mode = useLabourMode();
  const wm = !!mode?.wm_active;
  const [status, setStatus] = useState("");
  const [runs, setRuns] = useState<PayRunSummary[] | null>(null);
  const [period, setPeriod] = useState<{ from_date: string; to_date: string } | null>(null);
  const [payDay, setPayDay] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<{ name: string; initial?: PayRunDetail } | null>(null);

  useEffect(() => {
    if (!canSeePay) return;
    let live = true;
    setLoading(true);
    setError(null);
    void listPayRuns(status || undefined, 100).then((r) => {
      if (!live) return;
      setLoading(false);
      if (isError(r)) return void setError(r.error);
      setRuns(r.runs);
      setPeriod(r.default_period);
      setPayDay(r.pay_day);
    });
    return () => {
      live = false;
    };
  }, [canSeePay, status, tick]);

  const changed = useCallback(() => setTick((t) => t + 1), []);
  const waiting = firstLoad(loading, !!runs);

  const actions = canSeePay ? (
    <>
      <FilterSelect label="Status" value={status} onChange={setStatus} options={STATUSES} allLabel="All statuses" />
      {canManage && !wm && (
        <ToolbarButton onClick={() => setCreating(true)} disabled={!period}>
          <Plus className="h-4 w-4" strokeWidth={1.75} />
          New pay run
        </ToolbarButton>
      )}
      <RefreshButton onClick={changed} loading={loading} label="pay runs" />
    </>
  ) : undefined;

  return (
    <PageShell
      title="Pay runs"
      eyebrow={crop.name}
      actions={actions}
      description={`Casual labour pay, gathered from approved work for a period${payDay ? `. Pay day is ${payDay}` : ""}.`}
    >
      {!canSeePay ? (
        <div role="note" className="flex items-center gap-2.5 rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-info)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          <Lock className="h-4 w-4 shrink-0 text-[var(--sd-quiet)]" />
          Pay runs are only shown to people who can see pay.
        </div>
      ) : (
        <>
          {wm && (
            <div role="note" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-info)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
              Pay is handled in Work Management. <a className="underline" href="/work-payment">Open Work Payment</a>
            </div>
          )}
          <Panel title="Pay runs" hint="Open a run for its lines, then approve it and mark it paid." bodyClassName="px-0 pb-2">
            {error ? (
              <div className="flex flex-col items-start gap-3 px-5 py-4 text-[13px] text-[var(--sd-muted)]">
                {error}
                <ToolbarButton onClick={changed}>Try again</ToolbarButton>
              </div>
            ) : !waiting && !runs?.length ? (
              <div className="px-5">
                <EmptyNote>{status ? `No ${status.toLowerCase()} pay runs.` : "No pay runs yet. Use New pay run to gather a period's approved work."}</EmptyNote>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-[var(--sd-line)] text-left text-[10.5px] uppercase tracking-[0.12em] text-[var(--sd-quiet)]">
                      <th className={TH}>Pay run</th>
                      <th className={TH}>Period</th>
                      <th className={TH}>Farm</th>
                      <th className={TH}>Status</th>
                      <th className={`${NUM} font-medium`}>People</th>
                      <th className={`${NUM} font-medium`}>Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--sd-line-soft)]">
                    {waiting ? (
                      <TableRowsSkeleton cols={6} rows={5} />
                    ) : (
                      runs!.map((r) => (
                        <tr key={r.name} onClick={() => setOpen({ name: r.name })} className="cursor-pointer transition-colors hover:bg-[var(--sd-bg-soft)]">
                          <td className="px-4 py-2.5 font-medium text-[var(--sd-ink)]">{r.name}</td>
                          <td className="px-4 py-2.5 tabular-nums">{shortDate(r.from_date)} to {shortDate(r.to_date)}</td>
                          <td className="px-4 py-2.5 text-[var(--sd-muted)]">{r.farm || "All farms"}</td>
                          <td className="px-4 py-2.5"><StatusChip status={r.status} /></td>
                          <td className={NUM}>{r.total_people}</td>
                          <td className={NUM}>{kes(r.total_amount)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
      {creating && period && (
        <NewPayRunDialog
          period={period}
          farms={crop.boot.farms ?? []}
          onClose={() => setCreating(false)}
          onCreated={(run) => {
            setCreating(false);
            changed();
            setOpen({ name: run.name, initial: run });
          }}
        />
      )}
      {open && <PayRunDialog name={open.name} initial={open.initial} readOnly={wm || !canManage} onClose={() => setOpen(null)} onChanged={changed} />}
    </PageShell>
  );
}
