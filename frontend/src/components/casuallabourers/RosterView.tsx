import { useEffect, useMemo, useState } from "react";
import { Download, UserPlus } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { TableRowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { SearchInput } from "@/components/SearchInput";
import { ToolbarButton } from "@/components/ToolbarButton";
import { AddLabourersDialog } from "@/components/casuallabourers/AddLabourersDialog";
import { LabourerDialog } from "@/components/casuallabourers/LabourerDialog";
import { weeklySeries } from "@/components/casuallabourers/series";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import { addDays, rowDate } from "@/components/plan/fmt";
import { formatUoms, kes } from "@/lib/format";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { listLabourers, type RosterDay, type RosterRow, type RosterTotals } from "@/lib/labourers-api";
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

/** The Labourers tab: the casual labour roster with each person's KPIs over the period. Add people
 *  from the Employee list; open one for the full picture, targets and paid status. */
export function RosterView({ tabs }: { tabs?: React.ReactNode }) {
  const crop = useCurrentCrop();
  const canPay = crop.boot.can_see_pay;
  const accent = crop.accent_color || "#3f7d3a";
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("1");
  const [department, setDepartment] = useState("");
  const [designation, setDesignation] = useState("");
  const [rows, setRows] = useState<RosterRow[] | null>(null);
  const [days, setDays] = useState<RosterDay[]>([]);
  const [totals, setTotals] = useState<RosterTotals | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState<RosterRow | null>(null);
  const [adding, setAdding] = useState(false);
  const { from, to } = range;

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    void listLabourers(crop.name, from, to).then((r) => {
      if (!live) return;
      setLoading(false);
      if (isError(r)) {
        setError(r.error);
        return;
      }
      setRows(r.rows);
      setDays(r.days);
      setTotals(r.totals);
    });
    return () => {
      live = false;
    };
  }, [crop.name, from, to, tick]);

  const shown = useMemo(
    () =>
      (rows ?? [])
        .filter((r) => (status === "" ? true : String(r.active) === status))
        .filter((r) => !department || r.department === department)
        .filter((r) => !designation || r.designation === designation)
        .filter((r) => matchesQuery(`${r.employee_name} ${r.employee} ${r.crew ?? ""} ${r.supervisor_name ?? ""}`, query))
        .sort((a, b) => b.days_worked - a.days_worked || a.employee_name.localeCompare(b.employee_name)),
    [rows, status, department, designation, query],
  );
  const departments = useMemo(() => [...new Set((rows ?? []).map((r) => r.department).filter(Boolean) as string[])].sort(), [rows]);
  const designations = useMemo(() => [...new Set((rows ?? []).map((r) => r.designation).filter(Boolean) as string[])].sort(), [rows]);
  const waiting = firstLoad(loading, !!rows);
  const dirty = !!query || status !== "1" || !!department || !!designation || from !== defaultRange().from || to !== defaultRange().to;
  const hit = totals?.hit_rate;

  function exportCsv() {
    const head = ["Labourer", "Employee", "Active", "Crew", "Supervisor", "Days worked", "Quantity", "Target hit rate %", ...(canPay ? ["Pay", "Unpaid"] : [])];
    const lines = [
      head,
      ...shown.map((r) => [
        r.employee_name, r.employee, r.active ? "Yes" : "No", r.crew ?? "", r.supervisor_name ?? "", r.days_worked,
        formatUoms(r.qty_by_uom), r.hit_rate ?? "", ...(canPay ? [r.pay_value ?? "", r.unpaid_value ?? ""] : []),
      ]),
    ];
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
      <FilterSelect
        label="Status"
        value={status}
        onChange={setStatus}
        options={[
          { value: "1", label: "Active" },
          { value: "0", label: "Inactive" },
        ]}
        allLabel="All labourers"
      />
      {departments.length > 0 && <FilterSelect label="Department" value={department} onChange={setDepartment} options={departments} allLabel="All departments" />}
      {designations.length > 0 && <FilterSelect label="Designation" value={designation} onChange={setDesignation} options={designations} allLabel="All designations" />}
      <SearchInput size="md" value={query} onChange={setQuery} placeholder="Search" className="w-44" />
      <ClearFiltersPill
        active={dirty}
        onClear={() => {
          setQuery("");
          setStatus("1");
          setDepartment("");
          setDesignation("");
          setRange(defaultRange());
        }}
      />
      <ToolbarButton onClick={() => setAdding(true)}>
        <UserPlus className="h-4 w-4" strokeWidth={1.75} />
        Add labourers
      </ToolbarButton>
      <ToolbarButton onClick={exportCsv} disabled={!shown.length}>
        <Download className="h-4 w-4" strokeWidth={1.75} />
        Export CSV
      </ToolbarButton>
      <RefreshButton onClick={() => setTick((t) => t + 1)} loading={loading} label="casual labourers" />
    </>
  );

  return (
    <PageShell
      title="Casual Labourers"
      eyebrow={crop.name}
      actions={actions}
      tabs={tabs}
      description="The casual labour roster with each person's work against their daily targets. Pay is per unit of work."
    >
      <KpiGrid cols={4}>
        <KpiCard
          label="Casual labourers"
          value={totals ? totals.active : "—"}
          hint={totals ? `${totals.working} worked in this period, ${totals.labourers} on the roster` : undefined}
          loading={waiting}
        />
        <KpiCard
          label="Days worked"
          value={totals ? totals.days_worked : "—"}
          hint="person-days with approved work"
          series={weeklySeries(days, (r) => r.labourers)}
          goodDirection="up"
          loading={waiting}
        />
        <KpiCard
          label="Target hit rate"
          value={hit == null ? "—" : `${hit}%`}
          hint={totals?.target_days ? `of ${totals.target_days} person-days with a daily target` : "no daily targets set yet"}
          tone={hit == null ? "default" : hit >= 80 ? "good" : hit >= 50 ? "warning" : "critical"}
          loading={waiting}
        />
        {canPay && (
          <KpiCard
            label="Unpaid"
            value={kes(totals?.unpaid_value)}
            hint={totals ? `of ${kes(totals.pay_value)} earned, awaiting payroll` : undefined}
            tone={totals?.unpaid_value ? "warning" : "default"}
            series={weeklySeries(days, (r) => r.pay_value ?? 0)}
            loading={waiting}
          />
        )}
      </KpiGrid>

      <Panel
        className="mt-4"
        title="Roster"
        hint={`${rowDate(from)} to ${rowDate(to)}. Open a person for their KPIs, targets and paid status.`}
        bodyClassName="px-0 pb-2"
      >
        {error ? (
          <div className="flex flex-col items-start gap-3 px-5 py-4 text-[13px] text-[var(--sd-muted)]">
            {error}
            <ToolbarButton onClick={() => setTick((t) => t + 1)}>Try again</ToolbarButton>
          </div>
        ) : !waiting && !shown.length ? (
          <div className="px-5">
            <EmptyNote>
              {rows && rows.length
                ? "No labourers match these filters."
                : "No casual labourers on the roster yet. Use Add labourers to choose them from the Employee list."}
            </EmptyNote>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--sd-line)] text-left text-[10.5px] uppercase tracking-[0.12em] text-[var(--sd-quiet)]">
                  <th className={cn(TH, "w-10")}>#</th>
                  <th className={TH}>Labourer</th>
                  <th className={TH}>Crew / supervisor</th>
                  <th className={cn(NUM, "font-medium")}>Days</th>
                  <th className={cn(NUM, "font-medium")}>Quantity</th>
                  <th className={cn(TH, "w-[16%]")}>Target hit rate</th>
                  {canPay && <th className={cn(NUM, "font-medium")}>Pay</th>}
                  {canPay && <th className={cn(NUM, "font-medium")}>Unpaid</th>}
                  <th className={TH}>Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--sd-line-soft)]">
                {waiting ? (
                  <TableRowsSkeleton cols={canPay ? 9 : 7} rows={6} />
                ) : (
                  shown.map((r, i) => (
                    <tr
                      key={r.employee}
                      onClick={() => setOpen(r)}
                      className="cursor-pointer transition-colors hover:bg-[var(--sd-bg-soft)]"
                    >
                      <td className="px-4 py-2.5 tabular-nums text-[var(--sd-quiet)]">{i + 1}</td>
                      <td className="px-4 py-2.5 text-[var(--sd-ink)]">
                        <span className="flex items-center gap-2.5">
                          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--sd-pistachio)] text-[10.5px] font-semibold">
                            {initials(r.employee_name)}
                          </span>
                          <span>
                            <span className="block font-medium">{r.employee_name}</span>
                            <span className="block text-[11px] text-[var(--sd-quiet)]">
                              {[r.designation, r.department].filter(Boolean).join(" · ") || r.employee}
                              {r.overrides > 0 ? ` · ${r.overrides} own target${r.overrides === 1 ? "" : "s"}` : ""}
                            </span>
                          </span>
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-[var(--sd-muted)]">{[r.crew, r.supervisor_name].filter(Boolean).join(" · ") || "—"}</td>
                      <td className={NUM}>{r.days_worked}</td>
                      <td className={cn(NUM, "whitespace-normal")}>{formatUoms(r.qty_by_uom) || "—"}</td>
                      <td className="px-4 py-2.5">
                        {r.hit_rate == null ? (
                          <span className="text-[var(--sd-quiet)]">—</span>
                        ) : (
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--sd-bg-soft)]">
                              <div
                                className="h-full rounded-full"
                                style={{ width: `${Math.min(100, r.hit_rate)}%`, background: r.hit_rate >= 50 ? accent : "var(--sd-amber)" }}
                              />
                            </div>
                            <span className="w-11 text-right tabular-nums">{r.hit_rate}%</span>
                          </div>
                        )}
                      </td>
                      {canPay && <td className={NUM}>{kes(r.pay_value)}</td>}
                      {canPay && (
                        <td className={cn(NUM, r.unpaid_value ? "text-[var(--sd-amber)]" : "text-[var(--sd-quiet)]")}>{kes(r.unpaid_value)}</td>
                      )}
                      <td className="px-4 py-2.5">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[11.5px] font-medium",
                            r.active ? "bg-[var(--sd-pistachio)] text-[var(--sd-ink)]" : "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
                          )}
                        >
                          {r.active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {open && (
        <LabourerDialog
          crop={crop.name}
          employee={open.employee}
          name={open.employee_name}
          from={from}
          to={to}
          canPay={canPay}
          accent={accent}
          onClose={() => setOpen(null)}
          onChanged={() => setTick((t) => t + 1)}
        />
      )}
      <AddLabourersDialog open={adding} onOpenChange={setAdding} onAdded={() => setTick((t) => t + 1)} />
    </PageShell>
  );
}
