import { PageShell } from "@/components/PageShell";
import { useCurrentCrop, viewLabel } from "@/lib/crops";

/** Placeholder — replaced by the page's real implementation. */
export function DryMatter() {
  const crop = useCurrentCrop();
  return <PageShell eyebrow={crop.name} title={viewLabel("dry-matter", crop)} />;
}
