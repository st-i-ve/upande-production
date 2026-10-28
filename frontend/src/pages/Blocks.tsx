import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { RowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { useToast } from "@/components/Toast";
import { StatusPill } from "@/components/blocks/StatusPill";
import { UnitDrawer } from "@/components/blocks/UnitDrawer";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeaderRow,
  CardHeading,
  CardTitle,
  CardTools,
} from "@/components/ui/card";
import { listUnits, type UnitRow } from "@/lib/api";
import { pluralise, useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { ha, qty } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Node {
  unit: UnitRow;
  depth: number;
}

/** Depth-first flatten: parents first, children indented, collapsed groups skip their children. */
function flatten(units: UnitRow[], collapsed: Set<string>): Node[] {
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
      out.push({ unit: u, depth });
      if (!collapsed.has(u.name)) walk(u.name, depth + 1, new Set(seen).add(u.name));
    }
  };
  walk(null, 0, new Set());
  return out;
}

export function Blocks() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [units, setUnits] = useState<UnitRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
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
    void load();
  }, [load]);

  const rows = useMemo(() => flatten(units ?? [], collapsed), [units, collapsed]);
  const waiting = loading && !units;
  const plural = pluralise(crop.unit_label);

  const toggle = (name: string) =>
    setCollapsed((s) => {
      const n = new Set(s);
      if (!n.delete(name)) n.add(name);
      return n;
    });

  return (
    <PageShell
      title={viewLabel("blocks", crop)}
      eyebrow={crop.name}
      actions={<RefreshButton onClick={load} loading={loading} label={`the ${plural.toLowerCase()}`} />}
      description={`Every ${crop.unit_label.toLowerCase()} under ${crop.parent_unit_label.toLowerCase()}, with its current cycle. Open one for its rotation history and recent work.`}
    >
      <Card>
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>{plural}</CardTitle>
            <CardDescription>
              {units ? `${qty(units.length)} in total` : "Loading…"}
            </CardDescription>
          </CardHeading>
          <CardTools />
        </CardHeaderRow>
        <CardContent>
          {waiting ? (
            <RowsSkeleton rows={7} />
          ) : units && units.length === 0 ? (
            <p className="text-[13px] text-[var(--sd-muted)]">
              No {plural.toLowerCase()} recorded for {crop.name} yet.
            </p>
          ) : (
            <ScrollTable tall>
              <table className="w-full min-w-[760px] text-[13px]">
                <thead>
                  <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
                    <th className={TH}>{crop.unit_label}</th>
                    <th className={TH}>Type</th>
                    <th className={THR}>Area (ha)</th>
                    <th className={TH}>Current cycle</th>
                    <th className={TH}>Status</th>
                    <th className={TH}>Cost centre</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ unit: u, depth }) => {
                    const group = !!u.is_group;
                    return (
                      <tr
                        key={u.name}
                        className={cn(BODY_ROW, "cursor-pointer hover:bg-[var(--sd-bg-soft)]")}
                        onClick={() => setOpen(u.name)}
                      >
                        <td className={TD}>
                          <div className="flex items-center gap-1.5" style={{ paddingLeft: depth * 20 }}>
                            {group ? (
                              <button
                                type="button"
                                aria-label={collapsed.has(u.name) ? `Expand ${u.name}` : `Collapse ${u.name}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggle(u.name);
                                }}
                                className="rounded p-0.5 text-[var(--sd-quiet)] hover:text-[var(--sd-ink)]"
                              >
                                {collapsed.has(u.name) ? (
                                  <ChevronRight className="h-3.5 w-3.5" />
                                ) : (
                                  <ChevronDown className="h-3.5 w-3.5" />
                                )}
                              </button>
                            ) : (
                              <span className="w-[22px]" />
                            )}
                            <span className={cn("text-[var(--sd-ink)]", group ? "font-semibold" : "font-medium")}>
                              {u.name}
                            </span>
                          </div>
                        </td>
                        <td className={cn(TD, "text-[var(--sd-muted)]")}>{u.unit_type}</td>
                        <td className={TDR}>{ha(u.area_ha)}</td>
                        <td className={TD}>
                          {u.current_cycle ? (
                            <>
                              <div className="text-[var(--sd-ink)]">{u.item || u.current_cycle}</div>
                              <div className="text-[11px] text-[var(--sd-quiet)]">{u.current_cycle}</div>
                            </>
                          ) : (
                            <span className="text-[var(--sd-quiet)]">—</span>
                          )}
                        </td>
                        <td className={TD}>
                          <StatusPill status={u.status} />
                        </td>
                        <td className={cn(TD, "tabular-nums text-[var(--sd-muted)]")}>{u.cost_center || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </ScrollTable>
          )}
        </CardContent>
      </Card>

      {open && (
        <UnitDrawer
          name={open}
          unitLabel={crop.unit_label}
          canSeePay={crop.boot.can_see_pay}
          onClose={() => setOpen(null)}
        />
      )}
    </PageShell>
  );
}
