import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { AccentScope, Chip } from "@/components/avocado/calendar-grid";
import { dayMonth } from "@/components/avocado/calendar-format";
import { MonitorChart } from "@/components/avocado/dm-monitor-chart";
import { AddReadingDialog, TagFruitDialog } from "@/components/avocado/dm-monitor-dialogs";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { Bar, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { ToolbarButton } from "@/components/ToolbarButton";
import { TogglePill } from "@/components/TogglePill";
import { useToast } from "@/components/Toast";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import {
  deleteFruitReading,
  getMonitor,
  updateFruitTag,
  type FruitTag,
  type Monitor,
  type Projection,
  type TagStatus,
} from "@/lib/dmmonitor-api";
import { cn } from "@/lib/utils";

type Scope = "block" | "tree" | "fruit";
const SCOPES: { id: Scope; label: string }[] = [
  { id: "block", label: "Block average" },
  { id: "tree", label: "Tree average" },
  { id: "fruit", label: "One fruit" },
];
const STATUSES: TagStatus[] = ["Active", "Harvested", "Lost"];
const pct = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(1)}%`);

export function projectionText(p: Projection | undefined, target: number | null): { value: string; hint: string } {
  if (!target) return { value: "—", hint: "no export target set on the crop" };
  switch (p?.state) {
    case "reached":
      return { value: p.date ? dayMonth(p.date) : "Reached", hint: `first at or over ${target}%` };
    case "rising":
      return { value: `~${dayMonth(p.date)}`, hint: `straight line through the last ${p.points} readings, ${(p.slope_per_week ?? 0).toFixed(1)} points a week` };
    case "flat":
      return { value: "Not gaining", hint: "the recent readings are flat or falling" };
    case "far":
      return { value: "Over 180 days", hint: "the straight line is too slow to call" };
    case "few":
      return { value: "—", hint: "needs two readings on different days" };
    default:
      return { value: "—", hint: "no readings yet" };
  }
}

export function DryMatterMonitoring() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [data, setData] = useState<Monitor | null>(null);
  const [loading, setLoading] = useState(true);
  const [farm, setFarm] = useState("");
  const [block, setBlock] = useState("");
  const [showClosed, setShowClosed] = useState(false);
  const [scope, setScope] = useState<Scope>("block");
  const [item, setItem] = useState("");
  const [tagging, setTagging] = useState(false);
  const [reading, setReading] = useState<{ tag: FruitTag | null } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getMonitor(crop.name);
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as Monitor);
  }, [crop.name, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const farms = useMemo(() => [...new Set((data?.blocks ?? []).map((b) => b.farm).filter((f): f is string => !!f))], [data]);
  const blockOptions = useMemo(() => (data?.blocks ?? []).filter((b) => !farm || b.farm === farm).map((b) => b.unit), [data, farm]);
  const tags = useMemo(
    () => (data?.tags ?? []).filter((t) => (!farm || t.farm === farm) && (!block || t.unit === block) && (showClosed || t.status === "Active")),
    [data, farm, block, showClosed],
  );

  const options = useMemo(() => {
    if (scope === "fruit") return tags.map((t) => ({ value: t.name, label: `${t.unit} · ${t.tree_label} · fruit ${t.fruit_tag}` }));
    if (scope === "tree") return [...new Set(tags.map((t) => `${t.unit}||${t.tree_label}`))].map((k) => ({ value: k, label: k.replace("||", " · ") }));
    return [...new Set(tags.map((t) => t.unit))].map((u) => ({ value: u, label: u }));
  }, [scope, tags]);
  const key = options.some((o) => o.value === item) ? item : options[0]?.value ?? "";
  const series = data && key ? data.series[scope][key] : undefined;
  const unitOfKey = scope === "block" ? key : scope === "tree" ? key.split("||")[0] : data?.tags.find((t) => t.name === key)?.unit ?? "";
  const selected = scope === "fruit" ? data?.tags.find((t) => t.name === key) ?? null : null;
  const target = data?.target_pct ?? null;
  const last = series?.points[series.points.length - 1];
  const proj = projectionText(series?.projection, target);
  const readyCount = tags.filter((t) => t.status === "Active" && t.ready).length;
  const activeCount = tags.filter((t) => t.status === "Active").length;
  const chartLabel = `Dry matter over time, ${options.find((o) => o.value === key)?.label ?? ""}`;

  const patch = (t: FruitTag) => setData((d) => (d ? { ...d, tags: d.tags.map((x) => (x.name === t.name ? t : x)) } : d));
  const refreshAfter = (t?: FruitTag) => {
    if (t) {
      setScope("fruit");
      setItem(t.name);
    }
    void load();
  };

  const setStatus = async (t: FruitTag, status: TagStatus) => {
    const r = await updateFruitTag(t.name, { status });
    if (isError(r)) return toast(r.error, "error");
    patch(r);
    void load();
  };
  const removeReading = async (t: FruitTag, row: string) => {
    const r = await deleteFruitReading(t.name, row);
    if (isError(r)) return toast(r.error, "error");
    toast("Reading removed.");
    refreshAfter();
  };

  return (
    <PageShell
      title={viewLabel("dry-matter-monitoring", crop)}
      eyebrow={crop.name}
      description={
        data
          ? `Tagged fruit measured over time · export target ${data.target_pct ?? "not set"}%${data.max_pct ? `, max ${data.max_pct}%` : ""} · a reading with both methods counts as their average`
          : undefined
      }
      actions={
        <>
          <FilterSelect label="Farm" value={farm} onChange={(v) => { setFarm(v); setBlock(""); }} options={farms} allLabel="All farms" />
          <FilterSelect label="Block" value={block} onChange={setBlock} options={blockOptions} allLabel="All blocks" />
          <TogglePill pressed={showClosed} onPressedChange={setShowClosed}>Harvested and lost</TogglePill>
          <ClearFiltersPill active={!!farm || !!block} onClear={() => { setFarm(""); setBlock(""); }} />
          <RefreshButton onClick={load} loading={loading} label="the readings" />
          <ToolbarButton onClick={() => setReading({ tag: selected })} disabled={!data || !data.tags.length}>
            <Plus className="h-4 w-4" />
            Add a reading
          </ToolbarButton>
          <ToolbarButton onClick={() => setTagging(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Tag a fruit
          </ToolbarButton>
        </>
      }
    >
      <AccentScope accent={accent} className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard loading={first} label="Fruit being followed" value={data ? activeCount : "—"} hint={data ? `${tags.length} tagged in view` : ""} />
        <KpiCard loading={first} label="At or over target" value={data ? `${readyCount} of ${activeCount}` : "—"} hint={target ? `latest reading at ${target}% or more` : "no export target set"} tone={readyCount ? "good" : "default"} />
        <KpiCard loading={first} label="Latest, selection" value={pct(last?.dm_pct)} hint={last ? `${dayMonth(last.date)}${scope !== "fruit" ? `, ${last.fruit} fruit` : ""}` : "no readings yet"} />
        <KpiCard loading={first} label="Reaches target" value={proj.value} hint={proj.hint} />
      </AccentScope>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Dry matter over time</CardTitle>
            <CardDescription>
              Tree and block lines are weekly averages of their tagged fruit. The dotted projection is a straight line through the last few readings, not a forecast model.
            </CardDescription>
          </CardHeading>
          <div className="flex flex-wrap items-center gap-2">
            {SCOPES.map((s) => (
              <TogglePill key={s.id} pressed={scope === s.id} onPressedChange={() => setScope(s.id)}>{s.label}</TogglePill>
            ))}
            <FilterSelect aria-label="Chart subject" value={key} onChange={setItem} options={options} className="max-w-[260px]" />
          </div>
        </CardHeaderRow>
        <div className="px-5 pb-5">
          {first || !data ? (
            <Bar className="h-[320px] w-full" />
          ) : (
            <MonitorChart series={series} lab={data.lab[unitOfKey]} target={target} max={data.max_pct} accent={accent} label={chartLabel} />
          )}
        </div>
      </Card>

      {selected && (
        <Card className="mt-4 overflow-hidden" data-testid="dm-fruit-panel">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>{selected.tree_label} · fruit {selected.fruit_tag}</CardTitle>
              <CardDescription>{selected.unit}{selected.variety ? ` · ${selected.variety}` : ""} · tagged {selected.tagged_on ? dayMonth(selected.tagged_on) : "—"}{selected.notes ? ` · ${selected.notes}` : ""}</CardDescription>
            </CardHeading>
            <div className="flex items-center gap-2">
              {STATUSES.map((s) => (
                <TogglePill key={s} pressed={selected.status === s} onPressedChange={() => selected.status !== s && void setStatus(selected, s)}>{s}</TogglePill>
              ))}
              <ToolbarButton onClick={() => setReading({ tag: selected })}><Plus className="h-4 w-4" /> Reading</ToolbarButton>
            </div>
          </CardHeaderRow>
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Date</th>
                  <th className={TH}>Method</th>
                  <th className={THR}>Fresh g</th>
                  <th className={THR}>Dish g</th>
                  <th className={THR}>Dry g</th>
                  <th className={THR}>Microwave</th>
                  <th className={THR}>Machine</th>
                  <th className={THR}>Dry matter</th>
                  <th className={TH}>Recorded by</th>
                  <th className={TH}><span className="sr-only">Remove</span></th>
                </tr>
              </thead>
              <tbody>
                {selected.readings.length ? (
                  [...selected.readings].reverse().map((r) => (
                    <tr key={r.name} className={BODY_ROW}>
                      <td className={cn(TD, "font-semibold")}>{dayMonth(r.reading_date)}</td>
                      <td className={TD}>{r.method}{r.instrument ? ` · ${r.instrument}` : ""}</td>
                      <td className={TDR}>{r.fresh_g ?? "—"}</td>
                      <td className={TDR}>{r.dish_g || "—"}</td>
                      <td className={TDR}>{r.dry_g ?? "—"}</td>
                      <td className={TDR}>{pct(r.microwave_pct)}</td>
                      <td className={TDR}>{pct(r.machine_pct)}</td>
                      <td className={cn(TDR, "font-semibold")}>{pct(r.dm_pct)}</td>
                      <td className={cn(TD, "text-[var(--sd-muted)]")}>{r.recorded_by ?? "—"}</td>
                      <td className={TD}>
                        <button type="button" aria-label={`Remove the ${r.reading_date} reading`} onClick={() => void removeReading(selected, r.name)} className="text-[var(--sd-quiet)] hover:text-[var(--sd-data-red)]">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan={10} className="px-5 py-6 text-center text-[var(--sd-quiet)]">No readings yet.</td></tr>
                )}
              </tbody>
            </table>
          </ScrollTable>
        </Card>
      )}

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Tagged fruit</CardTitle>
            <CardDescription>Choose a row to draw that fruit and see its readings.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="px-5 pb-6"><Bar className="h-10 w-full" /></div>
        ) : tags.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]" data-testid="dm-tags">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Block</th>
                  <th className={TH}>Tree</th>
                  <th className={TH}>Fruit</th>
                  <th className={TH}>Tagged</th>
                  <th className={THR}>Readings</th>
                  <th className={TH}>Last</th>
                  <th className={THR}>Latest dry matter</th>
                  <th className={TH}>Status</th>
                </tr>
              </thead>
              <tbody>
                {tags.map((t) => (
                  <tr key={t.name} className={cn(BODY_ROW, "cursor-pointer", scope === "fruit" && key === t.name && "bg-[var(--sd-bg-soft)]")} onClick={() => { setScope("fruit"); setItem(t.name); }}>
                    <td className={TD}>{t.unit}</td>
                    <td className={cn(TD, "font-semibold")}>{t.tree_label}</td>
                    <td className={TD}>{t.fruit_tag}</td>
                    <td className={TD}>{t.tagged_on ? dayMonth(t.tagged_on) : "—"}</td>
                    <td className={TDR}>{t.readings.length}</td>
                    <td className={TD}>{t.latest_on ? dayMonth(t.latest_on) : "—"}</td>
                    <td className={cn(TDR, "font-semibold")}>{pct(t.latest_pct)}</td>
                    <td className={TD}>
                      <Chip className={t.status !== "Active" ? "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]" : t.ready ? "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]" : "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]"}>
                        {t.status !== "Active" ? t.status : t.ready ? "At target" : "Below target"}
                      </Chip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">
            No tagged fruit yet. Use Tag a fruit to pick a fruit on a tree and start following it.
          </p>
        )}
      </Card>

      {data && <TagFruitDialog open={tagging} onOpenChange={setTagging} monitor={data} defaultUnit={block} onSaved={refreshAfter} />}
      {data && <AddReadingDialog open={!!reading} onOpenChange={(o) => !o && setReading(null)} monitor={data} tag={reading?.tag ?? null} onSaved={refreshAfter} />}
    </PageShell>
  );
}
