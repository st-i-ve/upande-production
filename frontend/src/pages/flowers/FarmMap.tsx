import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";
import { firstLoad, MapPageSkeleton } from "@/components/Loading";
import { MapBase } from "@/components/map";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { farmMap, type MapHouse, type MapPayload } from "@/lib/flowers-api";
import { ClassicLink } from "./ClassicLink";

const SRC = "farm-houses";
const FILL = "farm-houses-fill";
const PLANTED = "#3f7d3a";
const EMPTY = "#9a968c";
const SURGE = "#e9a23b";

const n = (v: number | null | undefined) => (v ?? 0).toLocaleString("en-US");

function color(h: MapHouse) {
  if (h.empty || !h.plantings.length) return EMPTY;
  return (h.surge ?? 0) >= 20 ? SURGE : PLANTED;
}

function toCollection(houses: MapHouse[]) {
  return {
    type: "FeatureCollection" as const,
    features: houses
      .filter((h) => h.polygons?.length)
      .map((h) => ({
        type: "Feature" as const,
        geometry: { type: "MultiPolygon" as const, coordinates: h.polygons },
        properties: { name: h.name, label: h.label, color: color(h) },
      })),
  };
}

function draw(map: maplibregl.Map, houses: MapHouse[], selected: string | null) {
  const data = toCollection(houses) as never;
  const src = map.getSource(SRC) as maplibregl.GeoJSONSource | undefined;
  if (src) src.setData(data);
  else {
    map.addSource(SRC, { type: "geojson", data });
    map.addLayer({ id: FILL, type: "fill", source: SRC, paint: { "fill-color": ["get", "color"], "fill-opacity": 0.62 } });
    map.addLayer({ id: `${FILL}-line`, type: "line", source: SRC, paint: { "line-color": "#ffffff", "line-width": 1.5 } });
    map.addLayer({
      id: `${FILL}-sel`, type: "line", source: SRC, filter: ["==", ["get", "name"], ""],
      paint: { "line-color": "#0a0a0a", "line-width": 3 },
    });
    map.addLayer({
      id: `${FILL}-label`, type: "symbol", source: SRC,
      layout: { "text-field": ["get", "label"], "text-size": 11 },
      paint: { "text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,.6)", "text-halo-width": 1.2 },
    });
  }
  if (map.getLayer(`${FILL}-sel`)) map.setFilter(`${FILL}-sel`, ["==", ["get", "name"], selected ?? ""]);
}

/** Farm Map: what is planted where, and which houses are about to run hot. The greenhouse geometry and
 *  plantings come from `farm_map.map_payload`, the same endpoint as the classic budget-forecast map. */
export function FarmMap() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [data, setData] = useState<MapPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const fitted = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await farmMap();
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as MapPayload);
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!map || !data) return;
    draw(map, data.greenhouses, selected);
    if (!fitted.current && data.bounds) {
      fitted.current = true;
      map.fitBounds(data.bounds as never, { padding: 60, animate: false });
    }
  }, [map, data, selected]);

  useEffect(() => {
    if (!map) return;
    const click = (e: maplibregl.MapLayerMouseEvent) => setSelected((e.features?.[0]?.properties?.name as string) ?? null);
    map.on("click", FILL, click);
    const pointer = () => (map.getCanvas().style.cursor = "pointer");
    const reset = () => (map.getCanvas().style.cursor = "");
    map.on("mouseenter", FILL, pointer);
    map.on("mouseleave", FILL, reset);
    return () => {
      map.off("click", FILL, click);
      map.off("mouseenter", FILL, pointer);
      map.off("mouseleave", FILL, reset);
    };
  }, [map]);

  const house = useMemo(() => data?.greenhouses.find((h) => h.name === selected) ?? null, [data, selected]);
  const waiting = firstLoad(loading, !!data);
  const t = data?.totals;

  return (
    <PageShell
      title="Farm Map"
      eyebrow={crop.name}
      actions={
        <>
          <ClassicLink href="/budget-forecast#map" />
          <RefreshButton onClick={() => void load()} loading={loading} label="the farm map" />
        </>
      }
      description={
        t
          ? `${t.houses} planted greenhouses${t.empty ? ` · ${t.empty} empty` : ""} · ${n(t.plants)} plants · ${n(t.week_stems)} stems budgeted for week ${data?.now_week}`
          : undefined
      }
    >
      {waiting ? (
        <MapPageSkeleton />
      ) : (
        <div className="relative h-[calc(100vh-240px)] min-h-[480px] overflow-hidden rounded-[var(--sd-radius-lg)] shadow-[var(--sd-shadow-1)]">
          <MapBase className="h-full" onReady={setMap} />
          {data && data.geometry_source === "none" && (
            <div className="absolute left-3 top-3 max-w-xs rounded-lg bg-[var(--sd-card)] px-3 py-2 text-[12px] text-[var(--sd-muted)] shadow-[var(--sd-shadow-2)]">
              No greenhouse geometry is surveyed on this site yet, so there is nothing to draw.
            </div>
          )}
          <div className="absolute bottom-3 left-3 flex gap-3 rounded-lg bg-[var(--sd-card)] px-3 py-2 text-[11px] shadow-[var(--sd-shadow-2)]">
            {[["Planted", PLANTED], ["Surging (+20% next 4 weeks)", SURGE], ["Empty", EMPTY]].map(([l, c]) => (
              <span key={l} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{l}</span>
            ))}
          </div>
          {house && (
            <aside className="absolute right-3 top-3 max-h-[80%] w-80 overflow-auto rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] p-4 shadow-[var(--sd-shadow-2)]">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-[15px] font-semibold text-[var(--sd-ink)]">{house.label}</h3>
                  <p className="text-[12px] text-[var(--sd-quiet)]">
                    {n(house.plants)} plants · {n(house.area)} m² · {n(house.beds)} beds
                  </p>
                </div>
                <button type="button" aria-label="Close" className="text-[var(--sd-muted)]" onClick={() => setSelected(null)}>×</button>
              </div>
              <p className="mt-2 text-[12px] text-[var(--sd-muted)]">
                {n(house.week_stems)} stems this week · {n(house.ahead_stems)} in the next 4
                {house.surge != null && ` (${house.surge > 0 ? "+" : ""}${house.surge}%)`}
              </p>
              <ul className="mt-3 space-y-2">
                {house.plantings.length === 0 && <li className="text-[12px] text-[var(--sd-muted)]">Nothing planted.</li>}
                {house.plantings.map((p) => (
                  <li key={p.cycle} className="rounded-lg bg-[var(--sd-bg-soft)] px-3 py-2 text-[12px]">
                    <b>{p.variety}</b> <span className="text-[var(--sd-muted)]">· {p.stage}{p.age_weeks != null ? `, ${p.age_weeks} wk` : ""}</span>
                    <div className="text-[var(--sd-muted)]">{n(p.plants)} plants · {n(p.area)} m² · {n(p.week_stems)} stems this week</div>
                  </li>
                ))}
              </ul>
            </aside>
          )}
        </div>
      )}
    </PageShell>
  );
}
