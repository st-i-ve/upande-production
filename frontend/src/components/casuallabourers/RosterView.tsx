import { useEffect, useMemo, useState } from "react";
import { Download, UserPlus } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { RowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { SearchInput } from "@/components/SearchInput";
import { ToolbarButton } from "@/components/ToolbarButton";
import { AddLabourersDialog } from "@/components/casuallabourers/AddLabourersDialog";
import { LabourerCard } from "@/components/casuallabourers/LabourerCard";
import { LabourerDialog } from "@/components/casuallabourers/LabourerDialog";
import { weeklySeries } from "@/components/casuallabourers/series";
import { EmptyNote } from "@/components/overview/Panel";
import { addDays, rowDate } from "@/components/plan/fmt";
import { formatUoms, kes } from "@/lib/format";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { listLabourers, type RosterDay, type RosterRow, type RosterTotals } from "@/lib/labourers-api";
import { matchesQuery, parseYmd, todayISO, ymd } from "@/lib/utils";

const defaultRange = (): DateRange => ({ from: ymd(addDays(parseYmd(todayISO())!, -28)), to: todayISO() });

function csvCell(v: unknown): string {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
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
  const [supervisor, setSupervisor] = useState("");
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
        .filter((r) => !supervisor || r.supervisor === supervisor)
        .filter((r) => matchesQuery(`${r.employee_name} ${r.employee} ${r.crew ?? ""} ${r.supervisor_name ?? ""}`, query))
        .sort((a, b) => b.days_worked - a.days_worked || a.employee_name.localeCompare(b.employee_name)),
    [rows, status, department, designation, supervisor, query],
  );
  // One entry per supervisor id on the roster (inactive ones included); two people with one name stay apart.
  const supervisors = useMemo(() => {
    const byId = new Map<string, string>();
    for (const r of rows ?? []) if (r.supervisor) byId.set(r.supervisor, r.supervisor_name || r.supervisor);
    const names = [...byId.values()];
    return [...byId]
      .map(([value, name]) => ({ value, label: names.filter((n) => n === name).length > 1 ? `${name} (${value})` : name }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [rows]);
  const departments = useMemo(() => [...new Set((rows ?? []).map((r) => r.department).filter(Boolean) as string[])].sort(), [rows]);
  const designations = useMemo(() => [...new Set((rows ?? []).map((r) => r.designation).filter(Boolean) as string[])].sort(), [rows]);
  const waiting = firstLoad(loading, !!rows);
  const dirty = !!query || status !== "1" || !!department || !!designation || !!supervisor || from !== defaultRange().from || to !== defaultRange().to;
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
      {supervisors.length > 0 && <FilterSelect label="Supervisor" value={supervisor} onChange={setSupervisor} options={supervisors} allLabel="All supervisors" />}
      <SearchInput size="md" value={query} onChange={setQuery} placeholder="Search" className="w-44" />
      <ClearFiltersPill
        active={dirty}
        onClear={() => {
          setQuery("");
          setStatus("1");
          setDepartment("");
          setDesignation("");
          setSupervisor("");
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

      <h2 className="mb-1 mt-4 text-[13px] font-semibold text-[var(--sd-ink)]">Roster</h2>
      <p className="mb-3 text-[12px] text-[var(--sd-quiet)]">
        {rowDate(from)} to {rowDate(to)}. Open a person for their KPIs, targets and paid status.
      </p>
      {error ? (
        <div className="flex flex-col items-start gap-3 text-[13px] text-[var(--sd-muted)]">
          {error}
          <ToolbarButton onClick={() => setTick((t) => t + 1)}>Try again</ToolbarButton>
        </div>
      ) : waiting ? (
        <RowsSkeleton rows={4} />
      ) : !shown.length ? (
        <EmptyNote>
          {rows && rows.length
            ? "No labourers match these filters."
            : "No casual labourers on the roster yet. Use Add labourers to choose them from the Employee list."}
        </EmptyNote>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((r) => (
            <LabourerCard key={r.employee} row={r} canPay={canPay} accent={accent} onOpen={() => setOpen(r)} />
          ))}
        </div>
      )}

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
