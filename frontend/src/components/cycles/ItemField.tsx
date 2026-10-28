import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { searchItems } from "@/lib/frappe";

type Hit = { name: string; item_name: string; stock_uom: string };

/** The Item a cycle grows: type a name, pick from the item master's matches.
 *  The typed text is the value, so an item that is not offered can still be
 *  entered by its exact code. */
export function ItemField({
  id,
  value,
  onChange,
}: {
  id?: string;
  value: string;
  onChange: (next: string) => void;
}) {
  const [hits, setHits] = useState<Hit[]>([]);
  const [focus, setFocus] = useState(false);
  const picked = useRef(value);

  useEffect(() => {
    if (!focus || value.trim().length < 2 || value === picked.current) {
      setHits([]);
      return;
    }
    let live = true;
    const t = setTimeout(() => {
      void searchItems(value.trim()).then((r) => live && setHits(r.slice(0, 8)));
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [value, focus]);

  return (
    <div className="relative">
      <Input
        id={id}
        value={value}
        placeholder="Item name"
        autoComplete="off"
        onFocus={() => setFocus(true)}
        onBlur={() => setTimeout(() => setFocus(false), 150)}
        onChange={(e) => {
          picked.current = "";
          onChange(e.target.value);
        }}
      />
      {focus && hits.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-[var(--sd-radius)] border border-[var(--sd-line)] bg-[var(--sd-card)] p-1 shadow-[var(--sd-shadow-3)]"
        >
          {hits.map((h) => (
            <li key={h.name} role="option" aria-selected={h.name === value}>
              <button
                type="button"
                className="flex w-full items-baseline justify-between gap-3 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-[var(--sd-bg-soft)]"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  picked.current = h.name;
                  onChange(h.name);
                  setHits([]);
                }}
              >
                <span className="truncate text-[var(--sd-ink)]">{h.item_name}</span>
                <span className="shrink-0 text-[11px] tabular-nums text-[var(--sd-quiet)]">{h.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
