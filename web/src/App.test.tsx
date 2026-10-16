import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const dashboard = {
  latest_cattle_track_count: 5,
  latest_cattle_processed_at: "2026-10-14T10:01:00+08:00",
  high_risk_alerts: 1,
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

const completedInventoryJob = {
  id: "video-1",
  status: "completed",
  progress: 1,
  result: {
    video_path: "video-1/cattle_tracked.mp4",
    trajectory_csv: "video-1/cattle_tracks.csv",
    alert_csv: "video-1/cattle_alerts.csv",
    health_summary_csv: "video-1/cattle_health.csv",
    health_report_html: "video-1/cattle_health.html",
    frame_count: 30,
    tracked_cattle: 3,
    alert_count: 0,
    species: "cattle",
    track_ids: [1, 2, 3],
    health_evidence: [],
  },
};

const inventoryChecks = [{
  id: "check-1", job_id: "video-1", species: "cattle", pen_id: "A-1",
  expected_count: 3, observed_count: 3, current_count: 3, difference: 0,
  baseline_source: "台账", coverage: "complete", coverage_note: "完整覆盖",
  operator_name: "张三", observed_at: "2026-10-16T08:00:00+08:00",
  created_at: "2026-10-16T08:00:00+08:00", status: "preliminary_match",
  rechecks: [], lost_count: null, video_track_count: 3, verification_status: "user_recorded",
}];

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

    expect(await screen.findByText("识别到 9 个目标")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "识别类别" }), { target: { value: "0" } });
    expect(screen.getByText("识别到 9 个目标")).toBeInTheDocument();
    expect(screen.getByAltText("牛只图片识别结果")).toHaveAttribute(
      "src",
      "/media/results/cattle_detected.jpg",
    );
  });

  it("renders dashboard metrics and alerts returned by the API", async () => {
    render(<App />);

    expect(await screen.findByText("视频内 ID 7")).toBeInTheDocument();
    expect(screen.getByText("持续低活动")).toBeInTheDocument();
    expect(screen.getByTestId("monitored-cattle")).toHaveTextContent("5");
    expect(screen.getByText("最近牛视频 Track ID 数")).toBeInTheDocument();
    expect(screen.getByText(/处理时间：2026/)).toBeInTheDocument();
    expect(screen.getByText("历史未处理规则提示")).toBeInTheDocument();
    expect(screen.getByTestId("open-alerts")).toHaveTextContent("2");
  });

  it("shows no record when no cattle video was processed", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response({
        ...dashboard, latest_cattle_track_count: null, latest_cattle_processed_at: null,
      });
      if (url.startsWith("/api/alerts")) return response(alerts);
      throw new Error(`Unexpected request: ${url}`);
    });
    render(<App />);
    expect(await screen.findByTestId("monitored-cattle")).toHaveTextContent("暂无记录");
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

    expect(await screen.findByText("视频内 Track ID：3 个")).toBeInTheDocument();
    expect(screen.getByLabelText("牛只视频追踪结果")).toHaveAttribute(
      "src",
      "/media/results/job-1/cattle_tracked.mp4",
    );
    expect(screen.getByLabelText("跟踪算法")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "下载结果视频" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "告警 CSV" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "健康汇总 CSV" })).toBeInTheDocument();
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
  it("switches every operator navigation button to a focused view", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "实时监控" }));
    expect(screen.getByRole("heading", { name: "实时监控" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "实时监控" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    await user.click(screen.getByRole("button", { name: "健康告警" }));
    expect(screen.getByRole("heading", { name: "全部健康告警" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "牛只档案" }));
    expect(screen.getByRole("heading", { name: "牛只档案" })).toBeInTheDocument();
    expect(screen.getByText(/视频内 Track ID 不能直接作为牛只档案编号/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "数据分析" }));
    expect(screen.getByRole("heading", { name: "数据分析" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "今日工作台" }));
    expect(screen.getByRole("heading", { name: "视频任务与历史规则概览" })).toBeInTheDocument();
  });

  it("opens the full alerts view from 查看全部", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "查看全部" }));

    expect(screen.getByRole("heading", { name: "全部健康告警" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "健康告警" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("opens the monitor view from the overview video action", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "开始视频识别" }));

    expect(screen.getByRole("heading", { name: "实时监控" })).toBeInTheDocument();
  });

  it("opens completed video evidence from the global inventory list", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      if (url === "/api/inventory-checks") return response(inventoryChecks);
      if (url === "/api/jobs/video-1") return response(completedInventoryJob);
      if (
        url === "/api/jobs/video" ||
        url === "/api/jobs/video-1/reviews" ||
        url === "/api/jobs/video-1/events" ||
        url === "/api/jobs/video-1/corrections" ||
        url === "/api/jobs/video-1/animal-links"
      ) return response([]);
      if (url === "/api/experiments/cross-domain-behavior") return response({ status: "not_run" });
      throw new Error(`Unexpected request: ${url}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "圈舍盘点" }));
    await user.click(await screen.findByRole("button", { name: "打开视频证据" }));

    expect(await screen.findByRole("heading", { name: "实时监控" })).toBeInTheDocument();
    expect(await screen.findByLabelText("牛只视频追踪结果")).toHaveAttribute(
      "src",
      "/media/results/video-1/cattle_tracked.mp4",
    );
  });

  it("opens the default recognition workspace after leaving inventory evidence", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      if (url === "/api/inventory-checks") return response(inventoryChecks);
      if (url === "/api/jobs/video-1") return response(completedInventoryJob);
      if (
        url === "/api/jobs/video" ||
        url === "/api/jobs/video-1/reviews" ||
        url === "/api/jobs/video-1/events" ||
        url === "/api/jobs/video-1/corrections" ||
        url === "/api/jobs/video-1/animal-links"
      ) return response([]);
      if (url === "/api/experiments/cross-domain-behavior") return response({ status: "not_run" });
      throw new Error(`Unexpected request: ${url}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "圈舍盘点" }));
    await user.click(await screen.findByRole("button", { name: "打开视频证据" }));
    expect(await screen.findByLabelText("牛只视频追踪结果")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "健康告警" }));
    await user.click(screen.getByRole("button", { name: "实时监控" }));

    expect(screen.getByLabelText("选择牛只图片")).toBeInTheDocument();
    expect(screen.queryByLabelText("牛只视频追踪结果")).not.toBeInTheDocument();
  });

  it("keeps the inventory view open when its video task is unavailable", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      if (url === "/api/inventory-checks") return response(inventoryChecks);
      if (url === "/api/jobs/video-1") {
        return response({ id: "video-1", status: "failed", progress: 1, result: null });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "圈舍盘点" }));
    await user.click(await screen.findByRole("button", { name: "打开视频证据" }));

    expect(await screen.findByText("视频任务尚未完成，暂不能打开证据")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "圈舍存栏核对" })).toBeInTheDocument();
  });

  it.each([
    ["null", null],
    ["missing id", { status: "completed", progress: 1, result: completedInventoryJob.result }],
    ["missing status", { id: "video-1", progress: 1, result: completedInventoryJob.result }],
    ["unknown status", { id: "video-1", status: "unknown", progress: 1, result: null }],
    ["missing progress", { id: "video-1", status: "failed", result: null }],
    ["non-finite progress", { id: "video-1", status: "failed", progress: Number.NaN, result: null }],
    ["completed without a result object", { id: "video-1", status: "completed", progress: 1, result: null }],
    ["completed with an empty result", { id: "video-1", status: "completed", progress: 1, result: {} }],
  ])("keeps inventory open for malformed video evidence: %s", async (_label, payload) => {
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      if (url === "/api/inventory-checks") return response(inventoryChecks);
      if (url === "/api/jobs/video-1") return response(payload);
      throw new Error(`Unexpected request: ${url}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "圈舍盘点" }));
    await user.click(await screen.findByRole("button", { name: "打开视频证据" }));

    expect(await screen.findByText("视频证据加载失败")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "圈舍存栏核对" })).toBeInTheDocument();
    expect(screen.queryByText("视频任务尚未完成，暂不能打开证据")).not.toBeInTheDocument();
  });

  it("does not let a pending evidence request override newer workspace navigation", async () => {
    let resolveJob!: (value: Response) => void;
    let jobResolved = false;
    const pendingJob = new Promise<Response>((resolve) => { resolveJob = resolve; });
    pendingJob.then(() => { jobResolved = true; });
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      if (url === "/api/inventory-checks") return response(inventoryChecks);
      if (url === "/api/jobs/video-1") return pendingJob;
      throw new Error(`Unexpected request: ${url}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "圈舍盘点" }));
    await user.click(await screen.findByRole("button", { name: "打开视频证据" }));
    await user.click(screen.getByRole("button", { name: "健康告警" }));
    resolveJob(response(completedInventoryJob));

    await waitFor(() => {
      expect(jobResolved).toBe(true);
      expect(screen.getByRole("heading", { name: "全部健康告警" })).toBeInTheDocument();
    });
  });

  it("keeps the last inventory evidence click when requests finish out of order", async () => {
    let resolveFirst!: (value: Response) => void;
    let resolveSecond!: (value: Response) => void;
    let firstResolved = false;
    const firstJob = new Promise<Response>((resolve) => { resolveFirst = resolve; });
    const secondJob = new Promise<Response>((resolve) => { resolveSecond = resolve; });
    firstJob.then(() => { firstResolved = true; });
    const secondCheck = { ...inventoryChecks[0], id: "check-2", job_id: "video-2", pen_id: "A-2" };
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/dashboard")) return response(dashboard);
      if (url.startsWith("/api/alerts")) return response(alerts);
      if (url === "/api/inventory-checks") return response([...inventoryChecks, secondCheck]);
      if (url === "/api/jobs/video-1") return firstJob;
      if (url === "/api/jobs/video-2") return secondJob;
      if (
        url === "/api/jobs/video" ||
        url === "/api/jobs/video-2/reviews" ||
        url === "/api/jobs/video-2/events" ||
        url === "/api/jobs/video-2/corrections" ||
        url === "/api/jobs/video-2/animal-links"
      ) return response([]);
      if (url === "/api/experiments/cross-domain-behavior") return response({ status: "not_run" });
      throw new Error(`Unexpected request: ${url}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "圈舍盘点" }));
    const firstCard = (await screen.findByRole("heading", { name: "A-1 · 牛" })).closest("article");
    const secondCard = screen.getByRole("heading", { name: "A-2 · 牛" }).closest("article");
    if (!firstCard || !secondCard) throw new Error("Inventory cards were not rendered");
    await user.click(within(firstCard).getByRole("button", { name: "打开视频证据" }));
    await user.click(within(secondCard).getByRole("button", { name: "打开视频证据" }));
    resolveSecond(response({
      ...completedInventoryJob,
      id: "video-2",
      result: { ...completedInventoryJob.result, video_path: "video-2/cattle_tracked.mp4" },
    }));

    expect(await screen.findByLabelText("牛只视频追踪结果")).toHaveAttribute(
      "src", "/media/results/video-2/cattle_tracked.mp4",
    );
    resolveFirst(response(completedInventoryJob));
    await waitFor(() => {
      expect(firstResolved).toBe(true);
      expect(screen.getByLabelText("牛只视频追踪结果")).toHaveAttribute(
        "src", "/media/results/video-2/cattle_tracked.mp4",
      );
    });
  });

  it("toggles actionable alert details", async () => {
    const user = userEvent.setup();
    render(<App />);

    const alertButton = await screen.findByRole("button", {
      name: /视频内 ID 7，持续低活动，中风险/,
    });
    await user.click(alertButton);

    expect(screen.getByText("处置建议：现场复核")).toBeInTheDocument();
    expect(screen.getByText("置信度 90%")).toBeInTheDocument();
    expect(alertButton).toHaveAttribute("aria-expanded", "true");

    await user.click(alertButton);

    expect(screen.queryByText("处置建议：现场复核")).not.toBeInTheDocument();
    expect(alertButton).toHaveAttribute("aria-expanded", "false");
  });

});
