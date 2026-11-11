import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { MapBase, MapControlPanel, MapKpiPill, MapPanelDock } from "@/components/map";
import { durationLabel, hasPosition, positionsBounds } from "@/lib/machine-scan";
import type { Machine } from "@/lib/machines-api";

const BUSY = "#c0662b";
const IDLE = "#3f7d3a";

function markerEl(m: Machine): HTMLElement {
  const el = document.createElement("div");
  el.className = "flex items-center gap-1.5";
  el.style.pointerEvents = "auto";
  const dot = document.createElement("span");
  dot.style.cssText = `width:14px;height:14px;border-radius:999px;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4);background:${m.open_allocation ? BUSY : IDLE}`;
  const label = document.createElement("span");
  label.textContent = m.machine_name;
  label.style.cssText = "font:600 11px system-ui,sans-serif;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.8);white-space:nowrap";
  el.append(dot, label);
  return el;
}

/** The last position of each machine (from its latest scan) on the farm map. */
export function MachinePositions({ machines }: { machines: Machine[] }) {
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const placed = machines.filter(hasPosition);
  const bounds = positionsBounds(machines);
  const onReady = useCallback((m: maplibregl.Map) => setMap(m), []);

  useEffect(() => {
    if (!map) return;
    for (const mk of markers.current) mk.remove();
    markers.current = placed.map((m) =>
      new maplibregl.Marker({ element: markerEl(m), anchor: "left" })
        .setLngLat([Number(m.last_longitude), Number(m.last_latitude)])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setText(
            `${m.machine_name}: ${m.open_allocation ? `with ${m.open_allocation.operator_name ?? m.open_allocation.operator} (${m.open_allocation.allocated_to}, ${durationLabel(m.open_allocation.running_hours)})` : "idle"} · seen ${m.last_seen_at?.slice(0, 16) ?? ""}`,
          ),
        )
        .addTo(map),
    );
    if (bounds) map.fitBounds(bounds, { padding: 64, maxZoom: 17, duration: 0 });
    return () => {
      for (const mk of markers.current) mk.remove();
      markers.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, machines]);

  const fly = (m: Machine) => map?.flyTo({ center: [Number(m.last_longitude), Number(m.last_latitude)], zoom: 17 });

  return (
    <div className="relative h-[26rem] overflow-hidden rounded-[20px]" data-testid="machine-map">
      <MapBase initialBounds={bounds ?? undefined} onReady={onReady} />
      <MapKpiPill>
        <span className="tabular-nums">
          {placed.length} of {machines.length} machines located · <span style={{ color: BUSY }}>{machines.filter((m) => m.open_allocation).length} allocated</span>
        </span>
      </MapKpiPill>
      {!placed.length && (
        <div className="pointer-events-none absolute inset-0 z-[500] flex items-center justify-center p-6">
          <p className="rounded-2xl bg-[var(--sd-card)] px-5 py-4 text-center text-[13px] text-[var(--sd-muted)] shadow-[var(--sd-shadow-1)]">
            No machine has a position yet. A machine is placed on the map when its QR code is scanned with location allowed.
          </p>
        </div>
      )}
      {placed.length > 0 && (
        <MapPanelDock>
          <MapControlPanel title="Last seen" count={placed.length}>
            <ul className="flex flex-col">
              {placed.map((m) => (
                <li key={m.name}>
                  <button type="button" onClick={() => fly(m)} className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12.5px] hover:bg-[var(--sd-bg-soft)]">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: m.open_allocation ? BUSY : IDLE }} />
                    <span className="min-w-0 flex-1 truncate font-medium">{m.machine_name}</span>
                    <span className="shrink-0 text-[var(--sd-quiet)]">{m.last_seen_at?.slice(5, 16) ?? ""}</span>
                  </button>
                </li>
              ))}
            </ul>
          </MapControlPanel>
        </MapPanelDock>
      )}
    </div>
  );
}
