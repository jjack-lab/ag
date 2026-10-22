import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import SpatialAnalysisPanel from "./SpatialAnalysisPanel";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("reuses the same camera zone and saves a new video report", async () => {
  const previous = { job_id: "old", pen_id: "A-01", camera_id: "C-01",
    observed_at: "2026-10-21T09:00:00+08:00", kind: "feeding", reverse: false,
    geometry: [0.2, 0.2, 0.7, 0.7], metrics: { entries: 2, dwell_seconds: 3, hourly: [] } };
  let submitted: Record<string, unknown> | null = null;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (init?.method === "POST") {
      submitted = JSON.parse(String(init.body));
      return { ok: true, json: async () => ({ ...submitted, job_id: "new", metrics: { entries: 1, dwell_seconds: 2, hourly: [] } }) } as Response;
    }
    return { ok: true, json: async () => url.includes("/history") ? [previous] : [] } as Response;
  });
  const user = userEvent.setup();
  render(<SpatialAnalysisPanel jobId="new" videoPath="new/tracked.mp4" />);
  await user.type(screen.getByLabelText("圈舍编号"), "A-01");
  await user.type(screen.getByLabelText("固定机位编号"), "C-01");
  await user.click(screen.getByRole("button", { name: "沿用该机位上次画区" }));
  await user.click(screen.getByRole("button", { name: "保存采食区统计" }));
  expect(submitted).toMatchObject({ pen_id: "A-01", camera_id: "C-01",
    kind: "feeding", geometry: [0.2, 0.2, 0.7, 0.7] });
  expect(await screen.findByText(/进入区域 1 次/)).toBeInTheDocument();
});
