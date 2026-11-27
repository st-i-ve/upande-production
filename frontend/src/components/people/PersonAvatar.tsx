/** A person's face: the Employee photo, initials on a tint when there is none or it fails to load. */
import { useState } from "react";
import { initialsOf } from "@/lib/people";
import { cn } from "@/lib/utils";

export function tintFor(key: string): string {
  const tints = [
    "var(--sd-data-cyan)",
    "var(--sd-data-indigo)",
    "var(--sd-data-green)",
    "var(--sd-data-purple)",
    "var(--sd-data-amber)",
    "var(--sd-data-pink)",
  ];
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return tints[h % tints.length]!;
}

export function PersonAvatar({
  id,
  name,
  image,
  size = 36,
  className,
}: {
  id: string;
  name: string;
  image?: string | null;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const photo = !!image && !failed;
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full ring-1 ring-[var(--sd-line)]", className)}
      style={{ width: size, height: size }}
      aria-hidden
    >
      {photo ? (
        <img src={image!} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <span
          className="flex h-full w-full items-center justify-center font-semibold text-white"
          style={{ background: tintFor(id || name), fontSize: Math.round(size * 0.32) }}
        >
          {initialsOf(name)}
        </span>
      )}
    </span>
  );
}
