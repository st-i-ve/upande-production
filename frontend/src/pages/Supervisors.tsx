import { useEffect, useMemo, useState } from "react";
import { UserPlus } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { RowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { SearchInput } from "@/components/SearchInput";
import { ToolbarButton } from "@/components/ToolbarButton";
import { EmptyNote } from "@/components/overview/Panel";
import { SupervisorCard } from "@/components/supervisors/SupervisorCard";
import { SupervisorDialog } from "@/components/supervisors/SupervisorDialog";
import { SupervisorForm } from "@/components/supervisors/SupervisorForm";
import { WeekPicker } from "@/components/WeekPicker";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { assistantsWithoutManager, listSupervisors, type AssistantWithoutManager, type SupervisorCard as Card, type SupervisorDetail } from "@/lib/supervisors-api";
import { matchesQuery } from "@/lib/utils";
import { currentIsoWeek, type IsoWeek } from "@/lib/weeks";

/** Supervisors: a card per Production Supervisor with this week's blocks, tasks, crew and approvals.
 *  Open one for the detail; managers add and edit supervisors here. */
export function Supervisors() {
  const crop = useCurrentCrop();
  const canManage = !!(crop.boot.can_manage ?? crop.boot.can_plan);
  const [week, setWeek] = useState<IsoWeek>(currentIsoWeek);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("1");
  const [cards, setCards] = useState<Card[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [orphans, setOrphans] = useState<AssistantWithoutManager[]>([]);
  const [open, setOpen] = useState<Card | null>(null);
  const [form, setForm] = useState<{ existing: SupervisorDetail["supervisor"] | null } | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    void listSupervisors(crop.name, week.year, week.week).then((r) => {
      if (!live) return;
      setLoading(false);
      if (isError(r)) setError(r.error);
      else setCards(r);
    });
    return () => {
      live = false;
    };
  }, [crop.name, week.year, week.week, tick]);

  // Managers see which assistant managers have no manager: their work goes to every manager until it is set.
  useEffect(() => {
    if (!canManage) return;
    let live = true;
    void assistantsWithoutManager().then((r) => {
      if (live && !isError(r)) setOrphans(r);
    });
    return () => {
      live = false;
    };
  }, [canManage, tick]);

  const shown = useMemo(
    () =>
      (cards ?? [])
        .filter((c) => (status === "" ? true : String(c.active ? 1 : 0) === status))
        .filter((c) => matchesQuery(`${c.employee_name} ${c.employee} ${c.phone ?? ""} ${c.farm ?? ""}`, query)),
    [cards, status, query],
  );
  const waiting = firstLoad(loading, !!cards);
  const dirty = !!query || status !== "1";
  const reload = () => setTick((t) => t + 1);

  const actions = (
    <>
      <WeekPicker value={week} onChange={setWeek} />
      <FilterSelect
        label="Status"
        value={status}
        onChange={setStatus}
        options={[
          { value: "1", label: "Active" },
          { value: "0", label: "Inactive" },
        ]}
        allLabel="All supervisors"
      />
      <SearchInput size="md" value={query} onChange={setQuery} placeholder="Search" className="w-44" />
      <ClearFiltersPill
        active={dirty}
        onClear={() => {
          setQuery("");
          setStatus("1");
        }}
      />
      {canManage && (
        <ToolbarButton onClick={() => setForm({ existing: null })}>
          <UserPlus className="h-4 w-4" strokeWidth={1.75} />
          Add supervisor
        </ToolbarButton>
      )}
      <RefreshButton onClick={reload} loading={loading} label="supervisors" />
    </>
  );

  return (
    <PageShell
      title="Supervisors"
      eyebrow={crop.name}
      actions={actions}
      description="Who supervises what this week: blocks, task progress, crew size and entries waiting for approval."
    >
      {orphans.length > 0 && (
        <div role="status" data-testid="assistants-without-manager" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-warn)] px-4 py-3 text-[13px] text-[var(--sd-ink)]">
          <p className="font-medium">Assistant managers with no manager</p>
          <p className="mt-0.5 text-[var(--sd-muted)]">Set Reports To on their employee record so their work reaches a manager's team.</p>
          <ul className="mt-1.5 list-disc pl-5">
            {orphans.map((a) => (
              <li key={a.user}>{a.full_name}{a.employee ? ` (${a.employee})` : ""}</li>
            ))}
          </ul>
        </div>
      )}
      {error ? (
        <div className="flex flex-col items-start gap-3 text-[13px] text-[var(--sd-muted)]">
          {error}
          <ToolbarButton onClick={reload}>Try again</ToolbarButton>
        </div>
      ) : waiting ? (
        <RowsSkeleton rows={4} />
      ) : !shown.length ? (
        <EmptyNote>
          {cards && cards.length ? "No supervisors match these filters." : "No supervisors yet. Use Add supervisor to choose them from the Employee list."}
        </EmptyNote>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((c) => (
            <SupervisorCard key={c.employee} card={c} onOpen={() => setOpen(c)} />
          ))}
        </div>
      )}

      {open && (
        <SupervisorDialog
          employee={open.employee}
          name={open.employee_name}
          crop={crop.name}
          year={week.year}
          week={week.week}
          reloadKey={tick}
          onClose={() => setOpen(null)}
          onEdit={(d) => setForm({ existing: d.supervisor })}
        />
      )}
      {canManage && (
        <SupervisorForm
          open={!!form}
          onOpenChange={(o) => !o && setForm(null)}
          existing={form?.existing ?? null}
          crops={crop.boot.crops.map((c) => c.name)}
          farms={crop.boot.farms}
          onSaved={reload}
        />
      )}
    </PageShell>
  );
}
