import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";

export function Chip({ children, className, title }: { children: React.ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-[var(--sd-radius-pill)] px-2 py-0.5 text-[11px] font-medium tabular-nums",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Fact({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "bad" | "warn" }) {
  return (
    <div title={hint}>
      <div className="text-[10.5px] font-medium uppercase tracking-[0.12em] text-[var(--sd-quiet)]">{label}</div>
      <div
        className={cn(
          "mt-0.5 text-[13px] font-semibold tabular-nums",
          tone === "bad" && "text-[var(--sd-data-red)]",
          tone === "warn" && "text-[var(--sd-target)]",
        )}
      >
        {value}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-2xl bg-[var(--sd-card)] px-5 py-10 text-center text-[13px] text-[var(--sd-quiet)] shadow-[var(--sd-shadow-1)]">
      {children}
    </p>
  );
}

/** A labelled dialog field. */
export function Field({
  id,
  label,
  hint,
  className,
  children,
}: {
  id?: string;
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-[12px] text-[var(--sd-quiet)]">{hint}</p>}
    </div>
  );
}

export function Problems({ show, items }: { show: boolean; items: string[] }) {
  if (!show || !items.length) return null;
  return (
    <ul role="alert" className="list-disc space-y-0.5 pl-5 text-[12.5px] text-[var(--sd-data-red)]">
      {items.map((p) => (
        <li key={p}>{p}</li>
      ))}
    </ul>
  );
}

/** Recharts tooltip body in the app's dark chip. */
export function TipBox({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <div className="rounded-lg bg-foreground px-3 py-2 text-[12px] text-background shadow-[var(--sd-shadow-3)]">
      <div className="font-semibold">{title}</div>
      {rows.map(([k, v]) => (
        <div key={k}>
          {k}: {v}
        </div>
      ))}
    </div>
  );
}

export const AXIS = { fontSize: 11, fill: "var(--sd-quiet)" } as const;
