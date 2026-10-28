import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { listSamples, listUnits, saveSample, type Row, type UnitRow } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { qty, shortDate } from "@/lib/format";
import { todayISO } from "@/lib/utils";
import { BODY_ROW, EmptyRows, Field, HEAD_ROW, TH, THR } from "./records";

const BASES = ["Plants", "Trees", "Square Metres"];

export function SamplesPanel({
  crop,
  unitLabel,
  canEdit,
  onSaved,
}: {
  crop: string;
  unitLabel: string;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    const r = await listSamples(crop);
    if (isError(r)) {
      toast(r.error, "error");
      setRows([]);
      return;
    }
    setRows(r.rows ?? []);
  }, [crop, toast]);

  useEffect(() => {
    setRows(null);
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-3">
      {canEdit && (
        <div className="flex justify-end">
          <Button size="sm" className="rounded-full" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> New sample
          </Button>
        </div>
      )}
      {!rows ? (
        <RowsSkeleton rows={4} />
      ) : rows.length === 0 ? (
        <EmptyRows>No yield samples recorded yet.</EmptyRows>
      ) : (
        <div className="max-h-[min(52vh,440px)] overflow-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
          <table className="w-full min-w-[44rem] text-[13px]">
            <thead>
              <tr className={HEAD_ROW}>
                <th className={TH}>Date</th>
                <th className={TH}>{unitLabel}</th>
                <th className={TH}>Stage</th>
                <th className={TH}>Basis</th>
                <th className={THR}>Sample size</th>
                <th className={THR}>Sampled yield</th>
                <th className={THR}>Estimated yield</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={String(r.name ?? i)} className={BODY_ROW}>
                  <td className="px-3 py-2.5 tabular-nums">{shortDate(r.sample_date as string)}</td>
                  <td className="px-3 py-2.5 font-medium text-[var(--sd-ink)]">{String(r.unit ?? "")}</td>
                  <td className="px-3 py-2.5 text-[var(--sd-muted)]">{String(r.growth_stage || "—")}</td>
                  <td className="px-3 py-2.5 text-[var(--sd-muted)]">{String(r.sample_basis ?? "")}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{qty(Number(r.sample_size), 1)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{qty(Number(r.sampled_yield), 1)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {r.est_unit_yield == null ? "—" : `${qty(Number(r.est_unit_yield))} ${String(r.uom ?? "")}`.trim()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && (
        <SampleDialog
          crop={crop}
          unitLabel={unitLabel}
          onClose={() => setOpen(false)}
          onSaved={() => {
            setOpen(false);
            void load();
            onSaved();
          }}
        />
      )}
    </div>
  );
}

function SampleDialog({
  crop,
  unitLabel,
  onClose,
  onSaved,
}: {
  crop: string;
  unitLabel: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [unit, setUnit] = useState("");
  const [date, setDate] = useState(todayISO());
  const [basis, setBasis] = useState(BASES[0]);
  const [size, setSize] = useState("");
  const [sampled, setSampled] = useState("");
  const [stage, setStage] = useState("");
  const [population, setPopulation] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    void listUnits(crop).then((r) => {
      if (live && !isError(r)) setUnits((r.units ?? []).filter((u) => !u.is_group));
    });
    return () => {
      live = false;
    };
  }, [crop]);

  const valid = !!unit && Number(size) > 0 && sampled !== "" && Number(sampled) >= 0;

  async function save() {
    setSaving(true);
    const r = await saveSample({
      crop,
      unit,
      sample_date: date,
      sample_basis: basis,
      sample_size: Number(size),
      sampled_yield: Number(sampled),
      growth_stage: stage || undefined,
      unit_population: population === "" ? undefined : Number(population),
    });
    setSaving(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast("Sample saved.");
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New sample</DialogTitle>
          <DialogDescription>
            Weigh or count a small sample and the {unitLabel.toLowerCase()} estimate is worked out from it.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={unitLabel}>
            <FilterSelect
              aria-label={unitLabel}
              value={unit}
              placeholder={`Choose ${unitLabel.toLowerCase()}`}
              options={units.map((u) => ({ value: u.name, label: u.name }))}
              onChange={setUnit}
            />
          </Field>
          <Field label="Sample date">
            <DatePicker value={date} max={todayISO()} onChange={setDate} aria-label="Sample date" />
          </Field>
          <Field label="Sample basis">
            <FilterSelect
              aria-label="Sample basis"
              value={basis}
              options={BASES.map((b) => ({ value: b, label: b }))}
              onChange={setBasis}
            />
          </Field>
          <Field label="Sample size" htmlFor="sample-size">
            <Input id="sample-size" type="number" min="0" inputMode="decimal" value={size} onChange={(e) => setSize(e.target.value)} />
          </Field>
          <Field label="Sampled yield" htmlFor="sample-yield">
            <Input id="sample-yield" type="number" min="0" inputMode="decimal" value={sampled} onChange={(e) => setSampled(e.target.value)} />
          </Field>
          <Field label={`Population in ${unitLabel.toLowerCase()} (optional)`} htmlFor="sample-pop">
            <Input id="sample-pop" type="number" min="0" inputMode="decimal" value={population} onChange={(e) => setPopulation(e.target.value)} />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Growth stage (optional)" htmlFor="sample-stage">
              <Input id="sample-stage" value={stage} onChange={(e) => setStage(e.target.value)} />
            </Field>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" disabled={!valid || saving} onClick={save}>
            {saving ? "Saving…" : "Save sample"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
