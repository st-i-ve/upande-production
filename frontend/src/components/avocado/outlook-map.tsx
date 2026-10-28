import { useEffect, useMemo, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";
import { MapBase, MapControlPanel, MapFloatingCard, MapKpiPill, MapPanelDock } from "@/components/map";
import type { MapBlock, SeasonOutlook } from "@/lib/avocado-api";
import { qty } from "@/lib/format";
import { BandLegend } from "./outlook-treemap";
import { EmptyNote, SectionCard, tonnes } from "./forecast-ui";

const SRC = "orchard-blocks";
const FILL = "orchard-fill";

function geometryOf(g: unknown): unknown {
  const o = g as { type?: string; geometry?: unknown } | null;
  return o && o.type === "Feature" ? o.geometry : o;
}

export function blockFeatures(blocks: MapBlock[]) {
  return {
    type: "FeatureCollection" as const,
    features: blocks
      .map((b) => ({
        type: "Feature" as const,
        geometry: geometryOf(b.geojson),
        properties: { name: b.block, color: b.band.color },
      }))
      .filter((f) => !!f.geometry),
  };
}

function bounds(blocks: MapBlock[]): [[number, number], [number, number]] | null {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const walk = (c: unknown) => {
    if (Array.isArray(c) && typeof c[0] === "number") {
      x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]);
      y0 = Math.min(y0, c[1] as number); y1 = Math.max(y1, c[1] as number);
    } else if (Array.isArray(c)) c.forEach(walk);
  };
  blocks.forEach((b) => walk((geometryOf(b.geojson) as { coordinates?: unknown } | null)?.coordinates));
  return Number.isFinite(x0) ? [[x0, y0], [x1, y1]] : null;
}

/** The orchard on a satellite map: surveyed block polygons shaded by the same bands as the treemap. */
export function OrchardMap({
  data,
  selected,
  onSelect,
}: {
  data: SeasonOutlook;
  selected: string | null;
  onSelect: (block: string | null) => void;
}) {
  const { blocks, surveyed, without_boundary, area_disagrees } = data.map;
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const fitted = useRef("");
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const b = useMemo(() => bounds(blocks), [blocks]);
  const sel = blocks.find((x) => x.block === selected) ?? null;

  useEffect(() => {
    if (!map) return;
    const fc = blockFeatures(blocks) as never;
    const src = map.getSource(SRC) as maplibregl.GeoJSONSource | undefined;
    if (src) src.setData(fc);
    else {
      map.addSource(SRC, { type: "geojson", data: fc });
      map.addLayer({ id: FILL, type: "fill", source: SRC, paint: { "fill-color": ["get", "color"], "fill-opacity": 0.78 } });
      map.addLayer({ id: `${FILL}-line`, type: "line", source: SRC, paint: { "line-color": "#ffffff", "line-width": 1.6 } });
      map.addLayer({
        id: `${FILL}-sel`, type: "line", source: SRC, filter: ["==", ["get", "name"], ""],
        paint: { "line-color": "#0a0a0a", "line-width": 3 },
      });
      map.on("click", FILL, (e) => {
        const name = e.features?.[0]?.properties?.name;
        if (typeof name === "string") onSelectRef.current(name);
      });
      map.on("mouseenter", FILL, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", FILL, () => (map.getCanvas().style.cursor = ""));
    }
    const key = blocks.map((x) => x.block).join("|");
    if (b && fitted.current !== key) {
      fitted.current = key;
      map.fitBounds(b, { padding: 64, duration: 0, maxZoom: 17 });
    }
  }, [map, blocks, b]);

  useEffect(() => {
    if (map?.getLayer(`${FILL}-sel`)) map.setFilter(`${FILL}-sel`, ["==", ["get", "name"], selected ?? ""]);
  }, [map, selected]);

  return (
    <SectionCard
      testId="outlook-map"
      title="Orchard"
      description={
        blocks.length
          ? `${surveyed} surveyed ${surveyed === 1 ? "block" : "blocks"}${without_boundary ? `, ${without_boundary} never surveyed` : ""}. Shade follows the Blocks treemap below.`
          : undefined
      }
    >
      {!blocks.length ? (
        <EmptyNote big>
          <span>
            <b className="text-[var(--sd-text)]">No boundaries</b>
            <br />
            {without_boundary} {without_boundary === 1 ? "block has" : "blocks have"} never been surveyed · the treemap below sizes them
          </span>
        </EmptyNote>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="relative h-[420px] overflow-hidden rounded-[var(--sd-radius-lg)]" data-testid="orchard-map">
            <MapBase initialBounds={b ?? undefined} onReady={setMap} />
            <MapKpiPill>
              {surveyed} {surveyed === 1 ? "block" : "blocks"} · {tonnes(blocks.reduce((s, x) => s + x.expected_kg, 0))}
            </MapKpiPill>
            <MapPanelDock>
              <MapControlPanel title="Blocks" count={blocks.length}>
                <ul className="flex flex-col gap-1 text-[13px]">
                  {blocks.map((x) => (
                    <li key={x.block}>
                      <button
                        type="button"
                        onClick={() => onSelect(x.block === selected ? null : x.block)}
                        className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left hover:bg-[var(--sd-ink)]/[0.05]"
                      >
                        <i className="h-3 w-3 shrink-0 rounded-[3px]" style={{ background: x.band.color }} />
                        <span className="flex-1 truncate font-medium">{x.code}</span>
                        <span className="tabular-nums text-[var(--sd-quiet)]">{tonnes(x.expected_kg)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </MapControlPanel>
              {sel && (
                <MapFloatingCard eyebrow={sel.farm ?? undefined} title={sel.block} onClose={() => onSelect(null)}>
                  <div className="flex flex-col gap-1 text-[13px]">
                    <div>{tonnes(sel.expected_kg)} forecast{sel.vs_curve_pct != null ? ` · ${sel.vs_curve_pct}% of the age curve` : ""}</div>
                    {sel.basis && <div className="text-[var(--sd-quiet)]">{sel.basis}</div>}
                    {sel.area_gap && (
                      <div className="text-[var(--sd-sev-critical)]">
                        Surveyed {qty(sel.area_gap.surveyed_ha, 1)} ha against {qty(sel.area_gap.paper_ha, 1)} ha on paper
                      </div>
                    )}
                  </div>
                </MapFloatingCard>
              )}
            </MapPanelDock>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <BandLegend bands={data.treemap.bands} />
            {area_disagrees > 0 && (
              <span className="text-[12px] text-[var(--sd-sev-critical)]">
                {area_disagrees} {area_disagrees === 1 ? "block's" : "blocks'"} surveyed area disagrees with paper
              </span>
            )}
          </div>
        </div>
      )}
    </SectionCard>
  );
}
