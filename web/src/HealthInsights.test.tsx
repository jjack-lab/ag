import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import HealthInsights from "./HealthInsights";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const assessmentPayload = () => ({
  job_id: "job-1", model: { type: "rule_based", name: "牛只轨迹规则型健康风险筛查", behavior_model_status: "ready", behavior_model_version: "v1", score_basis: "轨迹规则" },
  summary: { track_count: 2, attention_count: 1, review_count: 1 },
  tracks: [
    { track_id: 7, risk_score: 40, risk_level: "medium", priority: "medium",
      priority_reasons: [{ label: "持续低活动", time_seconds: 20, detail: "持续低速", suggestion: "人工查看" }],
      review_hint: "先看 20.0 秒附近，再回看前后约 3 秒。",
      observations: [{ type: "still", label: "持续低活动", time_seconds: 20, detail: "持续低速", suggestion: "人工查看" }],
      behaviors: [{ behavior_name: "walking", behavior_display_name: "行走", duration_seconds: 4, eligible_ratio: 0.8 }],
      uncertain_duration_seconds: 1, reviews: [{ id: "r1", verdict: "uncertain", time_seconds: 20, note: "仍被遮挡" }],
      analysis: "规则提示与行走摘要需人工核查。" },
    { track_id: 8, risk_score: 0, risk_level: "normal", priority: "none", priority_reasons: [],
      review_hint: "该轨迹未触发规则提示，可按需抽看原视频，不必优先处理。",
      observations: [], behaviors: [], uncertain_duration_seconds: 0, reviews: [],
      analysis: "本次轨迹未触发规则提示。" },
  ],
});

it("shows review priority and evidence instead of a bare rule score", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/jobs/video") return { ok: true, json: async () => [
      { id: "job-1", status: "completed", created_at: "2026-10-22T10:00:00+08:00", result: { species: "cattle" } },
    ] } as Response;
    if (url === "/api/jobs/job-1/health-assessment") return { ok: true, json: async () => assessmentPayload() } as Response;
    throw new Error(`Unexpected request: ${url}`);
  });

  const { container } = render(<HealthInsights />);
  expect(await screen.findByText("持续低活动")).toBeInTheDocument();
  expect(screen.getByText("行走")).toBeInTheDocument();
  expect(screen.getByText(/仍被遮挡/)).toBeInTheDocument();
  expect(screen.getByText(/不能判断具体疾病/)).toBeInTheDocument();
  expect(screen.getAllByText("中 · 优先核查").length).toBeGreaterThan(0);
  expect(screen.getByRole("heading", { name: "为什么被标出来" })).toBeInTheDocument();
  expect(screen.getByText(/先看 20.0 秒附近/)).toBeInTheDocument();
  expect(screen.queryByText("规则分数")).not.toBeInTheDocument();
  expect(container.querySelector(".health-score-ring")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "生成健康报告" }));
  expect(screen.getByRole("dialog", { name: "牛只健康观察报告" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "关闭报告" }));
  await userEvent.click(screen.getByRole("button", { name: /Track ID 8/ }));
  expect(screen.getByText(/本次轨迹未形成规则告警/)).toBeInTheDocument();
  expect(screen.getAllByText("无 · 未触发规则").length).toBeGreaterThan(0);
});
