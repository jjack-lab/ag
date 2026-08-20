import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import RecognitionStudio from "./RecognitionStudio";

function response(payload: unknown) {
  return { ok: true, json: async () => payload } as Response;
}

async function completeVideoJob(result: Record<string, unknown>) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === "/api/jobs/video" && init?.method === "POST") {
      return response({ id: "job-1", status: "queued", progress: 0 });
    }
    if (url === "/api/jobs/job-1") {
      return response({
        id: "job-1",
        status: "completed",
        progress: 1,
        result: {
          video_path: "job-1/tracked.mp4",
          trajectory_csv: "job-1/tracks.csv",
          alert_csv: "job-1/alerts.csv",
          health_summary_csv: "job-1/health.csv",
          health_report_html: "job-1/health.html",
          frame_count: 30,
          tracked_cattle: 1,
          alert_count: 0,
          ...result,
        },
      });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  const user = userEvent.setup();
  render(<RecognitionStudio />);
  await user.click(screen.getByRole("button", { name: "视频识别" }));
  fireEvent.change(screen.getByLabelText("选择牛只视频"), {
    target: { files: [new File(["video"], "cattle.mp4", { type: "video/mp4" })] },
  });
  await user.click(screen.getByRole("button", { name: "开始视频识别" }));
  await screen.findByText("已追踪 1 头牛");
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("shows research behavior summaries and downloads", async () => {
  await completeVideoJob({
    behavior_csv: "job-1/behavior.csv",
    behavior_summary_csv: "job-1/behavior_summary.csv",
    behavior_model_status: "ready",
    behavior_model_version: "cvb-x3d-v1",
    behavior_model_error: null,
    behavior_summary: [
      {
        track_id: 7,
        behavior_name: "grazing",
        behavior_display_name: "采食",
        duration_seconds: 12.5,
        eligible_ratio: 0.625,
        uncertain_duration_seconds: 2.0,
        model_version: "cvb-x3d-v1",
      },
    ],
  });

  expect(screen.getByText("研究演示模型")).toBeInTheDocument();
  expect(screen.getByText("视频内 ID 7")).toBeInTheDocument();
  expect(screen.getByText("采食")).toBeInTheDocument();
  expect(screen.getByText("12.5 秒")).toBeInTheDocument();
  expect(screen.getByText("62.5%")).toBeInTheDocument();
  expect(screen.getByText("无法确定 2.0 秒")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "行为时间线 CSV" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "行为汇总 CSV" })).toBeInTheDocument();
});

it("keeps tracking results visible when behavior model is unavailable", async () => {
  await completeVideoJob({
    behavior_csv: null,
    behavior_summary_csv: null,
    behavior_model_status: "unavailable",
    behavior_model_version: null,
    behavior_model_error: "missing",
    behavior_summary: [],
  });

  expect(screen.getByText(/行为模型未加载/)).toBeInTheDocument();
  expect(screen.getByLabelText("牛只视频追踪结果")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "下载结果视频" })).toBeInTheDocument();
});
