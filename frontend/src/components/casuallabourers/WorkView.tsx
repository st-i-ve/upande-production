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
import { LabourerDialog } from "@/components/casuallabourers/LabourerDialog";
import { weeklySeries } from "@/components/casuallabourers/series";
import { formatUoms, kes, mergeUoms } from "@/lib/format";
import { casualLabourerSummary, type GroupBy, type CasualLabourerSummaryRow } from "@/lib/api";
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

/** The Work tab: who did how much and what it cost, by person, day or block. A person opens the
 *  labourer modal. Pay is per unit of work; there is no hourly pay. */
export function WorkView({ tabs }: { tabs?: React.ReactNode }) {
  const crop = useCurrentCrop();
  const { boot } = crop;
  const canPay = boot.can_see_pay;
  const accent = crop.accent_color || "#3f7d3a";
  const [groupBy, setGroupBy] = useState<GroupBy>("employee");
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [query, setQuery] = useState("");
  const [people, setPeople] = useState<CasualLabourerSummaryRow[] | null>(null);
  const [days, setDays] = useState<CasualLabourerSummaryRow[]>([]);
  const [grouped, setGrouped] = useState<CasualLabourerSummaryRow[] | null>(null);
  const [totalPay, setTotalPay] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState<CasualLabourerSummaryRow | null>(null);
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
    const need = (g: GroupBy) => casualLabourerSummary(crop.name, from, to, g);
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
    // People and units rank by days worked, then entries; days read in order, newest first.
    return groupBy === "day" ? [...list].reverse() : [...list].sort((a, b) => b.days - a.days || b.entries - a.entries);
  }, [groupBy, people, days, grouped, query]);

  const totals = useMemo(
    () => ({
      days: (people ?? []).reduce((s, r) => s + r.days, 0),
      qty: mergeUoms((people ?? []).map((r) => r.qty_by_uom)),
      entries: (people ?? []).reduce((s, r) => s + r.entries, 0),
    }),
    [people],
  );
  const maxEntries = Math.max(1, ...rows.map((r) => r.entries));
  const dirty = !!query || groupBy !== "employee" || from !== defaultRange().from || to !== defaultRange().to;
  const waiting = firstLoad(loading, !!people);

  function exportCsv() {
    const head = [keyHeader, "Days", "Qty", ...(canPay ? ["Pay"] : []), "Entries"];
    const lines = [head, ...rows.map((r) => [r.label, r.days, formatUoms(r.qty_by_uom), ...(canPay ? [r.pay_value ?? ""] : []), r.entries])];
    if (rows.length) lines.push(["Total", totals.days, formatUoms(totals.qty), ...(canPay ? [totalPay ?? ""] : []), totals.entries]);
    const blob = new Blob([lines.map((l) => l.map(csvCell).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `casual-labourers-${from}-to-${to}.csv`;
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
      <RefreshButton onClick={() => setTick((t) => t + 1)} loading={loading} label="casual labourers" />
    </>
  );

  const top = people && people.length ? [...people].sort((a, b) => b.days - a.days)[0] : null;

  return (
    <PageShell
      title="Casual Labourers"
      eyebrow={crop.name}
      actions={actions}
      tabs={tabs}
      description="Work done and pay figures for casual labourers. Pay is per unit of work."
    >
      <KpiGrid cols={4}>
        <KpiCard label="Casual labourers" value={people ? people.length : "—"} hint={top ? `most days: ${top.label}` : "with approved work"} loading={waiting} />
        <KpiCard
          label="Entries"
          value={q(totals.entries)}
          hint={`${q(totals.days)} person-days`}
          series={weeklySeries(days, (r) => r.entries)}
          goodDirection="up"
          loading={waiting}
        />
        <KpiCard label="Quantity" value={formatUoms(totals.qty)} hint="per unit of measure, never added together" loading={waiting} />
        {canPay && (
          <KpiCard
            label="Total pay"
            value={kes(totalPay)}
            hint={totals.entries ? `${kes((totalPay ?? 0) / totals.entries)} per entry` : undefined}
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
            <EmptyNote>No casual labour work was recorded between these dates.</EmptyNote>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--sd-line)] text-left text-[10.5px] uppercase tracking-[0.12em] text-[var(--sd-quiet)]">
                  <th className={cn(TH, "w-10")}>#</th>
                  <th className={TH}>{keyHeader}</th>
                  <th className={cn(TH, "w-[22%]")}>Share of entries</th>
                  <th className={cn(NUM, "font-medium")}>Days</th>
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
                              style={{ width: `${(r.entries / maxEntries) * 100}%`, background: accent }}
                            />
                          </div>
                        </td>
                        <td className={NUM}>{r.days}</td>
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
                    <td className={NUM}>{q(totals.days)}</td>
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
        <LabourerDialog
          crop={crop.name}
          employee={open.key}
          name={open.label}
          from={from}
          to={to}
          canPay={canPay}
          onClose={() => setOpen(null)}
          onChanged={() => setTick((t) => t + 1)}
        />
      )}
    </PageShell>
  );
}
