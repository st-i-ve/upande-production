import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Undo2 } from "lucide-react";
import { cn } from "@/lib/utils";

/** Undocked pill at the bottom centre while cards are selected: "N selected · Approve · Send back". */
export function ActionPill({
  count,
  busy,
  onApprove,
  onSendBack,
  onClear,
}: {
  count: number;
  busy: boolean;
  onApprove: () => void;
  onSendBack: () => void;
  onClear: () => void;
}) {
  const want = count > 0;
  const [mounted, setMounted] = useState(want);
  const [shown, setShown] = useState(false);
  const [last, setLast] = useState(count);
  useEffect(() => {
    if (want) {
      setLast(count);
      setMounted(true);
      const id = requestAnimationFrame(() => setShown(true));
      return () => cancelAnimationFrame(id);
    }
    setShown(false);
    const id = window.setTimeout(() => setMounted(false), 220);
    return () => window.clearTimeout(id);
  }, [want, count]);
  if (!mounted) return null;
  const n = want ? count : last;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-5 z-30 flex justify-center px-4">
      <div
        role="toolbar"
        aria-label="Selected submissions"
        data-testid="approval-action-pill"
        className={cn(
          "pointer-events-auto flex max-w-full items-center gap-2 rounded-full bg-[var(--sd-card)] py-2 pl-5 pr-2 shadow-[var(--sd-shadow-4)] transition-all duration-200 ease-out",
          shown ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0",
        )}
      >
        <button type="button" onClick={onClear} className="mr-1 text-[12px] text-[var(--sd-muted)] hover:text-[var(--sd-ink)]">
          <span className="font-semibold text-[var(--sd-ink)]">{n}</span> selected
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onSendBack}
          className="inline-flex h-9 items-center gap-1.5 rounded-full px-4 text-[12.5px] font-medium text-[var(--sd-ink)] transition-colors hover:bg-[rgba(10,10,10,0.06)] disabled:opacity-50"
        >
          <Undo2 className="h-3.5 w-3.5" /> Send back
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onApprove}
          className="inline-flex h-9 items-center gap-1.5 rounded-full bg-[var(--sd-ink)] px-4 text-[12.5px] font-medium text-[var(--sd-card)] transition-colors hover:opacity-90 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />} Approve
        </button>
      </div>
    </div>
  );
}
