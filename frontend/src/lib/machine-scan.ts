/**
 * Pure helpers for the machine pages: reading a scanned QR code, the one GPS fix taken at the
 * scan, label layout, durations and the map's points.
 *
 * GPS IS READ ONLY WHEN A QR CODE IS SCANNED. `readFixOnce` is the only place the app touches
 * `navigator.geolocation`, it asks for one position (never `watchPosition`) and the scan screen
 * calls it from the handler that received a decoded code, nowhere else. This mirrors SCP's field
 * apps, which send `latitude`, `longitude`, `accuracy` and `captured_at` with the entry they
 * belong to.
 */

/** The query parameter the label's link carries the machine token in. */
export const SCAN_PARAM = "machine";

/** The machine token in whatever a scanner read: the label's link (`?machine=TOKEN`) or the bare
 *  token typed by hand. "" when there is nothing. Mirrors `qr.parse_scan_code` on the server. */
export function parseScanCode(text: string | null | undefined): string {
  const raw = String(text ?? "").trim();
  if (!raw) return "";
  if (raw.includes(`${SCAN_PARAM}=`)) {
    const parts: string[] = [];
    const q = raw.indexOf("?");
    if (q >= 0) parts.push(raw.slice(q + 1).split("#")[0]);
    const h = raw.indexOf("#");
    if (h >= 0 && raw.indexOf("?", h) >= 0) parts.push(raw.slice(raw.indexOf("?", h) + 1));
    for (const p of parts) {
      const v = new URLSearchParams(p).get(SCAN_PARAM);
      if (v && v.trim()) return v.trim();
    }
  }
  return raw;
}

/** The token a phone camera opened the app with (`/production_app?machine=TOKEN#/…/scan`). */
export function tokenFromSearch(search: string): string {
  return (new URLSearchParams(search || "").get(SCAN_PARAM) || "").trim();
}

/** The search string with the token removed, so a reload does not scan the machine again. */
export function searchWithoutToken(search: string): string {
  const params = new URLSearchParams(search || "");
  params.delete(SCAN_PARAM);
  const s = params.toString();
  return s ? `?${s}` : "";
}

export interface Fix {
  latitude: number;
  longitude: number;
  /** metres, the device's own estimate */
  accuracy: number | null;
  /** when the fix was taken, `YYYY-MM-DD HH:MM:SS` local time */
  captured_at: string;
}

export type FixResult = { fix: Fix } | { fix: null; reason: string };

/** `YYYY-MM-DD HH:MM:SS` in local time (Frappe's datetime format). */
export function frappeDateTime(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

interface GeoLike {
  getCurrentPosition: (
    ok: (p: { coords: { latitude: number; longitude: number; accuracy?: number | null }; timestamp?: number }) => void,
    err: (e: { code?: number; message?: string }) => void,
    opts?: { enableHighAccuracy?: boolean; timeout?: number; maximumAge?: number },
  ) => void;
}

const GEO_REASON: Record<number, string> = {
  1: "Location was not allowed. The machine is allocated without a position.",
  2: "The position could not be found. The machine is allocated without one.",
  3: "The position took too long. The machine is allocated without one.",
};

/**
 * ONE position, now, for the scan that just happened. Never rejects: no geolocation, a refusal or
 * a timeout resolve to `{fix: null, reason}` and the allocation goes ahead without a position.
 * `maximumAge: 0` so a cached fix from somewhere else is never reused.
 */
export function readFixOnce(geo: GeoLike | null | undefined = typeof navigator !== "undefined" ? navigator.geolocation : null, timeoutMs = 15000): Promise<FixResult> {
  return new Promise((resolve) => {
    if (!geo) {
      resolve({ fix: null, reason: "This device has no location. The machine is allocated without a position." });
      return;
    }
    geo.getCurrentPosition(
      (p) =>
        resolve({
          fix: {
            latitude: p.coords.latitude,
            longitude: p.coords.longitude,
            accuracy: p.coords.accuracy ?? null,
            captured_at: frappeDateTime(new Date()),
          },
        }),
      (e) => resolve({ fix: null, reason: GEO_REASON[e?.code ?? 0] ?? (e?.message || "No position.") }),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 },
    );
  });
}

/** The fix as the API's fields (latitude, longitude, accuracy, scanned_at); {} without one. */
export function fixPayload(fix: Fix | null): Record<string, unknown> {
  if (!fix) return {};
  return { latitude: fix.latitude, longitude: fix.longitude, accuracy: fix.accuracy, scanned_at: fix.captured_at };
}

/** "2 h 05 min", "45 min", "—". */
export function durationLabel(hours: number | null | undefined): string {
  if (hours == null || !Number.isFinite(hours) || hours < 0) return "—";
  const mins = Math.round(hours * 60);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (!h) return `${m} min`;
  return `${h} h ${String(m).padStart(2, "0")} min`;
}

export interface Positioned {
  name: string;
  last_latitude?: number | null;
  last_longitude?: number | null;
}

/** Machines with a last position, as GeoJSON points (properties carry every given field). */
export function positionsGeoJSON<T extends Positioned>(rows: T[], props: (r: T) => Record<string, unknown> = () => ({})) {
  return {
    type: "FeatureCollection" as const,
    features: rows
      .filter((r) => hasPosition(r))
      .map((r) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [Number(r.last_longitude), Number(r.last_latitude)] },
        properties: { name: r.name, ...props(r) },
      })),
  };
}

export function hasPosition(r: Positioned): boolean {
  const lat = Number(r.last_latitude);
  const lng = Number(r.last_longitude);
  return Number.isFinite(lat) && Number.isFinite(lng) && !(lat === 0 && lng === 0) && r.last_latitude != null && r.last_longitude != null;
}

/** [[minLng, minLat], [maxLng, maxLat]] around the positioned rows, padded so a single machine is
 *  not a zero-size box; null when none has a position. */
export function positionsBounds(rows: Positioned[], pad = 0.002): [[number, number], [number, number]] | null {
  const pts = rows.filter(hasPosition).map((r) => [Number(r.last_longitude), Number(r.last_latitude)] as const);
  if (!pts.length) return null;
  const lngs = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);
  return [
    [Math.min(...lngs) - pad, Math.min(...lats) - pad],
    [Math.max(...lngs) + pad, Math.max(...lats) + pad],
  ];
}

/**
 * Label sizes, ported from SCP's Labels page. The bunch-tag, 50 × 25 mm and A4 presets are dropped:
 * a machine label goes on a cab or a fuel cap and its QR must scan from a step away.
 */
export const LABEL_SIZES = [
  { id: "100x50", label: "100 × 50 mm (standard)", w: 100, h: 50 },
  { id: "60x45", label: "60 × 45 mm (ZQ520)", w: 60, h: 45 },
  { id: "70x40", label: "70 × 40 mm", w: 70, h: 40 },
  { id: "102x152", label: "102 × 152 mm (4×6 thermal)", w: 102, h: 152 },
] as const;

export type LabelSizeId = (typeof LABEL_SIZES)[number]["id"];

export interface LabelLayout {
  /** QR side in mm */
  qr: number;
  /** "row": QR left, text right; "stack": QR above text */
  orientation: "row" | "stack";
  /** title font size in pt */
  titlePt: number;
  /** small text in pt */
  textPt: number;
  /** padding in mm */
  pad: number;
}

/**
 * How a label of w × h mm is laid out. The idea of SCP's label tiers (`label_tiers.json`): the QR
 * takes a share of the shorter side, never less than a scannable minimum; a label close to square
 * stacks; text scales with the label.
 */
export function labelLayout(w: number, h: number): LabelLayout {
  const minDim = Math.max(1, Math.min(w, h));
  const maxDim = Math.max(w, h);
  const orientation: "row" | "stack" = maxDim / minDim < 1.45 || h > w ? "stack" : "row";
  const pad = minDim < 50 ? 2 : 3;
  const share = orientation === "stack" ? 0.62 : 0.84;
  const qr = Math.max(18, Math.round((minDim - 2 * pad) * share));
  const titlePt = Math.max(9, Math.min(22, Math.round(minDim / 3.6)));
  return { qr, orientation, titlePt, textPt: Math.max(6, Math.round(titlePt * 0.55)), pad };
}

/** Escape text for the print window's HTML. */
export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

export interface PrintableLabel {
  machine_name: string;
  machine_type: string;
  qr_code: string;
  image: string | null;
}

/** The whole print document for a set of labels: one label per page at the chosen size. */
export function labelsHtml(labels: PrintableLabel[], w: number, h: number, siteName = ""): string {
  const L = labelLayout(w, h);
  const body = labels
    .map(
      (l) => `<section class="label ${L.orientation}">
  ${l.image ? `<img src="${l.image}" alt="" />` : `<div class="noqr">QR unavailable</div>`}
  <div class="text">
    <div class="title">${escapeHtml(l.machine_name)}</div>
    <div class="meta">${escapeHtml(l.machine_type || "")}</div>
    <div class="code">${escapeHtml(l.qr_code)}</div>
    ${siteName ? `<div class="meta">${escapeHtml(siteName)}</div>` : ""}
  </div>
</section>`,
    )
    .join("\n");
  return `<!doctype html><html><head><meta charset="utf-8"><title>Machine labels</title><style>
@page { size: ${w}mm ${h}mm; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #000; }
.label { width: ${w}mm; height: ${h}mm; padding: ${L.pad}mm; display: flex; gap: ${L.pad}mm; align-items: center; overflow: hidden; page-break-after: always; break-after: page; }
.label.stack { flex-direction: column; justify-content: center; text-align: center; }
.label img, .noqr { width: ${L.qr}mm; height: ${L.qr}mm; flex: 0 0 ${L.qr}mm; image-rendering: pixelated; }
.noqr { border: 1px dashed #000; display: flex; align-items: center; justify-content: center; font-size: ${L.textPt}pt; }
.text { min-width: 0; display: flex; flex-direction: column; gap: 0.6mm; }
.title { font-size: ${L.titlePt}pt; font-weight: 700; line-height: 1.05; word-break: break-word; }
.meta { font-size: ${L.textPt}pt; }
.code { font-size: ${L.textPt}pt; font-family: ui-monospace, Menlo, monospace; letter-spacing: 0.08em; }
</style></head><body>${body}</body></html>`;
}
