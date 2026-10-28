/** Styles for the bits MapLibre renders as raw DOM (controls, credit) and the card entrance.
 *  Injected once; every map component calls ensureMapStyles(). */
const ID = "prod-map-style";

export function ensureMapStyles() {
  if (typeof document === "undefined" || document.getElementById(ID)) return;
  const el = document.createElement("style");
  el.id = ID;
  el.textContent = `
    .maplibregl-ctrl-group { border: none !important; border-radius: 10px !important; overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,.18) !important; }
    .maplibregl-ctrl-group button { width: 34px !important; height: 34px !important; }
    .prod-basemap-toggle { position: absolute; z-index: 1000; top: 5.5rem; right: 10px; width: 34px; height: 34px;
      display: flex; align-items: center; justify-content: center; padding: 0; border: none; border-radius: 10px;
      background: #fff; color: #374151; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.18); }
    .prod-basemap-toggle:hover { background: #f3f4f6; color: #111827; }
    .prod-basemap-toggle svg { width: 16px; height: 16px; }
    .prod-map-credit { position: absolute; z-index: 1000; left: 8px; bottom: 8px; display: flex; align-items: center;
      gap: 6px; font: 400 10px Poppins, sans-serif; color: #5d5b55; }
    .prod-map-credit button { width: 18px; height: 18px; border-radius: 9999px; border: 1px solid rgba(0,0,0,.12);
      background: rgba(255,255,255,.85); color: #5d5b55; font: italic 600 10px/1 Georgia, serif; cursor: pointer; opacity: .7; padding: 0; }
    .prod-map-credit button:hover { opacity: 1; }
    .prod-map-credit span { display: none; padding: 2px 8px; border-radius: 9999px; background: rgba(255,255,255,.92); }
    .prod-map-credit:hover span, .prod-map-credit.open span { display: inline; }
    .prod-map-credit a { color: inherit; text-decoration: underline; }
    @keyframes prod-card-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
    .prod-card-in { animation: prod-card-in .18s ease-out; }
    @media (prefers-reduced-motion: reduce) { .prod-card-in { animation: none; } }
  `;
  document.head.appendChild(el);
}
