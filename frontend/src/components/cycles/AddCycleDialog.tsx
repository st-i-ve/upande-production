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
import { addCycle, importCycles, importTemplate, previewImport, type ImportResult, type ImportRow } from "@/lib/cycle-setup-api";
import { listProtocols, type Crop, type UnitRow } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { ha, qty } from "@/lib/format";
import { cn, todayISO } from "@/lib/utils";
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

/**
 * Add a crop cycle to an avocado block: a new one, one that is already in production (planting date, current
 * stage, history) or many from a sheet. Several cycles may run on one block; going past the block's area or
 * trees warns and still saves.
 */
export function AddCycleDialog({
  crop,
  units,
  defaultUnit,
  defaultMode = "new",
  open,
  onOpenChange,
  onSaved,
}: {
  crop: Crop;
  units: UnitRow[];
  defaultUnit?: string;
  defaultMode?: Mode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [mode, setMode] = useState<Mode>(defaultMode);
  const [unit, setUnit] = useState(defaultUnit ?? "");
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
    setMode(defaultMode);
    setUnit(defaultUnit ?? "");
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
  }, [open, crop.name, defaultUnit, defaultMode]);

  const unitRow = units.find((u) => u.name === unit);
  const v = varieties.find((x) => x.name === variety);
  const stages = useMemo(() => (v?.stages ?? []).map((s) => s.stage), [v]);
  const protoOptions = useMemo(() => protocols.filter((p) => !p.variety || p.variety === variety), [protocols, variety]);

  // Choosing a variety offers its stages and its own protocol; choosing a block offers its area and trees.
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
  const can =
    !!unit && !!variety && !busy && (existing ? !!planting && !!stage : !!start);

  async function save() {
    setBusy(true);
    const r = await addCycle({
      unit,
      variety,
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
            starts from the stage it is in now; nothing before today is planned.
          </DialogDescription>
        </DialogHeader>

        <div role="tablist" aria-label="Kind of cycle" className="flex flex-wrap gap-2">
          {MODES.map((m) => (
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
              <Field label="Variety" htmlFor="ac-variety">
                <Picker id="ac-variety" label="Variety" value={variety} onChange={setVariety} options={varieties.map((x) => ({ value: x.name, label: x.variety_name }))} placeholder="Choose a variety…" />
              </Field>
              <Field label="Protocol" htmlFor="ac-protocol" hint={variety && protoOptions.length === 0 ? "No active protocol for this variety." : undefined}>
                <Picker id="ac-protocol" label="Protocol" value={protocol} onChange={setProtocol} options={protoOptions} clearable clearLabel="No protocol" placeholder="No protocol" />
              </Field>

              {existing ? (
                <>
                  <Field label="Planting date" hint={planting ? `Tree age ${treeAge(planting)}` : "When the trees were planted"}>
                    <DatePicker value={planting} onChange={setPlanting} max={todayISO()} aria-label="Planting date" className="w-full" />
                  </Field>
                  <Field label="Current stage" htmlFor="ac-stage" hint={variety ? undefined : "Choose a variety first"}>
                    <Picker id="ac-stage" label="Current stage" value={stage} onChange={setStage} options={stages} placeholder="Choose a stage…" disabled={!stages.length} />
                  </Field>
                  <Field label="Trees standing" htmlFor="ac-trees" hint={unitRow?.plant_count ? `Block records ${qty(unitRow.plant_count)} trees` : undefined}>
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
              {existing && (
                <>
                  <Field label="Last flowering date (optional)">
                    <OptionalDate value={lastFlower} onChange={setLastFlower} label="Last flowering date" max={todayISO()} />
                  </Field>
                  <Field label="Last harvest date (optional)">
                    <OptionalDate value={lastHarvest} onChange={setLastHarvest} label="Last harvest date" max={todayISO()} />
                  </Field>
                  <Field label="Last season yield (kg per year, optional)" htmlFor="ac-lastkg" hint={treesN && lastKg ? `${qty(Number(lastKg) / treesN, 1)} kg/tree/year` : undefined}>
                    <Input id="ac-lastkg" inputMode="decimal" className="tabular-nums" value={lastKg} onChange={(e) => setLastKg(e.target.value)} />
                  </Field>
                </>
              )}
            </div>

            {yearKg != null && (
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
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState("");
  const [rows, setRows] = useState<ImportRow[] | null>(null);
  const [results, setResults] = useState<ImportResult[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function template() {
    const r = await importTemplate();
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
        Upload a CSV or Excel sheet of cycles that are already in production: block, variety, planting date, trees, area, current stage and last
        season&rsquo;s kg per year. Rows are checked first; nothing is created until you confirm.
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
                  <th className="px-3 py-2">Variety</th>
                  <th className="px-3 py-2">Planted</th>
                  <th className="px-3 py-2 text-right">Trees</th>
                  <th className="px-3 py-2 text-right">Area (ha)</th>
                  <th className="px-3 py-2">Stage</th>
                  <th className="px-3 py-2 text-right">Last kg/yr</th>
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
                      <td className="px-3 py-2">{r.values.variety ?? r.raw.variety}</td>
                      <td className="px-3 py-2 tabular-nums">{r.values.planting_date ?? "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{r.values.plant_count ? qty(r.values.plant_count) : "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{r.values.area_ha ? ha(r.values.area_ha) : "—"}</td>
                      <td className="px-3 py-2">{r.values.current_stage || "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{r.values.last_season_yield_kg ? qty(r.values.last_season_yield_kg) : "—"}</td>
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
