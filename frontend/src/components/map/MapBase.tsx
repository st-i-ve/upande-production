import { useEffect, useRef, useState } from "react";
import maplibregl, { type LngLatBoundsLike, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { cn } from "@/lib/utils";
import { ensureMapStyles } from "./map-styles";

/**
 * Shared MapLibre base map: satellite imagery (default) or street map, a toggle under the
 * zoom buttons, and a small (i) credit at the bottom-left (the licences still require it;
 * it is one tap or hover away instead of a permanent label).
 *
 * `onReady(map)` fires once the style has loaded, so a page can add its sources and layers
 * straight away; both basemaps live in the style as two raster layers and the toggle only
 * flips their visibility, so page layers survive switching. The container needs a height
 * (min 420px by default). Resizes are tracked with a ResizeObserver.
 */
export interface MapBaseProps {
  className?: string;
  /** [lng, lat] */
  initialCenter?: [number, number];
  initialZoom?: number;
  /** Fit these bounds instead of centre/zoom: [[minLng, minLat], [maxLng, maxLat]]. */
  initialBounds?: LngLatBoundsLike;
  /** Which basemap first. Default "satellite". */
  basemap?: Basemap;
  onReady: (map: maplibregl.Map) => void;
}

export type Basemap = "satellite" | "street";

/** Mutara, Laikipia: the starting view until the surveyed block outlines load and the map fits to them. */
export const DEFAULT_CENTER: [number, number] = [36.75, 0.06];
export const DEFAULT_ZOOM = 14;

const SAT_LAYER = "basemap-satellite";
const STREET_LAYER = "basemap-street";

const CREDITS: Record<Basemap, string> = {
  satellite: 'Imagery © <a href="https://www.esri.com" target="_blank" rel="noreferrer">Esri</a>, Maxar, Earthstar Geographics',
  street: 'Map data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors',
};

function baseStyle(initial: Basemap): StyleSpecification {
  return {
    version: 8,
    sources: {
      satellite: {
        type: "raster",
        tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        tileSize: 256,
        maxzoom: 19,
      },
      street: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        maxzoom: 19,
      },
    },
    layers: [
      { id: STREET_LAYER, type: "raster", source: "street", layout: { visibility: initial === "street" ? "visible" : "none" } },
      { id: SAT_LAYER, type: "raster", source: "satellite", layout: { visibility: initial === "satellite" ? "visible" : "none" } },
    ],
  };
}

const SAT_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></svg>';
const STREET_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/></svg>';

export function MapBase({
  className,
  initialCenter = DEFAULT_CENTER,
  initialZoom = DEFAULT_ZOOM,
  initialBounds,
  basemap = "satellite",
  onReady,
}: MapBaseProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [current, setCurrent] = useState<Basemap>(basemap);
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    ensureMapStyles();
    const map = new maplibregl.Map({
      container: el,
      style: baseStyle(basemap),
      center: initialCenter,
      zoom: initialZoom,
      bounds: initialBounds,
      fitBoundsOptions: { padding: 48 },
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    map.once("load", () => {
      setReady(true);
      onReady(map);
    });
    return () => {
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Flip the basemap by visibility so page layers stay put.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setLayoutProperty(SAT_LAYER, "visibility", current === "satellite" ? "visible" : "none");
    map.setLayoutProperty(STREET_LAYER, "visibility", current === "street" ? "visible" : "none");
  }, [current, ready]);

  useEffect(() => {
    if (!ready) return;
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => mapRef.current?.resize());
    ro.observe(el);
    return () => ro.disconnect();
  }, [ready]);

  return (
    <div ref={containerRef} className={cn("relative h-full min-h-[420px] w-full bg-[var(--sd-bg-soft)]", className)}>
      <button
        type="button"
        className="prod-basemap-toggle"
        title={current === "satellite" ? "Switch to street map" : "Switch to satellite"}
        aria-label={current === "satellite" ? "Switch to street map" : "Switch to satellite"}
        onClick={() => setCurrent((c) => (c === "satellite" ? "street" : "satellite"))}
        dangerouslySetInnerHTML={{ __html: current === "satellite" ? STREET_ICON : SAT_ICON }}
      />
      <div className={cn("prod-map-credit", open && "open")}>
        <button type="button" aria-label="Map data credits" title="Map data credits" onClick={() => setOpen((o) => !o)}>
          i
        </button>
        <span dangerouslySetInnerHTML={{ __html: CREDITS[current] }} />
      </div>
    </div>
  );
}
