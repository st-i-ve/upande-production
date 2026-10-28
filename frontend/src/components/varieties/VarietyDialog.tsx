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
import { isError } from "@/lib/frappe";
import { saveVariety, type StageAnchor, type Variety } from "@/lib/varieties-api";

const ANCHORS: StageAnchor[] = ["Planting", "Flowering", "Stocking"];

const numOrNull = (s: string) => (s.trim() === "" ? null : Number(s));
const text = (v: number | null | undefined) => (v == null ? "" : String(v));

/** The first problem with a variety form, or null. Exported for the tests. */
export function varietyProblem(f: { variety_name: string; item: string; days: string; window: string }, rows: StageDraft[]): string | null {
  if (!f.variety_name.trim()) return "Give the variety a name.";
  if (!f.item.trim()) return "Choose the stock item this variety is sold as.";
  for (const [label, v] of [["Days to first harvest", f.days], ["Harvest window", f.window]] as const) {
    if (v.trim() !== "" && !(Number(v) >= 0)) return `${label} must be a number of days.`;
  }
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
  const [days, setDays] = useState(text(variety?.days_to_first_harvest));
  const [window, setWindow] = useState(text(variety?.harvest_window_days));
  const [yieldHa, setYieldHa] = useState(text(variety?.expected_yield_per_ha));
  const [yieldPlant, setYieldPlant] = useState(text(variety?.expected_yield_per_plant));
  const [density, setDensity] = useState(text(variety?.plants_per_ha));
  const [protocol, setProtocol] = useState(variety?.default_protocol ?? "");
  const [anchor, setAnchor] = useState<string>(variety?.stage_anchor ?? "Planting");
  const [enabled, setEnabled] = useState(variety ? !!Number(variety.enabled) : true);
  const [rows, setRows] = useState<StageDraft[]>(() => toStageDrafts(variety?.stages));
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => setFailure(null), [name, item, rows]);

  const problem = varietyProblem({ variety_name: name, item, days, window }, rows);

  async function save() {
    setBusy(true);
    const r = await saveVariety({
      ...(variety ? { name: variety.name } : { variety_name: name.trim() }),
      crop,
      item: item.trim(),
      product: product.trim() || null,
      days_to_first_harvest: numOrNull(days),
      harvest_window_days: numOrNull(window),
      expected_yield_per_ha: numOrNull(yieldHa),
      expected_yield_per_plant: numOrNull(yieldPlant),
      plants_per_ha: numOrNull(density),
      default_protocol: protocol || null,
      stage_anchor: anchor as StageAnchor,
      enabled: enabled ? 1 : 0,
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
            <Label htmlFor="v-days">Days to first harvest</Label>
            <Input id="v-days" inputMode="numeric" className="tabular-nums" value={days} onChange={(e) => setDays(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-window">Harvest window (days)</Label>
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
            <Label htmlFor="v-density">Plants per ha</Label>
            <Input id="v-density" inputMode="decimal" className="tabular-nums" value={density} onChange={(e) => setDensity(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="v-anchor">Stages count from</Label>
            <Picker id="v-anchor" label="Stages count from" value={anchor} onChange={setAnchor} options={ANCHORS} />
          </div>
          <label className="flex items-center gap-2 text-[13px] text-[var(--sd-ink)]">
            <Switch checked={enabled} onCheckedChange={setEnabled} aria-label="Enabled" />
            Enabled
          </label>
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
