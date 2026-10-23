import { describe, expect, it } from "vitest";
import { moduleHref, parseSiteRoute } from "./moduleRoutes";

describe("module URLs", () => {
  it("resolves the home and module selection pages", () => {
    expect(parseSiteRoute("")).toEqual({ kind: "home" });
    expect(parseSiteRoute("#/" )).toEqual({ kind: "home" });
    expect(parseSiteRoute("#/modules")).toEqual({ kind: "modules" });
  });

  it("resolves every supported module and rejects unknown names", () => {
    for (const name of ["overview", "monitor", "health", "alerts", "tasks", "cattle", "analytics", "inventory"] as const) {
      expect(parseSiteRoute(moduleHref(name))).toEqual({ kind: "module", name });
    }
    expect(parseSiteRoute("#/module/unknown")).toEqual({ kind: "home" });
  });
});
