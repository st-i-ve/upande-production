import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Chip, Field, Problems } from "@/components/aquaculture/ui";
import { TONE } from "@/components/aquaculture/format";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { DatePicker } from "@/components/DatePicker";
import { Bar } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Picker } from "@/components/ui/picker";
import { SearchPicker } from "@/components/ui/search-picker";
import { kes, qty, shortDate, trimQty } from "@/lib/format";
import { isError } from "@/lib/frappe";
import {
  activityLabour,
  closeProblems,
  costPerKg,
  inputPayload,
  inputProblems,
  OPEN_STATUSES,
  perKgLabel,
  statusTone,
  type InputLine,
} from "@/lib/silage";
import {
  addSilageActivity,
  closeSilageCycle,
  getSilageCycle,
  issueSilageInputs,
  removeSilageActivity,
  saveSilageCycle,
  searchSilageItems,
  type ItemOption,
  type SilageCycleDetail,
  type SilageOptions,
  type SilageStatus,
} from "@/lib/silage-api";
import { todayISO } from "@/lib/utils";

const TONES = { ok: TONE.ok, warn: TONE.warn, quiet: TONE.quiet, info: "bg-[var(--sd-bg-soft)] text-[var(--sd-ink)]" };

export function StatusChip({ status }: { status: SilageStatus }) {
  return <Chip className={TONES[statusTone(status)]}>{status}</Chip>;
}

function useItems(open: boolean) {
  const [items, setItems] = useState<ItemOption[]>([]);
  useEffect(() => {
    if (!open || items.length) return;
    void searchSilageItems().then((r) => {
      if (!isError(r)) setItems(r.items);
    });
  }, [open, items.length]);
  return useMemo(
    () => items.map((i) => ({ value: i.item_code, label: `${i.item_name} (${i.stock_uom})`, short: i.item_name })),
    [items],
  );
}

// -- New cycle ---------------------------------------------------------------------------------

export function NewCycleDialog({
  open,
  onOpenChange,
  options,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  options: SilageOptions;
  onSaved: (name: string) => void;
}) {
  const toast = useToast();
  const items = useItems(open);
  const [crop, setCrop] = useState(options.crops[0] ?? "");
  const [unit, setUnit] = useState("");
  const [start, setStart] = useState(todayISO());
  const [item, setItem] = useState("");
  const [pit, setPit] = useState(options.pit_warehouse ?? "");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (open) {
      setCrop(options.crops[0] ?? ""); setUnit(""); setStart(todayISO()); setItem("");
      setPit(options.pit_warehouse ?? ""); setTried(false);
    }
  }, [open, options]);

  const problems: string[] = [];
  if (!crop) problems.push("Choose the crop.");
  if (!start) problems.push("Choose the start date.");

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveSilageCycle({
      crop, start_date: start, production_unit: unit || undefined, silage_item: item || undefined,
      pit_warehouse: pit || undefined, status: "Planned",
    });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Silage cycle started.", "ok", { hint: r.cycle.title });
    onOpenChange(false);
    onSaved(r.name);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New silage cycle</DialogTitle>
          <DialogDescription>
            One crop of forage on one field, from land preparation to a sealed pit. Its cost builds up from the
            inputs issued to it, the machines allocated to it and the labour on it.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="sc-crop" label="Crop">
            <Picker id="sc-crop" label="Crop" value={crop} onChange={setCrop} options={options.crops} />
          </Field>
          <Field label="Start date">
            <DatePicker value={start} onChange={setStart} aria-label="Start date" className="w-full" />
          </Field>
          <Field id="sc-unit" label="Field" hint={options.units.length ? undefined : "No field of a silage crop yet; set Grown for Silage on the crop."}>
            <Picker id="sc-unit" label="Field" value={unit} onChange={setUnit} clearable placeholder="Choose a field"
              options={options.units.map((u) => ({ value: u.name, label: u.unit_name || u.name }))} />
          </Field>
          <Field id="sc-pit" label="Pit">
            <Picker id="sc-pit" label="Pit" value={pit} onChange={setPit} clearable placeholder="Choose the pit" options={options.warehouses} />
          </Field>
          <Field id="sc-item" label="Silage item" className="sm:col-span-2" hint="The feed item livestock draws from the pit. Can be set at closing.">
            <SearchPicker id="sc-item" label="Silage item" value={item} onChange={setItem} options={items} placeholder="Search items" />
          </Field>
        </div>
        <Problems show={tried} items={problems} />
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Start cycle"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// -- One cycle ---------------------------------------------------------------------------------

function Section({ title, hint, children, action }: { title: string; hint?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h3 className="text-[13.5px] font-semibold text-[var(--sd-ink)]">{title}</h3>
          {hint && <p className="text-[12px] text-[var(--sd-quiet)]">{hint}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function CostBars({ c }: { c: SilageCycleDetail }) {
  return (
    <div className="space-y-2" data-testid="silage-cost-kinds">
      {c.by_kind.map((k) => (
        <div key={k.kind} className="grid grid-cols-[9rem_1fr_7rem] items-center gap-3 text-[12.5px]">
          <span className="text-[var(--sd-muted)]">{k.label}</span>
          <span className="h-2 overflow-hidden rounded-full bg-[var(--sd-bg-soft)]">
            <span className="block h-full rounded-full bg-[var(--sd-ink)]" style={{ width: `${k.share_pct ?? 0}%` }} />
          </span>
          <span className="text-right tabular-nums">{kes(k.amount)}</span>
        </div>
      ))}
      <div className="grid grid-cols-[9rem_1fr_7rem] gap-3 border-t border-[var(--sd-line-soft)] pt-2 text-[13px] font-semibold">
        <span>Total</span>
        <span className="text-[12px] font-normal text-[var(--sd-quiet)]">
          {c.ensiled_kg > 0 ? `${qty(c.ensiled_kg)} kg ensiled · ${perKgLabel(c.cost_per_kg)}` : "Nothing ensiled yet"}
        </span>
        <span className="text-right tabular-nums">{kes(c.cost.total)}</span>
      </div>
    </div>
  );
}

function ActivityForm({ c, options, onChanged }: { c: SilageCycleDetail; options: SilageOptions; onChanged: (c: SilageCycleDetail) => void }) {
  const toast = useToast();
  const [date, setDate] = useState(todayISO());
  const [activity, setActivity] = useState(options.activities[0] ?? "");
  const [workers, setWorkers] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const rate = options.day_rate;
  const preview = activityLabour(workers, rate, amount);

  const add = async () => {
    if (!activity || !date) return;
    setBusy(true);
    const r = await addSilageActivity({
      cycle: c.name, date, activity,
      workers: workers ? Number(workers) : undefined,
      labour_cost: amount ? Number(amount) : undefined,
      notes: notes.trim() || undefined,
    });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    setWorkers(""); setAmount(""); setNotes("");
    onChanged(r.cycle);
  };

  return (
    <div className="grid items-end gap-2 sm:grid-cols-[9rem_10rem_6rem_8rem_1fr_auto]">
      <DatePicker value={date} onChange={setDate} min={c.start_date} aria-label="Activity date" className="w-full" />
      <Picker label="Activity" value={activity} onChange={setActivity} options={options.activities} />
      <Input aria-label="Workers" inputMode="numeric" placeholder="Workers" value={workers} onChange={(e) => setWorkers(e.target.value)} />
      {rate != null ? (
        <Input aria-label="Amount paid" inputMode="decimal" placeholder={workers ? kes(preview) : "Amount"} value={amount}
          onChange={(e) => setAmount(e.target.value)} disabled={!!workers && rate > 0} />
      ) : (
        <span />
      )}
      <Input aria-label="Notes" placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <Button size="sm" onClick={add} disabled={busy || !activity}>
        <Plus className="h-4 w-4" /> Add
      </Button>
    </div>
  );
}

function IssueForm({ c, options, onChanged }: { c: SilageCycleDetail; options: SilageOptions; onChanged: (c: SilageCycleDetail) => void }) {
  const toast = useToast();
  const items = useItems(true);
  const [warehouse, setWarehouse] = useState(options.input_warehouse ?? "");
  const [date, setDate] = useState(todayISO());
  const [lines, setLines] = useState<InputLine[]>([{ item_code: "", qty: "" }]);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  const problems = inputProblems(lines, warehouse);
  const set = (i: number, patch: Partial<InputLine>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  const issue = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await issueSilageInputs({ cycle: c.name, items: inputPayload(lines), warehouse, posting_date: date });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Inputs issued.", "ok", { hint: r.stock_entry });
    setLines([{ item_code: "", qty: "" }]); setTried(false);
    onChanged(r.cycle);
  };

  return (
    <div className="space-y-2 rounded-xl bg-[var(--sd-bg-soft)] p-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <Picker label="Issue from" value={warehouse} onChange={setWarehouse} placeholder="Issue from store" options={options.warehouses} />
        <DatePicker value={date} onChange={setDate} min={c.start_date} max={todayISO()} aria-label="Issue date" className="w-full" />
      </div>
      {lines.map((l, i) => (
        <div key={i} className="grid grid-cols-[1fr_7rem_auto] gap-2">
          <SearchPicker label={`Item ${i + 1}`} value={l.item_code} onChange={(v) => set(i, { item_code: v })} options={items} placeholder="Search items" />
          <Input aria-label={`Quantity ${i + 1}`} inputMode="decimal" placeholder="Qty" value={l.qty} onChange={(e) => set(i, { qty: e.target.value })} />
          <Button variant="outline" size="icon" aria-label="Remove line" onClick={() => setLines((ls) => (ls.length > 1 ? ls.filter((_, j) => j !== i) : ls))}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Problems show={tried} items={problems} />
      <div className="flex justify-between">
        <Button variant="outline" size="sm" onClick={() => setLines((ls) => [...ls, { item_code: "", qty: "" }])}>
          <Plus className="h-4 w-4" /> Line
        </Button>
        <Button size="sm" onClick={issue} disabled={busy}>{busy ? "Issuing…" : "Issue from stock"}</Button>
      </div>
    </div>
  );
}

function CloseForm({ c, options, onChanged }: { c: SilageCycleDetail; options: SilageOptions; onChanged: (c: SilageCycleDetail) => void }) {
  const toast = useToast();
  const items = useItems(true);
  const [kg, setKg] = useState(c.ensiled_kg ? String(c.ensiled_kg) : "");
  const [date, setDate] = useState(todayISO());
  const [item, setItem] = useState(c.silage_item ?? "");
  const [pit, setPit] = useState(c.pit_warehouse ?? options.pit_warehouse ?? "");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  const openAllocations = c.allocations.filter((a) => !a.submitted).map((a) => a.allocation);
  const problems = closeProblems({ ensiledKg: kg, silageItem: item, pitWarehouse: pit, draftInputs: c.draft_inputs, openAllocations });
  const perKg = costPerKg(c.cost.total, kg);

  const close = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await closeSilageCycle({ name: c.name, ensiled_kg: Number(kg.replace(/,/g, "")), closed_on: date, silage_item: item, pit_warehouse: pit });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Cycle closed; silage received into the pit.", "ok", { hint: `${r.stock_entry} · ${perKgLabel(r.cycle.cost_per_kg)}` });
    onChanged(r.cycle);
  };

  return (
    <div className="space-y-3 rounded-xl bg-[var(--sd-bg-soft)] p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field id="sc-kg" label="Kilos ensiled">
          <Input id="sc-kg" inputMode="decimal" value={kg} onChange={(e) => setKg(e.target.value)} placeholder="250000" />
        </Field>
        <Field label="Closing date">
          <DatePicker value={date} onChange={setDate} min={c.start_date} max={todayISO()} aria-label="Closing date" className="w-full" />
        </Field>
        <Field id="sc-close-item" label="Silage item">
          <SearchPicker id="sc-close-item" label="Silage item" value={item} onChange={setItem} options={items} placeholder="Search items" />
        </Field>
        <Field id="sc-close-pit" label="Pit">
          <Picker id="sc-close-pit" label="Pit" value={pit} onChange={setPit} placeholder="Choose the pit" options={options.warehouses} />
        </Field>
      </div>
      <p className="text-[12.5px] text-[var(--sd-muted)]">
        Received at {perKgLabel(perKg)}: {kes(c.cost.total)} over {kg ? trimQty(Number(kg.replace(/,/g, ""))) : "—"} kg.
        The cost is frozen once the cycle is closed.
      </p>
      <Problems show={tried} items={problems} />
      <div className="flex justify-end">
        <Button onClick={close} disabled={busy}>{busy ? "Closing…" : "Close and receive into the pit"}</Button>
      </div>
    </div>
  );
}

export function CycleDialog({
  name,
  onOpenChange,
  options,
  canEdit,
  canClose,
  onChanged,
}: {
  name: string | null;
  onOpenChange: (o: boolean) => void;
  options: SilageOptions;
  canEdit: boolean;
  canClose: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [c, setC] = useState<SilageCycleDetail | null>(null);
  const [panel, setPanel] = useState<"" | "issue" | "close">("");

  useEffect(() => {
    setC(null);
    setPanel("");
    if (!name) return;
    void getSilageCycle(name).then((r) => {
      if (isError(r)) return void toast(r.error, "error");
      setC(r.cycle);
    });
  }, [name, toast]);

  const changed = (next: SilageCycleDetail) => {
    setC(next);
    setPanel("");
    onChanged();
  };

  const setStatus = async (status: string) => {
    if (!c) return;
    const r = await saveSilageCycle({ name: c.name, status: status as SilageStatus });
    if (isError(r)) return void toast(r.error, "error");
    changed(r.cycle);
  };

  const removeRow = async (row: string) => {
    if (!c) return;
    const r = await removeSilageActivity(c.name, row);
    if (isError(r)) return void toast(r.error, "error");
    changed(r.cycle);
  };

  const open = !!c && c.docstatus === 0;

  return (
    <Dialog open={!!name} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{c?.title ?? "Silage cycle"}</DialogTitle>
          <DialogDescription>
            {c ? (
              <span className="flex flex-wrap items-center gap-2">
                <StatusChip status={c.status} />
                <span>{c.crop}{c.production_unit ? ` · ${c.production_unit}` : ""} · started {shortDate(c.start_date)}</span>
                {c.closed_on && <span>· closed {shortDate(c.closed_on)}</span>}
                {c.receipt_stock_entry && <span>· pit receipt {c.receipt_stock_entry}</span>}
              </span>
            ) : (
              "Loading…"
            )}
          </DialogDescription>
        </DialogHeader>

        {!c ? (
          <div className="space-y-3"><Bar className="h-6 w-1/2" /><Bar className="h-24 w-full" /></div>
        ) : (
          <div className="space-y-6">
            {open && canEdit && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[12px] text-[var(--sd-quiet)]">Stage</span>
                <Picker label="Stage" value={c.status} onChange={setStatus} options={OPEN_STATUSES} className="w-40" />
                <span className="flex-1" />
                <Button variant="outline" size="sm" onClick={() => setPanel(panel === "issue" ? "" : "issue")}>Issue inputs</Button>
                {canClose && <Button size="sm" onClick={() => setPanel(panel === "close" ? "" : "close")}>Close cycle</Button>}
              </div>
            )}
            {panel === "issue" && open && <IssueForm c={c} options={options} onChanged={changed} />}
            {panel === "close" && open && <CloseForm c={c} options={options} onChanged={changed} />}

            <Section title={open ? "Running cost" : "Cost"} hint={open ? "Live: changes as inputs, machine work and labour are booked." : "Frozen when the cycle was closed; the pit receipt was valued at this."}>
              <CostBars c={c} />
            </Section>

            <Section title="Activities" hint={options.day_rate != null ? `Labour is workers x day rate (${kes(options.day_rate)} a day unless the row says otherwise), or the amount paid.` : undefined}>
              {c.activity_rows.length ? (
                <table className="w-full text-[13px]">
                  <thead><tr className={THEAD_ROW}><th className={TH}>Date</th><th className={TH}>Activity</th><th className={THR}>Workers</th><th className={THR}>Labour</th><th className={TH}>Notes</th>{open && canEdit && <th />}</tr></thead>
                  <tbody>
                    {c.activity_rows.map((r) => (
                      <tr key={r.name} className={BODY_ROW}>
                        <td className={TD}>{shortDate(r.date)}</td>
                        <td className={TD}>{r.activity}</td>
                        <td className={TDR}>{r.workers ?? "—"}</td>
                        <td className={TDR}>{kes(r.labour_cost)}</td>
                        <td className={`${TD} text-[var(--sd-muted)]`}>{r.notes}</td>
                        {open && canEdit && (
                          <td className="w-8 text-right">
                            <Button variant="ghost" size="icon" aria-label={`Remove ${r.activity}`} onClick={() => removeRow(r.name)}><Trash2 className="h-4 w-4" /></Button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-[12.5px] text-[var(--sd-quiet)]">No activity recorded yet.</p>
              )}
              {open && canEdit && <ActivityForm c={c} options={options} onChanged={changed} />}
            </Section>

            <Section title="Inputs issued" hint="Material Issues from stock booked to this cycle, valued from the stock ledger.">
              {c.draft_inputs.length > 0 && (
                <p className="text-[12.5px] text-[var(--sd-target)]">Draft issues not counted yet: {c.draft_inputs.join(", ")}</p>
              )}
              {c.inputs.length ? (
                <table className="w-full text-[13px]">
                  <thead><tr className={THEAD_ROW}><th className={TH}>Date</th><th className={TH}>Item</th><th className={THR}>Qty</th><th className={THR}>Value</th><th className={TH}>Entry</th></tr></thead>
                  <tbody>
                    {c.inputs.map((r, i) => (
                      <tr key={`${r.stock_entry}-${i}`} className={BODY_ROW}>
                        <td className={TD}>{shortDate(r.posting_date)}</td>
                        <td className={TD}>{r.item_name}</td>
                        <td className={TDR}>{trimQty(r.qty)} {r.uom}</td>
                        <td className={TDR}>{kes(r.amount)}</td>
                        <td className={`${TD} text-[var(--sd-muted)]`}>{r.stock_entry}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-[12.5px] text-[var(--sd-quiet)]">No inputs issued yet.</p>
              )}
            </Section>

            <Section title="Machine work" hint="Machines allocated to this cycle; the diesel of closed allocations counts.">
              {!c.allocations_available ? (
                <p className="text-[12.5px] text-[var(--sd-quiet)]">Machine allocation is not set up on this site yet.</p>
              ) : c.allocations.length ? (
                <table className="w-full text-[13px]">
                  <thead><tr className={THEAD_ROW}><th className={TH}>Machine</th><th className={TH}>Operator</th><th className={TH}>From</th><th className={THR}>Hours</th><th className={THR}>Diesel</th><th className={THR}>Cost</th></tr></thead>
                  <tbody>
                    {c.allocations.map((a) => (
                      <tr key={a.allocation} className={BODY_ROW}>
                        <td className={TD}>{a.machine}{!a.submitted && <Chip className={`ml-2 ${TONE.warn}`}>open</Chip>}</td>
                        <td className={TD}>{a.operator_name ?? "—"}</td>
                        <td className={TD}>{shortDate(a.start_time)}</td>
                        <td className={TDR}>{a.duration_hours != null ? trimQty(a.duration_hours) : "—"}</td>
                        <td className={TDR}>{a.diesel_litres != null ? `${trimQty(a.diesel_litres)} L` : "—"}</td>
                        <td className={TDR}>{kes(a.diesel_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-[12.5px] text-[var(--sd-quiet)]">No machine allocated to this cycle yet.</p>
              )}
            </Section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
