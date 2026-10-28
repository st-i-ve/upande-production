import { PageShell } from "@/components/PageShell";
import { RowsSkeleton } from "@/components/Loading";
import { useCurrentCrop, viewLabel } from "@/lib/crops";

/** Stub: filled in by the Task 8 slice for this view. */
export function Plan() {
  const crop = useCurrentCrop();
  return (
    <PageShell title={viewLabel("plan", crop)} eyebrow={crop.name}>
      <div className="rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] px-4 py-4 shadow-[var(--sd-shadow-1)]">
        <RowsSkeleton rows={5} />
      </div>
    </PageShell>
  );
}
