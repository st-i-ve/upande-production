import { describe, expect, it } from "vitest";
import { bandFor, bandTone, type Bands } from "@/lib/bands";
import { BANDS } from "@/pages/__tests__/bands-fixtures";
import { errorLimits, errorTone } from "@/components/forecast/AccuracyTable";
import { mmColor, mmLegend } from "@/components/fv/fv-format";

describe("bands", () => {
  it("matches min inclusive, max exclusive, open end", () => {
    expect(bandFor(BANDS, "Fish survival", 89.9)?.label).toBe("Low");
    expect(bandFor(BANDS, "Fish survival", 90)?.label).toBe("On track");
    expect(bandFor(BANDS, "Fish survival", null)).toBeNull();
    expect(bandFor(undefined, "Fish survival", 50)).toBeNull();
    expect(bandFor(BANDS, "Nope", 50)).toBeNull();
  });

  it("tones follow the severity the server sent, so editing a band recolours", () => {
    expect(bandTone(BANDS, "Queen status", 96)).toBe("good");
    expect(bandTone(BANDS, "Queen status", 90)).toBe("warning");
    expect(bandTone(BANDS, "Queen status", 70)).toBe("critical");
    const edited: Bands = { ...BANDS, "Queen status": BANDS["Queen status"].map((b) => (b.label === "weak" ? { ...b, severity: "Critical" as const } : b)) };
    expect(bandTone(edited, "Queen status", 90)).toBe("critical");
  });

  it("forecast error tone and limits come from the bands", () => {
    expect(errorTone(-5, BANDS)).toBe("good");
    expect(errorTone(-20, BANDS)).toBe("fair");
    expect(errorTone(60, BANDS)).toBe("poor");
    expect(errorTone(null, BANDS)).toBe("none");
    expect(errorTone(5, undefined)).toBe("none");
    expect(errorLimits(BANDS)).toEqual({ good: 10, fair: 25 });
    const tight: Bands = { "Forecast error": [{ band_set: "Forecast error", label: "ok", metric: "", min: 0, max: 3, severity: "Good" }, { band_set: "Forecast error", label: "bad", metric: "", min: 3, max: null, severity: "Critical" }] };
    expect(errorTone(5, tight)).toBe("poor");
    expect(errorLimits(tight)).toEqual({ good: 3, fair: null });
  });

  it("irrigation shades and legend follow the bands", () => {
    const rows = BANDS["Irrigation % of target"];
    expect(mmColor(40, rows)).toBe("#c0392b");
    expect(mmColor(100, rows)).toBe("#3f8f5a");
    expect(mmColor(200, rows)).toBe("#3b7ea1");
    expect(mmColor(100, undefined)).toBe("#c4c7cc");
    expect(mmLegend(rows).map((l) => l.label)).toEqual(["Under 50% of target", "50-90%", "On target (90-125%)", "Over 125%"]);
  });
});
