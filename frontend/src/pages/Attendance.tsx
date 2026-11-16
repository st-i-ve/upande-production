import { useCallback, useEffect, useMemo, useState } from "react";
import { Check } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { TableRowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { SearchInput } from "@/components/SearchInput";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { listLabourers, type RosterRow } from "@/lib/labourers-api";
import {
  ATTENDANCE_STATUSES,
  attendanceDay,
  getLabourSettings,
  markAttendance,
  type AttendanceStatus,
} from "@/lib/labourpay-api";
import { useLabourMode } from "@/lib/use-labour-mode";
import { cn, matchesQuery, todayISO } from "@/lib/utils";

type Marks = Record<string, AttendanceStatus | "">;

const TH = "px-4 py-2.5 font-medium";

/**
 * Attendance for one day: every active casual labourer with a status, marked in bulk and saved in
 * one go. Only people whose status changed are sent.
 */
export function Attendance() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const canMark = crop.boot.can_manage;
  const mode = useLabourMode();
  const [date, setDate] = useState(todayISO());
  const [query, setQuery] = useState("");
  const [people, setPeople] = useState<RosterRow[] | null>(null);
  const [saved, setSaved] = useState<Marks>({});
  const [marks, setMarks] = useState<Marks>({});
  const [required, setRequired] = useState<{ on: boolean; source: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    void getLabourSettings().then((s) => {
      if (live && !isError(s)) setRequired({ on: !!Number(s.attendance_required), source: s.attendance_source });
    });
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    void Promise.all([listLabourers(crop.name, date, date, { active: "1" }), attendanceDay(date)]).then(([roster, day]) => {
      if (!live) return;
      setLoading(false);
      if (isError(roster)) return void setError(roster.error);
      if (isError(day)) return void setError(day.error);
      const m: Marks = {};
      for (const r of day.rows) m[r.employee] = r.status;
      setPeople([...roster.rows].sort((a, b) => a.employee_name.localeCompare(b.employee_name)));
      setSaved(m);
      setMarks(m);
    });
    return () => {
      live = false;
    };
  }, [crop.name, date, tick]);

  const shown = useMemo(() => (people ?? []).filter((p) => matchesQuery(`${p.employee_name} ${p.employee} ${p.crew ?? ""}`, query)), [people, query]);
  const changed = useMemo(() => Object.keys(marks).filter((e) => marks[e] && marks[e] !== saved[e]), [marks, saved]);
  const waiting = firstLoad(loading, !!people);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const s of Object.values(marks)) if (s) c[s] = (c[s] ?? 0) + 1;
    return c;
  }, [marks]);

  const markAll = useCallback(() => {
    setMarks((m) => {
      const n = { ...m };
      for (const p of shown) n[p.employee] = "Present";
      return n;
    });
  }, [shown]);

  async function save() {
    setBusy(true);
    const groups = new Map<AttendanceStatus, string[]>();
    for (const e of changed) {
      const s = marks[e] as AttendanceStatus;
      groups.set(s, [...(groups.get(s) ?? []), e]);
    }
    let total = 0;
    for (const [status, employees] of groups) {
      const r = await markAttendance(employees, date, status);
      if (isError(r)) {
        setBusy(false);
        toast(r.error, "error");
        setTick((t) => t + 1);
        return;
      }
      total += r.marked;
    }
    setBusy(false);
    toast(`Attendance saved for ${total} ${total === 1 ? "person" : "people"}.`);
    setTick((t) => t + 1);
  }

  const actions = (
    <>
      <DatePicker aria-label="Attendance date" value={date} onChange={(d) => d && setDate(d)} max={todayISO()} className="h-9" />
      <SearchInput size="md" value={query} onChange={setQuery} placeholder="Search" className="w-44" />
      {canMark && (
        <ToolbarButton onClick={markAll} disabled={!shown.length || mode?.wm_active}>
          <Check className="h-4 w-4" strokeWidth={1.75} />
          Mark all present
        </ToolbarButton>
      )}
      <RefreshButton onClick={() => setTick((t) => t + 1)} loading={loading} label="attendance" />
    </>
  );

  const note = required
    ? required.on
      ? `Attendance is required: work can only be keyed for a day a person is marked Present or Half Day (source: ${required.source}).`
      : "Attendance is not required: work can be keyed without it. Marking is optional."
    : null;

  return (
    <PageShell
      title="Attendance"
      eyebrow={crop.name}
      actions={actions}
      description="Mark who was at work on a day. Pick the date, set each person's status, then save."
    >
      {mode?.wm_active && (
        <div role="note" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-info)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          Work Management is handling labour. Attendance is assigned there: open the{" "}
          <a className="underline" href="/work-assigner">Work Assigner</a>.
        </div>
      )}
      {note && (
        <div role="note" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-bg-soft)] px-4 py-3 text-[13px] text-[var(--sd-muted)]">
          {note}
        </div>
      )}
      <Panel
        title="Roster"
        hint={ATTENDANCE_STATUSES.filter((s) => counts[s]).map((s) => `${counts[s]} ${s}`).join(" · ") || "Nobody marked yet for this day."}
        bodyClassName="px-0 pb-2"
        tools={
          canMark && (
            <ToolbarButton onClick={() => void save()} disabled={!changed.length || busy}>
              {busy ? "Saving…" : changed.length ? `Save attendance (${changed.length})` : "Save attendance"}
            </ToolbarButton>
          )
        }
      >
        {error ? (
          <div className="flex flex-col items-start gap-3 px-5 py-4 text-[13px] text-[var(--sd-muted)]">
            {error}
            <ToolbarButton onClick={() => setTick((t) => t + 1)}>Try again</ToolbarButton>
          </div>
        ) : !waiting && !shown.length ? (
          <div className="px-5">
            <EmptyNote>{people?.length ? "Nobody matches this search." : "No active casual labourers on the roster."}</EmptyNote>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--sd-line)] text-left text-[10.5px] uppercase tracking-[0.12em] text-[var(--sd-quiet)]">
                  <th className={TH}>Labourer</th>
                  <th className={TH}>Crew</th>
                  <th className={TH}>Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--sd-line-soft)]">
                {waiting ? (
                  <TableRowsSkeleton cols={3} rows={6} />
                ) : (
                  shown.map((p) => (
                    <tr key={p.employee} data-testid={`att-${p.employee}`}>
                      <td className="px-4 py-2.5 font-medium text-[var(--sd-ink)]">{p.employee_name}</td>
                      <td className="px-4 py-2.5 text-[var(--sd-muted)]">{p.crew || "—"}</td>
                      <td className="px-4 py-2">
                        <div role="radiogroup" aria-label={`Status for ${p.employee_name}`} className="inline-flex flex-wrap gap-1">
                          {ATTENDANCE_STATUSES.map((s) => (
                            <button
                              key={s}
                              type="button"
                              role="radio"
                              aria-checked={marks[p.employee] === s}
                              disabled={!canMark}
                              onClick={() => setMarks((m) => ({ ...m, [p.employee]: s }))}
                              className={cn(
                                "rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors disabled:cursor-default",
                                marks[p.employee] === s
                                  ? "bg-[var(--sd-pistachio)] text-[var(--sd-ink)] ring-1 ring-foreground/20"
                                  : "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)] hover:text-[var(--sd-ink)]",
                              )}
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </PageShell>
  );
}
