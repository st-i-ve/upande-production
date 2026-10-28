import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { TableRowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { SearchInput } from "@/components/SearchInput";
import { ToolbarButton } from "@/components/ToolbarButton";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import { q } from "@/components/plan/fmt";
import { PersonDetail } from "@/components/valueadders/PersonDetail";
import { weeklySeries } from "@/components/valueadders/series";
import { formatUoms, kes, mergeUoms } from "@/lib/format";
import { valueAdderSummary, type GroupBy, type ValueAdderSummaryRow } from "@/lib/api";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { addDays, rowDate } from "@/components/plan/fmt";
import { cn, matchesQuery, parseYmd, todayISO, ymd } from "@/lib/utils";

const TH = "px-4 py-2.5 font-medium";
const NUM = "px-4 py-2.5 text-right tabular-nums";

const defaultRange = (): DateRange => ({ from: ymd(addDays(parseYmd(todayISO())!, -28)), to: todayISO() });

function csvCell(v: unknown): string {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

/** Who did how much, for how long, and what it cost: a ranked roster with a
 *  per-person detail panel. */
export function ValueAdders() {
  const crop = useCurrentCrop();
  const { boot } = crop;
  const canPay = boot.can_see_pay;
  const accent = crop.accent_color || "#3f7d3a";
  const [groupBy, setGroupBy] = useState<GroupBy>("employee");
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [query, setQuery] = useState("");
  const [people, setPeople] = useState<ValueAdderSummaryRow[] | null>(null);
  const [days, setDays] = useState<ValueAdderSummaryRow[]>([]);
  const [grouped, setGrouped] = useState<ValueAdderSummaryRow[] | null>(null);
  const [totalPay, setTotalPay] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState<ValueAdderSummaryRow | null>(null);
  const { from, to } = range;

  const unitWord = crop.unit_label || "Block";
  const groupOptions = [
    { value: "employee", label: "By person" },
    { value: "day", label: "By day" },
    { value: "unit", label: `By ${unitWord.toLowerCase()}` },
  ];
  const keyHeader = groupBy === "employee" ? "Person" : groupBy === "day" ? "Day" : unitWord;

  // The roster and the day series feed the KPIs whatever the grouping is.
  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    const need = (g: GroupBy) => valueAdderSummary(crop.name, from, to, g);
    void Promise.all([need("employee"), need("day"), groupBy === "unit" ? need("unit") : Promise.resolve(null)]).then(
      ([e, d, u]) => {
        if (!live) return;
        setLoading(false);
        const bad = [e, d, u].find((r) => r && isError(r));
        if (bad && isError(bad)) {
          setError(bad.error);
          return;
        }
        if (isError(e) || isError(d)) return;
        setPeople(e.rows);
        setDays(d.rows);
        setTotalPay(e.total_pay);
        setGrouped(u && !isError(u) ? u.rows : null);
      },
    );
    return () => {
      live = false;
    };
  }, [crop.name, from, to, groupBy, tick]);

  const rows = useMemo(() => {
    const base = groupBy === "employee" ? people : groupBy === "day" ? days : grouped;
    const list = (base ?? []).filter((r) => matchesQuery(r.label, query));
    // People and units rank by hours; days read in order, newest first.
    return groupBy === "day" ? [...list].reverse() : [...list].sort((a, b) => b.hours - a.hours);
  }, [groupBy, people, days, grouped, query]);

  const totals = useMemo(
    () => ({
      hours: (people ?? []).reduce((s, r) => s + r.hours, 0),
      qty: mergeUoms((people ?? []).map((r) => r.qty_by_uom)),
      entries: (people ?? []).reduce((s, r) => s + r.entries, 0),
    }),
    [people],
  );
  const maxHours = Math.max(1, ...rows.map((r) => r.hours));
  const dirty = !!query || groupBy !== "employee" || from !== defaultRange().from || to !== defaultRange().to;
  const waiting = firstLoad(loading, !!people);

  function exportCsv() {
    const head = [keyHeader, "Hours", "Qty", ...(canPay ? ["Pay"] : []), "Entries"];
    const lines = [head, ...rows.map((r) => [r.label, r.hours, formatUoms(r.qty_by_uom), ...(canPay ? [r.pay_value ?? ""] : []), r.entries])];
    if (rows.length) lines.push(["Total", totals.hours, formatUoms(totals.qty), ...(canPay ? [totalPay ?? ""] : []), totals.entries]);
    const blob = new Blob([lines.map((l) => l.map(csvCell).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `value-adders-${from}-to-${to}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const actions = (
    <>
      <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
      <FilterSelect label="Group by" value={groupBy} options={groupOptions} onChange={(v) => setGroupBy(v as GroupBy)} />
      <SearchInput size="md" value={query} onChange={setQuery} placeholder="Search" className="w-44" />
      <ClearFiltersPill
        active={dirty}
        onClear={() => {
          setQuery("");
          setGroupBy("employee");
          setRange(defaultRange());
        }}
      />
      <ToolbarButton onClick={exportCsv} disabled={!rows.length}>
        <Download className="h-4 w-4" strokeWidth={1.75} />
        Export CSV
      </ToolbarButton>
      <RefreshButton onClick={() => setTick((t) => t + 1)} loading={loading} label="value adders" />
    </>
  );

  const top = people && people.length ? [...people].sort((a, b) => b.hours - a.hours)[0] : null;

  return (
    <PageShell
      title="Value Adders"
      eyebrow={crop.name}
      actions={actions}
      description="Work done and pay figures for casual value adders."
    >
      <KpiGrid cols={4}>
        <KpiCard label="Value adders" value={people ? people.length : "—"} hint={top ? `most hours: ${top.label}` : "with approved work"} loading={waiting} />
        <KpiCard
          label="Hours"
          value={q(totals.hours)}
          hint={`${q(totals.entries)} entries`}
          series={weeklySeries(days, (r) => r.hours)}
          goodDirection="up"
          loading={waiting}
        />
        <KpiCard label="Quantity" value={formatUoms(totals.qty)} hint="per unit of measure, never added together" loading={waiting} />
        {canPay && (
          <KpiCard
            label="Total pay"
            value={kes(totalPay)}
            hint={totals.hours ? `${kes((totalPay ?? 0) / totals.hours)} per hour` : undefined}
            series={weeklySeries(days, (r) => r.pay_value ?? 0)}
            loading={waiting}
          />
        )}
      </KpiGrid>

      <Panel
        className="mt-4"
        title={groupBy === "employee" ? "Ranking" : `Work ${groupBy === "day" ? "by day" : `by ${unitWord.toLowerCase()}`}`}
        hint={`${rowDate(from)} to ${rowDate(to)}${groupBy === "employee" ? ". Open a person for their breakdown." : ""}`}
        bodyClassName="px-0 pb-2"
      >
        {error ? (
          <div className="flex flex-col items-start gap-3 px-5 py-4 text-[13px] text-[var(--sd-muted)]">
            {error}
            <ToolbarButton onClick={() => setTick((t) => t + 1)}>Try again</ToolbarButton>
          </div>
        ) : !waiting && !rows.length ? (
          <div className="px-5">
            <EmptyNote>No value adder work was recorded between these dates.</EmptyNote>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--sd-line)] text-left text-[10.5px] uppercase tracking-[0.12em] text-[var(--sd-quiet)]">
                  <th className={cn(TH, "w-10")}>#</th>
                  <th className={TH}>{keyHeader}</th>
                  <th className={cn(TH, "w-[22%]")}>Share of hours</th>
                  <th className={cn(NUM, "font-medium")}>Hours</th>
                  <th className={cn(NUM, "font-medium")}>Quantity</th>
                  {canPay && <th className={cn(NUM, "font-medium")}>Pay</th>}
                  <th className={cn(NUM, "font-medium")}>Entries</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--sd-line-soft)]">
                {waiting ? (
                  <TableRowsSkeleton cols={canPay ? 7 : 6} rows={6} />
                ) : (
                  rows.map((r, i) => {
                    const clickable = groupBy === "employee";
                    return (
                      <tr
                        key={r.key}
                        onClick={clickable ? () => setOpen(r) : undefined}
                        className={cn(clickable && "cursor-pointer transition-colors hover:bg-[var(--sd-bg-soft)]")}
                      >
                        <td className="px-4 py-2.5 tabular-nums text-[var(--sd-quiet)]">{groupBy === "day" ? "" : i + 1}</td>
                        <td className="px-4 py-2.5 text-[var(--sd-ink)]">
                          <span className="flex items-center gap-2.5">
                            {groupBy === "employee" && (
                              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--sd-pistachio)] text-[10.5px] font-semibold">
                                {initials(r.label)}
                              </span>
                            )}
                            <span className="font-medium">{groupBy === "day" ? rowDate(r.label) : r.label}</span>
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--sd-bg-soft)]">
                            <div
                              className="h-full rounded-full"
                              style={{ width: `${(r.hours / maxHours) * 100}%`, background: accent }}
                            />
                          </div>
                        </td>
                        <td className={NUM}>{q(r.hours)}</td>
                        <td className={cn(NUM, "whitespace-normal")}>{formatUoms(r.qty_by_uom)}</td>
                        {canPay && <td className={NUM}>{kes(r.pay_value)}</td>}
                        <td className={NUM}>{r.entries}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
              {!waiting && rows.length > 0 && (
                <tfoot>
                  <tr className="border-t border-[var(--sd-line)] font-semibold text-[var(--sd-ink)]">
                    <td className="px-4 py-3" />
                    <td className="px-4 py-3">Total</td>
                    <td />
                    <td className={NUM}>{q(totals.hours)}</td>
                    <td className={cn(NUM, "whitespace-normal")}>{formatUoms(totals.qty)}</td>
                    {canPay && <td className={NUM}>{kes(totalPay)}</td>}
                    <td className={NUM}>{totals.entries}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </Panel>

      {open && (
        <PersonDetail
          crop={crop.name}
          employee={open.key}
          name={open.label}
          from={from}
          to={to}
          canPay={canPay}
          onClose={() => setOpen(null)}
        />
      )}
    </PageShell>
  );
}
