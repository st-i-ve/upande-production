import { useCallback, useEffect, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";
import { MapBase, MapControlPanel, MapFloatingCard, MapKpiPill, MapPanelDock } from "@/components/map";
import type { IrrigationPage, SliceMm } from "@/lib/fv-api";
import { fmtNum, MM_LEGEND, mmColor } from "./fv-format";

const SRC = "fv-slices";
const FILL = "fv-slices-fill";

function paint(map: maplibregl.Map, data: IrrigationPage, accent: string) {
  const fc = {
    type: "FeatureCollection" as const,
    features: data.map.features.map((f) => ({
      ...f,
      properties: { ...f.properties, color: mmColor(f.properties.pct_of_target, accent) },
    })),
  };
  const src = map.getSource(SRC) as maplibregl.GeoJSONSource | undefined;
  if (src) {
    src.setData(fc as never);
    return;
  }
  map.addSource(SRC, { type: "geojson", data: fc as never });
  map.addLayer({ id: FILL, type: "fill", source: SRC, paint: { "fill-color": ["get", "color"], "fill-opacity": 0.7 } });
  map.addLayer({ id: "fv-slices-line", type: "line", source: SRC, paint: { "line-color": "#ffffff", "line-width": 1.5 } });
  map.addLayer({
    id: "fv-slices-selected",
    type: "line",
    source: SRC,
    filter: ["==", ["get", "slice"], ""],
    paint: { "line-color": "#0a0a0a", "line-width": 3 },
  });
}

/** A pivot map: every slice shaded by the mm it received against the period target. */
export function PivotMap({ data, accent }: { data: IrrigationPage; accent: string }) {
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const fitted = useRef("");
  const onReady = useCallback((m: maplibregl.Map) => {
    m.on("click", FILL, (e) => {
      const n = e.features?.[0]?.properties?.slice;
      if (typeof n === "string") setSelected(n);
    });
    m.on("mouseenter", FILL, () => (m.getCanvas().style.cursor = "pointer"));
    m.on("mouseleave", FILL, () => (m.getCanvas().style.cursor = ""));
    setMap(m);
  }, []);

  useEffect(() => {
    if (!map) return;
    paint(map, data, accent);
    const key = data.pivot ?? "";
    if (data.map.bounds && fitted.current !== key) {
      fitted.current = key;
      map.fitBounds(data.map.bounds, { padding: 40, duration: 0 });
    }
  }, [map, data, accent]);

  useEffect(() => {
    if (map?.getLayer("fv-slices-selected")) map.setFilter("fv-slices-selected", ["==", ["get", "slice"], selected ?? ""]);
  }, [map, selected]);

  const sel: SliceMm | undefined = data.slices.find((s) => s.slice === selected);
  return (
    <div className="relative h-[420px] overflow-hidden rounded-[var(--sd-radius-card)]" data-testid="pivot-map">
      <MapBase onReady={onReady} initialBounds={data.map.bounds ?? undefined} />
      <MapKpiPill>
        {data.kpis.slices_on_target} of {data.kpis.slices} slices on target · {fmtNum(data.target.period_mm, 0)} mm target
      </MapKpiPill>
      <MapPanelDock>
        <MapControlPanel title="mm applied vs target" defaultOpen>
          <ul className="flex flex-col gap-1.5 text-[12px]">
            {MM_LEGEND.map((l) => (
              <li key={l.label} className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-sm" style={{ background: l.color || accent }} />
                {l.label}
              </li>
            ))}
          </ul>
        </MapControlPanel>
        {sel && (
          <MapFloatingCard eyebrow={`${sel.pivot}${sel.item ? ` · ${sel.item}` : ""}`} title={sel.slice} onClose={() => setSelected(null)}>
            <div className="text-[13px]">
              <div className="text-[22px] font-semibold tabular-nums">{fmtNum(sel.mm, 1)} mm</div>
              <div className="text-[var(--sd-quiet)]">
                {sel.pct_of_target}% of the {fmtNum(sel.target_mm, 0)} mm target
              </div>
            </div>
          </MapFloatingCard>
        )}
      </MapPanelDock>
    </div>
  );
}
