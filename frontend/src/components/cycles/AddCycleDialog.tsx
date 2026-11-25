import { SubCropField } from "@/components/cycles/SubCropField";
import { useEffect, useMemo, useRef, useState } from "react";
import { Download, TriangleAlert, Upload } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { SearchPicker } from "@/components/ui/search-picker";
import { ItemField } from "@/components/cycles/ItemField";
import { addCycle, hasNewCycleTab, importCycles, importTemplate, previewImport, type ImportResult, type ImportRow } from "@/lib/cycle-setup-api";
import { listProtocols, type Crop, type UnitRow } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { ha, qty } from "@/lib/format";
import { cn, todayISO } from "@/lib/utils";
import { cropPickerOptions, hasFieldCrops, subCropsOf } from "@/lib/field-crops";
import { listVarieties, type Variety } from "@/lib/varieties-api";

/** Cycle types an avocado block takes (a season of an established block, or a new planting). */
const TYPES = ["Season", "Planting"];

type Mode = "new" | "existing" | "import";
const MODES: { id: Mode; label: string }[] = [
  { id: "new", label: "New cycle" },
  { id: "existing", label: "Existing cycle — already in production" },
  { id: "import", label: "Bulk import" },
];

interface ProtocolOption {
  value: string;
  label: string;
  variety: string | null;
}

/** Whole years (one decimal) between a planting date and today. */
export function treeAge(planted: string, on = todayISO()): string {
  if (!planted) return "—";
  const years = (new Date(on).getTime() - new Date(planted).getTime()) / (365.25 * 86400000);
  if (!Number.isFinite(years) || years < 0) return "—";
  return years < 1 ? `${Math.round(years * 12)} months` : `${years.toFixed(1)} years`;
}

/** Warnings when `extra` area / trees on top of the cycles already running on the block pass the block's own. */
export function capacityWarnings(unit: UnitRow | undefined, area: number, trees: number): string[] {
  if (!unit) return [];
  const run = (unit.cycles ?? []).filter((c) => c.status === "Active" || c.status === "Harvesting");
  const a = run.reduce((t, c) => t + (c.area_ha || 0), 0) + area;
  const n = run.reduce((t, c) => t + (c.plant_count || 0), 0) + trees;
  const out: string[] = [];
  if (unit.area_ha && a > unit.area_ha * 1.0001) out.push(`Running cycles on ${unit.name} would cover ${ha(a)} ha, more than the block's ${ha(unit.area_ha)} ha.`);
  if (unit.plant_count && n > unit.plant_count) out.push(`Running cycles on ${unit.name} would hold ${qty(n)} trees, more than the block's ${qty(unit.plant_count)}.`);
  return out;
}

const Warn = ({ children }: { children: React.ReactNode }) => (
  <div role="alert" className="flex items-start gap-2 rounded-[var(--sd-radius-md)] bg-[var(--sd-alert-warn)] px-3 py-2 text-[12.5px] text-[var(--sd-sev-high)]">
    <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
    <span>{children}</span>
  </div>
);

function Field({ label, htmlFor, hint, children, className }: { label: string; htmlFor?: string; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <span className="text-[11.5px] text-[var(--sd-quiet)]">{hint}</span>}
    </div>
  );
}

/** A date that may be left empty. */
function OptionalDate({ value, onChange, label, max }: { value: string; onChange: (v: string) => void; label: string; max?: string }) {
  return (
    <div className="flex items-center gap-2">
      <DatePicker value={value} onChange={onChange} max={max} aria-label={label} placeholder="Not known" className="w-full" />
      {value && (
        <button type="button" className="text-[12px] text-[var(--sd-muted)] underline-offset-2 hover:underline" onClick={() => onChange("")}>
          Clear
        </button>
      )}
    </div>
  );
}

/** Said in the existing-cycle form and the import: the scheduler plans nothing before today. */
export const PICKS_UP_FROM_TODAY = "Picks up from today: nothing before today is planned.";

/**
 * Add a crop cycle to a block: a new one (avocado; other crops start theirs in their own form), one that is
 * already in production in another application (planting or start date, current stage if the variety has
 * stages, history) or many from a sheet. Several cycles may run on one block; going past the block's area or
 * trees warns and still saves.
 */
export function AddCycleDialog({
  crop,
  units,
  defaultUnit,
  defaultMode,
  modes,
  open,
  onOpenChange,
  onSaved,
}: {
  crop: Crop;
  units: UnitRow[];
  defaultUnit?: string;
  defaultMode?: Mode;
  /** Which ways in to offer; avocado has all three, other crops add an existing cycle or import. */
  modes?: Mode[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const avocado = crop.crop_key === "avocado";
  const offered = modes ?? (hasNewCycleTab(crop) ? MODES.map((m) => m.id) : (["existing", "import"] as Mode[]));
  const firstMode = defaultMode && offered.includes(defaultMode) ? defaultMode : offered[0];
  const [mode, setMode] = useState<Mode>(firstMode);
  const [item, setItem] = useState("");
  const [harvesting, setHarvesting] = useState(false);
  const [unit, setUnit] = useState(defaultUnit ?? "");
  const [fieldCrop, setFieldCrop] = useState("");
  const [subCrop, setSubCrop] = useState("");
  const [variety, setVariety] = useState("");
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const [protocol, setProtocol] = useState("");
  const [protocols, setProtocols] = useState<ProtocolOption[]>([]);
  const [type, setType] = useState(TYPES[0]);
  const [start, setStart] = useState(todayISO());
  const [planting, setPlanting] = useState("");
  const [stage, setStage] = useState("");
  const [area, setArea] = useState("");
  const [trees, setTrees] = useState("");
  const [lastFlower, setLastFlower] = useState("");
  const [lastHarvest, setLastHarvest] = useState("");
  const [lastKg, setLastKg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setMode(firstMode);
    setUnit(defaultUnit ?? "");
    setItem("");
    setHarvesting(false);
    let live = true;
    void listVarieties(crop.name).then((r) => live && !isError(r) && setVarieties(r.varieties.filter((v) => !!Number(v.enabled))));
    void listProtocols(crop.name).then((r) => {
      if (!live || isError(r)) return;
      setProtocols(
        (r as { rows: Record<string, unknown>[] }).rows.map((p) => ({
          value: String(p.name),
          label: `${String(p.protocol_name ?? p.name)}${p.version ? ` v${String(p.version)}` : ""}`,
          variety: (p.variety as string) || null,
        })),
      );
    });
    return () => {
      live = false;
    };
  }, [open, crop.name, defaultUnit, firstMode]);

  const unitRow = units.find((u) => u.name === unit);
  // A section with named crops (Fruits & Vegetables): the crop is chosen first and the variety list follows it.
  const withCrops = hasFieldCrops(crop);
  const cropOptions = useMemo(() => cropPickerOptions(crop.field_crops), [crop.field_crops]);
  const cropSubs = useMemo(() => subCropsOf(crop.field_crops, fieldCrop), [crop.field_crops, fieldCrop]);
  const shownVarieties = useMemo(() => (withCrops && fieldCrop ? varieties.filter((x) => x.field_crop === fieldCrop && (!subCrop || !x.sub_crop || x.sub_crop === subCrop)) : varieties), [varieties, withCrops, fieldCrop, subCrop]);
  const v = varieties.find((x) => x.name === variety);
  const stages = useMemo(() => (v?.stages ?? []).map((s) => s.stage), [v]);
  const stageDefs = v?.stages ?? [];
  const pickedStage = stageDefs.find((s) => s.stage === stage);
  const stageIsHarvest = !!pickedStage && !!Number(pickedStage.is_harvest);
  const protoOptions = useMemo(() => protocols.filter((p) => !p.variety || p.variety === variety), [protocols, variety]);

  // Choosing a variety offers its stages and its own protocol; choosing a block offers its area and trees.
  useEffect(() => {
    if (variety && fieldCrop && v && v.field_crop && v.field_crop !== fieldCrop) setVariety("");
  }, [fieldCrop, variety, v]);
  useEffect(() => {
    setProtocol((cur) => {
      if (cur && protoOptions.some((p) => p.value === cur)) return cur;
      const own = v?.default_protocol && protoOptions.find((p) => p.value === v.default_protocol);
      return own ? own.value : (protoOptions.find((p) => p.variety === variety)?.value ?? "");
    });
    setStage((cur) => (cur && stages.includes(cur) ? cur : ""));
  }, [variety, protoOptions, stages, v]);
  useEffect(() => {
    if (!unitRow) return;
    setArea(unitRow.area_ha ? String(unitRow.area_ha) : "");
    setTrees(unitRow.plant_count ? String(unitRow.plant_count) : "");
  }, [unitRow?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  const areaN = Number(area) || 0;
  const treesN = Number(trees) || (v?.plants_per_ha && areaN ? Math.round(v.plants_per_ha * areaN) : 0);
  const warnings = capacityWarnings(unitRow, areaN, treesN);
  const yearKg = v?.expected_yield_per_plant && treesN ? v.expected_yield_per_plant * treesN : null;
  const existing = mode === "existing";
  const can = !!unit && !busy && (!withCrops || (!!fieldCrop && (!cropSubs.length || !!subCrop))) && (existing
    ? !!planting && (avocado ? !!variety && !!stage : !!variety || !!item.trim())
    : !!variety && !!start);

  async function save() {
    setBusy(true);
    const r = await addCycle({
      unit,
      field_crop: withCrops ? fieldCrop || null : null,
      sub_crop: withCrops && cropSubs.length ? subCrop || null : null,
      variety: variety || null,
      item: !variety && existing ? item.trim() || null : null,
      already_harvesting: existing && !avocado ? harvesting && !stageIsHarvest : false,
      protocol: protocol || null,
      cycle_type: existing ? "Season" : type,
      start_date: existing ? null : start,
      area_ha: areaN || null,
      plant_count: Number(trees) || null,
      existing,
      planting_date: existing ? planting : null,
      current_stage: existing ? stage : null,
      last_flowering_date: existing ? lastFlower || null : null,
      last_harvest_date: existing ? lastHarvest || null : null,
      last_season_yield_kg: existing && lastKg ? Number(lastKg) : null,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    const ok = r as { name: string; warnings: string[] };
    toast(`Cycle ${ok.name} added.`);
    ok.warnings.forEach((w) => toast(w, "error"));
    setVariety("");
    setFieldCrop("");
    setSubCrop("");
    setItem("");
    setHarvesting(false);
    setPlanting("");
    setLastFlower("");
    setLastHarvest("");
    setLastKg("");
    onOpenChange(false);
    onSaved();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl grid-cols-[minmax(0,1fr)]">
        <DialogHeader>
          <DialogTitle>Add crop cycle</DialogTitle>
          <DialogDescription>
            Several cycles can run on one {crop.unit_label.toLowerCase()} at the same time, for instance two varieties. An existing cycle
            carries on from where it is in another application.
          </DialogDescription>
        </DialogHeader>

        <div role="tablist" aria-label="Kind of cycle" className="flex flex-wrap gap-2">
          {MODES.filter((m) => offered.includes(m.id)).map((m) => (
            <button
              key={m.id}
              role="tab"
              type="button"
              aria-selected={mode === m.id}
              onClick={() => setMode(m.id)}
              className={cn(
                "h-9 rounded-full px-4 text-[13px] font-medium transition-colors",
                mode === m.id ? "bg-[var(--sd-ink)] text-[var(--sd-card)]" : "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)] hover:text-[var(--sd-ink)]",
              )}
            >
              {m.label}
            </button>
          ))}
        </div>

        {mode === "import" ? (
          <BulkImport crop={crop} onDone={() => { onOpenChange(false); onSaved(); }} onCancel={() => onOpenChange(false)} />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label={crop.unit_label} htmlFor="ac-unit">
                <SearchPicker
                  id="ac-unit"
                  label={crop.unit_label}
                  value={unit}
                  onChange={setUnit}
                  placeholder={`Choose a ${crop.unit_label.toLowerCase()}…`}
                  options={units.filter((u) => !u.is_group).map((u) => ({ value: u.name, label: u.name }))}
                />
              </Field>
              {withCrops && (
                <Field label="Crop" htmlFor="ac-crop">
                  <Picker id="ac-crop" label="Crop" value={fieldCrop} onChange={(c) => { setFieldCrop(c); setSubCrop(""); }} options={cropOptions} placeholder="Choose a crop…" />
                </Field>
              )}
              {withCrops && <SubCropField id="ac-subcrop" subCrops={cropSubs} value={subCrop} onChange={setSubCrop} />}
              <Field label="Variety" htmlFor="ac-variety">
                <Picker
                  id="ac-variety"
                  label="Variety"
                  value={variety}
                  onChange={setVariety}
                  disabled={withCrops && !fieldCrop}
                  options={shownVarieties.map((x) => ({ value: x.name, label: x.variety_name }))}
                  placeholder={avocado || !existing ? "Choose a variety…" : "No variety"}
                  clearable={!avocado && existing}
                  clearLabel="No variety"
                />
              </Field>
              {existing && !avocado && !variety && (
                <Field label="Item" htmlFor="ac-item" hint="What the cycle grows, when it has no variety">
                  <ItemField id="ac-item" value={item} onChange={setItem} />
                </Field>
              )}
              <Field label="Protocol" htmlFor="ac-protocol" hint={variety && protoOptions.length === 0 ? "No active protocol for this variety." : undefined}>
                <Picker id="ac-protocol" label="Protocol" value={protocol} onChange={setProtocol} options={protoOptions} clearable clearLabel="No protocol" placeholder="No protocol" />
              </Field>

              {existing ? (
                <>
                  <Field
                    label={avocado ? "Planting date" : "Planted / started on"}
                    hint={avocado ? (planting ? `Tree age ${treeAge(planting)}` : "When the trees were planted") : "The date it was planted or started in the other system"}
                  >
                    <DatePicker value={planting} onChange={setPlanting} max={todayISO()} aria-label={avocado ? "Planting date" : "Planted or started on"} className="w-full" />
                  </Field>
                  {(avocado || stages.length > 0) && (
                    <Field label="Current stage" htmlFor="ac-stage" hint={variety ? undefined : "Choose a variety first"}>
                      <Picker
                        id="ac-stage"
                        label="Current stage"
                        value={stage}
                        onChange={setStage}
                        options={stages}
                        placeholder={avocado ? "Choose a stage…" : "Not known"}
                        disabled={!stages.length}
                        clearable={!avocado}
                        clearLabel="Not known"
                      />
                    </Field>
                  )}
                  <Field label={avocado ? "Trees standing" : "Plants"} htmlFor="ac-trees" hint={unitRow?.plant_count ? `${crop.unit_label} records ${qty(unitRow.plant_count)}` : undefined}>
                    <Input id="ac-trees" inputMode="numeric" className="tabular-nums" value={trees} onChange={(e) => setTrees(e.target.value)} />
                  </Field>
                </>
              ) : (
                <>
                  <Field label="Start / planting date">
                    <DatePicker value={start} onChange={setStart} aria-label="Start date" className="w-full" />
                  </Field>
                  <Field label="Cycle type" htmlFor="ac-type">
                    <Picker id="ac-type" label="Cycle type" value={type} onChange={setType} options={TYPES} />
                  </Field>
                  <Field label="Trees" htmlFor="ac-trees" hint={!trees && treesN ? `${qty(treesN)} from ${qty(v?.plants_per_ha ?? 0)} plants per ha` : undefined}>
                    <Input id="ac-trees" inputMode="numeric" className="tabular-nums" value={trees} onChange={(e) => setTrees(e.target.value)} />
                  </Field>
                </>
              )}
              <Field label="Area (ha)" htmlFor="ac-area" hint={unitRow?.area_ha ? `Block area ${ha(unitRow.area_ha)} ha` : undefined}>
                <Input id="ac-area" inputMode="decimal" className="tabular-nums" value={area} onChange={(e) => setArea(e.target.value)} />
              </Field>
              {existing && !avocado && !stageIsHarvest && (
                <label className="flex items-center gap-2 self-end pb-2 text-[13px] text-[var(--sd-ink)]">
                  <input type="checkbox" className="h-4 w-4" checked={harvesting} onChange={(e) => setHarvesting(e.target.checked)} />
                  Already harvesting
                </label>
              )}
              {existing && (
                <>
                  {(avocado || v?.stage_anchor === "Flowering") && (
                  <Field label="Last flowering date (optional)">
                    <OptionalDate value={lastFlower} onChange={setLastFlower} label="Last flowering date" max={todayISO()} />
                  </Field>
                  )}
                  <Field label="Last harvest date (optional)">
                    <OptionalDate value={lastHarvest} onChange={setLastHarvest} label="Last harvest date" max={todayISO()} />
                  </Field>
                  <Field label={avocado ? "Last season yield (kg per year, optional)" : "Last yield (kg, optional)"} htmlFor="ac-lastkg" hint={avocado && treesN && lastKg ? `${qty(Number(lastKg) / treesN, 1)} kg/tree/year` : undefined}>
                    <Input id="ac-lastkg" inputMode="decimal" className="tabular-nums" value={lastKg} onChange={(e) => setLastKg(e.target.value)} />
                  </Field>
                </>
              )}
            </div>

            {existing && <p className="text-[12.5px] text-[var(--sd-muted)]">{PICKS_UP_FROM_TODAY}</p>}
            {yearKg != null && avocado && (
              <p className="text-[12.5px] text-[var(--sd-muted)]">
                At {qty(v?.expected_yield_per_plant ?? 0, 1)} kg/tree/year this cycle is expected to give about{" "}
                <span className="tabular-nums text-[var(--sd-ink)]">{qty(yearKg)} kg per year</span>.
              </p>
            )}
            {unitRow && (unitRow.cycles ?? []).length > 0 && (
              <p className="text-[12.5px] text-[var(--sd-muted)]">
                Already running on {unitRow.name}: {(unitRow.cycles ?? []).map((c) => `${c.variety || c.item || c.name} (${ha(c.area_ha ?? 0)} ha, ${qty(c.plant_count ?? 0)} trees)`).join("; ")}.
              </p>
            )}
            {warnings.map((w) => (
              <Warn key={w}>{w} You can still add it.</Warn>
            ))}

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={save} disabled={!can}>
                {busy ? "Saving…" : existing ? "Add existing cycle" : "Create cycle"}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function toBase64(buf: ArrayBuffer): string {
  let s = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

function BulkImport({ crop, onDone, onCancel }: { crop: Crop; onDone: () => void; onCancel: () => void }) {
  const toast = useToast();
  const avocado = crop.crop_key === "avocado";
  const withCrops = hasFieldCrops(crop);
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState("");
  const [rows, setRows] = useState<ImportRow[] | null>(null);
  const [results, setResults] = useState<ImportResult[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function template() {
    const r = await importTemplate(crop.name);
    if (isError(r)) return toast(r.error, "error");
    const t = r as { filename: string; content: string };
    const url = URL.createObjectURL(new Blob([t.content], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = t.filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function pick(f: File | undefined) {
    if (!f) return;
    setBusy(true);
    setResults(null);
    setFile(f.name);
    const r = await previewImport(crop.name, f.name, toBase64(await f.arrayBuffer()));
    setBusy(false);
    if (isError(r)) {
      setRows(null);
      return toast(r.error, "error");
    }
    setRows((r as { rows: ImportRow[] }).rows);
  }

  const good = (rows ?? []).filter((r) => !r.errors.length);

  async function create() {
    setBusy(true);
    const r = await importCycles(crop.name, good.map((x) => x.raw));
    setBusy(false);
    if (isError(r)) return toast(r.error, "error");
    const out = r as { results: ImportResult[]; created: number };
    setResults(out.results);
    toast(`${out.created} cycle${out.created === 1 ? "" : "s"} created.`);
    if (out.results.every((x) => x.ok)) onDone();
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] text-[var(--sd-muted)]">
        {avocado
          ? "Upload a CSV or Excel sheet of cycles that are already in production: block, variety, planting date, trees, area, current stage and last season’s kg per year."
          : withCrops
            ? "Upload a CSV or Excel sheet of cycles that are already running in another application: block, crop (for example Cabbage), variety, protocol, the date each was planted or started, area, current stage and last harvest."
            : "Upload a CSV or Excel sheet of cycles that are already running in another application: block, variety or item, protocol, the date each was planted or started, area, current stage and last harvest."}{" "}
        Rows are checked first; nothing is created until you confirm. {PICKS_UP_FROM_TODAY}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={template}>
          <Download className="mr-1.5 h-4 w-4" />
          Download template
        </Button>
        <Button variant="outline" onClick={() => input.current?.click()} disabled={busy}>
          <Upload className="mr-1.5 h-4 w-4" />
          Choose file
        </Button>
        <input ref={input} data-testid="import-file" type="file" accept=".csv,.xlsx,.xlsm" className="sr-only" onChange={(e) => void pick(e.target.files?.[0])} />
        {file && <span className="text-[12.5px] text-[var(--sd-quiet)]">{file}</span>}
      </div>

      {rows && (
        <div className="flex flex-col gap-2">
          <p className="text-[12.5px] text-[var(--sd-muted)]">
            {good.length} of {rows.length} rows are ready{rows.length - good.length ? `; ${rows.length - good.length} need fixing in the sheet` : ""}.
          </p>
          <div className="max-h-[320px] overflow-auto rounded-[var(--sd-radius-md)] border border-[var(--sd-line)]">
            <table className="w-full text-[12.5px]">
              <thead className="sticky top-0 bg-[var(--sd-card)]">
                <tr className="text-left text-[11px] uppercase tracking-wide text-[var(--sd-quiet)]">
                  <th className="px-3 py-2">Row</th>
                  <th className="px-3 py-2">Block</th>
                  {withCrops && <th className="px-3 py-2">Crop</th>}
                  <th className="px-3 py-2">{avocado ? "Variety" : "Variety / item"}</th>
                  {!avocado && <th className="px-3 py-2">Protocol</th>}
                  <th className="px-3 py-2">{avocado ? "Planted" : "Started"}</th>
                  {avocado && <th className="px-3 py-2 text-right">Trees</th>}
                  <th className="px-3 py-2 text-right">Area (ha)</th>
                  <th className="px-3 py-2">Stage</th>
                  {avocado && <th className="px-3 py-2 text-right">Last kg/yr</th>}
                  <th className="px-3 py-2">Check</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const res = results?.find((x) => x.row === r.row);
                  return (
                    <tr key={r.row} className="border-t border-[var(--sd-line)] align-top">
                      <td className="px-3 py-2 tabular-nums text-[var(--sd-quiet)]">{r.row}</td>
                      <td className="px-3 py-2">{r.values.unit ?? r.raw.block}</td>
                      {withCrops && <td className="px-3 py-2">{r.values.field_crop ?? r.raw.crop ?? "—"}</td>}
                      <td className="px-3 py-2">{r.values.variety ?? r.values.item ?? (r.raw.variety || r.raw.item)}</td>
                      {!avocado && <td className="px-3 py-2">{r.values.protocol ?? "—"}</td>}
                      <td className="px-3 py-2 tabular-nums">{r.values.planting_date ?? "—"}</td>
                      {avocado && <td className="px-3 py-2 text-right tabular-nums">{r.values.plant_count ? qty(r.values.plant_count) : "—"}</td>}
                      <td className="px-3 py-2 text-right tabular-nums">{r.values.area_ha ? ha(r.values.area_ha) : "—"}</td>
                      <td className="px-3 py-2">{r.values.current_stage || (!avocado && r.values.already_harvesting ? "Harvesting" : "—")}</td>
                      {avocado && <td className="px-3 py-2 text-right tabular-nums">{r.values.last_season_yield_kg ? qty(r.values.last_season_yield_kg) : "—"}</td>}
                      <td className="px-3 py-2">
                        {r.errors.map((e) => (
                          <div key={e} className="text-[var(--sd-sev-high)]">{e}</div>
                        ))}
                        {r.warnings.map((w) => (
                          <div key={w} className="text-[var(--sd-quiet)]">{w}</div>
                        ))}
                        {res && (res.ok ? <div className="font-medium text-[var(--sd-sev-moderate)]">Created {res.name}</div> : <div className="text-[var(--sd-sev-high)]">{res.error}</div>)}
                        {!r.errors.length && !r.warnings.length && !res && <span className="text-[var(--sd-sev-moderate)]">Ready</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel} disabled={busy}>
          Close
        </Button>
        <Button onClick={create} disabled={busy || !good.length || !!results}>
          {busy ? "Working…" : `Create ${good.length || ""} cycle${good.length === 1 ? "" : "s"}`.trim()}
        </Button>
      </div>
    </div>
  );
}
