import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

/** The person's photo (Employee image), initials when there is none. */
export function Portrait({ name, image, className }: { name: string; image?: string | null; className?: string }) {
  return (
    <Avatar className={cn("h-12 w-12", className)}>
      {image ? <AvatarImage src={image} alt={name} /> : null}
      <AvatarFallback className="flex h-full w-full items-center justify-center rounded-full bg-[var(--sd-pistachio)] text-[13px] font-semibold text-[var(--sd-ink)]">
        {initials(name)}
      </AvatarFallback>
    </Avatar>
  );
}
