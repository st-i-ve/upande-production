import { describe, expect, it } from "vitest";

// Every generated mark (productivity + one per crop). The browser's animate() throws on
// keyframes whose offsets go backwards, so a bad scene must fail here, not in the app.
const MARKS = import.meta.glob("@/assets/production_logo*.svg", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("production marks", () => {
  it("includes the productivity mark and a scene per crop", () => {
    const names = Object.keys(MARKS).map((p) => p.split("/").pop());
    for (const n of ["production_logo.svg", "production_logo_avocado.svg", "production_logo_fruits-vegetables.svg",
      "production_logo_aquaculture.svg", "production_logo_apiary.svg"]) {
      expect(names).toContain(n);
    }
  });

  for (const [path, svg] of Object.entries(MARKS)) {
    it(`${path.split("/").pop()} has ordered keyframe offsets`, () => {
      const m = /<metadata id="production-motion">([\s\S]*?)<\/metadata>/.exec(svg);
      expect(m).not.toBeNull();
      const spec = JSON.parse(m![1]) as { enter: { sel: string; frames: { offset: number }[] }[]; loop: typeof spec.enter };
      for (const t of [...spec.enter, ...spec.loop]) {
        const offs = t.frames.map((f) => f.offset);
        offs.forEach((o, i) => {
          expect(o, `${t.sel}`).toBeGreaterThanOrEqual(i ? offs[i - 1] : 0);
          expect(o, `${t.sel}`).toBeLessThanOrEqual(1);
        });
      }
    });
  }
});
