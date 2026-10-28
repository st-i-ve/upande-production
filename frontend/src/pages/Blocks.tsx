import { StageChip } from "@/components/varieties/StageChip";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { TableRowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { SearchInput } from "@/components/SearchInput";
import { TogglePill } from "@/components/TogglePill";
import { useToast } from "@/components/Toast";
import { StatusPill } from "@/components/blocks/StatusPill";
import { UnitDrawer } from "@/components/blocks/UnitDrawer";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import { getOverview, listUnits, type OverviewBlock, type UnitRow } from "@/lib/api";
import { cropUsesCycles, pluralise, useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { ha, qty } from "@/lib/format";
import { cn, matchesQuery } from "@/lib/utils";

interface Node {
  unit: UnitRow;
  depth: number;
}

/** Depth-first flatten: parents first, children indented. `keep` limits the
 *  rows to a set (matches and their ancestors); collapsed groups skip their
 *  children unless a filter is active. */
function flatten(units: UnitRow[], collapsed: Set<string>, keep: Set<string> | null): Node[] {
  const names = new Set(units.map((u) => u.name));
  const kids = new Map<string | null, UnitRow[]>();
  for (const u of units) {
    const key = u.parent && names.has(u.parent) ? u.parent : null;
    kids.set(key, [...(kids.get(key) ?? []), u]);
  }
  const out: Node[] = [];
  const walk = (key: string | null, depth: number, seen: Set<string>) => {
    for (const u of kids.get(key) ?? []) {
      if (seen.has(u.name)) continue;
      if (keep && !keep.has(u.name)) continue;
      out.push({ unit: u, depth });
      if (keep || !collapsed.has(u.name)) walk(u.name, depth + 1, new Set(seen).add(u.name));
    }
  };
  walk(null, 0, new Set());
  return out;
}

/** The matches plus every ancestor, so a hit still shows where it sits. */
function withAncestors(units: UnitRow[], hits: UnitRow[]): Set<string> {
  const byName = new Map(units.map((u) => [u.name, u]));
  const keep = new Set<string>();
  for (const h of hits) {
    let cur: UnitRow | undefined = h;
    while (cur && !keep.has(cur.name)) {
      keep.add(cur.name);
      cur = cur.parent ? byName.get(cur.parent) : undefined;
    }
  }
  return keep;
}

export function Blocks() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [units, setUnits] = useState<UnitRow[] | null>(null);
  const [stats, setStats] = useState<Map<string, OverviewBlock>>(new Map());
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [cycleOnly, setCycleOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    // Season totals per unit are a bonus column set; the list never waits on them.
    void getOverview(crop.name)
      .then((o) => {
        if (o && !isError(o)) setStats(new Map(o.blocks.map((b) => [b.unit, b])));
      })
      .catch(() => {});
    const r = await listUnits(crop.name);
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setUnits((r as { units: UnitRow[] }).units);
  }, [crop.name, toast]);

  useEffect(() => {
    setUnits(null);
    setOpen(null);
    setStats(new Map());
    void load();
  }, [load]);

  const dirty = !!query || !!status || !!type || cycleOnly;
  const rows = useMemo(() => {
    const all = units ?? [];
    if (!dirty) return flatten(all, collapsed, null);
    const hits = all.filter(
      (u) =>
        matchesQuery(`${u.name} ${u.item ?? ""} ${u.variety ?? ""} ${u.current_stage ?? ""} ${usesCycles ? u.current_cycle ?? "" : ""}`, query) &&
        (!status || u.status === status) &&
        (!type || u.unit_type === type) &&
        (!usesCycles || !cycleOnly || !!u.current_cycle),
    );
    return flatten(all, collapsed, withAncestors(all, hits));
  }, [units, collapsed, dirty, query, status, type, cycleOnly]);

  const waiting = firstLoad(loading, !!units);
  const plural = pluralise(crop.unit_label);
  const statuses = useMemo(() => [...new Set((units ?? []).map((u) => u.status).filter(Boolean))].sort(), [units]);
  const types = useMemo(() => [...new Set((units ?? []).map((u) => u.unit_type).filter(Boolean))].sort(), [units]);

  // Groups hold the area of their children already; count leaves only.
  const leaves = useMemo(() => (units ?? []).filter((u) => !u.is_group), [units]);
  const totalArea = leaves.reduce((s, u) => s + (u.area_ha || 0), 0);
  const usesCycles = cropUsesCycles(crop);
  const withCycle = leaves.filter((u) => u.current_cycle).length;
  const maxArea = Math.max(1, ...(units ?? []).map((u) => u.area_ha || 0));
  const plants = leaves.reduce((s, u) => s + (u.plant_count || 0), 0);

  const toggle = (name: string) =>
    setCollapsed((s) => {
      const n = new Set(s);
      if (!n.delete(name)) n.add(name);
      return n;
    });

  const actions = (
    <>
      <SearchInput size="md" value={query} onChange={setQuery} placeholder={`Search ${plural.toLowerCase()}`} className="w-52" />
      <FilterSelect label="Status" value={status} options={statuses} onChange={setStatus} allLabel="All statuses" />
      {types.length > 1 && <FilterSelect label="Type" value={type} options={types} onChange={setType} allLabel="All types" />}
      {usesCycles && (
        <TogglePill pressed={cycleOnly} onPressedChange={setCycleOnly}>
          With active cycle
        </TogglePill>
      )}
      <ClearFiltersPill
        active={dirty}
        onClear={() => {
          setQuery("");
          setStatus("");
          setType("");
          setCycleOnly(false);
        }}
      />
      <RefreshButton onClick={load} loading={loading} label={`the ${plural.toLowerCase()}`} />
    </>
  );

  return (
    <PageShell
      title={viewLabel("blocks", crop)}
      eyebrow={crop.name}
      actions={actions}
      description={
        usesCycles
          ? `Every ${crop.unit_label.toLowerCase()} under ${crop.parent_unit_label.toLowerCase()}, with its current cycle. Open one for its rotation history and recent work.`
          : `Every ${crop.unit_label.toLowerCase()}, with its area, status and recent work. Open one for its latest activity.`
      }
    >
      <KpiGrid cols={usesCycles ? 4 : 3}>
        <KpiCard label={plural} value={units ? leaves.length : "—"} hint={units ? `${qty(units.length - leaves.length)} groups` : undefined} loading={waiting} />
        <KpiCard label="Total area" value={units ? `${ha(totalArea)} ha` : "—"} hint="across all units" loading={waiting} />
        {usesCycles && (
        <KpiCard
          label="With active cycle"
          value={units ? withCycle : "—"}
          hint={units ? `${leaves.length - withCycle} without a cycle` : undefined}
          tone={units && withCycle < leaves.length ? "warning" : "good"}
          loading={waiting}
        />
        )}
        <KpiCard label="Plants" value={units ? qty(plants) : "—"} hint="recorded plant count" loading={waiting} />
      </KpiGrid>

      <Panel
        className="mt-4"
        title={plural}
        hint={units ? `${qty(rows.length)} shown of ${qty(units.length)}` : "Loading…"}
        bodyClassName="px-3 pb-3"
      >
        {units && units.length === 0 ? (
          <EmptyNote>
            No {plural.toLowerCase()} recorded for {crop.name} yet.
          </EmptyNote>
        ) : (
          <ScrollTable tall>
            <table className="w-full min-w-[900px] text-[13px]">
              <thead>
                <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
                  <th className={TH}>{crop.unit_label}</th>
                  <th className={TH}>Type</th>
                  <th className={THR}>Area (ha)</th>
                  {usesCycles && <th className={TH}>Current cycle</th>}
                  <th className={TH}>Status</th>
                  <th className={THR}>Open tasks</th>
                  <th className={THR}>Harvest{crop.yield_uom ? ` (${crop.yield_uom})` : ""}</th>
                  <th className={TH}>Cost centre</th>
                </tr>
              </thead>
              <tbody>
                {waiting ? (
                  <TableRowsSkeleton cols={usesCycles ? 8 : 7} rows={7} />
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={usesCycles ? 8 : 7} className="px-3 py-6 text-center text-[13px] text-[var(--sd-muted)]">
                      Nothing matches these filters.
                    </td>
                  </tr>
                ) : (
                  rows.map(({ unit: u, depth }) => {
                    const group = !!u.is_group;
                    const s = stats.get(u.name);
                    return (
                      <tr
                        key={u.name}
                        className={cn(BODY_ROW, "cursor-pointer hover:bg-[var(--sd-bg-soft)]")}
                        onClick={() => setOpen(u.name)}
                      >
                        <td className={TD}>
                          <div className="flex items-center gap-1.5" style={{ paddingLeft: depth * 20 }}>
                            {group && !dirty ? (
                              <button
                                type="button"
                                aria-label={collapsed.has(u.name) ? `Expand ${u.name}` : `Collapse ${u.name}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggle(u.name);
                                }}
                                className="rounded p-0.5 text-[var(--sd-quiet)] hover:text-[var(--sd-ink)]"
                              >
                                {collapsed.has(u.name) ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                              </button>
                            ) : (
                              <span className="w-[22px]" />
                            )}
                            <span className={cn("text-[var(--sd-ink)]", group ? "font-semibold" : "font-medium")}>{u.name}</span>
                          </div>
                        </td>
                        <td className={cn(TD, "text-[var(--sd-muted)]")}>{u.unit_type}</td>
                        <td className={TDR}>
                          <div className="flex flex-col items-end gap-1">
                            {ha(u.area_ha)}
                            <span className="block h-1 w-14 overflow-hidden rounded-full bg-[var(--sd-bg-soft)]">
                              <span
                                className="block h-full rounded-full"
                                style={{ width: `${((u.area_ha || 0) / maxArea) * 100}%`, background: accent }}
                              />
                            </span>
                          </div>
                        </td>
                        {usesCycles && (
                        <td className={TD}>
                          {u.current_cycle ? (
                            <>
                              <div className="text-[var(--sd-ink)]">{u.variety || u.item || u.current_cycle}</div>
                              <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--sd-quiet)]">
                                {u.variety && u.item ? <span>{u.item} ·</span> : null}
                                <span>{u.current_cycle}</span>
                                <StageChip stage={u.current_stage} accent={accent} />
                              </div>
                            </>
                          ) : (
                            <span className="text-[var(--sd-quiet)]">—</span>
                          )}
                        </td>
                        )}
                        <td className={TD}>
                          <StatusPill status={u.status} />
                        </td>
                        <td className={cn(TDR, s?.tasks_open ? "text-[var(--sd-ink)]" : "text-[var(--sd-quiet)]")}>
                          {s ? qty(s.tasks_open) : "—"}
                        </td>
                        <td className={TDR}>{s ? qty(s.harvest_qty_season) : "—"}</td>
                        <td className={cn(TD, "tabular-nums text-[var(--sd-muted)]")}>{u.cost_center || "—"}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </ScrollTable>
        )}
      </Panel>

      {open && (
        <UnitDrawer
          name={open}
          unitLabel={crop.unit_label}
          canSeePay={crop.boot.can_see_pay}
          stats={stats.get(open)}
          uom={crop.yield_uom}
          usesCycles={usesCycles}
          onClose={() => setOpen(null)}
        />
      )}
    </PageShell>
  );
}
