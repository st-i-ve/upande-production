import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { PendingChip } from "@/components/plan/QtyBar";
import { rowDate } from "@/components/plan/fmt";
import { TargetBadge } from "@/components/casuallabourers/TargetBadge";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { SearchPicker } from "@/components/ui/search-picker";
import { Switch } from "@/components/ui/switch";
import { listOperations } from "@/lib/api";
import { isError, searchLink } from "@/lib/frappe";
import { formatUoms, kes, trimQty } from "@/lib/format";
import {
  addLabourers,
  getLabourerDetail,
  removeLabourer,
  saveLabourer,
  type LabourerDetail,
} from "@/lib/labourers-api";
import { cn } from "@/lib/utils";

const AXIS = { fontSize: 11, fill: "var(--sd-quiet)" };

interface OpInfo {
  name: string;
  operation_name: string;
  work_uom: string | null;
  daily_target: number | null;
  target_uom: string | null;
}

interface TargetRow {
  key: number;
  operation: string;
  target: string;
  uom: string;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

function HitChart({ detail, operation, accent }: { detail: LabourerDetail; operation: string; accent: string }) {
  const rows = detail.daily
    .filter((d) => d.operation === operation)
    .map((d) => ({ ...d, label: rowDate(d.date) }));
  const target = rows.find((r) => r.target)?.target ?? null;
  if (rows.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center rounded-xl bg-[var(--sd-bg-soft)] text-[12px] text-[var(--sd-quiet)]">
        No work recorded for this operation in the period
      </div>
    );
  }
  return (
    <div style={{ height: 220 }} data-testid="labourer-chart" role="img" aria-label="Quantity per day against the daily target">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--sd-line-soft)" vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={AXIS} interval="preserveStartEnd" />
          <YAxis width={40} tickLine={false} axisLine={false} tick={AXIS} />
          {target && (
            <ReferenceLine
              y={target}
              stroke="var(--sd-target)"
              strokeDasharray="4 3"
              label={{ value: `target ${trimQty(target)}`, position: "insideTopRight", fontSize: 10, fill: "var(--sd-target)" }}
            />
          )}
          <Tooltip
            cursor={{ fill: "var(--sd-bg-soft)" }}
            content={({ active, payload }) => {
              const r = active ? (payload?.[0]?.payload as (typeof rows)[number] | undefined) : undefined;
              if (!r) return null;
              return (
                <div className="rounded-lg bg-[var(--sd-card)] px-3 py-2 text-[12px] shadow-[var(--sd-shadow-3)]">
                  <div className="font-medium text-[var(--sd-ink)]">{r.label}</div>
                  <div className="tabular-nums text-[var(--sd-muted)]">
                    {trimQty(r.qty)} {r.uom ?? ""}
                    {r.target ? ` of ${trimQty(r.target)}` : ""}
                  </div>
                  {r.met != null && <div className="text-[var(--sd-muted)]">{r.met ? "Target met" : "Target not met"}</div>}
                </div>
              );
            }}
          />
          <Bar dataKey="qty" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {rows.map((r, i) => (
              <Cell key={i} fill={r.met === false ? "var(--sd-amber)" : accent} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** One casual labourer in a big modal: KPIs over the period, quantity against the daily target,
 *  per-operation figures, target overrides, roster settings and paid status. */
export function LabourerDialog({
  crop,
  employee,
  name,
  from,
  to,
  canPay,
  accent = "#3f7d3a",
  onClose,
  onChanged,
}: {
  crop: string;
  employee: string;
  name: string;
  from: string;
  to: string;
  canPay: boolean;
  accent?: string;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const toast = useToast();
  const [data, setData] = useState<LabourerDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const [ops, setOps] = useState<OpInfo[]>([]);
  const [people, setPeople] = useState<{ value: string; label: string }[]>([]);
  const [chartOp, setChartOp] = useState("");
  const [rows, setRows] = useState<TargetRow[]>([]);
  const [dirty, setDirty] = useState(false);
  const [crew, setCrew] = useState("");
  const [busy, setBusy] = useState(false);
  const [seq, setSeq] = useState(0);

  useEffect(() => {
    let live = true;
    setLoading(true);
    void getLabourerDetail(crop, employee, from, to).then((r) => {
      if (!live) return;
      setLoading(false);
      if (isError(r)) {
        setFailed(true);
        return;
      }
      const d = r as LabourerDetail;
      setFailed(false);
      setData(d);
      setCrew(d.crew ?? "");
      setRows(d.targets.map((t, i) => ({ key: i + 1, operation: t.operation, target: String(t.target), uom: t.uom ?? "" })));
      setSeq(d.targets.length);
      setDirty(false);
      setChartOp((cur) => (cur && d.by_operation.some((o) => o.operation === cur) ? cur : d.by_operation[0]?.operation ?? ""));
    });
    return () => {
      live = false;
    };
  }, [crop, employee, from, to, tick]);

  useEffect(() => {
    let live = true;
    void listOperations(crop).then((r) => {
      if (!live || isError(r)) return;
      setOps(
        ((r as { rows: Record<string, unknown>[] }).rows ?? []).map((o) => ({
          name: String(o.name),
          operation_name: String(o.operation_name ?? o.name),
          work_uom: (o.work_uom as string) || null,
          daily_target: o.daily_target ? Number(o.daily_target) : null,
          target_uom: (o.target_uom as string) || null,
        })),
      );
    });
    void searchLink("Employee", "", 200).then((r) =>
      live && setPeople((r ?? []).map((x) => ({ value: x.value, label: x.description ? `${x.description} (${x.value})` : x.value }))),
    );
    return () => {
      live = false;
    };
  }, [crop]);

  const opById = useMemo(() => new Map(ops.map((o) => [o.name, o])), [ops]);
  const reload = useCallback(() => {
    setTick((t) => t + 1);
    onChanged?.();
  }, [onChanged]);

  async function patch(p: Parameters<typeof saveLabourer>[1], done: string) {
    setBusy(true);
    const r = await saveLabourer(employee, p);
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(done);
    reload();
  }

  async function join() {
    setBusy(true);
    const r = await addLabourers([employee]);
    setBusy(false);
    if (isError(r)) toast(r.error, "error");
    else {
      toast(`${name} added to the roster.`);
      reload();
    }
  }

  async function remove() {
    const r = await removeLabourer(employee);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(r.removed ? `${name} removed from the roster.` : `${name} has work on record, so was made inactive instead.`);
    onChanged?.();
    if (r.removed) onClose();
    else setTick((t) => t + 1);
  }

  function saveTargets() {
    const bad = rows.find((r) => !r.operation || !(Number(r.target) > 0));
    if (bad) {
      toast("Each target needs an operation and a quantity above zero.", "error");
      return;
    }
    void patch(
      { targets: rows.map((r) => ({ operation: r.operation, daily_target: Number(r.target), uom: r.uom || null })) },
      "Daily targets saved.",
    );
  }

  const k = data?.kpis;
  const opOptions = (data?.by_operation ?? []).map((o) => ({ value: o.operation, label: `${o.operation_name}${o.uom ? ` (${o.uom})` : ""}` }));
  const hit = k?.hit_rate;
  const dirSet = (fn: () => void) => {
    fn();
    setDirty(true);
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-5xl" aria-describedby="lb-desc">
        <DialogHeader>
          <div className="flex flex-wrap items-center gap-3 pr-8">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[var(--sd-pistachio)] text-[14px] font-semibold">
              {initials(data?.employee_name || name)}
            </span>
            <div className="min-w-0 flex-1">
              <DialogTitle className="text-[22px] tracking-tight">{data?.employee_name || name}</DialogTitle>
              <DialogDescription id="lb-desc" className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                <span>
                  {[data?.designation, data?.department, employee].filter(Boolean).join(" · ")} · {rowDate(from)} to {rowDate(to)}
                </span>
                {data && data.pending_entries > 0 && <PendingChip>{data.pending_entries} awaiting approval</PendingChip>}
              </DialogDescription>
            </div>
            {data?.on_roster && (
              <label className="flex items-center gap-2 text-[13px] text-[var(--sd-muted)]">
                Active
                <Switch
                  aria-label="Active"
                  checked={!!data.active}
                  disabled={busy}
                  onCheckedChange={(v) => void patch({ active: v }, v ? "Marked active." : "Marked inactive.")}
                />
              </label>
            )}
            {data && !data.on_roster && (
              <Button size="sm" onClick={() => void join()} disabled={busy}>
                <Plus className="h-3.5 w-3.5" /> Add to roster
              </Button>
            )}
          </div>
        </DialogHeader>

        {loading && !data ? (
          <RowsSkeleton rows={8} />
        ) : failed || !data || !k ? (
          <p className="text-[13px] text-[var(--sd-muted)]">This person's work could not be loaded.</p>
        ) : (
          <>
            <KpiGrid cols={3}>
              <KpiCard label="Days worked" value={k.days_worked} hint={`${k.entries} entries`} />
              <KpiCard
                label="Target hit rate"
                value={hit == null ? "—" : `${hit}%`}
                hint={k.target_days ? `${k.met_days} of ${k.target_days} days met the target` : "no daily targets set"}
                tone={hit == null ? "default" : hit >= 80 ? "good" : hit >= 50 ? "warning" : "critical"}
              />
              <KpiCard
                label="Average vs target"
                value={k.avg_vs_target == null ? "—" : `${k.avg_vs_target}%`}
                hint="average day as a share of the target"
              />
              <KpiCard label="Quantity" value={formatUoms(k.qty_by_uom) || "—"} hint="per unit of measure, never added together" />
              {canPay && <KpiCard label="Pay value" value={kes(k.pay_value)} hint={`${kes(k.paid_value)} paid`} />}
              {canPay && (
                <KpiCard label="Unpaid" value={kes(k.unpaid_value)} hint="awaiting payroll" tone={k.unpaid_value ? "warning" : "good"} />
              )}
            </KpiGrid>

            <section className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-[13px] font-semibold text-[var(--sd-ink)]">Quantity per day against the target</h3>
                {opOptions.length > 0 && (
                  <Picker label="Operation" value={chartOp} onChange={setChartOp} options={opOptions} className="w-56" />
                )}
              </div>
              <HitChart detail={data} operation={chartOp} accent={accent} />
            </section>

            {data.by_operation.length > 0 && (
              <section className="flex flex-col gap-2">
                <h3 className="text-[13px] font-semibold text-[var(--sd-ink)]">By operation</h3>
                <div className="overflow-auto">
                  <table className="w-full min-w-[640px] text-[13px]">
                    <thead>
                      <tr className={THEAD_ROW}>
                        <th className={TH}>Operation</th>
                        <th className={THR}>Quantity</th>
                        <th className={THR}>Days</th>
                        <th className={THR}>Avg / day</th>
                        <th className={THR}>Daily target</th>
                        <th className={THR}>Hit rate</th>
                        {canPay && <th className={THR}>Pay</th>}
                        {canPay && <th className={THR}>Unpaid</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {data.by_operation.map((o) => (
                        <tr key={`${o.operation}-${o.uom}`} className={BODY_ROW}>
                          <td className={TD}>{o.operation_name}</td>
                          <td className={TDR}>
                            {trimQty(o.qty)} {o.uom ?? ""}
                          </td>
                          <td className={TDR}>{o.days}</td>
                          <td className={TDR}>{o.avg_per_day == null ? "—" : trimQty(o.avg_per_day)}</td>
                          <td className={TDR}>
                            {o.target ? (
                              <>
                                {trimQty(o.target)} {o.target_uom ?? ""}
                                {o.override && <span className="ml-1 text-[11px] text-[var(--sd-quiet)]">own</span>}
                              </>
                            ) : (
                              <span className="text-[var(--sd-quiet)]">—</span>
                            )}
                          </td>
                          <td className={TDR}>{o.hit_rate == null ? "—" : `${o.hit_rate}%`}</td>
                          {canPay && <td className={TDR}>{kes(o.pay_value)}</td>}
                          {canPay && <td className={TDR}>{kes(o.unpaid_value)}</td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {data.on_roster && (
              <section className="flex flex-col gap-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] p-4">
                <div>
                  <h3 className="text-[13px] font-semibold text-[var(--sd-ink)]">Daily targets for {data.employee_name}</h3>
                  <p className="text-[12px] text-[var(--sd-quiet)]">
                    An operation's default target applies unless you set one here. Targets are a yardstick: pay stays per unit of work.
                  </p>
                </div>
                {rows.map((r) => {
                  const d = opById.get(r.operation);
                  return (
                    <div key={r.key} className="flex flex-wrap items-center gap-2" data-testid="target-row">
                      <div className="w-56">
                        <Picker
                          label="Operation"
                          value={r.operation}
                          onChange={(v) => dirSet(() => setRows((all) => all.map((x) => (x.key === r.key ? { ...x, operation: v } : x))))}
                          options={ops.map((o) => ({ value: o.name, label: o.operation_name }))}
                          placeholder="Operation"
                        />
                      </div>
                      <Input
                        inputMode="decimal"
                        aria-label="Daily target"
                        className="w-24 tabular-nums"
                        value={r.target}
                        onChange={(e) => dirSet(() => setRows((all) => all.map((x) => (x.key === r.key ? { ...x, target: e.target.value } : x))))}
                      />
                      <span className="text-[12px] text-[var(--sd-muted)]">{d?.target_uom || d?.work_uom || ""} per day</span>
                      <span className="text-[12px] text-[var(--sd-quiet)]">
                        {d?.daily_target ? `default ${trimQty(d.daily_target)}` : "no default"}
                      </span>
                      <button
                        type="button"
                        aria-label="Remove target"
                        className="rounded-full p-1 text-[var(--sd-quiet)] hover:text-[var(--sd-sev-critical)]"
                        onClick={() => dirSet(() => setRows((all) => all.filter((x) => x.key !== r.key)))}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  );
                })}
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      dirSet(() => {
                        setSeq((s) => s + 1);
                        setRows((all) => [...all, { key: seq + 1, operation: "", target: "", uom: "" }]);
                      })
                    }
                  >
                    <Plus className="h-3.5 w-3.5" /> Add a target
                  </Button>
                  {dirty && (
                    <Button type="button" size="sm" onClick={saveTargets} disabled={busy}>
                      Save targets
                    </Button>
                  )}
                </div>

                <div className="grid gap-3 border-t border-[var(--sd-line)] pt-3 sm:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="lb-sup">Default supervisor</Label>
                    <SearchPicker
                      id="lb-sup"
                      label="Default supervisor"
                      value={data.supervisor ?? ""}
                      onChange={(v) => void patch({ supervisor: v }, "Supervisor saved.")}
                      placeholder="Choose a supervisor…"
                      options={people}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="lb-crew">Default crew</Label>
                    <div className="flex gap-2">
                      <Input id="lb-crew" value={crew} onChange={(e) => setCrew(e.target.value)} placeholder="e.g. Pruning crew A" />
                      {crew !== (data.crew ?? "") && (
                        <Button type="button" size="sm" className="self-center" onClick={() => void patch({ crew }, "Crew saved.")} disabled={busy}>
                          Save
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </section>
            )}

            <section className="flex flex-col gap-2">
              <h3 className="text-[13px] font-semibold text-[var(--sd-ink)]">Recent work</h3>
              {data.recent.length === 0 ? (
                <p className="text-[13px] text-[var(--sd-muted)]">No approved work in this period.</p>
              ) : (
                <div className="overflow-auto">
                  <table className="w-full min-w-[640px] text-[13px]">
                    <thead>
                      <tr className={THEAD_ROW}>
                        <th className={TH}>Date</th>
                        <th className={TH}>Operation</th>
                        <th className={TH}>Block</th>
                        <th className={THR}>Qty</th>
                        <th className={THR}>Day vs target</th>
                        {canPay && <th className={THR}>Pay</th>}
                        {canPay && <th className={TH}>Paid</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent.map((w) => (
                        <tr key={w.name} className={BODY_ROW}>
                          <td className={cn(TD, "tabular-nums")}>{rowDate(w.work_date)}</td>
                          <td className={TD}>{w.operation_name}</td>
                          <td className={TD}>{w.unit}</td>
                          <td className={TDR}>
                            {trimQty(w.qty)} {w.uom ?? ""}
                          </td>
                          <td className={TDR}>
                            <TargetBadge target={w.target} actual={w.day_qty} met={w.target_met} uom={w.target_uom} />
                          </td>
                          {canPay && <td className={TDR}>{kes(w.pay_value)}</td>}
                          {canPay && (
                            <td className={TD}>
                              <span
                                className={cn(
                                  "rounded-full px-2 py-0.5 text-[11.5px] font-medium",
                                  w.paid === "Paid"
                                    ? "bg-[var(--sd-pistachio)] text-[var(--sd-ink)]"
                                    : "bg-[var(--sd-amber-bg)] text-[var(--sd-amber)]",
                                )}
                                title={w.payroll_reference ? `Payroll ${w.payroll_reference}${w.paid_on ? ` on ${rowDate(w.paid_on)}` : ""}` : undefined}
                              >
                                {w.paid}
                              </span>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {data.on_roster && (
              <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={() => void remove()}>
                  <Trash2 className="h-3.5 w-3.5" /> Remove from roster
                </Button>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
