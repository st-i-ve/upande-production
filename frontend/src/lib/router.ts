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
  "value-adders",
  "costs",
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
] as const;

export type View = (typeof VIEWS)[number];

export const DEFAULT_VIEW: View = "overview";

const KNOWN: ReadonlySet<string> = new Set<string>(VIEWS);

export function isView(v: string): v is View {
  return KNOWN.has(v);
}

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
  const v = (view || "").toLowerCase();
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
