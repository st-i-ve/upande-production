import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { getCropModel, saveCropModel, type CropModel, type ModelField, type ModelTable } from "@/lib/crop-model-api";
import { isError } from "@/lib/frappe";

type Values = Record<string, string | number | boolean | null>;
type Tables = Record<string, Record<string, string | number | null>[]>;

const NUMERIC = ["Int", "Float", "Currency", "Percent"];

/** Values and rows as the server described them, ready to edit. */
export function draftOf(m: CropModel): { values: Values; tables: Tables } {
  const values: Values = {};
  const tables: Tables = {};
  for (const g of m.groups) {
    for (const f of g.fields) values[f.fieldname] = f.fieldtype === "Check" ? !!f.value : f.value ?? "";
    for (const t of g.tables) tables[t.fieldname] = t.rows.map((r) => ({ ...r }));
  }
  return { values, tables };
}

/** What to send back: numbers as numbers, checks as 0/1, blanks as null. */
export function payloadOf(m: CropModel, values: Values, tables: Tables): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const g of m.groups) {
    for (const f of g.fields) {
      const v = values[f.fieldname];
      out[f.fieldname] = f.fieldtype === "Check" ? (v ? 1 : 0) : NUMERIC.includes(f.fieldtype) ? (v === "" || v == null ? null : Number(v)) : v === "" ? null : v;
    }
    for (const t of g.tables) {
      out[t.fieldname] = (tables[t.fieldname] ?? []).map((r) =>
        Object.fromEntries(t.columns.map((c) => [c.fieldname, NUMERIC.includes(c.fieldtype) ? (r[c.fieldname] === "" || r[c.fieldname] == null ? null : Number(r[c.fieldname])) : r[c.fieldname] ?? null])),
      );
    }
  }
  return out;
}

function FieldInput({ f, values, set, disabled }: { f: ModelField; values: Values; set: (name: string, v: string | boolean) => void; disabled: boolean }) {
  const id = `cm-${f.fieldname}`;
  if (f.depends_on && !values[f.depends_on]) return null;
  return (
    <div className="flex flex-col gap-1.5">
      {f.fieldtype === "Check" ? (
        <label className="flex items-center gap-2 text-[13px] text-[var(--sd-ink)]">
          <Switch checked={!!values[f.fieldname]} disabled={disabled} onCheckedChange={(v) => set(f.fieldname, v)} aria-label={f.label} />
          {f.label}
        </label>
      ) : (
        <>
          <Label htmlFor={id}>{f.label}</Label>
          {f.fieldtype === "Select" ? (
            <select id={id} aria-label={f.label} disabled={disabled} value={String(values[f.fieldname] ?? "")} onChange={(e) => set(f.fieldname, e.target.value)} className="h-9 rounded-md border border-[var(--sd-line)] bg-transparent px-2 text-[13px]">
              {(f.options ?? "").split("\n").map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : (
            <Input id={id} disabled={disabled} inputMode={NUMERIC.includes(f.fieldtype) ? "decimal" : undefined} className={NUMERIC.includes(f.fieldtype) ? "tabular-nums" : undefined} value={String(values[f.fieldname] ?? "")} onChange={(e) => set(f.fieldname, e.target.value)} />
          )}
        </>
      )}
      {f.description && <span className="text-[11.5px] text-[var(--sd-quiet)]">{f.description}</span>}
    </div>
  );
}

function TableEditor({ t, rows, onChange, disabled }: { t: ModelTable; rows: Tables[string]; onChange: (rows: Tables[string]) => void; disabled: boolean }) {
  const setCell = (i: number, name: string, v: string) => onChange(rows.map((r, j) => (j === i ? { ...r, [name]: v } : r)));
  return (
    <section data-testid={`cm-table-${t.fieldname}`}>
      <div className="mb-1 flex items-center justify-between">
        <h4 className="text-[13px] font-semibold">{t.label}</h4>
        {!disabled && (
          <Button type="button" variant="ghost" size="sm" onClick={() => onChange([...rows, Object.fromEntries(t.columns.map((c) => [c.fieldname, c.fieldtype === "Check" ? 0 : ""]))])}>
            <Plus className="mr-1 h-3.5 w-3.5" /> Add row
          </Button>
        )}
      </div>
      {t.description && <p className="mb-2 text-[11.5px] text-[var(--sd-quiet)]">{t.description}</p>}
      {rows.length === 0 ? (
        <p className="text-[12.5px] text-[var(--sd-quiet)]">No rows yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                {t.columns.map((c) => <th key={c.fieldname} className="px-3 py-2 font-medium">{c.label}</th>)}
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-[var(--sd-line-soft)] last:border-0">
                  {t.columns.map((c) => (
                    <td key={c.fieldname} className="px-3 py-1.5">
                      {c.fieldtype === "Check" ? (
                        <Switch checked={!!Number(r[c.fieldname])} disabled={disabled} onCheckedChange={(v) => setCell(i, c.fieldname, v ? "1" : "0")} aria-label={`${t.label} ${i + 1} ${c.label}`} />
                      ) : c.fieldtype === "Select" ? (
                        <select aria-label={`${t.label} ${i + 1} ${c.label}`} disabled={disabled} value={String(r[c.fieldname] ?? "")} onChange={(e) => setCell(i, c.fieldname, e.target.value)} className="h-9 w-full rounded-md border border-[var(--sd-line)] bg-transparent px-2 text-[13px]">
                          {(c.options ?? "").split("\n").map((o) => <option key={o} value={o}>{o}</option>)}
                        </select>
                      ) : (
                        <Input aria-label={`${t.label} ${i + 1} ${c.label}`} disabled={disabled} inputMode={NUMERIC.includes(c.fieldtype) ? "decimal" : undefined} className={NUMERIC.includes(c.fieldtype) ? "tabular-nums" : undefined} value={String(r[c.fieldname] ?? "")} onChange={(e) => setCell(i, c.fieldname, e.target.value)} />
                      )}
                    </td>
                  ))}
                  <td className="px-1">
                    {!disabled && (
                      <button type="button" aria-label={`Remove ${t.label} row ${i + 1}`} onClick={() => onChange(rows.filter((_, j) => j !== i))} className="p-1.5 text-[var(--sd-quiet)] hover:text-[var(--sd-data-red)]">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/**
 * A crop's model parameters: price, crate weight, picking rates, dry matter window, model constants, count
 * sizes and the other limits the server lists for this crop. The layout comes from the server; managers edit,
 * everyone else reads.
 */
export function CropModelPanel({ crop, canEdit }: { crop: string; canEdit: boolean }) {
  const toast = useToast();
  const [model, setModel] = useState<CropModel | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [values, setValues] = useState<Values>({});
  const [tables, setTables] = useState<Tables>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setModel(null);
    const r = await getCropModel(crop);
    if (isError(r)) {
      setFailure(r.error);
      return;
    }
    setFailure(null);
    setModel(r);
    const d = draftOf(r);
    setValues(d.values);
    setTables(d.tables);
    setDirty(false);
  }, [crop]);

  useEffect(() => {
    void load();
  }, [load]);

  if (failure) return <p role="alert" className="text-[13px] text-[var(--sd-muted)]">{failure}</p>;
  if (!model) return <RowsSkeleton rows={4} />;
  const editable = canEdit && model.can_edit !== false;

  const save = async () => {
    setSaving(true);
    const r = await saveCropModel(crop, payloadOf(model, values, tables));
    setSaving(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Crop model saved.");
    void load();
  };

  return (
    <div className="space-y-6" data-testid="crop-model-panel">
      {model.groups.map((g) => (
        <section key={g.label} data-testid={`cm-group-${g.label}`} className="space-y-3">
          <h3 className="text-[14px] font-semibold">{g.label}</h3>
          {g.fields.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {g.fields.map((f) => (
                <FieldInput key={f.fieldname} f={f} values={values} disabled={!editable} set={(n, v) => { setValues((cur) => ({ ...cur, [n]: v })); setDirty(true); }} />
              ))}
            </div>
          )}
          {g.tables.map((t) => (
            <TableEditor key={t.fieldname} t={t} rows={tables[t.fieldname] ?? []} disabled={!editable} onChange={(rows) => { setTables((cur) => ({ ...cur, [t.fieldname]: rows })); setDirty(true); }} />
          ))}
        </section>
      ))}
      {editable && (
        <div className="flex justify-end">
          <Button type="button" onClick={() => void save()} disabled={!dirty || saving}>
            {saving ? "Saving" : "Save crop model"}
          </Button>
        </div>
      )}
    </div>
  );
}
