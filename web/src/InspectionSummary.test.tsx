import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import InspectionSummary from "./InspectionSummary";
import type { VideoJob } from "./api";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows a video evidence summary with human review and handling", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => ({ ok: true, json: async () =>
    String(input).includes("action-tasks") ? [{ id: "a1", title: "检查采食", status: "followup",
      assignee: "李四", track_id: 7, time_seconds: 12, due_at: "2026-10-23T09:00:00+08:00",
      updates: [{ id: "u1", note: "明日复查", status: "followup", actor: "李四" }] }] :
      [{ id: "r1", issue_type: "health_concern", verdict: "uncertain", note: "现场待核查" }],
  }) as Response);
  const job = { id: "job-1", status: "completed", progress: 1,
    created_at: "2026-10-22T10:00:00+08:00", result: { species: "cattle", frame_count: 210,
      tracked_cattle: 3, alert_count: 2, video_path: "job-1/result.mp4" } } as VideoJob;
  render(<InspectionSummary job={job} />);
  await userEvent.setup().click(screen.getByRole("button", { name: "生成巡检摘要" }));
  expect(await screen.findByText(/检查采食/)).toBeInTheDocument();
  expect(screen.getByText(/明日复查/)).toBeInTheDocument();
  expect(screen.getByText(/现场待核查/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看结果视频" })).toHaveAttribute("href", "/media/results/job-1/result.mp4");
  expect(screen.getByText(/不能据此诊断疾病/)).toBeInTheDocument();
});
