import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SendBackDialog } from "@/components/approvals/SendBackDialog";
import { qty } from "@/lib/format";
import type { ProtocolFamily, ProtocolStep, ProtocolVersion, VersionStatus } from "@/lib/protocols-api";
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

function cadence(s: ProtocolStep): string {
  const every = Number(s.repeat_every_days || 0);
  const times = Number(s.repeat_count || 1);
  return every > 0 && times > 1 ? `every ${every} d, ${times} times` : "once";
}

export interface ProtocolActions {
  newVersion: (v: ProtocolVersion) => void;
  submit: (v: ProtocolVersion) => void;
  approve: (v: ProtocolVersion) => void;
  sendBack: (v: ProtocolVersion, note: string) => void;
  saveDraft: (v: ProtocolVersion, steps: ProtocolStep[]) => void;
}

function Steps({ v, opNames, editable, onSave }: {
  v: ProtocolVersion;
  opNames: Record<string, string>;
  editable: boolean;
  onSave: (steps: ProtocolStep[]) => void;
}) {
  const [steps, setSteps] = useState<ProtocolStep[]>(v.steps);
  const dirty = JSON.stringify(steps) !== JSON.stringify(v.steps);
  const set = (i: number, k: keyof ProtocolStep, val: string) =>
    setSteps((rows) => rows.map((r, j) => (j === i ? { ...r, [k]: k === "note" ? val : val === "" ? null : Number(val) } : r)));
  if (!steps.length) return <p className="text-[12px] text-[var(--sd-muted)]">This version has no steps.</p>;
  return (
    <div>
      <table className="w-full min-w-[28rem] text-[12.5px]">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
            <th className="py-1.5 pr-3 font-medium">Day</th>
            <th className="py-1.5 pr-3 font-medium">Operation</th>
            <th className="py-1.5 pr-3 font-medium">Repeats</th>
            <th className="py-1.5 pr-3 text-right font-medium">Planned qty</th>
            <th className="py-1.5 font-medium">Note</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((s, i) => {
            const op = (s.operation && opNames[s.operation]) || s.operation || "—";
            return (
              <tr key={i}>
                {editable ? (
                  <>
                    <td className="py-1 pr-2"><Input aria-label={`Day for ${op}`} className="h-8 w-16" type="number" value={s.day_offset ?? ""} onChange={(e) => set(i, "day_offset", e.target.value)} /></td>
                    <td className="py-1 pr-3 font-medium text-[var(--sd-ink)]">{op}</td>
                    <td className="py-1 pr-2">
                      <span className="flex items-center gap-1">
                        <Input aria-label={`Repeat every for ${op}`} className="h-8 w-14" type="number" value={s.repeat_every_days ?? ""} onChange={(e) => set(i, "repeat_every_days", e.target.value)} />
                        <span className="text-[var(--sd-muted)]">d x</span>
                        <Input aria-label={`Repeat count for ${op}`} className="h-8 w-14" type="number" value={s.repeat_count ?? ""} onChange={(e) => set(i, "repeat_count", e.target.value)} />
                      </span>
                    </td>
                    <td className="py-1 pr-2 text-right"><Input aria-label={`Planned qty for ${op}`} className="ml-auto h-8 w-20 text-right" type="number" value={s.planned_qty ?? ""} onChange={(e) => set(i, "planned_qty", e.target.value)} /></td>
                    <td className="py-1"><Input aria-label={`Note for ${op}`} className="h-8" value={s.note ?? ""} onChange={(e) => set(i, "note", e.target.value)} /></td>
                  </>
                ) : (
                  <>
                    <td className="py-1.5 pr-3 tabular-nums text-[var(--sd-muted)]">{s.day_offset ?? 0}</td>
                    <td className="py-1.5 pr-3 font-medium text-[var(--sd-ink)]">{op}</td>
                    <td className="py-1.5 pr-3 text-[var(--sd-muted)]">{cadence(s)}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{s.planned_qty ? qty(s.planned_qty, 1) : "—"}</td>
                    <td className="py-1.5 text-[var(--sd-muted)]">{s.note || ""}</td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      {editable && (
        <div className="mt-2 flex justify-end">
          <Button type="button" size="sm" disabled={!dirty} onClick={() => onSave(steps)}>Save draft</Button>
        </div>
      )}
    </div>
  );
}

function Version({ fam, v, opNames, canPlan, canManage, actions }: {
  fam: ProtocolFamily;
  v: ProtocolVersion;
  opNames: Record<string, string>;
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
      <Steps key={JSON.stringify(v.steps)} v={v} opNames={opNames} editable={v.version_status === "Draft" && canPlan} onSave={(s) => actions.saveDraft(v, s)} />
      <SendBackDialog open={asking} cards={1} busy={false} onCancel={() => setAsking(false)} onConfirm={(n) => { setAsking(false); actions.sendBack(v, n); }} />
    </div>
  );
}

/** Protocol families, each opening to its versions (status chips, steps, actions). Edit only on Drafts. */
export function ProtocolsList({ families, opNames, canPlan, canManage, actions }: {
  families: ProtocolFamily[];
  opNames: Record<string, string>;
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
                  v{shown.version} · {shown.steps.length} {shown.steps.length === 1 ? "step" : "steps"}
                </span>
              </span>
            </button>
            {expanded && (
              <div className="mb-1 ml-7 flex flex-col gap-2 overflow-x-auto">
                {f.versions.map((v) => (
                  <Version key={v.name} fam={f} v={v} opNames={opNames} canPlan={canPlan} canManage={canManage} actions={actions} />
                ))}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
