import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { RowsSkeleton, firstLoad } from "@/components/Loading";
import { DatePicker } from "@/components/DatePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable } from "@/components/ScrollTable";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchPicker } from "@/components/ui/search-picker";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listUnits, type UnitRow } from "@/lib/api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import {
  cancelCost,
  capitalActivities,
  listCosts,
  listOpeningBalances,
  saveCost,
  saveOpeningBalance,
  type CapitalActivity,
  type EstablishmentByUnit,
  type EstablishmentCostRow,
  type OpeningBalance,
} from "@/lib/establishment-api";
import { isError } from "@/lib/frappe";
import { ha, kes, shortDate } from "@/lib/format";
import { num, todayISO } from "@/lib/utils";

const ALL = "";

export interface SplitRow {
  unit: string;
  share_pct: number;
  amount: number;
  /** By area with no area on the block: cannot be split. */
  noArea?: boolean;
}

/** The leaf blocks under each chosen unit (a leaf stands for itself), without repeats. */
export function leavesOf(chosen: string[], units: UnitRow[]): UnitRow[] {
  const kids = new Map<string, UnitRow[]>();
  for (const u of units) if (u.parent) kids.set(u.parent, [...(kids.get(u.parent) ?? []), u]);
  const byName = new Map(units.map((u) => [u.name, u]));
  const out = new Map<string, UnitRow>();
  const walk = (u: UnitRow, depth: number) => {
    if (depth > 20) return;
    if (!u.is_group) out.set(u.name, u);
    else for (const k of kids.get(u.name) ?? []) walk(k, depth + 1);
  };
  for (const name of chosen) {
    const u = byName.get(name);
    if (u) walk(u, 0);
  }
  return [...out.values()];
}

/** By area: share by hectares, cents rounded, the remainder on the largest block (as the server does). */
export function splitByArea(amount: number, leaves: UnitRow[]): SplitRow[] {
  const total = leaves.reduce((t, u) => t + (u.area_ha || 0), 0);
  if (!leaves.length || amount <= 0) return leaves.map((u) => ({ unit: u.name, share_pct: 0, amount: 0, noArea: !(u.area_ha > 0) }));
  if (total <= 0) return leaves.map((u) => ({ unit: u.name, share_pct: 0, amount: 0, noArea: true }));
  const rows = leaves.map((u) => {
    const share = (u.area_ha || 0) / total;
    return { unit: u.name, share_pct: share * 100, amount: Math.round(amount * share * 100) / 100, noArea: !(u.area_ha > 0) };
  });
  const rest = Math.round((amount - rows.reduce((t, r) => t + r.amount, 0)) * 100) / 100;
  if (rest !== 0) {
    const big = rows.reduce((a, b) => (b.share_pct > a.share_pct ? b : a));
    big.amount = Math.round((big.amount + rest) * 100) / 100;
  }
  return rows;
}

function AddCostDialog({
  crop,
  farm,
  units,
  activities,
  onClose,
  onSaved,
}: {
  crop: string;
  farm: string;
  units: UnitRow[];
  activities: CapitalActivity[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [date, setDate] = useState(todayISO());
  const [operation, setOperation] = useState("");
  const [amount, setAmount] = useState("");
  const [paidTo, setPaidTo] = useState("");
  const [reference, setReference] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  const [method, setMethod] = useState<"By area" | "Manual">("By area");
  const [manual, setManual] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const total = num(amount) ?? 0;
  const leaves = useMemo(() => leavesOf(chosen, units), [chosen, units]);
  const preview = useMemo<SplitRow[]>(() => {
    if (method === "By area") return splitByArea(total, leaves);
    return leaves.map((u) => {
      const pct = num(manual[u.name] ?? "") ?? 0;
      return { unit: u.name, share_pct: pct, amount: Math.round(total * pct) / 100 };
    });
  }, [method, total, leaves, manual]);
  const shareSum = preview.reduce((t, r) => t + r.share_pct, 0);
  const noArea = method === "By area" ? preview.filter((r) => r.noArea).map((r) => r.unit) : [];
  const manualOff = method === "Manual" && leaves.length > 0 && Math.abs(shareSum - 100) > 0.01;
  const ready = !!operation && total > 0 && leaves.length > 0 && noArea.length === 0 && !manualOff;

  const opOptions = activities.map((a) => ({ value: a.operation, label: a.operation, short: a.operation }));
  const toggle = (name: string) => setChosen((c) => (c.includes(name) ? c.filter((x) => x !== name) : [...c, name]));

  async function save() {
    setBusy(true);
    setFailure(null);
    const r = await saveCost({
      crop,
      farm: farm || null,
      posting_date: date,
      operation,
      amount: total,
      paid_to: paidTo || null,
      reference: reference || null,
      split_method: method,
      // Manual shares are typed per leaf block, so send the leaves (a chosen group is expanded here).
      blocks:
        method === "Manual"
          ? leaves.map((u) => ({ unit: u.name, share_pct: num(manual[u.name] ?? "") ?? 0 }))
          : chosen.map((unit) => ({ unit })),
    });
    setBusy(false);
    if (isError(r)) return setFailure(r.error);
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto" aria-describedby="est-desc">
        <DialogHeader>
          <DialogTitle>Add cost</DialogTitle>
          <DialogDescription id="est-desc">
            Capital or setup spend, shared over one or more blocks. A group is split over the blocks inside it.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Date</Label>
            <DatePicker value={date} onChange={setDate} max={todayISO()} aria-label="Date" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="est-amount">Amount (KES)</Label>
            <Input id="est-amount" inputMode="decimal" className="tabular-nums" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Activity</Label>
          <SearchPicker value={operation} onChange={setOperation} options={opOptions} placeholder="Choose an activity" label="Activity" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="est-paid">Supplier / paid to</Label>
            <Input id="est-paid" value={paidTo} onChange={(e) => setPaidTo(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="est-ref">Reference</Label>
            <Input id="est-ref" value={reference} onChange={(e) => setReference(e.target.value)} />
          </div>
        </div>
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1 text-[13px] font-medium">Blocks</legend>
          <div className="max-h-40 overflow-y-auto rounded-[var(--sd-radius)] border border-[var(--sd-line)] p-2">
            {units.map((u) => (
              <label key={u.name} className="flex cursor-pointer items-center gap-2 py-1 text-[13px]" style={{ paddingLeft: u.parent ? 16 : 0 }}>
                <input type="checkbox" checked={chosen.includes(u.name)} onChange={() => toggle(u.name)} aria-label={u.name} />
                <span>{u.name}</span>
                <span className="text-[11.5px] text-[var(--sd-quiet)]">
                  {u.is_group ? "group" : `${ha(u.area_ha)} ha`}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="flex items-center gap-2" role="group" aria-label="Split method">
          {(["By area", "Manual"] as const).map((m) => (
            <Button key={m} type="button" size="sm" variant={method === m ? "default" : "outline"} aria-pressed={method === m} onClick={() => setMethod(m)}>
              {m === "By area" ? "Split by area" : "Split manually"}
            </Button>
          ))}
        </div>
        {preview.length > 0 && (
          <div data-testid="split-preview" className="rounded-[var(--sd-radius)] border border-[var(--sd-line)]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Block</TableHead>
                  <TableHead className="text-right">Share</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {preview.map((r) => (
                  <TableRow key={r.unit} data-testid={`split-${r.unit}`}>
                    <TableCell>{r.unit}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {method === "Manual" ? (
                        <Input
                          aria-label={`Share ${r.unit}`}
                          inputMode="decimal"
                          className="ml-auto h-8 w-20 text-right tabular-nums"
                          value={manual[r.unit] ?? ""}
                          onChange={(e) => setManual((m) => ({ ...m, [r.unit]: e.target.value }))}
                        />
                      ) : (
                        `${r.share_pct.toFixed(1)}%`
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{kes(r.amount)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        {noArea.length > 0 && (
          <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px]">
            {noArea.map((n) => `Block ${n} has no area; enter its area or split manually.`).join(" ")}
          </p>
        )}
        {manualOff && (
          <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-info)] px-3 py-2 text-[13px]">
            Shares add up to {shareSum.toFixed(1)}%; they must total 100%.
          </p>
        )}
        {failure && (
          <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px]">
            {failure}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void save()} disabled={busy || !ready}>
            {busy ? "Saving…" : "Save cost"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** One editable row of the Opening balances tab. */
function BalanceRow({ unit, saved, onSave }: { unit: string; saved?: OpeningBalance; onSave: (b: OpeningBalance) => Promise<void> }) {
  const init = {
    as_of: saved?.as_of_date ?? "",
    setup: saved ? String(saved.setup_cost ?? 0) : "",
    running: saved ? String(saved.running_costs_to_date ?? 0) : "",
    value: saved ? String(saved.value_recovered_to_date ?? 0) : "",
    planted: saved?.planted_on ?? "",
  };
  const [d, setD] = useState(init);
  const [busy, setBusy] = useState(false);
  const dirty = JSON.stringify(d) !== JSON.stringify(init);
  const set = (k: keyof typeof init) => (v: string) => setD((x) => ({ ...x, [k]: v }));

  async function save() {
    setBusy(true);
    await onSave({
      unit,
      as_of_date: d.as_of,
      setup_cost: num(d.setup) ?? 0,
      running_costs_to_date: num(d.running) ?? 0,
      value_recovered_to_date: num(d.value) ?? 0,
      planted_on: d.planted || null,
    });
    setBusy(false);
  }
  const money = (k: "setup" | "running" | "value", label: string) => (
    <Input
      aria-label={`${label} ${unit}`}
      inputMode="decimal"
      className="ml-auto h-8 w-32 text-right tabular-nums"
      value={d[k]}
      onChange={(e) => set(k)(e.target.value)}
    />
  );
  return (
    <TableRow data-testid={`balance-${unit}`}>
      <TableCell className="font-medium">{unit}</TableCell>
      <TableCell><DatePicker value={d.planted} onChange={set("planted")} aria-label={`Planted on ${unit}`} /></TableCell>
      <TableCell><DatePicker value={d.as_of} onChange={set("as_of")} max={todayISO()} aria-label={`As of ${unit}`} /></TableCell>
      <TableCell className="text-right">{money("setup", "Setup cost")}</TableCell>
      <TableCell className="text-right">{money("running", "Running costs")}</TableCell>
      <TableCell className="text-right">{money("value", "Value recovered")}</TableCell>
      <TableCell className="text-right">
        <Button size="sm" aria-label={`Save ${unit}`} disabled={busy || !dirty || !d.as_of} onClick={() => void save()}>
          {busy ? "Saving…" : "Save"}
        </Button>
      </TableCell>
    </TableRow>
  );
}

/**
 * What it cost to set each block up (land clearing, trellis, irrigation, plants...), and the
 * opening balance of blocks that were already running before this system. Cash spend, not pay,
 * so figures are not hidden by the pay rule; writing needs a manager.
 */
export function Establishment() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const canWrite = crop.boot.can_manage;
  const farms = crop.boot.farms ?? [];
  const [farm, setFarm] = useState(ALL);
  const [rows, setRows] = useState<EstablishmentCostRow[] | null>(null);
  const [byUnit, setByUnit] = useState<EstablishmentByUnit[]>([]);
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [activities, setActivities] = useState<CapitalActivity[]>([]);
  const [balances, setBalances] = useState<OpeningBalance[]>([]);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [c, u, a, b] = await Promise.all([listCosts(crop.name, farm || null), listUnits(crop.name), capitalActivities(crop.name), listOpeningBalances(crop.name)]);
    setLoading(false);
    if (isError(c)) {
      setFailure(c.error);
      toast(c.error, "error");
      setRows((cur) => cur ?? []);
    } else {
      setFailure(null);
      setRows(c.rows ?? []);
      setByUnit(c.by_unit ?? []);
    }
    if (!isError(u)) setUnits(u.units ?? []);
    if (!isError(a)) setActivities(a.rows ?? []);
    if (!isError(b)) setBalances(b.rows ?? []);
  }, [crop.name, farm, toast]);

  useEffect(() => {
    setRows(null);
    void load();
  }, [load]);

  const areaOf = useMemo(() => new Map(units.map((u) => [u.name, u.area_ha || 0])), [units]);
  const totals = useMemo(() => {
    const invested = byUnit.reduce((t, r) => t + (r.total || 0), 0);
    const area = byUnit.reduce((t, r) => t + (r.area_ha ?? areaOf.get(r.unit) ?? 0), 0);
    let budget = 0;
    let actualBudgeted = 0;
    for (const r of byUnit) for (const a of r.by_activity) if (a.budget) { budget += a.budget; actualBudgeted += a.amount; }
    return { invested, area, budget, actualBudgeted, blocks: byUnit.filter((r) => r.total > 0).length };
  }, [byUnit, areaOf]);

  const activityCols = useMemo(() => [...new Set(byUnit.flatMap((r) => r.by_activity.map((a) => a.operation)))], [byUnit]);
  const leafUnits = useMemo(() => units.filter((u) => !u.is_group), [units]);
  const balanceOf = useMemo(() => new Map(balances.map((b) => [b.unit, b])), [balances]);

  async function remove(name: string) {
    if (!window.confirm("Cancel this cost? Its share leaves every block it was split over.")) return;
    const r = await cancelCost(name);
    if (isError(r)) return toast(r.error, "error");
    toast("Cost cancelled.", "ok");
    void load();
  }

  async function saveBalance(b: OpeningBalance) {
    const r = await saveOpeningBalance({ ...b, crop: crop.name });
    if (isError(r)) return void toast(r.error, "error");
    toast(`Opening balance saved for ${b.unit}.`, "ok");
    void load();
  }

  const first = firstLoad(loading, !!rows);
  const overBudget = totals.budget > 0 && totals.actualBudgeted > totals.budget;

  return (
    <PageShell
      title={viewLabel("establishment", crop)}
      eyebrow={crop.name}
      description={`What it cost to set up each ${(crop.unit_label || "block").toLowerCase()}, and the opening balance of those already running. Break-even starts from these figures.`}
      actions={
        <>
          {farms.length > 1 && <FilterSelect label="Farm" value={farm} onChange={setFarm} options={farms} allLabel="All farms" />}
          <RefreshButton onClick={load} loading={loading} label="the setup costs" />
          {canWrite && (
            <ToolbarButton onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> Add cost
            </ToolbarButton>
          )}
        </>
      }
    >
      {failure && (
        <div role="alert" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-error)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          {failure}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard loading={first} label="Total invested" value={kes(totals.invested)} hint="submitted setup costs" />
        <KpiCard loading={first} label="Per ha" value={totals.area > 0 ? kes(totals.invested / totals.area) : "—"} hint={`over ${ha(totals.area)} ha`} />
        <KpiCard loading={first} label="Blocks set up" value={totals.blocks} hint="with a cost recorded" />
        <KpiCard
          loading={first}
          label="Budget vs actual"
          value={totals.budget > 0 ? `${Math.round((totals.actualBudgeted / totals.budget) * 100)}%` : "—"}
          hint={totals.budget > 0 ? `${kes(totals.actualBudgeted)} of ${kes(totals.budget)}` : "no budget set"}
          tone={overBudget ? "critical" : "default"}
        />
      </div>

      <Tabs defaultValue="costs" className="flex flex-col gap-4">
        <TabsList className="self-start">
          <TabsTrigger value="costs">Costs</TabsTrigger>
          <TabsTrigger value="opening">Opening balances</TabsTrigger>
        </TabsList>

        <TabsContent value="costs" className="m-0 flex flex-col gap-6">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>By {(crop.unit_label || "block").toLowerCase()} and activity</CardTitle>
                <CardDescription>Each cost split over its blocks; budget shows where one is set.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent className="pt-0">
              {!rows ? (
                <RowsSkeleton rows={5} />
              ) : byUnit.length === 0 ? (
                <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">No setup costs recorded yet.</p>
              ) : (
                <ScrollTable>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{crop.unit_label || "Block"}</TableHead>
                        {activityCols.map((a) => (
                          <TableHead key={a} className="text-right">{a}</TableHead>
                        ))}
                        <TableHead className="text-right">Total</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {byUnit.map((r) => (
                        <TableRow key={r.unit} data-testid={`unit-${r.unit}`}>
                          <TableCell className="font-medium">{r.unit}</TableCell>
                          {activityCols.map((a) => {
                            const cell = r.by_activity.find((x) => x.operation === a);
                            const over = !!cell?.budget && cell.amount > cell.budget;
                            return (
                              <TableCell key={a} className={`text-right tabular-nums ${over ? "text-[var(--sd-data-red)]" : ""}`} title={cell?.budget ? `Budget ${kes(cell.budget)}` : undefined}>
                                {cell ? kes(cell.amount) : "—"}
                              </TableCell>
                            );
                          })}
                          <TableCell className="text-right font-medium tabular-nums">{kes(r.total)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollTable>
              )}
            </CardContent>
          </Card>

          {rows && rows.length > 0 && (
            <Card>
              <CardHeaderRow>
                <CardHeading>
                  <CardTitle>Costs entered</CardTitle>
                </CardHeading>
              </CardHeaderRow>
              <CardContent className="pt-0">
                <ScrollTable>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Activity</TableHead>
                        <TableHead>Paid to</TableHead>
                        <TableHead>Reference</TableHead>
                        <TableHead>Blocks</TableHead>
                        <TableHead className="text-right">Amount</TableHead>
                        {canWrite && <TableHead className="w-10" />}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((r) => (
                        <TableRow key={r.name}>
                          <TableCell>{shortDate(r.posting_date)}</TableCell>
                          <TableCell>{r.operation}</TableCell>
                          <TableCell>{r.supplier || r.paid_to || "—"}</TableCell>
                          <TableCell>{r.reference || "—"}</TableCell>
                          <TableCell className="max-w-[18rem] truncate">{(r.blocks ?? []).map((b) => b.unit).join(", ") || "—"}</TableCell>
                          <TableCell className="text-right tabular-nums">{kes(r.amount)}</TableCell>
                          {canWrite && (
                            <TableCell>
                              <Button size="sm" variant="ghost" aria-label={`Cancel ${r.name}`} onClick={() => void remove(r.name)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollTable>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="opening" className="m-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Opening balances</CardTitle>
                <CardDescription>
                  For blocks that were running before this system: what they had cost and earned up to the date given. The system counts only what happens after that date.
                </CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent className="pt-0">
              {first ? (
                <RowsSkeleton rows={5} />
              ) : leafUnits.length === 0 ? (
                <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">No blocks yet.</p>
              ) : (
                <ScrollTable>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{crop.unit_label || "Block"}</TableHead>
                        <TableHead>Planted on</TableHead>
                        <TableHead>As of</TableHead>
                        <TableHead className="text-right">Setup cost</TableHead>
                        <TableHead className="text-right">Running costs</TableHead>
                        <TableHead className="text-right">Value recovered</TableHead>
                        <TableHead className="w-20" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {leafUnits.map((u) => (
                        <BalanceRow key={`${u.name}:${balanceOf.get(u.name)?.as_of_date ?? ""}`} unit={u.name} saved={balanceOf.get(u.name)} onSave={saveBalance} />
                      ))}
                    </TableBody>
                  </Table>
                </ScrollTable>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {adding && (
        <AddCostDialog
          crop={crop.name}
          farm={farm}
          units={units}
          activities={activities}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            toast("Cost saved.", "ok");
            void load();
          }}
        />
      )}
    </PageShell>
  );
}
