import { afterEach, expect, it, vi } from "vitest";

import { fetchDashboard } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  window.history.replaceState({}, "", "/");
});

it("sends the stored access token as a header without changing the request path", async () => {
  window.sessionStorage.setItem("agrinebula.apiToken", "s3cret");
  const seen: Array<{ url: string; headers: Headers }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    seen.push({ url: String(input), headers: new Headers(init?.headers) });
    return { ok: true, json: async () => ({}) } as Response;
  });

  await fetchDashboard();

  expect(seen[0].url).toBe("/api/dashboard");
  expect(seen[0].headers.get("X-API-Token")).toBe("s3cret");
});

it("adopts a token passed in the page URL so a LAN demo can be opened directly", async () => {
  window.history.replaceState({}, "", "/?token=from-url");
  const seen: Array<Headers> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
    seen.push(new Headers(init?.headers));
    return { ok: true, json: async () => ({}) } as Response;
  });

  await fetchDashboard();

  expect(seen[0].get("X-API-Token")).toBe("from-url");
  expect(window.sessionStorage.getItem("agrinebula.apiToken")).toBe("from-url");
});

it("sends no token header when nothing was configured", async () => {
  const seen: Array<Headers> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
    seen.push(new Headers(init?.headers));
    return { ok: true, json: async () => ({}) } as Response;
  });

  await fetchDashboard();

  expect(seen[0].get("X-API-Token")).toBeNull();
});
