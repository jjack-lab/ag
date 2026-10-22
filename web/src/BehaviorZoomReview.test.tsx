import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import BehaviorZoomReview from "./BehaviorZoomReview";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows original and track crop, then saves a human-only behavior review", async () => {
  let saved: Record<string, unknown> | null = null;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input) === "/api/jobs/job-1/reviews" && init?.method === "POST") {
      saved = JSON.parse(String(init.body));
      return { ok: true, json: async () => ({ id: "review-1", ...saved }) } as Response;
    }
    throw new Error(`Unexpected request: ${input}`);
  });
  const user = userEvent.setup();
  render(<BehaviorZoomReview jobId="job-1" videoPath="job-1/tracked.mp4" trackIds={[7, 8]} />);
  expect(screen.getByAltText("原视频全画面")).toHaveAttribute("src", expect.stringContaining("crop=false"));
  expect(screen.getByAltText("Track ID 局部放大")).toHaveAttribute("src", expect.stringContaining("track_id=7"));
  await user.selectOptions(screen.getByLabelText("放大查看的 Track ID"), "8");
  await user.click(screen.getByRole("button", { name: "后移 0.5 秒" }));
  expect(screen.getByAltText("Track ID 局部放大")).toHaveAttribute("src", expect.stringContaining("time_seconds=0.5"));
  await user.selectOptions(screen.getByLabelText("人工观察结论"), "walking");
  await user.type(screen.getByLabelText("复核说明"), "连续画面可见行走");
  await user.click(screen.getByRole("button", { name: "保存放大复核" }));
  expect(saved).toMatchObject({ issue_type: "other", verdict: "confirmed", track_id: 8, time_seconds: 0.5 });
  expect(JSON.stringify(saved)).toContain("行走");
  expect(await screen.findByText("已保存人工复核")).toBeInTheDocument();
});
