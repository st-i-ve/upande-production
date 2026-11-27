/** The left column: everyone, searchable, the selected one marked by fill. */
import { useMemo, useState } from "react";
import { AvatarSkeleton, TextSkeleton } from "@/components/Loading";
import { SearchInput } from "@/components/SearchInput";
import { PersonAvatar } from "@/components/people/PersonAvatar";
import { cn } from "@/lib/utils";

export interface PersonListItem {
  id: string;
  name: string;
  image?: string | null;
  /** second line: section, supervisor, last day worked ... */
  sub?: string;
  /** extra text the search also matches */
  keywords?: string;
  inactive?: boolean;
  /** right-hand figure and its caption */
  figure?: string;
  figureHint?: string;
}

export function PersonList({
  items,
  selectedId,
  onSelect,
  placeholder = "Name or ID…",
  label = "Find a person",
  noun = "people",
  loading = false,
}: {
  items: PersonListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  placeholder?: string;
  label?: string;
  noun?: string;
  /** First load: the search box stays, the rows are placeholders. */
  loading?: boolean;
}) {
  const [term, setTerm] = useState("");
  const shown = useMemo(() => {
    const q = term.trim().toLowerCase();
    if (!q) return items;
    return items.filter((p) => [p.id, p.name, p.sub || "", p.keywords || ""].some((f) => f.toLowerCase().includes(q)));
  }, [items, term]);

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <SearchInput size="md" value={term} onChange={setTerm} placeholder={placeholder} aria-label={label} disabled={loading} />
      <p className="px-1 text-[11.5px] text-[var(--sd-quiet)]">
        {loading ? <TextSkeleton width="9ch" /> : shown.length === items.length ? `${items.length} ${noun}` : `${shown.length} of ${items.length}`}
      </p>
      <div className="flex max-h-[min(62vh,600px)] min-h-0 flex-col gap-1 overflow-y-auto" aria-busy={loading || undefined}>
        {loading && (
          <ul className="flex flex-col gap-1" aria-hidden data-skeleton="person-list">
            {Array.from({ length: 7 }, (_, i) => (
              <li key={i} className="flex items-center gap-3 px-3 py-2.5">
                <AvatarSkeleton size={32} />
                <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <span className="block h-[13px] animate-pulse rounded bg-[var(--sd-bg-soft)]" style={{ width: `${48 + ((i * 11) % 28)}%` }} />
                  <span className="block h-[10px] w-[40%] animate-pulse rounded bg-[var(--sd-bg-soft)]" />
                </span>
              </li>
            ))}
          </ul>
        )}
        <ul className="flex flex-col gap-1">
          {shown.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onSelect(p.id)}
                data-testid={`person-${p.id}`}
                aria-current={p.id === selectedId ? "true" : undefined}
                className={cn(
                  "flex w-full items-center gap-3 rounded-[var(--sd-radius-lg)] px-3 py-2.5 text-left transition-colors",
                  p.id === selectedId ? "bg-[var(--sd-bg-soft)]" : "hover:bg-[var(--sd-bg-soft)]",
                  p.inactive && "opacity-60",
                )}
              >
                <PersonAvatar id={p.id} name={p.name} image={p.image} />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-[13.5px] font-medium text-[var(--sd-ink)]">{p.name}</span>
                  {p.sub && <span className="truncate text-[11.5px] text-[var(--sd-muted)]">{p.sub}</span>}
                </span>
                {p.figure != null && (
                  <span className="flex shrink-0 flex-col items-end">
                    <span className="text-[13px] font-semibold tabular-nums text-[var(--sd-ink)]">{p.figure}</span>
                    {p.figureHint && <span className="text-[10px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">{p.figureHint}</span>}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
        {!shown.length && !loading && (
          <p className="rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-3 py-6 text-center text-[12.5px] text-[var(--sd-muted)]">
            {term ? `Nobody matches “${term}”.` : `No ${noun} to show.`}
          </p>
        )}
      </div>
    </div>
  );
}
