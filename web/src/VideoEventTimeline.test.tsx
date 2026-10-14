import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import VideoEventTimeline from "./VideoEventTimeline";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows timestamped evidence, seeks the result video and links a clip", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true, json: async () => [{
      id: 0, kind: "alert", time_seconds: 12.5, track_id: 7,
      label: "持续低活动", detail: "连续静止",
    }],
  } as Response);
  const onSeek = vi.fn();
  const user = userEvent.setup();
  render(<VideoEventTimeline jobId="job-1" onSeek={onSeek} />);
  await user.click(await screen.findByRole("button", { name: "跳转到 00:12 持续低活动" }));
  expect(onSeek).toHaveBeenCalledWith(12.5);
  expect(screen.getByRole("link", { name: "下载证据片段" })).toHaveAttribute(
    "href", "/api/jobs/job-1/events/0/clip",
  );
});
