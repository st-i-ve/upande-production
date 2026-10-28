import { useEffect, useState } from "react";
import { useToast } from "@/components/Toast";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ToolbarButton } from "@/components/ToolbarButton";
import { saveSeasonBudget, type Budget, type EstimateVsDelivered, type PlantingYearRow, type VsBudget } from "@/lib/avocado-api";
import { isError } from "@/lib/frappe";
import { kes, qty } from "@/lib/format";
import { EmptyNote, Fig, FigRow, SectionCard, ShareBar, pct1, signedTonnes, tonnes } from "./forecast-ui";

export const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

// -- Season budget -------------------------------------------------------------------

export function BudgetDialog({
  budget,
  open,
  onOpenChange,
  onSaved,
}: {
  budget: Budget;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [kg, setKg] = useState<Record<string, string>>({});
  const [price, setPrice] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    const m: Record<string, string> = {};
    for (const x of budget.months) m[x.month] = String(x.budget_kg);
    setKg(m);
    setPrice(budget.budget_price_per_kg ? String(budget.budget_price_per_kg) : "");
    setNotes(budget.notes ?? "");
  }, [open, budget]);

  const months = MONTHS.map((month) => ({ month, budget_kg: Number(kg[month] || 0) })).filter((m) => m.budget_kg > 0);
  const total = months.reduce((s, m) => s + m.budget_kg, 0);

  async function save() {
    setBusy(true);
    const r = await saveSeasonBudget({
      season: budget.season,
      months,
      budget_price_per_kg: price ? Number(price) : undefined,
      notes: notes.trim() || undefined,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`Budget for ${budget.season} saved.`);
    onOpenChange(false);
    onSaved();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Season budget {budget.season}</DialogTitle>
          <DialogDescription>Kilograms budgeted for each month. The season total is their sum.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {MONTHS.map((m) => (
            <div key={m} className="flex flex-col gap-1.5">
              <Label htmlFor={`bm-${m}`}>{m}</Label>
              <Input
                id={`bm-${m}`}
                type="number"
                min={0}
                inputMode="numeric"
                value={kg[m] ?? ""}
                placeholder="0"
                onChange={(e) => setKg((p) => ({ ...p, [m]: e.target.value }))}
                className="tabular-nums"
              />
            </div>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="bm-price">Budgeted price (KES / kg)</Label>
            <Input id="bm-price" type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)} className="tabular-nums" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="bm-notes">Notes</Label>
            <Input id="bm-notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-[13px] text-[var(--sd-muted)]">Total {tonnes(total)}</span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
              Cancel
            </Button>
            <Button onClick={() => void save()} disabled={busy || total <= 0}>
              {busy ? "Saving…" : "Save budget"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function SeasonBudgetCard({
  budget,
  forecastKg,
  vsBudget,
  modeLabel,
  canEdit,
  onSaved,
}: {
  budget: Budget;
  forecastKg: number;
  vsBudget: VsBudget | null;
  modeLabel: string;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const peak = Math.max(1, ...budget.months.map((m) => m.budget_kg));
  const whole = modeLabel === "Manual";
  const delivered = vsBudget?.delivered_kg ?? 0;
  const onTrees = vsBudget?.on_trees_kg ?? forecastKg;
  const outturn = vsBudget?.outturn_kg ?? forecastKg;
  const diff = vsBudget?.diff_kg ?? outturn - (budget.budget_kg ?? 0);
  const pctOfBudget = vsBudget?.pct_of_budget ?? null;
  const edit = canEdit ? (
    <ToolbarButton onClick={() => setOpen(true)}>{budget.set ? "Edit budget" : "Set budget"}</ToolbarButton>
  ) : undefined;
  return (
    <SectionCard
      testId="forecast-budget"
      title="Season budget"
      description="What was budgeted for this season, set once by whoever planned it, next to whichever forecast is showing above."
      tools={edit}
    >
      {!budget.set ? (
        <EmptyNote>No budget has been set for {budget.season} yet.{canEdit ? " Use Set budget to add monthly figures." : ""}</EmptyNote>
      ) : (
        <div className="flex flex-col gap-5">
          <FigRow>
            <Fig label="Budget" value={tonnes(budget.budget_kg)} hint={`${budget.season} · ${budget.crop}${budget.set_by ? ` · set by ${budget.set_by}` : ""}`} />
            {whole ? (
              <Fig label={`${modeLabel} forecast`} value={tonnes(outturn)} hint="typed for the whole season, so compared as it stands" />
            ) : (
              <>
                <Fig label="Delivered so far" value={tonnes(delivered)} hint="harvested this season" />
                <Fig label="Still on the trees" value={tonnes(onTrees)} hint={`${modeLabel.toLowerCase()} forecast, to come`} />
              </>
            )}
            <Fig
              label="Season outturn"
              value={tonnes(outturn)}
              hint={whole ? "typed forecast" : `${tonnes(delivered)} delivered + ${tonnes(onTrees)} forecast`}
            />
            <Fig
              label="Vs budget"
              value={signedTonnes(diff)}
              tone={diff >= 0 ? "good" : "bad"}
              hint={`${diff >= 0 ? "over" : "under"} budget${pctOfBudget != null ? ` · outturn is ${pct1(pctOfBudget)} of budget` : ""}`}
            />
            <Fig
              label="Budget value"
              value={budget.budget_value ? kes(budget.budget_value) : "—"}
              hint={budget.budget_price_per_kg ? `at KES ${qty(budget.budget_price_per_kg)} / kg budgeted` : "no price was budgeted"}
            />
          </FigRow>
          {budget.months.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className={THEAD_ROW}>
                    <th className={TH}>Month</th>
                    <th className={THR}>Budget</th>
                    <th className={THR} title="Harvest-log kilograms for past months, scheduled forecast for the rest">Delivered / forecast</th>
                    <th className={THR}>Of budget</th>
                    <th className={TH}>Share of peak</th>
                    <th className={THR}>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {budget.months.map((m) => (
                    <tr key={m.month} className={BODY_ROW}>
                      <td className={`${TD} font-medium`}>{m.month}</td>
                      <td className={TDR}>{qty(m.budget_kg)} kg</td>
                      <td className={TDR}>
                        {m.delivered_kg ? <span>{qty(m.delivered_kg)} <span className="text-[var(--sd-quiet)]">delivered</span></span> : null}
                        {m.delivered_kg && m.forecast_kg ? " + " : null}
                        {m.forecast_kg ? <span>{qty(m.forecast_kg)} <span className="text-[var(--sd-quiet)]">forecast</span></span> : null}
                        {!m.delivered_kg && !m.forecast_kg ? "—" : null}
                      </td>
                      <td className={TDR}>{m.budget_kg > 0 && (m.delivered_kg || m.forecast_kg) ? pct1((((m.delivered_kg ?? 0) + (m.forecast_kg ?? 0)) / m.budget_kg) * 100) : "—"}</td>
                      <td className={TD}>
                        <div className="flex items-center gap-3">
                          <ShareBar pct={(m.budget_kg / peak) * 100} className="w-40" />
                          <span className="tabular-nums text-[var(--sd-quiet)]">{pct1(m.share_of_peak_pct)}</span>
                        </div>
                      </td>
                      <td className={TDR}>{m.budget_value ? qty(m.budget_value) : "—"}</td>
                    </tr>
                  ))}
                  <tr className="font-semibold">
                    <td className={TD}>Total</td>
                    <td className={TDR}>{qty(budget.months_total_kg ?? budget.budget_kg)} kg</td>
                    <td className={TDR}>{qty(budget.months.reduce((a, m) => a + (m.delivered_kg ?? 0), 0))} + {qty(budget.months.reduce((a, m) => a + (m.forecast_kg ?? 0), 0))}</td>
                    <td className={TD} />
                    <td className={TD} />
                    <td className={TDR}>{budget.budget_value ? qty(budget.budget_value) : "—"}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyNote>
              No months have been broken out yet — the total above is {budget.budget_kg ? "typed as one figure" : "empty"}. Add monthly rows for the month-by-month view.
            </EmptyNote>
          )}
          {budget.notes && <p className="text-[13px] text-[var(--sd-muted)]">{budget.notes}</p>}
        </div>
      )}
      <BudgetDialog budget={budget} open={open} onOpenChange={setOpen} onSaved={onSaved} />
    </SectionCard>
  );
}

// -- Estimate vs delivered -------------------------------------------------------------

export function EstimateCard({ e }: { e: EstimateVsDelivered }) {
  const none = e.basis === "none" || e.delivered_kg <= 0;
  return (
    <SectionCard
      testId="forecast-estimate"
      title="Estimate vs delivered"
      description="What the estate said each block would give, next to what it delivered. Only blocks carrying both an estimate and a harvest are scored."
    >
      {none ? (
        <EmptyNote>
          No harvest has been recorded against these estimates yet.{" "}
          {e.estimated_kg > 0 ? (
            <>
              Estimate <b>{tonnes(e.estimated_kg)}</b> across <b>{e.blocks_estimated}</b> {e.blocks_estimated === 1 ? "block" : "blocks"}.
            </>
          ) : (
            "No block carries a season estimate either."
          )}
        </EmptyNote>
      ) : (
        <div className="flex flex-col gap-5">
          <FigRow>
            <Fig label="Delivered" value={tonnes(e.delivered_kg)} hint={`${qty(e.delivered_kg)} kg over ${e.blocks_delivered} ${e.blocks_delivered === 1 ? "block" : "blocks"} · ${e.season} ${e.crop}`} />
            <Fig
              label="Against estimate"
              value={signedTonnes(e.diff_kg ?? 0)}
              tone={(e.diff_kg ?? 0) >= 0 ? "good" : "bad"}
              hint={`${(e.diff_kg ?? 0) >= 0 ? "more than estimated" : "short of estimate"}${e.diff_pct != null ? ` · ${pct1(Math.abs(e.diff_pct))}` : ""}`}
            />
            <Fig label="Performance" value={pct1(e.performance_pct)} hint={`estimate was ${tonnes(e.estimated_kg)} over ${e.blocks_estimated} ${e.blocks_estimated === 1 ? "block" : "blocks"}`} />
            {e.best && <Fig label="Best block" value={e.best.block} tone="good" hint={`${pct1(e.best.pct_of_estimate)} of its estimate${e.best.farm ? ` · ${e.best.farm}` : ""}`} />}
            {e.weakest && (
              <Fig
                label="Weakest block"
                value={e.weakest.block}
                tone={(e.weakest.pct_of_estimate ?? 100) < 100 ? "bad" : undefined}
                hint={`${pct1(e.weakest.pct_of_estimate)} of its estimate${e.weakest.farm ? ` · ${e.weakest.farm}` : ""}`}
              />
            )}
          </FigRow>
          {e.note && <p className="text-[13px] text-[var(--sd-muted)]">{e.note}</p>}
          {e.rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className={THEAD_ROW}>
                    <th className={TH}>Block</th>
                    <th className={THR}>Estimate</th>
                    <th className={THR}>Delivered</th>
                    <th className={TH}>Of estimate</th>
                  </tr>
                </thead>
                <tbody>
                  {e.rows.map((r) => (
                    <tr key={r.block} className={BODY_ROW}>
                      <td className={`${TD} font-medium`}>{r.block}</td>
                      <td className={TDR}>{tonnes(r.estimated_kg)}</td>
                      <td className={TDR}>{tonnes(r.delivered_kg)}</td>
                      <td className={TD}>
                        <div className="flex items-center gap-3">
                          <ShareBar pct={Math.min(100, r.pct_of_estimate ?? 0)} className="w-32" />
                          <span className="tabular-nums">{pct1(r.pct_of_estimate)}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-[13px] text-[var(--sd-muted)]" title="Either the fruit was never picked, or the harvest went in under another block">
            {e.waiting.length ? (
              <>
                <b>Estimated but never harvested: {e.waiting.length} {e.waiting.length === 1 ? "block" : "blocks"}.</b>{" "}
                {e.waiting.slice(0, 8).map((w) => `${w.block} (${tonnes(w.estimated_kg)})`).join(" · ")}
                {e.waiting.length > 8 ? ` and ${e.waiting.length - 8} more` : ""}
              </>
            ) : e.basis === "block" ? (
              "Every block with an estimate has a harvest against it."
            ) : (
              <>
                <b>These are whole-estate totals.</b> No block can be scored.
              </>
            )}
          </p>
        </div>
      )}
    </SectionCard>
  );
}

// -- By planting year --------------------------------------------------------------------

export function PlantingYearCard({ rows }: { rows: PlantingYearRow[] }) {
  const withHarvest = rows.filter((r) => r.delivered_kg > 0);
  return (
    <SectionCard
      testId="forecast-years"
      title="By planting year"
      description="The same comparison grouped by planting year. Young blocks and old blocks miss their estimate for different reasons."
    >
      {!withHarvest.length ? (
        <EmptyNote>Nothing to group — no harvest has been recorded against a block estimate.</EmptyNote>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className={THEAD_ROW}>
                <th className={TH}>Planted</th>
                <th className={THR}>Blocks picked</th>
                <th className={THR}>Estimate</th>
                <th className={THR}>Delivered</th>
                <th className={THR}>Of estimate</th>
                <th className={TH} title="Scaled to the strongest year. A year nobody harvested is left blank.">Vs best year</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={String(r.planting_year)} className={BODY_ROW}>
                  <td className={`${TD} font-medium`}>{r.planting_year ?? "Unknown"}</td>
                  <td className={TDR}>{r.blocks_picked} of {r.blocks}</td>
                  <td className={TDR}>{tonnes(r.estimated_kg)}</td>
                  <td className={TDR}>{tonnes(r.delivered_kg)}</td>
                  <td className={TDR}>{pct1(r.pct_of_estimate)}</td>
                  <td className={TD}>
                    {r.vs_best_year_pct != null ? (
                      <div className="flex items-center gap-3">
                        <ShareBar pct={r.vs_best_year_pct} className="w-28" />
                        <span className="tabular-nums text-[var(--sd-quiet)]">{pct1(r.vs_best_year_pct)}</span>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}
