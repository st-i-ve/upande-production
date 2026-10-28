import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { RowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { q } from "@/components/plan/fmt";
import { kes } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { valueAdderSummary, type GroupBy, type ValueAdderSummaryRow } from "@/lib/api";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { addDays } from "@/components/plan/fmt";
import { cn, todayISO, parseYmd, ymd } from "@/lib/utils";

const CARD = "rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)]";
const PILL_DATE =
  "h-7 rounded-full border-0 bg-transparent px-2.5 shadow-none hover:bg-[var(--sd-bg-soft)] hover:shadow-none";

function csvCell(v: unknown): string {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Who did how much, for how long, and what it cost. */
export function ValueAdders() {
  const crop = useCurrentCrop();
  const { boot } = crop;
  const canPay = boot.can_see_pay;
  const [groupBy, setGroupBy] = useState<GroupBy>("employee");
  const [to, setTo] = useState(todayISO);
  const [from, setFrom] = useState(() => ymd(addDays(parseYmd(todayISO())!, -28)));
  const [rows, setRows] = useState<ValueAdderSummaryRow[]>([]);
  const [totalPay, setTotalPay] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const unitWord = crop.unit_label || "Block";
  const groupOptions = [
    { value: "employee", label: "By person" },
    { value: "day", label: "By day" },
    { value: "unit", label: `By ${unitWord.toLowerCase()}` },
  ];
  const keyHeader = groupBy === "employee" ? "Person" : groupBy === "day" ? "Day" : unitWord;

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    void valueAdderSummary(crop.name, from, to, groupBy).then((r) => {
      if (!live) return;
      if (isError(r)) setError(r.error);
      else {
        setRows(r.rows);
        setTotalPay(r.total_pay);
      }
      setLoading(false);
    });
    return () => {
      live = false;
    };
  }, [crop.name, from, to, groupBy, tick]);

  const totals = useMemo(
    () => ({
      hours: rows.reduce((s, r) => s + r.hours, 0),
      entries: rows.reduce((s, r) => s + r.entries, 0),
    }),
    [rows],
  );

  function exportCsv() {
    const head = [keyHeader, "Hours", ...(canPay ? ["Pay"] : []), "Entries"];
    const lines = [head, ...rows.map((r) => [r.label, r.hours, ...(canPay ? [r.pay_value ?? ""] : []), r.entries])];
    if (rows.length) lines.push(["Total", totals.hours, ...(canPay ? [totalPay ?? ""] : []), totals.entries]);
    const blob = new Blob([lines.map((l) => l.map(csvCell).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `value-adders-${from}-to-${to}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const num = "px-4 py-2.5 text-right tabular-nums";
  const actions = (
    <>
      <FilterSelect value={groupBy} options={groupOptions} onChange={(v) => setGroupBy(v as GroupBy)} aria-label="Group by" />
      <div className="inline-flex h-9 items-center gap-0.5 rounded-full bg-[var(--sd-card)] px-1 text-[var(--sd-quiet)] shadow-[var(--sd-shadow-1)] ring-1 ring-border/60">
        <DatePicker
          value={from}
          max={to}
          className={PILL_DATE}
          aria-label="From"
          onChange={setFrom}
        />
        <span aria-hidden>→</span>
        <DatePicker
          value={to}
          min={from}
          className={PILL_DATE}
          aria-label="To"
          onChange={setTo}
        />
      </div>
      <Button variant="outline" onClick={exportCsv} disabled={!rows.length}>
        <Download className="h-4 w-4" strokeWidth={1.75} />
        Export CSV
      </Button>
    </>
  );

  return (
    <PageShell
      title="Value Adders"
      eyebrow={crop.name}
      actions={actions}
      description="Work done and pay figures for casual value adders."
    >
      <div className={cn(CARD, "overflow-hidden")}>
        {loading ? (
          <div className="px-4 py-4">
            <RowsSkeleton rows={6} />
          </div>
        ) : error ? (
          <div className="flex flex-col items-start gap-3 px-5 py-6 text-[13px] text-[var(--sd-muted)]">
            {error}
            <Button variant="outline" onClick={() => setTick((t) => t + 1)}>
              Try again
            </Button>
          </div>
        ) : !rows.length ? (
          <p className="px-5 py-8 text-[13px] text-[var(--sd-muted)]">
            No value adder work was recorded between these dates.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className={cn("border-b border-[var(--sd-line)] text-[10.5px] font-medium uppercase tracking-[0.12em] text-[var(--sd-quiet)]")}>
                  <th className="px-4 py-2.5 text-left font-medium">{keyHeader}</th>
                  <th className={cn(num, "font-medium")}>Hours</th>
                  {canPay && <th className={cn(num, "font-medium")}>Pay</th>}
                  <th className={cn(num, "font-medium")}>Entries</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--sd-line-soft)]">
                {rows.map((r) => (
                  <tr key={r.key}>
                    <td className="px-4 py-2.5 text-[var(--sd-ink)]">{r.label}</td>
                    <td className={num}>{q(r.hours)}</td>
                    {canPay && <td className={num}>{kes(r.pay_value)}</td>}
                    <td className={num}>{r.entries}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-[var(--sd-line)] font-semibold text-[var(--sd-ink)]">
                  <td className="px-4 py-3">Total</td>
                  <td className={num}>{q(totals.hours)}</td>
                  {canPay && <td className={num}>{kes(totalPay)}</td>}
                  <td className={num}>{totals.entries}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </PageShell>
  );
}
