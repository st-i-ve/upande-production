import { useState } from "react";
import { AlertTriangle, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { RuleStatus } from "@/lib/api";
import type { Breach } from "@/lib/rules";
import { cn } from "@/lib/utils";

const PILL = "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11.5px] font-medium";

/** Block (red) / Warn (amber) pill; nothing for OK. */
export function EnforcementPill({ status, className }: { status: string | null | undefined; className?: string }) {
  if (status !== "Block" && status !== "Warn") return null;
  return (
    <span
      className={cn(
        PILL,
        status === "Block" ? "bg-[var(--sd-alert-error)] text-[var(--sd-sev-critical)]" : "bg-[var(--sd-amber-bg)] text-[var(--sd-amber)]",
        className,
      )}
    >
      {status === "Block" ? <ShieldAlert className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
      {status}
    </span>
  );
}

/** A task's rule flag; the tooltip carries the rule notes and the reason the supervisor gave. */
export function RuleFlag({
  status,
  notes,
  overrideReason,
}: {
  status: RuleStatus | string | null | undefined;
  notes?: string | null;
  overrideReason?: string | null;
}) {
  if (status !== "Block" && status !== "Warn") return null;
  const tip = [notes, overrideReason ? `Reason given: ${overrideReason}` : null].filter(Boolean).join("\n");
  return (
    <span data-testid="rule-flag" title={tip || undefined} aria-label={`Rule ${status}${tip ? `: ${tip}` : ""}`}>
      <EnforcementPill status={status} />
    </span>
  );
}

/** The messages of the rules a call broke. */
export function BreachList({ breaches, className }: { breaches: Breach[]; className?: string }) {
  if (!breaches.length) return null;
  return (
    <ul className={cn("flex flex-col gap-1.5", className)} data-testid="breach-list">
      {breaches.map((b, i) => (
        <li key={`${b.rule}-${i}`} className="flex items-start gap-2 text-[13px] text-[var(--sd-ink)]">
          <EnforcementPill status={b.enforcement} className="mt-0.5 shrink-0" />
          <span className="min-w-0 break-words">{b.message}</span>
        </li>
      ))}
    </ul>
  );
}

/** Block: the rules that stop the save, shown inline in a dialog. */
export function BlockNotice({ breaches }: { breaches: Breach[] }) {
  return (
    <div role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2.5">
      <p className="mb-2 text-[13px] font-semibold text-[var(--sd-ink)]">An activity rule stops this. It cannot be saved.</p>
      <BreachList breaches={breaches} />
    </div>
  );
}

/** Warn: the work is allowed once a reason is given; the manager sees the reason in Approvals. */
export function OverrideReasonDialog({
  breaches,
  busy,
  onConfirm,
  onCancel,
}: {
  breaches: Breach[];
  busy?: boolean;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const ok = reason.trim().length > 0;
  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onCancel()}>
      <DialogContent className="max-w-md" aria-describedby="override-desc">
        <DialogHeader>
          <DialogTitle>Go ahead despite the rule?</DialogTitle>
          <DialogDescription id="override-desc">
            This breaks an activity rule that only warns. Give a reason; the manager will see it when approving.
          </DialogDescription>
        </DialogHeader>
        <BreachList breaches={breaches} />
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="override-reason">Reason</Label>
          <Textarea id="override-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why does this need to happen now?" />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => onConfirm(reason.trim())} disabled={busy || !ok}>
            {busy ? "Saving…" : "Save with reason"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
