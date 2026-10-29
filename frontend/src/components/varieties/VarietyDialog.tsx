import { useEffect, useState } from "react";
import { ItemField } from "@/components/cycles/ItemField";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Switch } from "@/components/ui/switch";
import { StageEditor, fromStageDrafts, stageProblem, toStageDrafts, type StageDraft } from "@/components/varieties/StageEditor";
import { qty } from "@/lib/format";
import { isError } from "@/lib/frappe";
import { FLOWERING_PATTERNS, HARVEST_PATTERNS, MONTHS, WATER_PARAMETERS, firstHarvestWeeks, saveVariety, type FloweringPattern, type FloweringSeason, type HarvestPattern, type StageAnchor, type Variety, type WaterBand } from "@/lib/varieties-api";

const ANCHORS: StageAnchor[] = ["Planting", "Flowering", "Stocking"];

const numOrNull = (s: string) => (s.trim() === "" ? null : Number(s));
/** A season row as typed; numbers stay strings until saved. */
interface SeasonDraft { season_name: string; start_month: string; weeks: string; share: string }
const toSeasonDrafts = (rows?: FloweringSeason[]): SeasonDraft[] =>
  (rows ?? []).map((r) => ({ season_name: r.season_name, start_month: r.start_month, weeks: r.weeks_flowering_to_harvest == null ? "" : String(r.weeks_flowering_to_harvest), share: r.crop_share_pct == null ? "" : String(r.crop_share_pct) }));

/** Sum of the shares typed, or null when none is set. */
export const seasonShareTotal = (rows: SeasonDraft[]): number | null =>
  rows.some((r) => r.share.trim() !== "") ? rows.reduce((a, r) => a + (Number(r.share) || 0), 0) : null;

/** A water band row as typed; numbers stay strings until saved. */
interface WaterDraft { parameter: string; min: string; max: string; unit: string }
const toWaterDrafts = (rows?: WaterBand[]): WaterDraft[] =>
  (rows ?? []).map((r) => ({ parameter: r.parameter, min: r.min ? String(r.min) : "", max: r.max ? String(r.max) : "", unit: r.unit ?? "" }));

const text = (v: number | null | undefined) => (v == null ? "" : String(v));

/** The first problem with a variety form, or null. Exported for the tests. */
export function varietyProblem(
  f: { variety_name: string; item: string; days: string; window: string; pattern?: FloweringPattern | null; seasons?: SeasonDraft[]; intervalWeeks?: string },
  rows: StageDraft[],
): string | null {
  if (!f.variety_name.trim()) return "Give the variety a name.";
  if (!f.item.trim()) return "Choose the stock item this variety is sold as.";
  for (const [label, v] of [["Weeks to first harvest", f.days], ["Harvest window", f.window]] as const) {
    if (v.trim() !== "" && !(Number(v) >= 0)) return `${label} must be a number of weeks.`;
  }
  if (f.pattern === "Seasonal") {
    const seasons = f.seasons ?? [];
    if (!seasons.length) return "Add at least one flowering season.";
    if (seasons.some((r) => !r.season_name.trim() || !r.start_month || !(Number(r.weeks) > 0))) return "Each season needs a name, a start month and weeks from flowering to harvest.";
  }
  if (f.pattern === "Interval" && !(Number(f.intervalWeeks) > 0)) return "Give the weeks between flowerings.";
  return stageProblem(rows);
}

export function VarietyDialog({
  crop,
  accent,
  variety,
  protocols,
  onClose,
  onSaved,
}: {
  crop: string;
  accent: string;
  /** Null to create. */
  variety: Variety | null;
  protocols: { value: string; label: string }[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(variety?.variety_name ?? "");
  const [item, setItem] = useState(variety?.item ?? "");
  const [product, setProduct] = useState(variety?.product ?? "");
  const [days, setDays] = useState(text(variety?.weeks_to_first_harvest));
  const [window, setWindow] = useState(text(variety?.harvest_window_weeks));
  const [lifespan, setLifespan] = useState(text(variety?.lifespan_years));
  const [pattern, setPattern] = useState<string>(variety?.harvest_pattern ?? "Once");
  const [interval, setInterval] = useState(text(variety?.harvest_interval_weeks));
  const [flowering, setFlowering] = useState(!!Number(variety?.is_flowering ?? 0));
  const [toFlower, setToFlower] = useState(text(variety?.weeks_to_first_flowering));
  const [toHarvest, setToHarvest] = useState(text(variety?.weeks_flowering_to_harvest));
  const [maturity, setMaturity] = useState(text(variety?.weeks_to_maturity));
  const [floweringPattern, setFloweringPattern] = useState<string>(variety?.flowering_pattern ?? "Interval");
  const [floweringInterval, setFloweringInterval] = useState(text(variety?.flowering_interval_weeks));
  const [seasons, setSeasons] = useState<SeasonDraft[]>(() => toSeasonDrafts(variety?.flowering_seasons));
  const [perM2, setPerM2] = useState(text(variety?.plants_per_m2));
  const [dryMatter, setDryMatter] = useState(text(variety?.dry_matter_target_pct));
  const [yieldHa, setYieldHa] = useState(text(variety?.expected_yield_per_ha));
  const [yieldPlant, setYieldPlant] = useState(text(variety?.expected_yield_per_plant));
  const [protocol, setProtocol] = useState(variety?.default_protocol ?? "");
  const [anchor, setAnchor] = useState<string>(variety?.stage_anchor ?? "Planting");
  const [enabled, setEnabled] = useState(variety ? !!Number(variety.enabled) : true);
  const [rows, setRows] = useState<StageDraft[]>(() => toStageDrafts(variety?.stages));
  const [irrigation, setIrrigation] = useState(text(variety?.irrigation_mm_week));
  const [water, setWater] = useState<WaterDraft[]>(() => toWaterDrafts(variety?.water_bands));
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => setFailure(null), [name, item, rows]);

  const repeats = pattern !== "Once";
  const computedFirst = firstHarvestWeeks(numOrNull(toFlower), numOrNull(toHarvest));
  const perHa = perM2.trim() === "" ? null : Number(perM2) * 10000;
  const seasonal = flowering && floweringPattern === "Seasonal";
  const interval_ = flowering && floweringPattern === "Interval";
  const shareTotal = seasonShareTotal(seasons);
  const shareOff = seasonal && shareTotal != null && Math.abs(shareTotal - 100) > 0.001;
  const setSeason = (i: number, patch: Partial<SeasonDraft>) => setSeasons((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const problem =
    varietyProblem(
      { variety_name: name, item, days: flowering ? "" : days, window, pattern: flowering ? (floweringPattern as FloweringPattern) : null, seasons, intervalWeeks: floweringInterval },
      rows,
    ) ?? (shareOff ? `Season shares total ${shareTotal}%; they must total 100%.` : null);

  async function save() {
    setBusy(true);
    const r = await saveVariety({
      ...(variety ? { name: variety.name } : { variety_name: name.trim() }),
      crop,
      item: item.trim(),
      product: product.trim() || null,
      lifespan_years: numOrNull(lifespan),
      harvest_pattern: pattern as HarvestPattern,
      harvest_interval_weeks: repeats ? numOrNull(interval) : null,
      is_flowering: flowering ? 1 : 0,
      weeks_to_maturity: numOrNull(maturity),
      flowering_pattern: flowering ? (floweringPattern as FloweringPattern) : null,
      flowering_seasons: seasonal
        ? seasons.map((r) => ({ season_name: r.season_name.trim(), start_month: r.start_month, weeks_flowering_to_harvest: numOrNull(r.weeks), crop_share_pct: numOrNull(r.share) }))
        : [],
      flowering_interval_weeks: interval_ ? numOrNull(floweringInterval) : null,
      weeks_to_first_flowering: interval_ ? numOrNull(toFlower) : null,
      weeks_flowering_to_harvest: interval_ ? numOrNull(toHarvest) : null,
      weeks_to_first_harvest: interval_ ? computedFirst : seasonal ? null : numOrNull(days),
      harvest_window_weeks: numOrNull(window),
      plants_per_m2: numOrNull(perM2),
      dry_matter_target_pct: numOrNull(dryMatter),
      expected_yield_per_ha: numOrNull(yieldHa),
      expected_yield_per_plant: numOrNull(yieldPlant),
      default_protocol: protocol || null,
      stage_anchor: anchor as StageAnchor,
      enabled: enabled ? 1 : 0,
      irrigation_mm_week: numOrNull(irrigation),
      water_bands: water.filter((w) => w.parameter).map((w) => ({ parameter: w.parameter, min: numOrNull(w.min), max: numOrNull(w.max), unit: w.unit.trim() || null })),
      stages: fromStageDrafts(rows),
    });
    setBusy(false);
    if (isError(r)) {
      setFailure(r.error);
      return;
    }
    toast(`${variety ? variety.variety_name : name.trim()} saved.`);
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto" aria-describedby="variety-desc">
        <DialogHeader>
          <DialogTitle>{variety ? `Edit ${variety.variety_name}` : "New variety"}</DialogTitle>
          <DialogDescription id="variety-desc">
            A variety is sold as its own stock item and has its own growth stages. Stage days count from the {anchor.toLowerCase()} date.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-name">Variety name</Label>
            <Input id="v-name" value={name} disabled={!!variety} onChange={(e) => setName(e.target.value)} placeholder="e.g. Shangi" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-item">Stock item</Label>
            <ItemField id="v-item" value={item} onChange={setItem} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-product">Product (optional)</Label>
            <ItemField id="v-product" value={product} onChange={setProduct} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-protocol">Default protocol</Label>
            <Picker id="v-protocol" label="Default protocol" value={protocol} onChange={setProtocol} options={protocols} clearable clearLabel="No default" placeholder="No default" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-lifespan">Lifespan (years)</Label>
            <Input id="v-lifespan" inputMode="decimal" className="tabular-nums" value={lifespan} onChange={(e) => setLifespan(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-pattern">Harvest pattern</Label>
            <Picker id="v-pattern" label="Harvest pattern" value={pattern} onChange={setPattern} options={HARVEST_PATTERNS} />
          </div>
          {repeats && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="v-interval">Harvest interval (weeks)</Label>
              <Input id="v-interval" inputMode="numeric" className="tabular-nums" value={interval} onChange={(e) => setInterval(e.target.value)} />
            </div>
          )}
          <label className="flex items-center gap-2 text-[13px] text-[var(--sd-ink)] sm:col-span-2">
            <Switch checked={flowering} onCheckedChange={setFlowering} aria-label="Flowering crop" />
            Flowering crop
          </label>
          {flowering && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="v-fpattern">Flowering pattern</Label>
              <Picker id="v-fpattern" label="Flowering pattern" value={floweringPattern} onChange={setFloweringPattern} options={FLOWERING_PATTERNS} />
            </div>
          )}
          {interval_ && (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="v-flower">Weeks to first flowering</Label>
                <Input id="v-flower" inputMode="numeric" className="tabular-nums" value={toFlower} onChange={(e) => setToFlower(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="v-flower-harvest">Weeks from flowering to harvest</Label>
                <Input id="v-flower-harvest" inputMode="numeric" className="tabular-nums" value={toHarvest} onChange={(e) => setToHarvest(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="v-finterval">Weeks between flowerings</Label>
                <Input id="v-finterval" inputMode="numeric" className="tabular-nums" value={floweringInterval} onChange={(e) => setFloweringInterval(e.target.value)} />
              </div>
            </>
          )}
          {seasonal && (
            <div className="flex flex-col gap-2 sm:col-span-2" data-testid="seasons-editor">
              <Label>Flowering seasons</Label>
              {seasons.map((r, i) => (
                <div key={i} className="grid grid-cols-[1.2fr_1fr_0.8fr_0.7fr_auto] items-center gap-2">
                  <Input aria-label={`Season ${i + 1} name`} placeholder="Season" value={r.season_name} onChange={(e) => setSeason(i, { season_name: e.target.value })} />
                  <Picker label={`Season ${i + 1} start month`} value={r.start_month} onChange={(v) => setSeason(i, { start_month: v })} options={[...MONTHS]} placeholder="Month" />
                  <Input aria-label={`Season ${i + 1} weeks flowering to harvest`} inputMode="numeric" className="tabular-nums" placeholder="Weeks" value={r.weeks} onChange={(e) => setSeason(i, { weeks: e.target.value })} />
                  <Input aria-label={`Season ${i + 1} crop share %`} inputMode="decimal" className="tabular-nums" placeholder="Share %" value={r.share} onChange={(e) => setSeason(i, { share: e.target.value })} />
                  <Button type="button" variant="outline" aria-label={`Remove season ${i + 1}`} onClick={() => setSeasons((rs) => rs.filter((_, j) => j !== i))}>
                    Remove
                  </Button>
                </div>
              ))}
              <div className="flex flex-wrap items-center gap-3">
                <Button type="button" variant="outline" onClick={() => setSeasons((rs) => [...rs, { season_name: "", start_month: "", weeks: "", share: "" }])}>
                  Add season
                </Button>
                {shareTotal != null && (
                  <span data-testid="season-total" className={shareOff ? "text-[12px] text-[var(--sd-amber)]" : "text-[12px] text-[var(--sd-quiet)]"}>
                    Shares total {shareTotal}%{shareOff ? " (should be 100%)" : ""}
                  </span>
                )}
              </div>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-maturity">Weeks to maturity</Label>
            <Input id="v-maturity" inputMode="numeric" className="tabular-nums" value={maturity} onChange={(e) => setMaturity(e.target.value)} />
            <span className="text-[11.5px] text-[var(--sd-quiet)]">Weeks after planting before the crop gives yield; earlier cycles are juvenile.</span>
          </div>
          {!seasonal && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-days">Weeks to first harvest</Label>
            <Input
              id="v-days"
              inputMode="numeric"
              className="tabular-nums"
              readOnly={flowering}
              value={flowering ? String(computedFirst) : days}
              onChange={(e) => setDays(e.target.value)}
            />
            {flowering && <span className="text-[11.5px] text-[var(--sd-quiet)]">Flowering weeks plus weeks from flowering to harvest.</span>}
          </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-window">Harvest window (weeks)</Label>
            <Input id="v-window" inputMode="numeric" className="tabular-nums" value={window} onChange={(e) => setWindow(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-yha">Expected yield per ha</Label>
            <Input id="v-yha" inputMode="decimal" className="tabular-nums" value={yieldHa} onChange={(e) => setYieldHa(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-yplant">Expected yield per plant</Label>
            <Input id="v-yplant" inputMode="decimal" className="tabular-nums" value={yieldPlant} onChange={(e) => setYieldPlant(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-density">Plants per m²</Label>
            <Input id="v-density" inputMode="decimal" className="tabular-nums" value={perM2} onChange={(e) => setPerM2(e.target.value)} />
            {perHa != null && <span className="text-[11.5px] text-[var(--sd-quiet)]">{qty(perHa)} plants per ha</span>}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-dm">Dry matter target (%)</Label>
            <Input id="v-dm" inputMode="decimal" className="tabular-nums" value={dryMatter} onChange={(e) => setDryMatter(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-anchor">Stages count from</Label>
            <Picker id="v-anchor" label="Stages count from" value={anchor} onChange={setAnchor} options={ANCHORS} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-irrigation">Irrigation target (mm per week)</Label>
            <Input id="v-irrigation" inputMode="decimal" className="tabular-nums" value={irrigation} onChange={(e) => setIrrigation(e.target.value)} />
            <span className="text-[11.5px] text-[var(--sd-quiet)]">Empty uses the crop's target.</span>
          </div>
          <label className="flex items-center gap-2 text-[13px] text-[var(--sd-ink)]">
            <Switch checked={enabled} onCheckedChange={setEnabled} aria-label="Enabled" />
            Enabled
          </label>
        </div>

        <div className="flex flex-col gap-2" data-testid="water-bands-editor">
          <Label>Safe water bands</Label>
          <span className="text-[11.5px] text-[var(--sd-quiet)]">For fish: oxygen needs a minimum, pH and temperature a range, ammonia and nitrite a maximum. Empty uses the crop's bands.</span>
          {water.map((w, i) => (
            <div key={i} className="grid grid-cols-[1.2fr_0.8fr_0.8fr_0.8fr_auto] items-center gap-2">
              <Picker label={`Water band ${i + 1} parameter`} value={w.parameter} onChange={(v) => setWater((rs) => rs.map((r, j) => (j === i ? { ...r, parameter: v } : r)))} options={[...WATER_PARAMETERS]} placeholder="Parameter" />
              <Input aria-label={`Water band ${i + 1} min`} inputMode="decimal" className="tabular-nums" placeholder="Min" value={w.min} onChange={(e) => setWater((rs) => rs.map((r, j) => (j === i ? { ...r, min: e.target.value } : r)))} />
              <Input aria-label={`Water band ${i + 1} max`} inputMode="decimal" className="tabular-nums" placeholder="Max" value={w.max} onChange={(e) => setWater((rs) => rs.map((r, j) => (j === i ? { ...r, max: e.target.value } : r)))} />
              <Input aria-label={`Water band ${i + 1} unit`} placeholder="Unit" value={w.unit} onChange={(e) => setWater((rs) => rs.map((r, j) => (j === i ? { ...r, unit: e.target.value } : r)))} />
              <Button type="button" variant="outline" aria-label={`Remove water band ${i + 1}`} onClick={() => setWater((rs) => rs.filter((_, j) => j !== i))}>
                Remove
              </Button>
            </div>
          ))}
          <div>
            <Button type="button" variant="outline" onClick={() => setWater((rs) => [...rs, { parameter: "", min: "", max: "", unit: "" }])}>
              Add water band
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label>Growth stages</Label>
          <StageEditor rows={rows} onChange={setRows} accent={accent} />
        </div>

        {failure && (
          <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px] text-[var(--sd-ink)]">
            {failure}
          </p>
        )}
        <div className="flex items-center justify-end gap-3">
          {problem && name && <span className="text-[12px] text-[var(--sd-amber)]">{problem}</span>}
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={save} disabled={busy || !!problem}>
            {busy ? "Saving…" : "Save variety"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
