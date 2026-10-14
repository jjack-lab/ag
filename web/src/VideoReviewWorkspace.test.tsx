import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import RecognitionStudio from "./RecognitionStudio";

const job = {
  id: "job-1", status: "completed", progress: 1,
  created_at: "2026-10-14T10:00:00+08:00",
  result: {
    species: "cattle", video_path: "job-1/tracked.mp4", trajectory_csv: "job-1/tracks.csv",
    track_ids: [7],
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
    if (url === "/api/jobs/job-1/animal-links" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return { ok: true, json: async () => ({ job_id: "job-1", species: "cattle", linked_at: "2026-10-14T11:01:00+08:00", ...body }) } as Response;
    }
    if (url === "/api/jobs/job-1/animal-links") return { ok: true, json: async () => [] } as Response;
    if (url === "/api/animals/C-023") return { ok: true, json: async () => ({
      animal_id: "C-023", species: "cattle", followups: [], visits: [{
        job_id: "job-1", track_id: 7, animal_id: "C-023", species: "cattle",
        linked_at: "2026-10-14T11:01:00+08:00", recorded_at: job.created_at,
        health_evidence: null, reviews: [],
      }],
    }) } as Response;
    if (url === "/api/animals/C-023/followups" && init?.method === "POST") {
      return { ok: true, json: async () => ({
        id: "followup-1", animal_id: "C-023", verification_status: "user_recorded",
        created_at: "2026-10-14T12:00:00+08:00", ...JSON.parse(String(init.body)),
      }) } as Response;
    }
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
  await user.selectOptions(screen.getByLabelText("视频内 Track ID"), "7");
  await user.type(screen.getByLabelText("耳标或稳定个体编号"), "C-023");
  await user.click(screen.getByRole("button", { name: "确认关联" }));
  expect(await screen.findByText(/C-023 · 牛 · 1 次视频记录/)).toBeInTheDocument();
  await user.type(screen.getByLabelText("回访日期"), "2026-10-16");
  await user.type(screen.getByLabelText("回访说明"), "采食正常");
  await user.click(screen.getByRole("button", { name: "保存回访记录" }));
  expect(await screen.findByText("采食正常")).toBeInTheDocument();
});
