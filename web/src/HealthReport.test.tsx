import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { HealthAssessment, VideoJob } from "./api";
import HealthReport from "./HealthReport";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("renders a traceable health report and invokes browser PDF printing", async () => {
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  const job = { id: "job-1", status: "completed", progress: 1,
    updated_at: "2026-10-22T10:00:00+08:00",
    result: { species: "cattle", frame_count: 210, video_path: "job-1/tracked.mp4" },
  } as VideoJob;
  const assessment = { job_id: "job-1",
    model: { type: "rule_based", name: "牛只轨迹规则型健康风险筛查", behavior_model_status: "ready", behavior_model_version: "v1", score_basis: "轨迹规则" },
    summary: { track_count: 1, attention_count: 1, review_count: 1 },
    tracks: [{ track_id: 7, risk_score: 40, risk_level: "medium", analysis: "规则提示与行为需人工核查。",
      observations: [{ type: "still", label: "持续低活动", time_seconds: 20, confidence: 0.8, detail: "低速", suggestion: "人工查看" }],
      behaviors: [{ track_id: 7, behavior_name: "walking", behavior_display_name: "行走", duration_seconds: 4, eligible_ratio: 1, uncertain_duration_seconds: 1, model_version: "v1" }],
      uncertain_duration_seconds: 1,
      reviews: [{ id: "r1", verdict: "uncertain", note: "遮挡", time_seconds: 20, created_at: "2026-10-22T10:01:00+08:00" }],
    }],
  } as HealthAssessment;
  render(<HealthReport assessment={assessment} job={job} generatedAt="2026-10-22T10:05:00+08:00" onClose={() => {}} />);

  const report = screen.getByRole("dialog", { name: "牛只健康观察报告" });
  expect(within(report).getAllByText(/job-1/).length).toBeGreaterThan(0);
  expect(within(report).getByText(/规则提示与行为需人工核查/)).toBeInTheDocument();
  expect(within(report).getByText(/持续低活动/)).toBeInTheDocument();
  expect(within(report).getAllByText(/行走 4.0 秒/).length).toBeGreaterThan(0);
  expect(within(report).getByText(/遮挡/)).toBeInTheDocument();
  expect(within(report).getByText(/不能用于疾病诊断/)).toBeInTheDocument();
  await userEvent.click(within(report).getByRole("button", { name: "打印或保存 PDF" }));
  expect(print).toHaveBeenCalledOnce();
});
