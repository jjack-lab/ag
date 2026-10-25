import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import type { VideoJob } from "./api";
import RecognitionStudio from "./RecognitionStudio";

const completedJob: VideoJob = {
  id: "job-1",
  status: "completed",
  progress: 1,
  result: {
    video_path: "job-1/cattle_tracked.mp4",
    trajectory_csv: "job-1/cattle_tracks.csv",
    alert_csv: "job-1/cattle_alerts.csv",
    health_summary_csv: "job-1/cattle_health.csv",
    health_report_html: "job-1/cattle_health.html",
    frame_count: 30,
    tracked_cattle: 3,
    alert_count: 0,
    species: "cattle",
    track_ids: [1, 2, 3],
    health_evidence: [],
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("opens an externally selected completed video job", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (
      url === "/api/jobs/video" ||
      url === "/api/jobs/job-1/reviews" ||
      url === "/api/jobs/job-1/events" ||
      url === "/api/jobs/job-1/corrections" ||
      url === "/api/jobs/job-1/animal-links" ||
      url === "/api/inventory-checks?job_id=job-1"
    ) {
      return { ok: true, json: async () => [] } as Response;
    }
    if (url === "/api/experiments/cross-domain-behavior") {
      return { ok: true, json: async () => ({ status: "not_run" }) } as Response;
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<RecognitionStudio requestedJob={completedJob} />);

  expect(await screen.findByText("视频内 Track ID：3 个")).toBeInTheDocument();
  expect(screen.getByLabelText("牛只视频追踪结果")).toHaveAttribute(
    "src",
    "/media/results/job-1/cattle_tracked.mp4",
  );
});

it("tells the operator how to restore the demo when the recorded task is missing", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/jobs/202d89f9aaad433480d8570bd90c3d41") {
      return { ok: false, status: 404, json: async () => ({ detail: "任务不存在" }) } as Response;
    }
    if (url === "/api/jobs/video") return { ok: true, json: async () => [] } as Response;
    if (url === "/api/experiments/cross-domain-behavior") {
      return { ok: true, json: async () => ({ status: "not_run" }) } as Response;
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<RecognitionStudio />);
  await userEvent.click(screen.getByRole("button", { name: "打开演示视频" }));
  expect(await screen.findByText(/VITE_CATTLE_DEMO_JOB_ID/)).toBeInTheDocument();
  expect(screen.getByText(/重新上传/)).toBeInTheDocument();
});

it("opens the filmed cattle development demo with clear provenance", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/jobs/202d89f9aaad433480d8570bd90c3d41") {
      return { ok: true, json: async () => completedJob } as Response;
    }
    if (
      url === "/api/jobs/video" ||
      url === "/api/jobs/job-1/reviews" ||
      url === "/api/jobs/job-1/events" ||
      url === "/api/jobs/job-1/corrections" ||
      url === "/api/jobs/job-1/animal-links" ||
      url === "/api/inventory-checks?job_id=job-1"
    ) return { ok: true, json: async () => [] } as Response;
    if (url === "/api/experiments/cross-domain-behavior") {
      return { ok: true, json: async () => ({ status: "not_run" }) } as Response;
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<RecognitionStudio />);
  expect(screen.getByText(/素材参与过开发，不代表新牧场独立验收/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "打开演示视频" }));
  expect(await screen.findByLabelText("牛只视频追踪结果")).toHaveAttribute(
    "src", "/media/results/job-1/cattle_tracked.mp4",
  );
});
