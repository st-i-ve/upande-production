import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Bar } from "@/components/Loading";
import { Button } from "@/components/ui/button";
import { SendBackDialog } from "@/components/approvals/SendBackDialog";
import { ProtocolRuleCheck } from "@/components/approvals/ProtocolRuleCheck";
import { ProtocolDiff } from "@/components/approvals/ProtocolDiff";
import type { PendingProtocol } from "@/lib/protocols-api";

/** Pending protocol versions with the diff against the previous version. Managers approve or send back. */
export function ProtocolReview({
  rows,
  busy,
  canReview,
  loading,
  onApprove,
  onSendBack,
}: {
  rows: PendingProtocol[] | null;
  busy: Set<string>;
  canReview: boolean;
  loading: boolean;
  onApprove: (p: PendingProtocol) => void;
  onSendBack: (p: PendingProtocol, note: string) => void;
}) {
  const [target, setTarget] = useState<PendingProtocol | null>(null);
  if (!rows && loading) {
    return (
      <div className="space-y-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] p-5 shadow-[var(--sd-shadow-1)]">
        <Bar className="h-5 w-56" />
        <Bar className="h-16 w-full" />
      </div>
    );
  }
  if (!rows?.length) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] px-6 py-14 text-center shadow-[var(--sd-shadow-1)]">
        <CheckCircle2 className="h-7 w-7 text-[var(--sd-quiet)]" />
        <h2 className="text-[15px] font-semibold text-[var(--sd-ink)]">No protocol versions waiting</h2>
        <p className="max-w-sm text-[13px] text-[var(--sd-muted)]">When a supervisor submits a new protocol version, it lands here for approval.</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4" data-testid="protocol-review">
      {rows.map((p) => (
        <article
          key={p.name}
          data-testid={`protocol-card-${p.name}`}
          className="flex flex-col gap-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] p-5 shadow-[var(--sd-shadow-1)]"
        >
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h3 className="text-[15px] font-semibold text-[var(--sd-ink)]">
                {p.protocol_name} <span className="text-[var(--sd-muted)]">v{p.version}</span>
              </h3>
              <p className="text-[12px] text-[var(--sd-muted)]">
                Submitted by {p.submitted_by_name ?? p.submitted_by ?? "unknown"}
                {p.previous_version ? ` · replaces ${p.previous_version}` : ""}
              </p>
            </div>
            {canReview && (
              <div className="flex gap-2">
                <Button type="button" variant="ghost" disabled={busy.has(p.name)} onClick={() => setTarget(p)}>
                  Send back
                </Button>
                <Button type="button" disabled={busy.has(p.name)} onClick={() => onApprove(p)}>
                  Approve
                </Button>
              </div>
            )}
          </header>
          <ProtocolRuleCheck problems={p.diff.rule_check} />
          <ProtocolDiff diff={p.diff} />
        </article>
      ))}
      <SendBackDialog
        open={!!target}
        cards={1}
        busy={false}
        onCancel={() => setTarget(null)}
        onConfirm={(note) => {
          const t = target;
          setTarget(null);
          if (t) onSendBack(t, note);
        }}
      />
    </div>
  );
}
