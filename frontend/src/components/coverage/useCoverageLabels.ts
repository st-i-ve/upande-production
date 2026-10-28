import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { CoverageUnit } from "@/lib/map-api";
import { unitCenter } from "./coverage-utils";

/** Block names as small DOM labels at each block's centre, shown from `minZoom` up. */
export function useCoverageLabels(map: maplibregl.Map | null, units: CoverageUnit[] | undefined, minZoom = 15) {
  const markers = useRef<maplibregl.Marker[]>([]);
  useEffect(() => {
    if (!map || !units) return;
    const els: HTMLElement[] = [];
    markers.current = units.flatMap((u) => {
      const c = unitCenter(u);
      if (!c) return [];
      const el = document.createElement("div");
      el.textContent = u.name;
      el.setAttribute("data-coverage-label", u.name);
      el.style.cssText =
        "font:600 11px Poppins,system-ui,sans-serif;color:#fff;text-shadow:0 0 3px rgba(0,0,0,.85);pointer-events:none;white-space:nowrap;font-variant-numeric:tabular-nums";
      els.push(el);
      return [new maplibregl.Marker({ element: el }).setLngLat(c).addTo(map)];
    });
    const sync = () => {
      const show = map.getZoom() >= minZoom;
      els.forEach((e) => (e.style.display = show ? "" : "none"));
    };
    sync();
    map.on("zoom", sync);
    return () => {
      map.off("zoom", sync);
      markers.current.forEach((m) => m.remove());
      markers.current = [];
    };
  }, [map, units, minZoom]);
}
