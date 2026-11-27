/** The portrait card: the Employee photo in a 4:5 frame (initials without one), the name on the picture,
 *  a pill, and the facts you would say out loud to identify the person. */
import { useState } from "react";
import { TextSkeleton } from "@/components/Loading";
import { tintFor } from "@/components/people/PersonAvatar";
import { initialsOf } from "@/lib/people";

export interface Fact {
  label: string;
  value: string;
}

export function PersonPortrait({ id, name, image, pill, facts }: { id: string; name: string; image?: string | null; pill?: string; facts: Fact[] }) {
  const [failed, setFailed] = useState(false);
  const tone = tintFor(id || name);
  return (
    <div className="flex flex-col gap-4">
      <div className="relative aspect-[4/5] w-full overflow-hidden rounded-[var(--sd-radius-card)] bg-[var(--sd-bg-soft)] shadow-[var(--sd-shadow-1)]">
        {image && !failed ? (
          <img src={image} alt={name} decoding="async" className="h-full w-full object-cover" onError={() => setFailed(true)} />
        ) : (
          <div
            className="flex h-full w-full items-center justify-center"
            style={{ background: `color-mix(in srgb, ${tone} 16%, var(--sd-bg-soft))` }}
            aria-label={`${name}, no photograph`}
          >
            <span className="select-none text-[64px] font-semibold leading-none tracking-[-0.04em]" style={{ color: `color-mix(in srgb, ${tone} 72%, var(--sd-ink))` }}>
              {initialsOf(name)}
            </span>
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 bg-gradient-to-t from-[rgba(10,10,10,0.72)] to-transparent px-4 pb-3.5 pt-10">
          <div className="min-w-0">
            <p className="truncate text-[19px] font-semibold leading-tight tracking-[-0.02em] text-white">{name}</p>
            <p className="text-[12px] tabular-nums text-white/70">{id}</p>
          </div>
          {pill && (
            <span className="shrink-0 rounded-[var(--sd-radius-pill)] bg-white/20 px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-white backdrop-blur">{pill}</span>
          )}
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {facts.map((f) => (
          <div key={f.label} className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-[10px] font-medium uppercase tracking-[0.13em] text-[var(--sd-quiet)]">{f.label}</dt>
            <dd className="truncate text-[13px] text-[var(--sd-ink)]" title={f.value}>{f.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** The photo frame and fact labels pending, so the card keeps its height. */
export function PersonPortraitSkeleton({ facts = [] }: { facts?: string[] }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="aspect-[4/5] w-full animate-pulse rounded-[var(--sd-radius-card)] bg-[var(--sd-bg-soft)]" aria-hidden />
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {facts.map((label) => (
          <div key={label} className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-[10px] font-medium uppercase tracking-[0.13em] text-[var(--sd-quiet)]">{label}</dt>
            <dd className="h-[19.5px] py-[3px]"><TextSkeleton width="9ch" /></dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
