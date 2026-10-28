import { describe, expect, it } from "vitest";
import { isoWeekOf, shiftWeek, weeksInYear, weekStart } from "@/lib/weeks";

describe("iso weeks", () => {
  it("matches known dates", () => {
    expect(isoWeekOf(new Date(2026, 9, 28))).toEqual({ year: 2026, week: 44 });
    expect(isoWeekOf(new Date(2027, 0, 1))).toEqual({ year: 2026, week: 53 });
  });
  it("knows 53-week years", () => {
    expect(weeksInYear(2026)).toBe(53);
    expect(weeksInYear(2025)).toBe(52);
  });
  it("shifts across year ends", () => {
    expect(shiftWeek({ year: 2026, week: 53 }, 1)).toEqual({ year: 2027, week: 1 });
    expect(shiftWeek({ year: 2026, week: 1 }, -1)).toEqual({ year: 2025, week: 52 });
  });
  it("finds the Monday", () => {
    expect(weekStart({ year: 2026, week: 44 })).toEqual(new Date(2026, 9, 26));
  });
});
