import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { firstLoad, MapPageSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { WeekPicker } from "@/components/WeekPicker";
import { BlockCard } from "@/components/coverage/BlockCard";
import { CoverageLegend } from "@/components/coverage/CoverageLegend";
import { RemainingPanel } from "@/components/coverage/RemainingPanel";
import { remainingBlockCount, remainingBlocks, unitBounds } from "@/components/coverage/coverage-utils";
import { useCoverageLabels } from "@/components/coverage/useCoverageLabels";
import {
  COVERAGE_FILL_LAYER,
  MapBase,
  MapKpiPill,
  MapPanelDock,
  setCoverageData,
  setCoverageSelected,
} from "@/components/map";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { COVERAGE_STATES, COVERAGE_STATE_LABEL, coverageMap, type CoverageMap as Data, type CoverageState } from "@/lib/map-api";
import { routeHash } from "@/lib/router";
import { currentIsoWeek, type IsoWeek } from "@/lib/weeks";

/**
 * Coverage Map: which blocks are done, in progress, not started, late or waiting for approval
 * this week, and what work remains. Units are coloured by state; the docked panels list the
 * work remaining (click to fly to a block) and show the selected block's tasks.
 */
export function CoverageMap() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [week, setWeek] = useState<IsoWeek>(currentIsoWeek);
  const [farm, setFarm] = useState("");
  const [operation, setOperation] = useState("");
  const [status, setStatus] = useState("");
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const seq = useRef(0);
  const fitted = useRef("");

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    const r = await coverageMap({
      crop: crop.name,
      year: week.year,
      week: week.week,
      farm: farm || null,
      operation: operation || null,
      status: (status || null) as CoverageState | null,
    });
    if (mine !== seq.current) return;
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r);
  }, [crop.name, week, farm, operation, status, toast]);

  // Different crop: start from a clean slate (the map remounts behind the skeleton).
  useEffect(() => {
    setData(null);
    setMap(null);
    setSelected(null);
    setFarm("");
    setOperation("");
    setStatus("");
    fitted.current = "";
  }, [crop.name]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const onReady = useCallback((m: maplibregl.Map) => {
    m.on("click", COVERAGE_FILL_LAYER, (e) => {
      const name = e.features?.[0]?.properties?.name;
      if (typeof name === "string") setSelected(name);
    });
    m.on("mouseenter", COVERAGE_FILL_LAYER, () => (m.getCanvas().style.cursor = "pointer"));
    m.on("mouseleave", COVERAGE_FILL_LAYER, () => (m.getCanvas().style.cursor = ""));
    setMap(m);
  }, []);

  useEffect(() => {
    if (!map || !data) return;
    setCoverageData(map, data, selectedRef.current);
    const key = `${crop.name}|${farm}`;
    if (data.bounds && fitted.current !== key) {
      fitted.current = key;
      map.fitBounds(data.bounds, { padding: 48, duration: 0 });
    }
  }, [map, data, crop.name, farm]);

  useEffect(() => {
    if (map) setCoverageSelected(map, selected);
  }, [map, selected]);

  // Drop a selection that the filters removed.
  useEffect(() => {
    if (data && selected && !data.units.some((u) => u.name === selected)) setSelected(null);
  }, [data, selected]);

  useCoverageLabels(map, data?.units);

  const pick = useCallback(
    (name: string) => {
      setSelected(name);
      const u = data?.units.find((x) => x.name === name);
      const b = u && unitBounds(u);
      if (map && b) map.fitBounds(b, { padding: 120, maxZoom: 18, duration: 600 });
    },
    [data, map],
  );

  const remaining = useMemo(() => remainingBlocks(data?.units ?? []), [data]);
  const selectedUnit = data?.units.find((u) => u.name === selected) ?? null;
  const dirty = !!farm || !!operation || !!status;
  const clear = () => {
    setFarm("");
    setOperation("");
    setStatus("");
  };
  const t = data?.totals;
  const noGeometry = !!data && !data.bounds;

  return (
    <PageShell
      title={viewLabel("map", crop)}
      eyebrow={crop.name}
      actions={
        <>
          <WeekPicker value={week} onChange={setWeek} />
          <FilterSelect label="Farm" value={farm} onChange={setFarm} options={crop.boot.farms} allLabel="All farms" />
          <FilterSelect
            label="Operation"
            value={operation}
            onChange={setOperation}
            options={(data?.operations ?? []).map((o) => ({ value: o.operation, label: o.operation_name }))}
            allLabel="All operations"
          />
          <FilterSelect
            label="Status"
            value={status}
            onChange={setStatus}
            options={COVERAGE_STATES.map((s) => ({ value: s, label: COVERAGE_STATE_LABEL[s] }))}
            allLabel="All statuses"
          />
          <ClearFiltersPill active={dirty} onClear={clear} />
          <RefreshButton onClick={load} loading={loading} label="the coverage map" />
        </>
      }
    >
      {firstLoad(loading, !!data) ? (
        <MapPageSkeleton />
      ) : (
        <div className="relative h-[calc(100vh-14rem)] min-h-[28rem] overflow-hidden rounded-[20px]" data-testid="coverage-map">
          <MapBase initialBounds={data?.bounds ?? undefined} onReady={onReady} />
          {t ? (
            <MapKpiPill>
              <span data-testid="coverage-kpis" className="tabular-nums">
                {t.blocks} {t.blocks === 1 ? "block" : "blocks"} · <span style={{ color: accent }}>{t.by_state.done ?? 0} done</span> ·{" "}
                {remainingBlockCount(t)} remaining · {t.late} late · {t.by_state.pending_approval ?? 0} pending approval
              </span>
            </MapKpiPill>
          ) : null}
          {noGeometry ? (
            <div className="absolute inset-0 z-[500] flex items-center justify-center p-6 pointer-events-none">
              <p className="rounded-2xl bg-[var(--sd-card)] px-5 py-4 text-center text-[13px] text-[var(--sd-muted)] shadow-[var(--sd-shadow-1)]">
                No {(crop.unit_label || "block").toLowerCase()} on this map has a boundary drawn yet.
              </p>
            </div>
          ) : null}
          {t ? (
            <MapPanelDock>
              <CoverageLegend counts={t.by_state} />
              <RemainingPanel blocks={remaining} selected={selected} onPick={pick} />
              {selectedUnit ? (
                <BlockCard unit={selectedUnit} accent={accent} planHref={routeHash(crop.crop_key, "plan")} onClose={() => setSelected(null)} />
              ) : null}
            </MapPanelDock>
          ) : null}
        </div>
      )}
    </PageShell>
  );
}
