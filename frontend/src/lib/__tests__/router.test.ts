import { describe, expect, it } from "vitest";
import { parseRoute, routeHash } from "@/lib/router";

describe("parseRoute", () => {
  it("reads crop and view", () => {
    expect(parseRoute("#/fruits-vegetables/plan")).toEqual({
      crop: "fruits-vegetables",
      view: "plan",
    });
  });
  it("defaults an empty hash", () => {
    expect(parseRoute("")).toEqual({ crop: null, view: "overview" });
  });
  it("defaults the view when only a crop is given or the view is unknown", () => {
    expect(parseRoute("#/avocado")).toEqual({ crop: "avocado", view: "overview" });
    expect(parseRoute("#/avocado/nonsense")).toEqual({ crop: "avocado", view: "overview" });
  });
  it("reads hyphenated views and ignores a query string", () => {
    expect(parseRoute("#/fish/value-adders?x=1")).toEqual({ crop: "fish", view: "value-adders" });
  });
  it("round-trips with routeHash", () => {
    expect(parseRoute(routeHash("hive", "costs"))).toEqual({ crop: "hive", view: "costs" });
  });
});
