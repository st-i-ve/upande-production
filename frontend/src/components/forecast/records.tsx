import { Label } from "@/components/ui/label";

/** A labelled form row used by the dialogs on this page. */
export function Field({ label, htmlFor, children }: { label: string; htmlFor?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor} className="text-[12px] text-[var(--sd-muted)]">
        {label}
      </Label>
      {children}
    </div>
  );
}

export function EmptyRows({ children }: { children: React.ReactNode }) {
  return <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">{children}</p>;
}

export const TH = "px-3 py-2.5 font-medium";
export const THR = `${TH} text-right`;
export const HEAD_ROW = "border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]";
export const BODY_ROW = "border-b border-[var(--sd-line-soft)] last:border-0";
