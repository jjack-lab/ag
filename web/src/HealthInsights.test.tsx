import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import HealthInsights from "./HealthInsights";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows real rule score with behavior context and switches the selected track", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/jobs/video") return { ok: true, json: async () => [
      { id: "job-1", status: "completed", created_at: "2026-10-22T10:00:00+08:00", result: { species: "cattle" } },
    ] } as Response;
    if (url === "/api/jobs/job-1/health-assessment") return { ok: true, json: async () => ({
      job_id: "job-1", model: { type: "rule_based", behavior_model_status: "ready", behavior_model_version: "v1" },
      summary: { track_count: 2, attention_count: 1, review_count: 1 },
      tracks: [
        { track_id: 7, risk_score: 40, risk_level: "medium", observations: [{ type: "still", label: "持续低活动", time_seconds: 20, detail: "持续低速", suggestion: "人工查看" }], behaviors: [{ behavior_name: "walking", behavior_display_name: "行走", duration_seconds: 4, eligible_ratio: 0.8 }], uncertain_duration_seconds: 1, reviews: [{ id: "r1", verdict: "uncertain", time_seconds: 20, note: "仍被遮挡" }], analysis: "规则提示与行走摘要需人工核查。" },
        { track_id: 8, risk_score: 0, risk_level: "normal", observations: [], behaviors: [], uncertain_duration_seconds: 0, reviews: [], analysis: "本次轨迹未触发规则提示。" },
      ],
    }) } as Response;
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<HealthInsights />);
  expect(await screen.findByText("持续低活动")).toBeInTheDocument();
  expect(screen.getByText("行走")).toBeInTheDocument();
  expect(screen.getByText(/仍被遮挡/)).toBeInTheDocument();
  expect(screen.getByText(/不能判断具体疾病/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Track ID 8/ }));
  expect(screen.getByText(/本次轨迹未形成规则告警/)).toBeInTheDocument();
});
