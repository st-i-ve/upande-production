import { useState } from "react";
import { ChevronRight, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Picker } from "@/components/ui/picker";
import { SendBackDialog } from "@/components/approvals/SendBackDialog";
import { qty } from "@/lib/format";
import type {
  CapitalActivity,
  CulturalActivity,
  KeyActivity,
  ProtocolFamily,
  ProtocolTables,
  ProtocolVersion,
  VersionStatus,
} from "@/lib/protocols-api";
import { cn } from "@/lib/utils";

const CHIP: Record<VersionStatus, string> = {
  Draft: "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]",
  "Pending Approval": "bg-[color-mix(in_srgb,var(--sd-data-amber)_18%,transparent)] text-[var(--sd-data-amber)]",
  Active: "bg-[color-mix(in_srgb,var(--sd-data-green)_18%,transparent)] text-[var(--sd-data-green)]",
  Superseded: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
  Rejected: "bg-[color-mix(in_srgb,var(--sd-data-red)_16%,transparent)] text-[var(--sd-data-red)]",
};

export function StatusChip({ status }: { status: VersionStatus }) {
  return (
    <span data-testid="status-chip" className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", CHIP[status])}>
      {status}
    </span>
  );
}

/** An operation as the protocol pickers see it. */
export interface OpOption {
  value: string;
  label: string;
  /** Production Operation `activity_type`. */
  type: string;
}

export interface ProtocolActions {
  newVersion: (v: ProtocolVersion) => void;
  submit: (v: ProtocolVersion) => void;
  approve: (v: ProtocolVersion) => void;
  sendBack: (v: ProtocolVersion, note: string) => void;
  saveDraft: (v: ProtocolVersion, tables: ProtocolTables) => void;
}

export const KEY_HINT = "List key activities in the order of their week.";

const EMPTY_KEY: KeyActivity = { operation: null, week: null, repeats: "Every cycle", planned_qty: null, description: null };
const EMPTY_CULTURAL: CulturalActivity = {
  operation: null, schedule: "Interval", interval_weeks: null, establishment_period_weeks: null,
  pre_harvest_interval_days: null, occurrences: null, planned_qty: null, description: null,
};
const EMPTY_CAPITAL: CapitalActivity = { operation: null, description: null, budget_per_ha: null };

const REPEATS = ["Every cycle", "First cycle only"];
const SCHEDULES = ["Interval", "As needed"];

/** Indexes of key rows whose week is lower than the row before (the list must run in week order). */
export function outOfOrder(rows: KeyActivity[]): Set<number> {
  const bad = new Set<number>();
  let last = -Infinity;
  rows.forEach((r, i) => {
    if (r.week == null) return;
    if (r.week < last) bad.add(i);
    else last = r.week;
  });
  return bad;
}

const num = (v: string): number | null => (v === "" ? null : Number(v));
const TH = "py-1.5 pr-3 font-medium";
const TH_CLS = "text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]";

function Section({ title, hint, children, onAdd, count }: {
  title: string;
  hint?: string;
  children: React.ReactNode;
  onAdd?: () => void;
  count: number;
}) {
  return (
    <section aria-label={title} className="mb-3 last:mb-0">
      <div className="mb-1 flex items-center gap-2">
        <h4 className="text-[12.5px] font-semibold text-[var(--sd-ink)]">{title}</h4>
        <span className="text-[11.5px] tabular-nums text-[var(--sd-quiet)]">{count}</span>
        <span className="flex-1" />
        {onAdd && (
          <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-[12px]" aria-label={`Add row to ${title}`} onClick={onAdd}>
            <Plus className="h-3.5 w-3.5" /> Add row
          </Button>
        )}
      </div>
      {hint && <p className="mb-1 text-[11.5px] text-[var(--sd-muted)]">{hint}</p>}
      {children}
    </section>
  );
}

function OpCell({ value, options, label, editable, names, onChange }: {
  value: string | null;
  options: OpOption[];
  label: string;
  editable: boolean;
  names: Record<string, string>;
  onChange: (v: string) => void;
}) {
  if (!editable) return <span className="font-medium text-[var(--sd-ink)]">{(value && names[value]) || value || "—"}</span>;
  const opts = options.map((o) => ({ value: o.value, label: o.label }));
  if (value && !opts.some((o) => o.value === value)) opts.push({ value, label: names[value] ?? value });
  return <Picker label={label} className="h-8 min-w-[11rem]" value={value ?? ""} onChange={onChange} options={opts} placeholder="Activity" />;
}

function RemoveCell({ editable, label, onRemove }: { editable: boolean; label: string; onRemove: () => void }) {
  if (!editable) return null;
  return (
    <td className="py-1 text-right">
      <button type="button" aria-label={label} onClick={onRemove} className="rounded p-1 text-[var(--sd-quiet)] hover:text-[var(--sd-data-red)]">
        <X className="h-3.5 w-3.5" />
      </button>
    </td>
  );
}

function floweringPattern(v: ProtocolVersion): string | null {
  if (!v.is_flowering) return null;
  if (v.flowering_pattern === "Seasonal") {
    const seasons = (v.flowering_seasons ?? []).map((s) => `${s.season_name} (${s.start_month})`);
    return seasons.length ? seasons.join(", ") : "Seasonal";
  }
  if (v.flowering_pattern === "Interval" && v.flowering_interval_weeks) return `Every ${v.flowering_interval_weeks} weeks`;
  return null;
}

function Template({ v }: { v: ProtocolVersion }) {
  const items: [string, unknown][] = [
    ["Lifespan (years)", v.lifespan_years],
    ["Harvest pattern", v.harvest_pattern],
    ["Harvest interval (weeks)", v.harvest_interval_weeks],
    ["Weeks to first flowering", v.is_flowering ? v.weeks_to_first_flowering : null],
    ["Weeks flowering to harvest", v.is_flowering ? v.weeks_flowering_to_harvest : null],
    ["Weeks to maturity", v.weeks_to_maturity],
    ["Flowering pattern", floweringPattern(v)],
    ["Plants per m²", v.plants_per_m2],
  ];
  const shown = items.filter(([, x]) => x !== null && x !== undefined && x !== "" && x !== 0);
  if (!shown.length) return null;
  return (
    <dl data-testid="protocol-template" className="mb-3 flex flex-wrap gap-x-5 gap-y-1.5 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] px-3 py-2">
      {shown.map(([k, x]) => (
        <div key={k} className="flex flex-col">
          <dt className="text-[10.5px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">{k}</dt>
          <dd className="text-[12.5px] font-medium tabular-nums text-[var(--sd-ink)]">{String(x)}</dd>
        </div>
      ))}
    </dl>
  );
}

function Activities({ v, operations, editable, onSave }: {
  v: ProtocolVersion;
  operations: OpOption[];
  editable: boolean;
  onSave: (t: ProtocolTables) => void;
}) {
  const initial = (): ProtocolTables => ({
    key_activities: v.key_activities ?? [],
    cultural_activities: v.cultural_activities ?? [],
    capital_activities: v.capital_activities ?? [],
  });
  const [t, setT] = useState<ProtocolTables>(initial);
  const dirty = JSON.stringify(t) !== JSON.stringify(initial());
  const names = Object.fromEntries(operations.map((o) => [o.value, o.label]));
  const scheduled = operations.filter((o) => o.type !== "Capital");
  const capital = operations.filter((o) => o.type === "Capital");
  const bad = outOfOrder(t.key_activities);

  const patch = <K extends keyof ProtocolTables>(k: K, i: number, p: Partial<ProtocolTables[K][number]>) =>
    setT((x) => ({ ...x, [k]: (x[k] as object[]).map((r, j) => (j === i ? { ...r, ...p } : r)) }));
  const add = <K extends keyof ProtocolTables>(k: K, row: ProtocolTables[K][number]) =>
    setT((x) => ({ ...x, [k]: [...(x[k] as object[]), { ...row }] }));
  const remove = (k: keyof ProtocolTables, i: number) => setT((x) => ({ ...x, [k]: x[k].filter((_, j) => j !== i) as never }));
  const empty = (n: number, text: string) => (n === 0 ? <p className="text-[12px] text-[var(--sd-muted)]">{text}</p> : null);

  return (
    <div>
      <Template v={v} />

      <Section title="Capital activities" count={t.capital_activities.length} onAdd={editable ? () => add("capital_activities", EMPTY_CAPITAL) : undefined}>
        {empty(t.capital_activities.length, "No capital activities.")}
        {t.capital_activities.length > 0 && (
          <table className="w-full min-w-[28rem] text-[12.5px]">
            <thead><tr className={TH_CLS}>
              <th className={TH}>Activity</th><th className={`${TH} text-right`}>Budget per ha</th><th className={TH}>Description</th>{editable && <th />}
            </tr></thead>
            <tbody>
              {t.capital_activities.map((r, i) => (
                <tr key={i}>
                  <td className="py-1 pr-2"><OpCell value={r.operation} options={capital} label={`Capital activity ${i + 1}`} editable={editable} names={names} onChange={(x) => patch("capital_activities", i, { operation: x })} /></td>
                  <td className="py-1 pr-2 text-right">
                    {editable
                      ? <Input aria-label={`Budget per ha ${i + 1}`} className="ml-auto h-8 w-28 text-right" type="number" value={r.budget_per_ha ?? ""} onChange={(e) => patch("capital_activities", i, { budget_per_ha: num(e.target.value) })} />
                      : <span className="tabular-nums">{r.budget_per_ha ? qty(r.budget_per_ha, 0) : "—"}</span>}
                  </td>
                  <td className="py-1 pr-2">
                    {editable
                      ? <Input aria-label={`Description of capital activity ${i + 1}`} className="h-8" value={r.description ?? ""} onChange={(e) => patch("capital_activities", i, { description: e.target.value })} />
                      : <span className="text-[var(--sd-muted)]">{r.description || ""}</span>}
                  </td>
                  <RemoveCell editable={editable} label={`Remove capital activity ${i + 1}`} onRemove={() => remove("capital_activities", i)} />
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title="Key activities" hint={KEY_HINT} count={t.key_activities.length} onAdd={editable ? () => add("key_activities", EMPTY_KEY) : undefined}>
        {empty(t.key_activities.length, "No key activities.")}
        {t.key_activities.length > 0 && (
          <table className="w-full min-w-[34rem] text-[12.5px]">
            <thead><tr className={TH_CLS}>
              <th className={TH}>Activity</th><th className={TH}>Week</th><th className={TH}>Repeats</th><th className={`${TH} text-right`}>Qty</th><th className={TH}>Description</th>{editable && <th />}
            </tr></thead>
            <tbody>
              {t.key_activities.map((r, i) => {
                const op = (r.operation && names[r.operation]) || r.operation || "—";
                const wrong = bad.has(i);
                return (
                  <tr key={i} data-testid={`key-row-${i}`} data-out-of-order={wrong ? "true" : undefined} className={cn(wrong && "bg-[var(--sd-alert-error)]")}>
                    <td className="py-1 pr-2"><OpCell value={r.operation} options={scheduled} label={`Key activity ${i + 1}`} editable={editable} names={names} onChange={(x) => patch("key_activities", i, { operation: x })} /></td>
                    <td className="py-1 pr-2">
                      {editable
                        ? <Input aria-label={`Week for ${op}`} aria-invalid={wrong || undefined} className={cn("h-8 w-16", wrong && "border-[var(--sd-data-red)] text-[var(--sd-data-red)]")} type="number" min="1" value={r.week ?? ""} onChange={(e) => patch("key_activities", i, { week: num(e.target.value) })} />
                        : <span className="tabular-nums text-[var(--sd-muted)]">{r.week ?? "—"}</span>}
                    </td>
                    <td className="py-1 pr-2">
                      {editable
                        ? <Picker label={`Repeats for ${op}`} className="h-8 w-36" value={r.repeats ?? "Every cycle"} onChange={(x) => patch("key_activities", i, { repeats: x as KeyActivity["repeats"] })} options={REPEATS} />
                        : <span className="text-[var(--sd-muted)]">{r.repeats}</span>}
                    </td>
                    <td className="py-1 pr-2 text-right">
                      {editable
                        ? <Input aria-label={`Planned qty for ${op}`} className="ml-auto h-8 w-20 text-right" type="number" value={r.planned_qty ?? ""} onChange={(e) => patch("key_activities", i, { planned_qty: num(e.target.value) })} />
                        : <span className="tabular-nums">{r.planned_qty ? qty(r.planned_qty, 1) : "—"}</span>}
                    </td>
                    <td className="py-1 pr-2">
                      {editable
                        ? <Input aria-label={`Description for ${op}`} className="h-8" value={r.description ?? ""} onChange={(e) => patch("key_activities", i, { description: e.target.value })} />
                        : <span className="text-[var(--sd-muted)]">{r.description || ""}</span>}
                    </td>
                    <RemoveCell editable={editable} label={`Remove key activity ${i + 1}`} onRemove={() => remove("key_activities", i)} />
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {bad.size > 0 && (
          <p role="alert" className="mt-1 text-[12px] text-[var(--sd-data-red)]">
            Some rows are out of week order. {KEY_HINT}
          </p>
        )}
      </Section>

      <Section title="Cultural activities" count={t.cultural_activities.length} onAdd={editable ? () => add("cultural_activities", EMPTY_CULTURAL) : undefined}>
        {empty(t.cultural_activities.length, "No cultural activities.")}
        {t.cultural_activities.length > 0 && (
          <table className="w-full min-w-[52rem] text-[12.5px]">
            <thead><tr className={TH_CLS}>
              <th className={TH}>Activity</th>
              <th className={TH}>Schedule</th>
              <th className={TH}>Interval (weeks)</th>
              <th className={TH} title="weeks after planting / last harvest">Establishment period (weeks)</th>
              <th className={TH} title="days before harvest">Pre-harvest interval, PHI (days)</th>
              <th className={TH} title="leave empty to repeat until the cycle ends">Occurrences</th>
              <th className={`${TH} text-right`}>Qty</th>
              <th className={TH}>Description</th>{editable && <th />}
            </tr></thead>
            <tbody>
              {t.cultural_activities.map((r, i) => {
                const op = (r.operation && names[r.operation]) || r.operation || "—";
                const asNeeded = r.schedule === "As needed";
                const numCell = (field: "interval_weeks" | "establishment_period_weeks" | "pre_harvest_interval_days" | "occurrences", label: string, off = false, blank = "—") =>
                  editable
                    ? <Input aria-label={`${label} for ${op}`} className="h-8 w-20" type="number" min="0" disabled={off} value={off ? "" : (r[field] ?? "")} onChange={(e) => patch("cultural_activities", i, { [field]: num(e.target.value) })} />
                    : <span className="tabular-nums text-[var(--sd-muted)]">{off ? "—" : (r[field] ?? blank)}</span>;
                return (
                  <tr key={i} data-testid={`cultural-row-${i}`}>
                    <td className="py-1 pr-2"><OpCell value={r.operation} options={scheduled} label={`Cultural activity ${i + 1}`} editable={editable} names={names} onChange={(x) => patch("cultural_activities", i, { operation: x })} /></td>
                    <td className="py-1 pr-2">
                      {editable
                        ? <Picker label={`Schedule for ${op}`} className="h-8 w-32" value={r.schedule ?? "Interval"} onChange={(x) => patch("cultural_activities", i, x === "As needed" ? { schedule: "As needed", interval_weeks: null } : { schedule: "Interval" })} options={SCHEDULES} />
                        : <span className="text-[var(--sd-muted)]">{r.schedule}</span>}
                    </td>
                    <td className="py-1 pr-2">{numCell("interval_weeks", "Interval weeks", asNeeded)}</td>
                    <td className="py-1 pr-2">{numCell("establishment_period_weeks", "Establishment period weeks")}</td>
                    <td className="py-1 pr-2">{numCell("pre_harvest_interval_days", "PHI days")}</td>
                    <td className="py-1 pr-2">{numCell("occurrences", "Occurrences", asNeeded, "until cycle end")}</td>
                    <td className="py-1 pr-2 text-right">
                      {editable
                        ? <Input aria-label={`Planned qty for ${op}`} className="ml-auto h-8 w-20 text-right" type="number" value={r.planned_qty ?? ""} onChange={(e) => patch("cultural_activities", i, { planned_qty: num(e.target.value) })} />
                        : <span className="tabular-nums">{r.planned_qty ? qty(r.planned_qty, 1) : "—"}</span>}
                    </td>
                    <td className="py-1 pr-2">
                      {editable
                        ? <Input aria-label={`Description for ${op}`} className="h-8" value={r.description ?? ""} onChange={(e) => patch("cultural_activities", i, { description: e.target.value })} />
                        : <span className="text-[var(--sd-muted)]">{r.description || ""}</span>}
                    </td>
                    <RemoveCell editable={editable} label={`Remove cultural activity ${i + 1}`} onRemove={() => remove("cultural_activities", i)} />
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Section>

      {editable && (
        <div className="mt-2 flex justify-end">
          <Button type="button" size="sm" disabled={!dirty} onClick={() => onSave(t)}>Save draft</Button>
        </div>
      )}
    </div>
  );
}

function Version({ fam, v, operations, canPlan, canManage, actions }: {
  fam: ProtocolFamily;
  v: ProtocolVersion;
  operations: OpOption[];
  canPlan: boolean;
  canManage: boolean;
  actions: ProtocolActions;
}) {
  const [asking, setAsking] = useState(false);
  const label = `${fam.label} v${v.version}`;
  return (
    <div data-testid={`version-${v.name}`} className="rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-4 py-3 shadow-[var(--sd-shadow-inset)]">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-medium text-[var(--sd-ink)]">Version {v.version}</span>
        <StatusChip status={v.version_status} />
        <span className="flex-1" />
        {v.version_status === "Active" && canPlan && !fam.has_pending && !fam.versions.some((x) => x.version_status === "Draft") && (
          <Button type="button" size="sm" variant="ghost" aria-label={`New version of ${fam.label}`} onClick={() => actions.newVersion(v)}>New version</Button>
        )}
        {v.version_status === "Draft" && canPlan && (
          <Button type="button" size="sm" aria-label={`Submit ${label} for approval`} onClick={() => actions.submit(v)}>Submit for approval</Button>
        )}
        {v.version_status === "Pending Approval" && canManage && (
          <>
            <Button type="button" size="sm" variant="ghost" aria-label={`Send back ${label}`} onClick={() => setAsking(true)}>Send back</Button>
            <Button type="button" size="sm" aria-label={`Approve ${label}`} onClick={() => actions.approve(v)}>Approve</Button>
          </>
        )}
      </div>
      {v.review_note && v.version_status === "Draft" && (
        <p className="mb-2 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] px-3 py-2 text-[12.5px] text-[var(--sd-ink)]">
          <span className="font-medium">Sent back:</span> {v.review_note}
        </p>
      )}
      <Activities key={tablesKey(v)} v={v} operations={operations} editable={v.version_status === "Draft" && canPlan} onSave={(t) => actions.saveDraft(v, t)} />
      <SendBackDialog open={asking} cards={1} busy={false} onCancel={() => setAsking(false)} onConfirm={(n) => { setAsking(false); actions.sendBack(v, n); }} />
    </div>
  );
}

const tablesKey = (v: ProtocolVersion) => JSON.stringify([v.key_activities, v.cultural_activities, v.capital_activities]);
const activityCount = (v: ProtocolVersion) =>
  (v.key_activities?.length ?? 0) + (v.cultural_activities?.length ?? 0) + (v.capital_activities?.length ?? 0);

/** Protocol families, each opening to its versions (status chips, steps, actions). Edit only on Drafts. */
export function ProtocolsList({ families, operations, canPlan, canManage, actions }: {
  families: ProtocolFamily[];
  operations: OpOption[];
  canPlan: boolean;
  canManage: boolean;
  actions: ProtocolActions;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (!families.length) {
    return <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">No protocols defined for this crop yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-1">
      {families.map((f) => {
        const expanded = open === f.family;
        const shown = f.versions.find((v) => v.version_status === "Active") ?? f.versions[0];
        return (
          <li key={f.family}>
            <button
              type="button"
              aria-expanded={expanded}
              onClick={() => setOpen(expanded ? null : f.family)}
              className="flex w-full items-center gap-3 rounded-[var(--sd-radius-lg)] px-3 py-2.5 text-left transition-all hover:bg-[var(--sd-bg-soft)]"
            >
              <ChevronRight className={cn("h-4 w-4 shrink-0 text-[var(--sd-quiet)] transition-transform", expanded && "rotate-90")} />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px] font-medium text-[var(--sd-ink)]">{f.label}</span>
                {f.item ? <span className="text-[11.5px] text-[var(--sd-muted)]">{f.item}</span> : null}
              </span>
              <span className="flex shrink-0 items-center gap-2">
                {f.versions.filter((v) => v.version_status !== "Active" && v.version_status !== "Superseded").map((v) => (
                  <StatusChip key={v.name} status={v.version_status} />
                ))}
                <span className="text-[11.5px] tabular-nums text-[var(--sd-quiet)]">
                  v{shown.version} · {activityCount(shown)} {activityCount(shown) === 1 ? "activity" : "activities"}
                </span>
              </span>
            </button>
            {expanded && (
              <div className="mb-1 ml-7 flex flex-col gap-2 overflow-x-auto">
                {f.versions.map((v) => (
                  <Version key={v.name} fam={f} v={v} operations={operations} canPlan={canPlan} canManage={canManage} actions={actions} />
                ))}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
