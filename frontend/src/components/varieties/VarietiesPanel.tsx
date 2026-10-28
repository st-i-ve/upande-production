import { useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { StageTimeline } from "@/components/varieties/StageEditor";
import { VarietyDialog } from "@/components/varieties/VarietyDialog";
import { Button } from "@/components/ui/button";
import { qty } from "@/lib/format";
import type { Variety } from "@/lib/varieties-api";

const CARD = "rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)]";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-[7rem] flex-col">
      <span className="text-[10.5px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">{label}</span>
      <span className="text-[13.5px] font-medium tabular-nums text-[var(--sd-ink)]">{value}</span>
    </div>
  );
}

const n = (v: number | null | undefined, unit = "") => (v == null || v === 0 ? "—" : `${qty(v)}${unit}`);

/** The crop's varieties: key numbers, default protocol and the stage timeline of each. */
export function VarietiesPanel({
  crop,
  accent,
  varieties,
  protocols,
  canEdit,
  onChanged,
}: {
  crop: string;
  accent: string;
  varieties: Variety[];
  protocols: { value: string; label: string }[];
  canEdit: boolean;
  onChanged: () => void;
}) {
  // undefined: closed; null: a new variety; otherwise the one being edited.
  const [editing, setEditing] = useState<Variety | null | undefined>(undefined);
  const protoLabel = (id: string | null) => protocols.find((p) => p.value === id)?.label ?? id ?? "—";
  return (
    <div className="flex flex-col gap-4">
      {canEdit && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setEditing(null)}>
            <Plus className="h-4 w-4" /> New variety
          </Button>
        </div>
      )}
      {varieties.length === 0 && (
        <p className="text-[13px] text-[var(--sd-muted)]">No varieties for {crop} yet.{canEdit ? " Use New variety to add one." : ""}</p>
      )}
      {varieties.map((v) => (
        <section key={v.name} className={CARD} aria-label={v.variety_name} data-testid={`variety-${v.name}`}>
          <header className="flex flex-wrap items-start gap-x-4 gap-y-2 px-4 pb-2 pt-4">
            <div className="min-w-[12rem] flex-1">
              <h3 className="flex flex-wrap items-center gap-2 text-[15px] font-semibold tracking-tight text-[var(--sd-ink)]">
                {v.variety_name}
                {!Number(v.enabled) && <span className="rounded-full bg-[var(--sd-bg-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--sd-quiet)]">Disabled</span>}
              </h3>
              <p className="break-words text-[12.5px] text-[var(--sd-muted)]">{v.item}</p>
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              <Stat label="To first harvest" value={v.weeks_to_first_harvest ? n(v.weeks_to_first_harvest, " wk") : n(v.days_to_first_harvest, " d")} />
              <Stat label="Harvest window" value={v.harvest_window_weeks ? n(v.harvest_window_weeks, " wk") : n(v.harvest_window_days, " d")} />
              <Stat label="Yield / ha" value={n(v.expected_yield_per_ha)} />
              <Stat label="Density / ha" value={n(v.plants_per_ha)} />
              {v.harvest_pattern && v.harvest_pattern !== "Once" && <Stat label="Harvest" value={`${v.harvest_pattern}${v.harvest_interval_weeks ? `, ${v.harvest_interval_weeks} wk` : ""}`} />}
              <Stat label="Default protocol" value={protoLabel(v.default_protocol)} />
            </div>
            {canEdit && (
              <Button variant="outline" size="sm" aria-label={`Edit ${v.variety_name}`} onClick={() => setEditing(v)}>
                <Pencil className="h-3.5 w-3.5" /> Edit
              </Button>
            )}
          </header>
          <div className="px-4 pb-4 pt-1">
            {v.stages.length ? (
              <StageTimeline stages={v.stages} accent={accent} />
            ) : (
              <p className="text-[12.5px] text-[var(--sd-quiet)]">No growth stages yet.</p>
            )}
          </div>
        </section>
      ))}
      {editing !== undefined && (
        <VarietyDialog
          crop={crop}
          accent={accent}
          variety={editing}
          protocols={protocols}
          onClose={() => setEditing(undefined)}
          onSaved={() => {
            setEditing(undefined);
            onChanged();
          }}
        />
      )}
    </div>
  );
}
