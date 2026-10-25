import { expect, it } from "vitest";

import { resolveCattleDemoJobId } from "./config";

it("prefers the configured demo task id", () => {
  expect(resolveCattleDemoJobId({ VITE_CATTLE_DEMO_JOB_ID: "  demo-task-1  " })).toBe("demo-task-1");
});

it("falls back to the recorded development task when nothing is configured", () => {
  expect(resolveCattleDemoJobId({})).toBe("202d89f9aaad433480d8570bd90c3d41");
  expect(resolveCattleDemoJobId({ VITE_CATTLE_DEMO_JOB_ID: "   " })).toBe("202d89f9aaad433480d8570bd90c3d41");
});
