/**
 * Small pieces shared by the Season Outlook and Block Forecast pages: tonne formatting,
 * the section card, figure tiles, share bars, empty states and the toolbar pill editor.
 * Highlights use the crop accent through `--crop-accent` (set on each page's root).
 */
import { useEffect, useState } from "react";
import { HEADER_PILL } from "@/components/header-controls";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle, CardTools } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { qty } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Kilograms for display as tonnes: 12,345 kg -> "12.3 t"; small amounts stay in kg. */
export function tonnes(kg: number | null | undefined, digits = 1): string {
  if (kg == null || !Number.isFinite(kg)) return "—";
  if (Math.abs(kg) < 1000) return `${qty(kg)} kg`;
  return `${qty(kg / 1000, digits)} t`;
}

/** Signed tonnes: +3.7 t / -161.7 t. */
export function signedTonnes(kg: number): string {
  return `${kg >= 0 ? "+" : "-"}${tonnes(Math.abs(kg))}`;
}

export const pct1 = (n: number | null | undefined) => (n == null ? "—" : `${qty(n, 1)}%`);

/** KES with compact millions/thousands: 14,282,980 -> "KES 14.3M". */
export function kesShort(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e6) return `KES ${qty(n / 1e6, 1)}M`;
  if (a >= 1e4) return `KES ${qty(n / 1e3, 0)}K`;
  return `KES ${qty(n)}`;
}

/** 2026-10-26 -> "26 Oct". */
export function dayMonth(ymd: string | null | undefined): string {
  if (!ymd) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ymd);
  if (!m) return "—";
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

export const ACCENT = "var(--sd-data-green, #3f7d3a)";

export function SectionCard({
  title,
  description,
  tools,
  children,
  className,
  testId,
}: {
  title: string;
  description?: React.ReactNode;
  tools?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <Card className={cn("scp-card-in overflow-hidden", className)} data-testid={testId}>
      <CardHeaderRow className="pb-2">
        <CardHeading>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription className="max-w-[70ch] text-[13px]">{description}</CardDescription>}
        </CardHeading>
        {tools && <CardTools>{tools}</CardTools>}
      </CardHeaderRow>
      <div className="px-5 pb-5">{children}</div>
    </Card>
  );
}

/** A figure tile inside a section: label, number, one-line hint. */
export function Fig({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "good" | "bad";
}) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--sd-quiet)]">{label}</div>
      <div
        className={cn(
          "mt-1 text-[26px] font-semibold leading-none tracking-[-0.02em] tabular-nums",
          tone === "good" && "text-[var(--sd-data-green)]",
          tone === "bad" && "text-[var(--sd-sev-critical)]",
        )}
      >
        {value}
      </div>
      {hint && <div className="mt-1.5 text-[12px] leading-snug text-[var(--sd-quiet)]">{hint}</div>}
    </div>
  );
}

export function FigRow({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-x-6 gap-y-5 md:grid-cols-4">{children}</div>;
}

/** A horizontal share bar, 0-100 of its track, filled in the crop accent. */
export function ShareBar({ pct, className, tone }: { pct: number | null | undefined; className?: string; tone?: "bad" | "muted" }) {
  const w = Math.max(0, Math.min(100, pct ?? 0));
  return (
    <div className={cn("h-2 min-w-[96px] overflow-hidden rounded-full bg-[var(--sd-ink)]/[0.06]", className)}>
      <div
        className="h-full rounded-full"
        style={{
          width: `${w}%`,
          background: tone === "bad" ? "var(--sd-sev-critical)" : tone === "muted" ? "var(--sd-series-4)" : ACCENT,
        }}
      />
    </div>
  );
}

/** What a section says when it has nothing: the original's helpful sentence. */
export function EmptyNote({ children, big }: { children: React.ReactNode; big?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-[var(--sd-radius-lg)] border border-dashed border-[var(--sd-line)] px-4 text-[13px] leading-relaxed text-[var(--sd-quiet)]",
        big ? "flex min-h-[160px] items-center justify-center py-8 text-center" : "py-4",
      )}
    >
      {children}
    </div>
  );
}

export function Chip({
  children,
  kind,
  className,
}: {
  children: React.ReactNode;
  kind?: "neg" | "warn" | "good" | "";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[12px] font-medium tabular-nums",
        !kind && "bg-[var(--sd-ink)]/[0.06] text-[var(--sd-text)]",
        kind === "neg" && "bg-[var(--sd-sev-critical)]/10 text-[var(--sd-sev-critical)]",
        kind === "warn" && "bg-[var(--sd-sev-high)]/15 text-[#9a6313]",
        kind === "good" && "bg-[var(--sd-data-green)]/12 text-[var(--sd-data-green)]",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Legend({ items }: { items: { color: string; label: string; dashed?: boolean }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-[var(--sd-quiet)]">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-[3px]" style={{ background: i.color, opacity: i.dashed ? 0.5 : 1 }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

/**
 * A toolbar pill that edits one number in a small popover ("Price / kg  KES 95").
 * `onSave` returns true when the write succeeded (the popover then closes).
 */
export function PillEditor({
  label,
  display,
  value,
  unit,
  step = 1,
  onSave,
  className,
}: {
  label: string;
  display: string;
  value: number;
  unit?: string;
  step?: number;
  onSave: (next: number) => Promise<boolean> | boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(String(value));
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setText(String(value));
  }, [open, value]);
  const n = Number(text);
  const valid = text.trim() !== "" && Number.isFinite(n) && n >= 0;

  async function save() {
    if (!valid) return;
    setBusy(true);
    const ok = await onSave(n);
    setBusy(false);
    if (ok) setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`${label}: ${display}`}
          className={cn(HEADER_PILL, "inline-flex cursor-pointer items-center justify-center whitespace-nowrap transition-all", className)}
        >
          <span className="text-[var(--sd-quiet)]">{label}</span>
          <span className="font-semibold tabular-nums">{display}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64" align="end">
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <label className="text-[12px] font-medium text-[var(--sd-muted)]" htmlFor={`pe-${label}`}>
            {label}
            {unit ? ` (${unit})` : ""}
          </label>
          <Input
            id={`pe-${label}`}
            type="number"
            inputMode="decimal"
            min={0}
            step={step}
            value={text}
            onChange={(e) => setText(e.target.value)}
            autoFocus
            className="tabular-nums"
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={!valid || busy}>
              {busy ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}
