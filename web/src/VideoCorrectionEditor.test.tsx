import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import VideoCorrectionEditor from "./VideoCorrectionEditor";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("draws a normalized missed detection box and saves the correction", async () => {
  let body: Record<string, unknown> | null = null;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (init?.method === "POST") {
      body = JSON.parse(String(init.body));
      return { ok: true, json: async () => ({ id: "fix-1", job_id: "job-1", species: "cattle",
        frame_index: 5, created_at: "now", ...body }) } as Response;
    }
    return { ok: true, json: async () => [] } as Response;
  });
  const user = userEvent.setup();
  render(<VideoCorrectionEditor jobId="job-1" videoPath="job-1/tracked.mp4" species="cattle" trackIds={[7]} />);
  const video = screen.getByLabelText("纠错视频画面") as HTMLVideoElement;
  vi.spyOn(video, "pause").mockImplementation(() => {});
  video.currentTime = 1;
  fireEvent.timeUpdate(video);
  await user.click(screen.getByRole("button", { name: "暂停并绘制漏检框" }));
  const layer = screen.getByLabelText("拖拽绘制漏检框");
  vi.spyOn(layer, "getBoundingClientRect").mockReturnValue({ left: 0, top: 0, width: 100, height: 100 } as DOMRect);
  fireEvent.pointerDown(layer, { clientX: 10, clientY: 20, pointerId: 1 });
  fireEvent.pointerUp(layer, { clientX: 40, clientY: 60, pointerId: 1 });
  await user.type(screen.getByLabelText("纠错说明"), "左侧一头漏检");
  await user.click(screen.getByRole("button", { name: "保存画面纠错" }));
  expect(body).toMatchObject({ kind: "missed_detection", time_seconds: 1,
    box: { x: 0.1, y: 0.2 } });
  const savedBox = body!.box as { width: number; height: number };
  expect(savedBox.width).toBeCloseTo(0.3);
  expect(savedBox.height).toBeCloseTo(0.4);
  expect(await screen.findByText("左侧一头漏检")).toBeInTheDocument();
});
