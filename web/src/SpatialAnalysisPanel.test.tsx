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
    if (url.includes("/audit")) return { ok: true, json: async () => ({
      events: [], audit: { verdicts: {}, missed: [], coverage_confirmed: false },
      summary: { automatic: 0, reviewed: 0, correct: 0, false_positive: 0,
        wrong_direction: 0, missed: 0, complete: false, precision: null, recall: null },
    }) } as Response;
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

it("reviews a gate crossing and adds a missed event from the video panel", async () => {
  const report = { job_id: "job-1", pen_id: "A-01", camera_id: "G-01",
    observed_at: "2026-10-22T09:00:00+08:00", kind: "gate", reverse: false,
    geometry: [0.2, 0.5, 0.8, 0.5], duration_seconds: 20, alerts: [],
    metrics: { enter: 1, leave: 0, events: [{ track_id: 7, time_seconds: 3, direction: "enter" }] } };
  let reviewed = false;
  let missed = false;
  let complete = false;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/spatial-reports")) return { ok: true, json: async () => [report] } as Response;
    if (url.includes("/audit/verdicts") && init?.method === "POST") reviewed = true;
    if (url.includes("/audit/missed") && init?.method === "POST") missed = true;
    if (url.includes("/audit/complete") && init?.method === "POST") complete = true;
    if (url.includes("/audit")) return { ok: true, json: async () => ({
      events: report.metrics.events, audit: { verdicts: reviewed ? { "0": { verdict: "correct" } } : {}, missed: missed ? [{ time_seconds: 5 }] : [], coverage_confirmed: false },
      summary: { automatic: 1, reviewed: reviewed ? 1 : 0, correct: reviewed ? 1 : 0,
        false_positive: 0, wrong_direction: 0, missed: missed ? 1 : 0, complete,
        precision: complete ? 1 : null, recall: complete ? 0.5 : null,
        verified_counts: complete ? { enter: 2, leave: 0 } : null },
    }) } as Response;
    return { ok: true, json: async () => [] } as Response;
  });
  const user = userEvent.setup();
  render(<SpatialAnalysisPanel jobId="job-1" videoPath="job-1/tracked.mp4" />);
  await user.click(screen.getByRole("button", { name: "栏门线" }));
  expect(await screen.findByText(/人工核对 0\/1/)).toBeInTheDocument();
  await user.type(screen.getByLabelText("核对人"), "张三");
  await user.type(screen.getByLabelText("核对备注"), "完整回看确认");
  await user.click(screen.getByRole("button", { name: "确认正确" }));
  expect(await screen.findByText(/人工核对 1\/1/)).toBeInTheDocument();
  await user.type(screen.getByLabelText("漏计时间（秒）"), "5");
  await user.type(screen.getByLabelText("漏计备注"), "遮挡后进入");
  await user.click(screen.getByRole("button", { name: "补录漏计" }));
  expect(await screen.findByText(/漏计 1/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "确认已回看完整视频" }));
  expect(await screen.findByText(/人工核对计数：进入 2 次，离开 0 次/)).toBeInTheDocument();
});

it("warns that an empty track result cannot establish an empty feeding area", async () => {
  const report = { job_id: "job-2", pen_id: "A-01", camera_id: "C-01",
    observed_at: "2026-10-22T09:00:00+08:00", kind: "feeding", reverse: false,
    geometry: [0.1, 0.2, 0.9, 0.6], duration_seconds: 10, alerts: [],
    tracking_status: "no_tracks", metrics: { entries: 0, dwell_seconds: 0, events: [], hourly: [] } };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => ({ ok: true,
    json: async () => String(input).endsWith("/spatial-reports") ? [report] : {
      events: [], audit: { verdicts: {}, missed: [], coverage_confirmed: false },
      summary: { automatic: 0, reviewed: 0, correct: 0, false_positive: 0,
        wrong_direction: 0, missed: 0, complete: false, precision: null, recall: null, verified_counts: null },
    },
  }) as Response);
  render(<SpatialAnalysisPanel jobId="job-2" videoPath="job-2/tracked.mp4" />);
  expect(await screen.findByText(/整段视频没有检测轨迹/)).toBeInTheDocument();
});
