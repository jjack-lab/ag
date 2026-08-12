import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const dashboard = {
  monitored_cattle: 5,
  high_risk_cattle: 1,
  open_alerts: 2,
  model_status: "ready",
};

const alerts = [
  {
    id: "a1",
    cattle_id: "7",
    risk_type: "still",
    level: "medium",
    reason: "持续低活动",
    suggestion: "现场复核",
    occurred_at: "2026-07-29T12:00:00+08:00",
    confidence: 0.9,
    status: "open",
  },
];

function response(payload: unknown, ok = true) {
  return {
    ok,
    json: async () => payload,
  } as Response;
}

describe("AgriNebula application", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      throw new Error(`Unexpected request: ${url}`);
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("presents a clear cattle-health entry", () => {
    render(<App />);

    expect(screen.getByText("看见每一头牛的变化")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入健康控制中心" })).toBeInTheDocument();
  });

  it("keeps technical parameters out of the operator navigation", () => {
    render(<App />);

    expect(screen.getAllByText("今日工作台").length).toBeGreaterThan(0);
    expect(screen.getAllByText("健康告警").length).toBeGreaterThan(0);
    expect(screen.queryByText("IOU")).not.toBeInTheDocument();
  });

  it("uploads an image and shows the real recognition result", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      if (url === "/api/recognition/image") {
        return response({
          kind: "image",
          status: "completed",
          detection_count: 9,
          source_url: "/media/uploads/cattle.jpg",
          result_url: "/media/results/cattle_detected.jpg",
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    const user = userEvent.setup();
    render(<App />);

    const file = new File(["cattle"], "cattle.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText("选择牛只图片"), {
      target: { files: [file] },
    });
    await user.click(screen.getByRole("button", { name: "开始图片识别" }));

    expect(await screen.findByText("识别到 9 头牛")).toBeInTheDocument();
    expect(screen.getByAltText("牛只图片识别结果")).toHaveAttribute(
      "src",
      "/media/results/cattle_detected.jpg",
    );
  });

  it("renders dashboard metrics and alerts returned by the API", async () => {
    render(<App />);

    expect(await screen.findByText("牛 7")).toBeInTheDocument();
    expect(screen.getByText("持续低活动")).toBeInTheDocument();
    expect(screen.getByTestId("monitored-cattle")).toHaveTextContent("5");
    expect(screen.getByTestId("open-alerts")).toHaveTextContent("2");
  });

  it("creates and polls a video tracking job", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      if (url === "/api/jobs/video" && init?.method === "POST") {
        return response({
          id: "job-1",
          status: "queued",
          progress: 0,
        });
      }
      if (url === "/api/jobs/job-1") {
        return response({
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
            alert_count: 1,
          },
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "视频识别" }));
    fireEvent.change(screen.getByLabelText("选择牛只视频"), {
      target: {
        files: [new File(["video"], "cattle.mp4", { type: "video/mp4" })],
      },
    });
    const studio = screen.getByRole("region", {
      name: "上传文件，直接查看识别结果",
    });
    await user.click(
      within(studio).getByRole("button", { name: "开始视频识别" }),
    );

    expect(await screen.findByText("已追踪 3 头牛")).toBeInTheDocument();
    expect(screen.getByLabelText("牛只视频追踪结果")).toHaveAttribute(
      "src",
      "/media/results/job-1/cattle_tracked.mp4",
    );
  });

  it("clears the selected file when switching recognition modes", async () => {
    const user = userEvent.setup();
    render(<App />);
    const file = new File(["cattle"], "cattle.jpg", { type: "image/jpeg" });
    const imageInput = screen.getByLabelText("选择牛只图片") as HTMLInputElement;
    fireEvent.change(imageInput, { target: { files: [file] } });

    await user.click(screen.getByRole("button", { name: "视频识别" }));

    const videoInput = screen.getByLabelText("选择牛只视频") as HTMLInputElement;
    expect(videoInput).not.toBe(imageInput);
    expect(videoInput.files).toHaveLength(0);
  });
  it("keeps a visible video recognition action in the overview", () => {
    render(<App />);

    expect(screen.getByRole("button", { name: "开始视频识别" })).toBeInTheDocument();
  });
});
