import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, TriangleAlert } from "lucide-react";
import { Bar } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { changeLines } from "@/lib/cycle-changes";
import {
  approveCycleChange,
  listCycleChanges,
  rejectCycleChange,
  resubmitCycleChange,
  sendBackCycleChange,
  withdrawCycleChange,
  type CycleChangeRequest,
} from "@/lib/cycle-setup-api";
import { isError } from "@/lib/frappe";

const STALE = /changed since/i;

/** Asks for the note the requester will read. */
function NoteDialog({
  title,
  confirm,
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  confirm: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onCancel()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>The requester reads this note. The cycle stays as it is.</DialogDescription>
        </DialogHeader>
        <Textarea aria-label="Note for the requester" value={note} onChange={(e) => setNote(e.target.value)} rows={4} autoFocus />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button type="button" disabled={!note.trim() || busy} onClick={() => onConfirm(note.trim())}>
            {confirm}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Cycle change requests. A manager sees every request and approves, sends back or rejects it; anyone else sees
 * their own and withdraws it, or edits and resubmits one that was sent back. The server refuses to apply a change
 * over a value that has moved since the request was made: the card then warns and holds Approve until "Apply anyway"
 * is ticked.
 */
export function CycleChanges({
  crop,
  isManager,
  onChanged,
  onEdit,
  reloadKey = 0,
}: {
  crop: string;
  /** Bump to load the list again (after a resubmit made elsewhere). */
  reloadKey?: number;
  isManager: boolean;
  onChanged: () => void;
  /** Opens the edit form of a request that was sent back (the page owns the dialog). */
  onEdit?: (r: CycleChangeRequest) => void;
}) {
  const toast = useToast();
  const [rows, setRows] = useState<CycleChangeRequest[] | null>(null);
  const [busy, setBusy] = useState<Set<string>>(new Set());
  const [stale, setStale] = useState<Record<string, string>>({});
  const [anyway, setAnyway] = useState<Record<string, boolean>>({});
  const [note, setNote] = useState<{ row: CycleChangeRequest; kind: "back" | "reject" } | null>(null);

  const load = useCallback(async () => {
    const r = await listCycleChanges(null, crop);
    if (isError(r)) toast(r.error, "error");
    else setRows((r as { rows: CycleChangeRequest[] }).rows);
  }, [crop, toast]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  async function act(row: CycleChangeRequest, run: () => ReturnType<typeof approveCycleChange>, done: string) {
    setBusy((b) => new Set([...b, row.name]));
    const r = await run();
    setBusy((b) => new Set([...b].filter((k) => k !== row.name)));
    if (isError(r)) {
      if (STALE.test(r.error)) setStale((s) => ({ ...s, [row.name]: r.error }));
      else toast(r.error, "error");
      return false;
    }
    toast(done);
    onChanged();
    await load();
    return true;
  }

  const approve = (row: CycleChangeRequest) =>
    act(row, () => approveCycleChange(row.name, stale[row.name] && anyway[row.name] ? 1 : 0), row.action === "Delete" ? `Cycle ${row.cycle} deleted.` : `Change to ${row.cycle} applied.`);

  async function confirmNote(text: string) {
    if (!note) return;
    const { row, kind } = note;
    const ok = await act(
      row,
      () => (kind === "back" ? sendBackCycleChange(row.name, text) : rejectCycleChange(row.name, text)),
      kind === "back" ? "Sent back to the requester." : "Request rejected.",
    );
    if (ok) setNote(null);
  }

  if (!rows) {
    return (
      <div className="space-y-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] p-5 shadow-[var(--sd-shadow-1)]">
        <Bar className="h-5 w-56" />
        <Bar className="h-16 w-full" />
      </div>
    );
  }
  if (!rows.length) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] px-6 py-14 text-center shadow-[var(--sd-shadow-1)]">
        <CheckCircle2 className="h-7 w-7 text-[var(--sd-quiet)]" />
        <h2 className="text-[15px] font-semibold text-[var(--sd-ink)]">No cycle changes</h2>
        <p className="max-w-sm text-[13px] text-[var(--sd-muted)]">
          {isManager ? "When someone asks to change or delete a cycle, the request lands here." : "Changes you ask for on a cycle are listed here with their answer."}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4" data-testid="cycle-changes">
      {rows.map((r) => {
        const lines = changeLines(r.changes);
        const wait = busy.has(r.name);
        const held = !!stale[r.name] && !anyway[r.name];
        return (
          <article
            key={r.name}
            data-testid={`cycle-change-${r.name}`}
            className="flex flex-col gap-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] p-5 shadow-[var(--sd-shadow-1)]"
          >
            <header className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <h3 className="text-[15px] font-semibold text-[var(--sd-ink)]">
                  {r.action === "Delete" ? "Delete" : "Change"} {r.cycle}
                  <span className="text-[var(--sd-muted)]"> · {r.unit ?? "cycle removed"}{r.cycle_title ? ` · ${r.cycle_title}` : ""}</span>
                </h3>
                <p className="text-[12px] text-[var(--sd-muted)]">Asked by {r.requested_by}</p>
              </div>
              <span className="rounded-full bg-[var(--sd-chip)] px-2 py-0.5 text-[11.5px] text-[var(--sd-muted)]">{r.status}</span>
            </header>
            {r.action === "Delete" ? (
              <p className="text-[13px] text-[var(--sd-ink)]">Delete this cycle.</p>
            ) : (
              <ul className="text-[13px] text-[var(--sd-ink)]">
                {lines.map((l) => (
                  <li key={l.field}>
                    <span className="text-[var(--sd-muted)]">{l.label}:</span> {l.old} → {l.next}
                  </li>
                ))}
              </ul>
            )}
            {r.reason && <p className="text-[13px] text-[var(--sd-muted)]">Reason: {r.reason}</p>}
            {r.review_note && <p className="text-[13px] text-[var(--sd-muted)]">Note: {r.review_note}</p>}
            {!!Number(r.stale) && <p className="text-[12px] text-[var(--sd-muted)]">Applied over a newer value.</p>}

            {isManager && r.status === "Pending" && stale[r.name] && (
              <div role="alert" className="flex flex-col gap-2 rounded-[var(--sd-radius-md)] bg-[var(--sd-alert-warn)] px-3 py-2 text-[12.5px] text-[var(--sd-sev-high)]">
                <span className="flex items-start gap-2">
                  <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {stale[r.name]}
                </span>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={!!anyway[r.name]} onChange={(e) => setAnyway((a) => ({ ...a, [r.name]: e.target.checked }))} />
                  Apply anyway
                </label>
              </div>
            )}

            <div className="flex flex-wrap justify-end gap-2">
              {isManager && r.status === "Pending" && (
                <>
                  <Button variant="outline" disabled={wait} onClick={() => setNote({ row: r, kind: "reject" })}>
                    Reject
                  </Button>
                  <Button variant="outline" disabled={wait} onClick={() => setNote({ row: r, kind: "back" })}>
                    Send back
                  </Button>
                  <Button disabled={wait || held} onClick={() => void approve(r)}>
                    Approve
                  </Button>
                </>
              )}
              {!isManager && (r.status === "Pending" || r.status === "Sent Back") && (
                <Button variant="outline" disabled={wait} onClick={() => void act(r, () => withdrawCycleChange(r.name), "Request withdrawn.")}>
                  Withdraw
                </Button>
              )}
              {!isManager && r.status === "Sent Back" && (
                r.action === "Edit" ? (
                  <Button disabled={wait} onClick={() => onEdit?.(r)}>
                    Edit &amp; resubmit
                  </Button>
                ) : (
                  <Button disabled={wait} onClick={() => void act(r, () => resubmitCycleChange(r.name, {}), "Sent to a manager for approval")}>
                    Resubmit
                  </Button>
                )
              )}
            </div>
          </article>
        );
      })}
      {note && (
        <NoteDialog
          title={note.kind === "back" ? `Send back the change to ${note.row.cycle}` : `Reject the change to ${note.row.cycle}`}
          confirm={note.kind === "back" ? "Send back" : "Reject"}
          busy={busy.has(note.row.name)}
          onCancel={() => setNote(null)}
          onConfirm={(t) => void confirmNote(t)}
        />
      )}
    </div>
  );
}
