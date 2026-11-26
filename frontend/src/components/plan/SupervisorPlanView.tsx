import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Copy, Plus, Save, X } from "lucide-react";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { ToolbarButton } from "@/components/ToolbarButton";
import { Button } from "@/components/ui/button";
import { SearchPicker } from "@/components/ui/search-picker";
import {
  copySupervisorPlan,
  getSupervisorOptions,
  getSupervisorPlan,
  saveSupervisorPlan,
  type SupervisorOption,
  type SupervisorPlan,
} from "@/lib/api";
import { isError } from "@/lib/frappe";
import { cn } from "@/lib/utils";

const CARD = "rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)]";
const NONE = "__none__";
/** Field Operation categories an activity can be shared under. */
const CATEGORIES = ["Spraying", "Weeding", "Fertilising", "Irrigation", "Harvesting", "Pruning", "Feeding", "Mulching", "Other"];

interface Activity {
  key: number;
  category: string;
  /** In sharing order: the first is who the activity's tasks route to. */
  sups: string[];
}
interface BlockDraft {
  overseer: string;
  activities: Activity[];
}
type Draft = Record<string, BlockDraft>;
type Row = { unit: string; supervisor: string; category: string };

let nextKey = 1;

/** Assignment rows -> per block: the overseer (blank category) and the activities, in row order. */
function toDraft(rows: { unit: string; supervisor: string; category?: string }[]): Draft {
  const out: Draft = {};
  for (const r of rows) {
    const b = (out[r.unit] ??= { overseer: "", activities: [] });
    if (!r.category) {
      if (!b.overseer) b.overseer = r.supervisor;
      continue;
    }
    let act = b.activities.find((x) => x.category === r.category);
    if (!act) b.activities.push((act = { key: nextKey++, category: r.category, sups: [] }));
    act.sups.push(r.supervisor);
  }
  return out;
}

/** The rows the server takes: overseer first, then each activity's supervisors in order. */
function toRows(draft: Draft, units: string[]): Row[] {
  const rows: Row[] = [];
  for (const unit of units) {
    const b = draft[unit];
    if (!b) continue;
    if (b.overseer) rows.push({ unit, supervisor: b.overseer, category: "" });
    for (const a of b.activities) {
      if (!a.category) continue;
      for (const s of a.sups) if (s) rows.push({ unit, supervisor: s, category: a.category });
    }
  }
  return rows;
}

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
  const [draft, setDraft] = useState<Draft>({});
  const [people, setPeople] = useState<SupervisorOption[] | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const seq = useRef(0);

  const apply = useCallback((r: SupervisorPlan) => {
    setData(r);
    setDraft(toDraft(r.assignments));
    setWarnings(r.warnings.map((w) => w.message));
  }, []);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    setError(null);
    setSaveError(null);
    const r = await getSupervisorPlan(crop, farm, year, week);
    if (mine !== seq.current) return; // a newer week was asked for
    if (isError(r)) setError(r.error);
    else apply(r);
    setLoading(false);
  }, [crop, farm, year, week, apply]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let live = true;
    void getSupervisorOptions(crop).then((r) => {
      if (live) setPeople(Array.isArray(r) ? r : null);
    });
    return () => {
      live = false;
    };
  }, [crop]);

  const unitNames = useMemo(() => (data?.units ?? []).map((u) => u.name), [data]);
  const rowsKey = (rows: Row[]) => JSON.stringify(rows);
  const dirty = useMemo(
    () =>
      rowsKey(toRows(draft, unitNames)) !== rowsKey(toRows(toDraft(data?.assignments ?? []), unitNames)) ||
      unitNames.some((u) => draft[u]?.activities.some((a) => !a.category && a.sups.some(Boolean))), // so Save can say what is missing
    [draft, data, unitNames],
  );
  // The active supervisors for the crop, plus anyone already assigned who is no longer listed (so they still show).
  const nameOf = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of people ?? data?.supervisors ?? []) m.set(s.name, s.employee_name || s.name);
    for (const r of data?.assignments ?? []) if (!m.has(r.supervisor)) m.set(r.supervisor, r.supervisor_name || r.supervisor);
    return m;
  }, [people, data]);
  // Assigned supervisors who are no longer active still show, marked.
  const inactive = useMemo(() => new Set((data?.supervisors ?? []).filter((s) => s.status === "Inactive").map((s) => s.name)), [data]);
  const labelOf = useCallback((id: string) => `${nameOf.get(id) || id}${inactive.has(id) ? " (inactive)" : ""}`, [nameOf, inactive]);
  const options = useMemo(() => [...nameOf].map(([value]) => ({ value, label: labelOf(value) })), [nameOf, labelOf]);
  const overseerOptions = useMemo(() => [{ value: NONE, label: "Unassigned" }, ...options], [options]);

  function edit(unit: string, fn: (b: BlockDraft) => BlockDraft) {
    setSaveError(null);
    setDraft((d) => ({ ...d, [unit]: fn(d[unit] ?? { overseer: "", activities: [] }) }));
  }
  const editActivity = (unit: string, key: number, fn: (a: Activity) => Activity) =>
    edit(unit, (b) => ({ ...b, activities: b.activities.map((a) => (a.key === key ? fn(a) : a)) }));
  const lastBy = useMemo(() => {
    const m: Record<string, string[]> = {};
    for (const r of data?.last_week ?? []) (m[r.unit] ??= []).push(`${r.category ? `${r.category}: ` : ""}${r.supervisor_name || r.supervisor}`);
    return m;
  }, [data]);
  const lastLabel = data ? `W${String(data.last_week_label.week).padStart(2, "0")}` : "";
  const weekEmpty = (data?.assignments.length ?? 0) === 0;

  async function save() {
    setSaveError(null);
    for (const unit of unitNames) {
      const lost = draft[unit]?.activities.find((a) => !a.category && a.sups.some(Boolean));
      if (lost) {
        setSaveError(`Choose an activity for the supervisors listed under ${unit}, or remove them.`);
        return;
      }
    }
    setBusy(true);
    const rows = toRows(draft, unitNames);
    const r = await saveSupervisorPlan(crop, farm, year, week, rows);
    setBusy(false);
    if (isError(r)) {
      setSaveError(r.error);
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
      setSaveError(r.error);
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
      {saveError && (
        <div role="alert" className="rounded-[var(--sd-radius-lg)] bg-[var(--sd-alert-error)] px-4 py-3 text-[13px] text-[var(--sd-ink)]">
          {saveError}
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
                <th className="px-2 py-2 font-medium">Overseer</th>
                <th className="px-2 py-2 font-medium">Activities</th>
                <th className="px-4 py-2 font-medium">{lastLabel}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--sd-line-soft)]">
              {data.units.map((u) => {
                const b = draft[u.name] ?? { overseer: "", activities: [] };
                const prev = lastBy[u.name];
                const taken = new Set(b.activities.map((a) => a.category));
                return (
                  <tr key={u.name} className="align-top">
                    <td className="px-4 py-2 font-medium text-[var(--sd-ink)]">
                      {u.name}
                      {u.area_ha ? <span className="ml-2 font-normal text-[var(--sd-muted)]">{u.area_ha} ha</span> : null}
                    </td>
                    <td className="w-56 px-2 py-1.5">
                      {canEdit ? (
                        <SearchPicker
                          value={b.overseer || NONE}
                          onChange={(v) => edit(u.name, (x) => ({ ...x, overseer: v === NONE ? "" : v }))}
                          options={overseerOptions}
                          placeholder="Unassigned"
                          label={`Overseer for ${u.name}`}
                        />
                      ) : (
                        <span className={b.overseer ? "text-[var(--sd-ink)]" : "text-[var(--sd-muted)]"}>
                          {b.overseer ? labelOf(b.overseer) : "Unassigned"}
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-1.5">
                      <div className="flex flex-col gap-2">
                        {b.activities.map((a, i) => (
                          <div key={a.key} className="flex flex-wrap items-center gap-1.5">
                            {canEdit ? (
                              <>
                                <div className="w-36">
                                  <SearchPicker
                                    value={a.category}
                                    onChange={(v) => editActivity(u.name, a.key, (x) => ({ ...x, category: v }))}
                                    options={CATEGORIES.filter((c) => c === a.category || !taken.has(c)).map((c) => ({ value: c, label: c }))}
                                    placeholder="Category"
                                    label={`Category of activity ${i + 1} for ${u.name}`}
                                  />
                                </div>
                                {a.sups.map((sup, j) => (
                                  <div key={j} className="w-40">
                                    <SearchPicker
                                      value={sup}
                                      onChange={(v) =>
                                        editActivity(u.name, a.key, (x) => ({
                                          ...x,
                                          sups: v === NONE ? x.sups.filter((_, k) => k !== j) : x.sups.map((y, k) => (k === j ? v : y)),
                                        }))
                                      }
                                      options={[{ value: NONE, label: "Remove" }, ...options.filter((o) => o.value === sup || !a.sups.includes(o.value))]}
                                      placeholder="Supervisor"
                                      label={`Supervisor ${j + 1} of activity ${i + 1} for ${u.name}`}
                                    />
                                  </div>
                                ))}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  aria-label={`Add supervisor to activity ${i + 1} for ${u.name}`}
                                  onClick={() => editActivity(u.name, a.key, (x) => ({ ...x, sups: [...x.sups, ""] }))}
                                >
                                  <Plus className="h-3.5 w-3.5" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  aria-label={`Remove activity ${i + 1} for ${u.name}`}
                                  onClick={() => edit(u.name, (x) => ({ ...x, activities: x.activities.filter((y) => y.key !== a.key) }))}
                                >
                                  <X className="h-3.5 w-3.5" />
                                </Button>
                              </>
                            ) : (
                              <span className="text-[var(--sd-ink)]">
                                {a.category}: {a.sups.map(labelOf).join(", ")}
                              </span>
                            )}
                          </div>
                        ))}
                        {canEdit && (
                          <div>
                            <Button
                              variant="ghost"
                              size="sm"
                              aria-label={`Add activity for ${u.name}`}
                              disabled={b.activities.length >= CATEGORIES.length}
                              onClick={() => edit(u.name, (x) => ({ ...x, activities: [...x.activities, { key: nextKey++, category: "", sups: [""] }] }))}
                            >
                              <Plus className="h-3.5 w-3.5" /> Add activity
                            </Button>
                          </div>
                        )}
                        {!canEdit && b.activities.length === 0 && <span className="text-[var(--sd-muted)]">·</span>}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-[var(--sd-muted)]">{prev ? prev.map((p) => <div key={p}>{p}</div>) : "·"}</td>
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
