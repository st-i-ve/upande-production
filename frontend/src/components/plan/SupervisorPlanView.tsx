import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Copy, Save } from "lucide-react";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { ToolbarButton } from "@/components/ToolbarButton";
import { Button } from "@/components/ui/button";
import { SearchPicker } from "@/components/ui/search-picker";
import {
  copySupervisorPlan,
  getSupervisorPlan,
  saveSupervisorPlan,
  type SupervisorPlan,
} from "@/lib/api";
import { isError } from "@/lib/frappe";
import { cn } from "@/lib/utils";

const CARD = "rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)]";
const NONE = "__none__";

/** unit -> supervisor, from a list of assignment rows. */
const toMap = (rows: { unit: string; supervisor: string }[]) => Object.fromEntries(rows.map((r) => [r.unit, r.supervisor]));

/**
 * Who supervises which block this week. A supervisor's phone shows the tasks of the blocks assigned here, and
 * the week's plan tasks take their supervisor from this table. Managers edit; everyone else reads.
 */
export function SupervisorPlanView({
  crop,
  farm,
  year,
  week,
  unitLabel,
  canEdit,
  onSaved,
}: {
  crop: string;
  farm: string;
  year: number;
  week: number;
  unitLabel: string;
  canEdit: boolean;
  /** The week's plan tasks may have changed supervisor: the page reloads them. */
  onSaved?: () => void;
}) {
  const toast = useToast();
  const [data, setData] = useState<SupervisorPlan | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const seq = useRef(0);

  const apply = useCallback((r: SupervisorPlan) => {
    setData(r);
    setDraft(toMap(r.assignments));
    setWarnings(r.warnings.map((w) => w.message));
  }, []);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    setError(null);
    const r = await getSupervisorPlan(crop, farm, year, week);
    if (mine !== seq.current) return; // a newer week was asked for
    if (isError(r)) setError(r.error);
    else apply(r);
    setLoading(false);
  }, [crop, farm, year, week, apply]);

  useEffect(() => {
    void load();
  }, [load]);

  const saved = useMemo(() => toMap(data?.assignments ?? []), [data]);
  const dirty = useMemo(() => {
    const units = new Set([...Object.keys(saved), ...Object.keys(draft)]);
    return [...units].some((u) => (saved[u] || "") !== (draft[u] || ""));
  }, [saved, draft]);
  const options = useMemo(
    () => [
      { value: NONE, label: "Unassigned" },
      ...(data?.supervisors ?? []).map((s) => ({ value: s.name, label: s.employee_name || s.name })),
    ],
    [data],
  );
  const nameOf = useMemo(() => new Map((data?.supervisors ?? []).map((s) => [s.name, s.employee_name || s.name])), [data]);
  const lastBy = useMemo(() => Object.fromEntries((data?.last_week ?? []).map((r) => [r.unit, r.supervisor_name || r.supervisor])), [data]);
  const lastLabel = data ? `W${String(data.last_week_label.week).padStart(2, "0")}` : "";
  const weekEmpty = (data?.assignments.length ?? 0) === 0;

  async function save() {
    setBusy(true);
    const rows = Object.entries(draft)
      .filter(([, sup]) => sup)
      .map(([unit, supervisor]) => ({ unit, supervisor }));
    const r = await saveSupervisorPlan(crop, farm, year, week, rows);
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    apply(r);
    const n = r.tasks_updated ?? 0;
    toast(`Supervisors saved${n ? ` · ${n} task${n === 1 ? "" : "s"} updated` : ""}`, r.warnings.length ? "warn" : "ok");
    onSaved?.();
  }

  async function copyLast() {
    setBusy(true);
    const r = await copySupervisorPlan(crop, farm, year, week);
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    apply(r);
    toast(`Copied ${r.copied ?? r.assignments.length} from ${lastLabel}`, r.warnings.length ? "warn" : "ok");
    onSaved?.();
  }

  if (loading && !data) {
    return (
      <div className={cn(CARD, "px-4 py-4")}>
        <RowsSkeleton rows={5} />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className={cn(CARD, "flex flex-col items-start gap-3 px-5 py-6 text-[13px] text-[var(--sd-muted)]")}>
        <h2 className="text-[16px] font-semibold text-[var(--sd-ink)]">Could not load the supervisors</h2>
        {error}
        <Button variant="outline" onClick={() => void load()}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4" data-testid="supervisor-plan">
      {warnings.length > 0 && (
        <div role="status" data-testid="supervisor-warnings" className="rounded-[var(--sd-radius-lg)] bg-[var(--sd-alert-error)] px-4 py-3 text-[13px] text-[var(--sd-ink)]">
          {warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}
      <section className={CARD} aria-label="Supervisors by block">
        <header className="flex flex-wrap items-center gap-3 px-4 pb-2 pt-3.5">
          <h2 className="flex-1 text-[15px] font-semibold tracking-tight text-[var(--sd-ink)]">Supervisors by {unitLabel.toLowerCase()}</h2>
          {canEdit && (
            <>
              <ToolbarButton onClick={copyLast} disabled={busy || dirty || !weekEmpty || data.last_week.length === 0} title={!weekEmpty ? "This week already has supervisors" : undefined}>
                <Copy className="h-4 w-4" strokeWidth={1.75} />
                Copy last week
              </ToolbarButton>
              <Button onClick={save} disabled={busy || !dirty}>
                <Save className="h-4 w-4" strokeWidth={1.75} />
                {busy ? "Saving…" : "Save"}
              </Button>
            </>
          )}
        </header>
        {data.units.length === 0 ? (
          <p className="px-4 pb-4 text-[13px] text-[var(--sd-muted)]">This crop has no {unitLabel.toLowerCase()}s on this farm.</p>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[12px] text-[var(--sd-muted)]">
                <th className="px-4 py-2 font-medium">{unitLabel}</th>
                <th className="px-2 py-2 font-medium">Supervisor</th>
                <th className="px-4 py-2 font-medium">{lastLabel}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--sd-line-soft)]">
              {data.units.map((u) => {
                const cur = draft[u.name] || "";
                const prev = lastBy[u.name];
                return (
                  <tr key={u.name}>
                    <td className="px-4 py-2 font-medium text-[var(--sd-ink)]">
                      {u.name}
                      {u.area_ha ? <span className="ml-2 font-normal text-[var(--sd-muted)]">{u.area_ha} ha</span> : null}
                    </td>
                    <td className="w-64 px-2 py-1.5">
                      {canEdit ? (
                        <SearchPicker
                          value={cur || NONE}
                          onChange={(v) => setDraft((d) => ({ ...d, [u.name]: v === NONE ? "" : v }))}
                          options={options}
                          placeholder="Unassigned"
                          label={`Supervisor for ${u.name}`}
                        />
                      ) : (
                        <span className={cur ? "text-[var(--sd-ink)]" : "text-[var(--sd-muted)]"}>
                          {cur ? nameOf.get(cur) || cur : "Unassigned"}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-[var(--sd-muted)]">{prev || "·"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
      {!canEdit && (
        <p className="text-[12.5px] text-[var(--sd-muted)]">Only a manager can change who supervises a {unitLabel.toLowerCase()}.</p>
      )}
    </div>
  );
}
