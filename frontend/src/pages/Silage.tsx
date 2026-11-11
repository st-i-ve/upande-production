import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { CycleDialog, NewCycleDialog, StatusChip } from "@/components/silage/silage-dialogs";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { Bar, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { useToast } from "@/components/Toast";
import { ToolbarButton } from "@/components/ToolbarButton";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { kes, qty, shortDate, trimQty } from "@/lib/format";
import { isError } from "@/lib/frappe";
import { openCount, perKgLabel, perUnitLabel, pitTotals } from "@/lib/silage";
import { getSilagePage, type SilagePage } from "@/lib/silage-api";

/**
 * Silage: cycles of forage grown, chopped and ensiled, what each has cost so far, what a kilo of
 * silage costs, and what is in the pits. Farm-wide: every silage cycle, whichever crop page it is
 * opened from. Livestock draws the silage from the pit at the cost the closed cycle set.
 */
export function Silage() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [data, setData] = useState<SilagePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [openName, setOpenName] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getSilagePage(status || undefined);
    setLoading(false);
    if (isError(r)) return void toast(r.error, "error");
    setData(r as SilagePage);
  }, [status, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const cycles = data?.cycles ?? [];
  const pits = pitTotals(data?.pit_stock ?? []);
  const s = data?.summary;

  return (
    <PageShell
      title={viewLabel("silage", crop)}
      eyebrow={crop.name}
      description="A silage cycle is one crop of forage on one field. Inputs issued from stock, machine diesel and labour add up to its cost; closing it receives the silage into the pit at that cost per kilo."
      actions={
        <>
          <FilterSelect label="Status" value={status} onChange={setStatus} options={data?.options.statuses ?? []} allLabel="Any status" />
          <ClearFiltersPill active={!!status} onClear={() => setStatus("")} />
          <RefreshButton onClick={load} loading={loading} label="the silage cycles" />
          {data?.can_edit && (
            <ToolbarButton onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              New cycle
            </ToolbarButton>
          )}
        </>
      }
    >
      <KpiGrid cols={4}>
        <KpiCard loading={first} label="Open cycles" value={data ? openCount(cycles) : "—"} hint={`${cycles.length} listed`} />
        <KpiCard loading={first} label="Cost per kg" value={perKgLabel(s?.cost_per_kg)} tone="accent"
          hint={s ? `${qty(s.ensiled_kg)} kg ensiled in the last 12 months` : undefined} />
        <KpiCard loading={first} label="Silage cost" value={s ? kes(s.cost.total) : "—"}
          hint={s ? `${s.cycles} cycle(s) that ran in the last 12 months` : undefined} />
        <KpiCard loading={first} label="In the pits" value={data ? `${qty(pits.kg)} kg` : "—"}
          hint={data ? `${kes(pits.value)} at stock value · ${pits.pits} pit(s)` : undefined} />
      </KpiGrid>

      <Card className="overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Silage cycles</CardTitle>
            <CardDescription>Open cycles show their running cost; closed ones the cost their silage was received at. Click a cycle to work on it.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div>
        ) : cycles.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Cycle</th>
                  <th className={TH}>Field</th>
                  <th className={TH}>Started</th>
                  <th className={TH}>Status</th>
                  <th className={THR}>Inputs</th>
                  <th className={THR}>Diesel</th>
                  <th className={THR}>Labour</th>
                  <th className={THR}>Total</th>
                  <th className={THR}>Ensiled</th>
                  <th className={THR}>Cost per kg</th>
                </tr>
              </thead>
              <tbody>
                {cycles.map((c) => {
                  const labour = c.cost.labour == null ? null : c.cost.labour + (c.cost.casual_labour ?? 0);
                  return (
                    <tr key={c.name} className={`${BODY_ROW} cursor-pointer hover:bg-[var(--sd-bg-soft)]`} onClick={() => setOpenName(c.name)}
                      data-testid={`silage-row-${c.name}`}>
                      <td className={`${TD} font-semibold`}>{c.title}<div className="text-[11.5px] font-normal text-[var(--sd-quiet)]">{c.crop} · {c.name}</div></td>
                      <td className={TD}>{c.production_unit ?? "—"}</td>
                      <td className={TD}>{shortDate(c.start_date)}</td>
                      <td className={TD}><StatusChip status={c.status} /></td>
                      <td className={TDR}>{kes(c.cost.inputs)}</td>
                      <td className={TDR}>{kes(c.cost.diesel)}</td>
                      <td className={TDR}>{kes(labour)}</td>
                      <td className={`${TDR} font-semibold`}>{kes(c.cost.total)}</td>
                      <td className={TDR}>{c.ensiled_kg > 0 ? `${qty(c.ensiled_kg)} kg` : "—"}</td>
                      <td className={TDR}>{perKgLabel(c.cost_per_kg)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">
            {status ? "No silage cycle has this status." : "No silage cycle yet. Use New cycle to start one."}
          </p>
        )}
      </Card>

      <Card className="overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Pit stock</CardTitle>
            <CardDescription>Silage on hand in each pit, from the stock ledger, at the value livestock draws it at.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div>
        ) : data.pit_stock.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Pit</th>
                  <th className={TH}>Silage</th>
                  <th className={THR}>On hand</th>
                  <th className={THR}>Rate</th>
                  <th className={THR}>Value</th>
                </tr>
              </thead>
              <tbody>
                {data.pit_stock.map((r) => (
                  <tr key={`${r.item_code}|${r.warehouse}`} className={BODY_ROW}>
                    <td className={`${TD} font-semibold`}>{r.warehouse}</td>
                    <td className={TD}>{r.item_name}</td>
                    <td className={TDR}>{trimQty(r.qty)} {r.stock_uom}</td>
                    <td className={TDR}>{r.qty > 0 ? perUnitLabel(r.valuation_rate, r.stock_uom ?? "Kg") : "—"}</td>
                    <td className={TDR}>{kes(r.stock_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">No silage in a pit yet. A closed cycle receives its silage into its pit.</p>
        )}
      </Card>

      {data && (
        <NewCycleDialog open={creating} onOpenChange={setCreating} options={data.options}
          onSaved={(name) => { void load(); setOpenName(name); }} />
      )}
      {data && (
        <CycleDialog name={openName} onOpenChange={(o) => !o && setOpenName(null)} options={data.options}
          canEdit={data.can_edit} canClose={data.can_close} onChanged={load} />
      )}
    </PageShell>
  );
}
