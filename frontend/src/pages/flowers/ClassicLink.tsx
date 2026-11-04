import { ExternalLink } from "lucide-react";

/** "Classic view": the legacy Crop Production screen this page was ported from (kept, same data). */
export function ClassicLink({ href, label = "Classic view" }: { href: string; label?: string }) {
  return (
    <a
      href={href}
      className="inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-[12px] font-medium text-[var(--sd-muted)] hover:bg-[var(--sd-bg-soft)] hover:text-[var(--sd-ink)]"
    >
      <ExternalLink className="h-3.5 w-3.5" aria-hidden />
      {label}
    </a>
  );
}
