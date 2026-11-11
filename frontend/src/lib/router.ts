import { useCallback, useEffect, useState } from "react";

/**
 * Hash routing, namespaced by crop: `#/<crop_key>/<view>`.
 *
 * A hash router rather than a history one because the page is served by Frappe
 * at a single route (/production_app); a path router would need a server-side
 * catch-all that does not exist. The crop is a segment of the route (not app
 * state) so a link to "the fish plan" is a link, and the back button undoes a
 * crop switch.
 */

export const VIEWS = [
  "overview",
  "blocks",
  "cycles",
  "plan",
  "casual-labourers",
  "costs",
  // Capital / setup costs and opening balances per block.
  "establishment",
  // Cumulative cost vs harvest value per block and per farm.
  "break-even",
  "forecast",
  "settings",
  // Approvals: the manager signs off supervisor-keyed work before it counts.
  "approvals",
  // Coverage map: blocks coloured by this week's work done / remaining.
  "map",
  // Avocado forecast pages (ported from the standalone /avocado-* pages).
  "outlook",
  "block-forecast",
  "harvest-calendar",
  "picking-plan",
  "dry-matter",
  // Tagged-fruit dry matter monitoring (avocado).
  "dry-matter-monitoring",
  // Generic dry matter tests for crops with dry_matter_testing on (avocado keeps "dry-matter").
  "dry-matter-tests",
  // Crop-specific field logs.
  "hive-inspections",
  "honey-harvest",
  "pond-batches",
  "water-quality",
  "feeding",
  "irrigation",
  "grading",
  // Flower crops (greenhouse -> bed), ported from the Crop Production desk screens and
  // the Crop Cycle Dashboard block. Same data, same endpoints as the legacy pages.
  "flower-overview",
  "greenhouses",
  "flower-cycles",
  "protocols",
  "cut-stages",
  "plan-form",
  "harvesting",
  "farm-map",
  // Summer flowers (Crop Production): planting calendars and protocol versions, ported from the desk lists.
  "planting-calendars",
  "protocol-versions",
  // Silage cycles, their cost per kg and the pit stock (crops marked Grown for Silage).
  "silage",
] as const;

export type View = (typeof VIEWS)[number];

export const DEFAULT_VIEW: View = "overview";

const KNOWN: ReadonlySet<string> = new Set<string>(VIEWS);

export function isView(v: string): v is View {
  return KNOWN.has(v);
}

/** Renamed views: old bookmarks / saved links keep working and are rewritten to the new route. */
const LEGACY_VIEWS: Record<string, View> = { "value-adders": "casual-labourers" };

export interface Route {
  /** null when the hash names no crop: the app then picks the first one. */
  crop: string | null;
  view: View;
}

/** `#/fruits-vegetables/plan` -> `{crop, view}`. Anything unreadable degrades
 *  to the default view rather than to an error screen. */
export function parseRoute(hash: string): Route {
  const raw = (hash || "").replace(/^#\/?/, "").split("?")[0];
  const [crop, view] = raw.split("/").filter(Boolean);
  const lower = (view || "").toLowerCase();
  const v = LEGACY_VIEWS[lower] ?? lower;
  return {
    crop: crop ? decodeURIComponent(crop) : null,
    view: isView(v) ? v : DEFAULT_VIEW,
  };
}

export function routeHash(crop: string, view: View = DEFAULT_VIEW): string {
  return `#/${encodeURIComponent(crop)}/${view}`;
}

export function useRoute(): [Route, (crop: string, view?: View) => void] {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));

  useEffect(() => {
    // A legacy hash (#/crop/value-adders) is rewritten to its new route without a history entry.
    const raw = window.location.hash.replace(/^#\/?/, "").split("?")[0].split("/").filter(Boolean);
    const legacy = raw[1] && LEGACY_VIEWS[raw[1].toLowerCase()];
    if (legacy) window.history.replaceState(null, "", routeHash(decodeURIComponent(raw[0]), legacy));
  }, []);

  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = useCallback((crop: string, view: View = DEFAULT_VIEW) => {
    const h = routeHash(crop, view);
    if (window.location.hash !== h) window.location.hash = h;
  }, []);

  return [route, navigate];
}

/** Rewrite the hash without adding a history entry (used to land on a default). */
export function replaceRoute(crop: string, view: View = DEFAULT_VIEW) {
  const h = routeHash(crop, view);
  if (window.location.hash !== h) {
    window.history.replaceState(null, "", h);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  }
}
