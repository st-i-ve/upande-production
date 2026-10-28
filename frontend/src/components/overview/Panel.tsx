import { cn } from "@/lib/utils";

/** SCP card with a heading row; shared by the Overview, Blocks and Value Adders pages. */
export function Panel({
  title,
  hint,
  tools,
  children,
  className,
  bodyClassName,
}: {
  title: React.ReactNode;
  hint?: React.ReactNode;
  tools?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section
      className={cn(
        "scp-card-in rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)]",
        className,
      )}
    >
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 px-5 pb-1 pt-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold tracking-tight text-[var(--sd-ink)]">{title}</h2>
          {hint && <p className="mt-0.5 text-[12px] text-[var(--sd-quiet)]">{hint}</p>}
        </div>
        {tools}
      </header>
      <div className={cn("px-5 pb-4 pt-2", bodyClassName)}>{children}</div>
    </section>
  );
}

export function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="py-3 text-[13px] text-[var(--sd-muted)]">{children}</p>;
}
