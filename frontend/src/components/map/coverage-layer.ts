import type maplibregl from "maplibre-gl";
import type { CoverageMap, CoverageUnit } from "@/lib/map-api";
import { COVERAGE_STATE_COLOR, NO_ACTIVITY_COLOR } from "@/lib/map-api";

/**
 * Draws a CoverageMap on a maplibre map: pivot outlines underneath, unit polygons filled by
 * state, a selected-unit highlight, and unit names at their centre. Call `setCoverageData`
 * on every refetch (it adds the layers the first time). Click handling stays with the page:
 * `map.on("click", COVERAGE_FILL_LAYER, e => e.features?.[0]?.properties?.name)`.
 */
export const COVERAGE_FILL_LAYER = "coverage-fill";
const SRC = "coverage-units";
const OUT_SRC = "coverage-outlines";

function feature(u: CoverageUnit, byActivity = false) {
  const gj = u.geojson;
  const geometry = gj ? (gj.type === "Feature" ? gj.geometry : gj.type === "FeatureCollection" ? undefined : (gj as never)) : undefined;
  if (!geometry) return null;
  return {
    type: "Feature" as const,
    geometry,
    properties: { name: u.name, state: u.state, color: byActivity ? u.activity?.color ?? NO_ACTIVITY_COLOR : COVERAGE_STATE_COLOR[u.state], progress: u.progress_pct },
  };
}

export function setCoverageData(map: maplibregl.Map, data: CoverageMap, selected?: string | null, byActivity = false) {
  const units = { type: "FeatureCollection" as const, features: data.units.map((u) => feature(u, byActivity)).filter(Boolean) as never[] };
  const outlines = {
    type: "FeatureCollection" as const,
    features: data.outlines
      .map((o) => feature({ ...o, state: "no_work", progress_pct: 0 } as unknown as CoverageUnit))
      .filter(Boolean) as never[],
  };
  const src = map.getSource(SRC) as maplibregl.GeoJSONSource | undefined;
  if (src) {
    src.setData(units);
    (map.getSource(OUT_SRC) as maplibregl.GeoJSONSource).setData(outlines);
  } else {
    map.addSource(OUT_SRC, { type: "geojson", data: outlines });
    map.addSource(SRC, { type: "geojson", data: units });
    map.addLayer({ id: "coverage-outline", type: "line", source: OUT_SRC, paint: { "line-color": "#ffffff", "line-width": 2, "line-opacity": 0.9 } });
    map.addLayer({
      id: COVERAGE_FILL_LAYER,
      type: "fill",
      source: SRC,
      paint: { "fill-color": ["get", "color"], "fill-opacity": 0.62 },
    });
    map.addLayer({ id: "coverage-line", type: "line", source: SRC, paint: { "line-color": "#ffffff", "line-width": 1.5 } });
    map.addLayer({
      id: "coverage-selected",
      type: "line",
      source: SRC,
      filter: ["==", ["get", "name"], ""],
      paint: { "line-color": "#0a0a0a", "line-width": 3 },
    });
  }
  setCoverageSelected(map, selected);
}

export function setCoverageSelected(map: maplibregl.Map, name?: string | null) {
  if (map.getLayer("coverage-selected")) map.setFilter("coverage-selected", ["==", ["get", "name"], name ?? ""]);
}
