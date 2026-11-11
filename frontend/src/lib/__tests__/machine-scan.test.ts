import { describe, expect, it, vi } from "vitest";
import {
  durationLabel,
  fixPayload,
  frappeDateTime,
  hasPosition,
  labelLayout,
  labelsHtml,
  parseScanCode,
  positionsBounds,
  positionsGeoJSON,
  readFixOnce,
  searchWithoutToken,
  tokenFromSearch,
} from "@/lib/machine-scan";
import { MACHINE_VIEWS, navForCrop, viewAllowed } from "@/lib/nav";
import { parseRoute } from "@/lib/router";
import type { Crop } from "@/lib/api";

describe("parseScanCode", () => {
  it("reads the token out of the label's link", () => {
    expect(parseScanCode("https://farm.example/production_app?machine=AB12CD#/_/scan")).toBe("AB12CD");
  });
  it("reads a token in the hash's query too", () => {
    expect(parseScanCode("https://farm.example/production_app#/_/scan?machine=ZZ9")).toBe("ZZ9");
  });
  it("takes a typed token as is", () => {
    expect(parseScanCode("  7F3A9C21B0 ")).toBe("7F3A9C21B0");
    expect(parseScanCode("")).toBe("");
    expect(parseScanCode(null)).toBe("");
  });
});

describe("token in the page URL", () => {
  it("reads and strips it", () => {
    expect(tokenFromSearch("?machine=AB12")).toBe("AB12");
    expect(tokenFromSearch("")).toBe("");
    expect(searchWithoutToken("?machine=AB12")).toBe("");
    expect(searchWithoutToken("?x=1&machine=AB12")).toBe("?x=1");
  });
  it("the label link routes to the scan screen", () => {
    expect(parseRoute("#/_/scan").view).toBe("scan");
  });
});

describe("readFixOnce", () => {
  it("asks for one fresh position and hands it back", async () => {
    const getCurrentPosition = vi.fn(
      (ok: (p: { coords: { latitude: number; longitude: number; accuracy: number } }) => void, _err: unknown, _opts?: unknown) =>
        ok({ coords: { latitude: 0.0612, longitude: 36.7531, accuracy: 6.2 } }),
    );
    const r = await readFixOnce({ getCurrentPosition });
    expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    expect(getCurrentPosition.mock.calls[0][2]).toMatchObject({ maximumAge: 0, enableHighAccuracy: true });
    expect(r.fix).toMatchObject({ latitude: 0.0612, longitude: 36.7531, accuracy: 6.2 });
  });
  it("a refusal resolves without a position", async () => {
    const r = await readFixOnce({ getCurrentPosition: (_ok, err) => err({ code: 1 }) });
    expect(r.fix).toBeNull();
    expect("reason" in r && r.reason).toMatch(/not allowed/);
  });
  it("no geolocation resolves without a position", async () => {
    const r = await readFixOnce(null);
    expect(r.fix).toBeNull();
  });
  it("payload uses the API's names", () => {
    expect(fixPayload(null)).toEqual({});
    expect(fixPayload({ latitude: 1, longitude: 2, accuracy: 3, captured_at: "2026-11-11 08:00:00" })).toEqual({
      latitude: 1,
      longitude: 2,
      accuracy: 3,
      scanned_at: "2026-11-11 08:00:00",
    });
  });
  it("formats Frappe datetimes in local time", () => {
    expect(frappeDateTime(new Date(2026, 10, 11, 7, 5, 9))).toBe("2026-11-11 07:05:09");
  });
});

describe("durations and positions", () => {
  it("labels durations", () => {
    expect(durationLabel(2.0833)).toBe("2 h 05 min");
    expect(durationLabel(0.75)).toBe("45 min");
    expect(durationLabel(null)).toBe("—");
  });
  it("only real positions go on the map", () => {
    const rows = [
      { name: "A", last_latitude: 0.06, last_longitude: 36.75 },
      { name: "B", last_latitude: null, last_longitude: null },
      { name: "C", last_latitude: 0, last_longitude: 0 },
    ];
    expect(rows.filter(hasPosition).map((r) => r.name)).toEqual(["A"]);
    const fc = positionsGeoJSON(rows, () => ({ busy: true }));
    expect(fc.features).toHaveLength(1);
    expect(fc.features[0].geometry.coordinates).toEqual([36.75, 0.06]);
    expect(fc.features[0].properties).toEqual({ name: "A", busy: true });
    expect(positionsBounds(rows, 0)).toEqual([
      [36.75, 0.06],
      [36.75, 0.06],
    ]);
    expect(positionsBounds([rows[1]])).toBeNull();
  });
});

describe("labels", () => {
  it("wide labels put the QR beside the text, square-ish ones stack it", () => {
    expect(labelLayout(100, 50).orientation).toBe("row");
    expect(labelLayout(60, 45).orientation).toBe("stack");
    expect(labelLayout(102, 152).orientation).toBe("stack");
  });
  it("the QR never drops under a scannable size and fits the label", () => {
    for (const [w, h] of [
      [100, 50],
      [60, 45],
      [70, 40],
      [102, 152],
    ]) {
      const L = labelLayout(w, h);
      expect(L.qr).toBeGreaterThanOrEqual(18);
      expect(L.qr).toBeLessThanOrEqual(Math.min(w, h));
    }
  });
  it("prints one page per label and escapes names", () => {
    const html = labelsHtml(
      [
        { machine_name: "Tractor <1>", machine_type: "Tractor", qr_code: "AB12", image: "data:image/svg+xml;base64,AA" },
        { machine_name: "Chopper", machine_type: "Chopper", qr_code: "CD34", image: null },
      ],
      100,
      50,
    );
    expect(html).toContain("@page { size: 100mm 50mm");
    expect(html.match(/<section class="label/g)).toHaveLength(2);
    expect(html).toContain("Tractor &lt;1&gt;");
    expect(html).toContain("QR unavailable");
  });
});

describe("machine views in the sidebar", () => {
  const crop = { name: "Avocado", crop_key: "avocado", unit_label: "Block" } as unknown as Crop;
  it("every crop has them, flower crops too", () => {
    for (const v of MACHINE_VIEWS) {
      expect(viewAllowed(v, "avocado", crop)).toBe(true);
      expect(viewAllowed(v, "spray-roses", { ...crop, crop_key: "spray-roses", desk_launcher: "Crop Production desk" } as never)).toBe(true);
    }
    const group = navForCrop(crop).find((g) => g.label === "Machines");
    expect(group?.items.map((i) => i.view)).toEqual(["machines", "allocations", "scan"]);
  });
});
