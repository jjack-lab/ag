import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import RecognitionStudio from "./RecognitionStudio";

const job = {
  id: "job-1", status: "completed", progress: 1,
  created_at: "2026-10-14T10:00:00+08:00",
  result: {
    species: "cattle", video_path: "job-1/tracked.mp4", trajectory_csv: "job-1/tracks.csv",
    alert_csv: "job-1/alerts.csv", health_summary_csv: "job-1/health.csv",
    health_report_html: "job-1/report.html", frame_count: 30,
    tracked_cattle: 2, alert_count: 1, health_evidence: [],
  },
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("reopens a completed job and saves a human review", async () => {
  let savedBody: Record<string, unknown> | null = null;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === "/api/jobs/video") return { ok: true, json: async () => [job] } as Response;
    if (url === "/api/jobs/job-1/reviews" && init?.method === "POST") {
      savedBody = JSON.parse(String(init.body));
      return { ok: true, json: async () => ({ id: "review-1", job_id: "job-1", species: "cattle", created_at: "2026-10-14T11:00:00+08:00", ...savedBody }) } as Response;
    }
    if (url === "/api/jobs/job-1/reviews") return { ok: true, json: async () => [] } as Response;
    throw new Error(`Unexpected request: ${url}`);
  });
  const user = userEvent.setup();
  render(<RecognitionStudio />);
  await user.click(screen.getByRole("button", { name: "视频识别" }));
  await user.click(await screen.findByRole("button", { name: /牛 · .*已完成 · 2 个视频内 ID/ }));
  expect(await screen.findByText("已追踪 2 头牛")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("问题类型"), "false_alert");
  await user.type(screen.getByLabelText("视频内 Track ID（可选）"), "7");
  await user.type(screen.getByLabelText("时间点，秒（可选）"), "12.5");
  await user.type(screen.getByLabelText("现场说明"), "现场未见异常");
  await user.click(screen.getByRole("button", { name: "保存复核记录" }));
  expect(await screen.findByText("误告警 · 已确认")).toBeInTheDocument();
  expect(savedBody).toMatchObject({ issue_type: "false_alert", track_id: 7, time_seconds: 12.5, note: "现场未见异常" });
});
