import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import type { Variety, YieldAge } from "@/lib/varieties-api";

/** The yield model of a variety as typed: numbers stay strings until saved. */
export interface YieldModelDraft {
  ages: { age: string; kg: string }[];
  offFactor: string;
  onYears: string;
  lateShare: string;
}

const text = (v: number | null | undefined) => (v == null || v === 0 ? "" : String(v));

export const toYieldModelDraft = (v?: Variety | null): YieldModelDraft => ({
  ages: (v?.yield_by_age ?? []).map((r) => ({ age: String(r.age_years), kg: String(r.kg_per_plant) })),
  offFactor: text(v?.biennial_off_factor),
  onYears: v?.on_years ?? "",
  lateShare: text(v?.late_crop_share_pct),
});

const numOrNull = (s: string) => (s.trim() === "" ? null : Number(s));

/** The save payload for the yield model. */
export const yieldModelPayload = (d: YieldModelDraft) => ({
  yield_by_age: d.ages.filter((r) => r.age.trim() !== "").map((r): YieldAge => ({ age_years: Number(r.age), kg_per_plant: Number(r.kg) || 0 })),
  biennial_off_factor: numOrNull(d.offFactor),
  on_years: d.onYears || null,
  late_crop_share_pct: numOrNull(d.lateShare),
});

/** The first problem with the yield model, or null. */
export function yieldModelProblem(d: YieldModelDraft): string | null {
  const ages = d.ages.filter((r) => r.age.trim() !== "").map((r) => r.age.trim());
  if (new Set(ages).size !== ages.length) return "Yield by age lists an age twice.";
  if (ages.some((a) => !(Number(a) >= 0))) return "Yield by age needs whole years.";
  if (d.offFactor.trim() !== "" && !d.onYears) return "Say whether the on years are even or odd.";
  return null;
}

/**
 * Yield by tree age, biennial bearing and the late crop's share for a variety. Each age row applies until the
 * next one; leave the off-year factor empty for a variety with no biennial swing.
 */
export function YieldModelEditor({ value, onChange }: { value: YieldModelDraft; onChange: (v: YieldModelDraft) => void }) {
  const setRow = (i: number, patch: Partial<{ age: string; kg: string }>) =>
    onChange({ ...value, ages: value.ages.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  return (
    <div className="flex flex-col gap-3" data-testid="yield-model-editor">
      <div className="flex flex-col gap-2">
        <Label>Yield by tree age</Label>
        <span className="text-[11.5px] text-[var(--sd-quiet)]">Kilograms per plant from each age; a row applies until the next one.</span>
        {value.ages.map((r, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_auto] items-center gap-2">
            <Input aria-label={`Yield row ${i + 1} from age (years)`} inputMode="numeric" className="tabular-nums" placeholder="From age (years)" value={r.age} onChange={(e) => setRow(i, { age: e.target.value })} />
            <Input aria-label={`Yield row ${i + 1} kg per plant`} inputMode="decimal" className="tabular-nums" placeholder="Kg per plant" value={r.kg} onChange={(e) => setRow(i, { kg: e.target.value })} />
            <Button type="button" variant="outline" aria-label={`Remove yield row ${i + 1}`} onClick={() => onChange({ ...value, ages: value.ages.filter((_, j) => j !== i) })}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ))}
        <div>
          <Button type="button" variant="outline" onClick={() => onChange({ ...value, ages: [...value.ages, { age: "", kg: "" }] })}>
            <Plus className="h-3.5 w-3.5" /> Add age
          </Button>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="v-off-factor">Off-year factor</Label>
          <Input id="v-off-factor" inputMode="decimal" className="tabular-nums" value={value.offFactor} onChange={(e) => onChange({ ...value, offFactor: e.target.value })} />
          <span className="text-[11.5px] text-[var(--sd-quiet)]">An off year yields this share of an on year. Empty: no biennial swing.</span>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="v-on-years">On years</Label>
          <Picker id="v-on-years" label="On years" value={value.onYears} onChange={(v) => onChange({ ...value, onYears: v })} options={["Even", "Odd"]} clearable clearLabel="Not biennial" placeholder="Not biennial" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="v-late-share">Late crop share (%)</Label>
          <Input id="v-late-share" inputMode="decimal" className="tabular-nums" value={value.lateShare} onChange={(e) => onChange({ ...value, lateShare: e.target.value })} />
          <span className="text-[11.5px] text-[var(--sd-quiet)]">Used when no flowering season is named Late.</span>
        </div>
      </div>
    </div>
  );
}
