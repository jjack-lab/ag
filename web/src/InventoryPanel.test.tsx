import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import InventoryPanel from "./InventoryPanel";
import type { InventoryCheck, NewInventoryCheck, VideoJob } from "./api";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const job = { id: "video-1", status: "completed", progress: 1,
  result: { species: "cattle", tracked_cattle: 7 } } as VideoJob;

const historicalCheck = { id: "check-history", job_id: "video-1", species: "cattle", pen_id: "A-9",
  expected_count: 10, observed_count: 10, current_count: 10, difference: 0,
  baseline_source: "台账", coverage: "complete", coverage_note: "完整覆盖",
  operator_name: "张三", observed_at: new Date().toISOString(), created_at: new Date().toISOString(),
  status: "preliminary_match", rechecks: [], lost_count: null, video_track_count: 7,
  verification_status: "user_recorded" } as InventoryCheck;

it("reports the bound video job when opening evidence from the global inventory list", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => ({
    ok: true, json: async () => ({ items: [historicalCheck], total: 1, limit: 20, offset: 0 }),
  } as Response));
  const onOpenVideo = vi.fn();
  const user = userEvent.setup();

  render(<InventoryPanel onOpenVideo={onOpenVideo} />);

  await user.click(await screen.findByRole("button", { name: "打开视频证据" }));
  expect(onOpenVideo).toHaveBeenCalledWith("video-1");
});

it("pages global history and resets to the first page when filters change", async () => {
  const requests: string[] = [];
  const older = { ...historicalCheck, id: "older", pen_id: "B-2", job_id: "video-2", status: "verified_match" } as InventoryCheck;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    requests.push(url);
    const query = new URLSearchParams(url.split("?")[1]);
    const filtered = query.get("status") === "verified_match" || query.get("pen_id") === "B";
    return { ok: true, json: async () => ({
      items: filtered || query.get("offset") === "20" ? [older] : [historicalCheck],
      total: filtered ? 1 : 21, limit: 20, offset: Number(query.get("offset")),
    }) } as Response;
  });
  const user = userEvent.setup();
  render(<InventoryPanel onOpenVideo={vi.fn()} />);

  expect(await screen.findByText("第 1 / 2 页 · 共 21 条")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "下一页" }));
  expect(await screen.findByText("第 2 / 2 页 · 共 21 条")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "B-2 · 牛" })).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("筛选盘点状态"), "verified_match");
  expect(await screen.findByText("第 1 / 1 页 · 共 1 条")).toBeInTheDocument();
  expect(requests.some((url) => url.includes("status=verified_match") && url.includes("offset=0"))).toBe(true);
  await user.type(screen.getByLabelText("筛选圈舍编号"), "B");
  await waitFor(() => expect(requests.some((url) => url.includes("pen_id=B"))).toBe(true));
});

it("shows an empty filtered result without retaining rows from an older request", async () => {
  let resolveOld!: (value: Response) => void;
  const oldRequest = new Promise<Response>((resolve) => { resolveOld = resolve; });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("status=coverage_needed")) {
      return { ok: true, json: async () => ({ items: [], total: 0, limit: 20, offset: 0 }) } as Response;
    }
    return oldRequest;
  });
  const user = userEvent.setup();
  render(<InventoryPanel onOpenVideo={vi.fn()} />);
  await user.selectOptions(screen.getByLabelText("筛选盘点状态"), "coverage_needed");
  expect(await screen.findByText("暂无盘点记录。")).toBeInTheDocument();
  resolveOld({ ok: true, json: async () => ({ items: [historicalCheck], total: 1, limit: 20, offset: 0 }) } as Response);
  await waitFor(() => expect(screen.queryByRole("heading", { name: "A-9 · 牛" })).not.toBeInTheDocument());
});

it("does not offer duplicate video navigation inside a selected video job", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true, json: async () => [historicalCheck],
  } as Response);

  render(<InventoryPanel selectedJob={job} onOpenVideo={vi.fn()} />);

  expect(await screen.findByText(/数量初步相符/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "打开视频证据" })).not.toBeInTheDocument();
});

it("loads the complete inventory history for the selected video job", async () => {
  const fetched: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    fetched.push(url);
    if (url !== "/api/inventory-checks?job_id=video-1") {
      return { ok: false, json: async () => ({ detail: "wrong query" }) } as Response;
    }
    return { ok: true, json: async () => [historicalCheck] } as Response;
  });

  render(<InventoryPanel selectedJob={job} />);

  expect(await screen.findByRole("heading", { name: "A-9 · 牛" })).toBeInTheDocument();
  expect(fetched).toEqual(["/api/inventory-checks?job_id=video-1"]);
  expect(screen.queryByLabelText("筛选圈舍编号")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "下一页" })).not.toBeInTheDocument();
});

it("records a coverage-limited count without calling video IDs livestock", async () => {
  const checks: InventoryCheck[] = [];
  const submitted: { value: Record<string, unknown> | null } = { value: null };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input) === "/api/inventory-checks" && init?.method === "POST") {
      const input = JSON.parse(String(init.body)) as NewInventoryCheck;
      submitted.value = input;
      const row: InventoryCheck = { ...input, id: "check-1", species: "cattle", status: "coverage_needed",
        difference: 2, current_count: 8, video_track_count: 7, rechecks: [], lost_count: null,
      verification_status: "user_recorded", created_at: new Date().toISOString() };
      checks.unshift(row);
      return { ok: true, json: async () => row } as Response;
    }
    return { ok: true, json: async () => checks } as Response;
  });
  const user = userEvent.setup();
  render(<InventoryPanel selectedJob={job} />);
  expect(screen.getByText(/Track ID.*不能作为存栏数/)).toBeInTheDocument();
  await user.type(screen.getByLabelText("圈舍编号"), "A-1");
  await user.type(screen.getByLabelText("登记存栏数"), "10");
  await user.type(screen.getByLabelText("登记来源"), "昨日台账");
  await user.type(screen.getByLabelText("人工清点数"), "8");
  await user.selectOptions(screen.getByLabelText("拍摄覆盖"), "partial");
  await user.type(screen.getByLabelText("覆盖说明"), "角落未拍到");
  await user.type(screen.getByLabelText("操作人"), "张三");
  await user.click(screen.getByRole("button", { name: "保存盘点" }));
  await waitFor(() => expect(submitted.value).not.toBeNull());
  expect(submitted.value?.observed_count).toBe(8);
  expect(screen.getByText(/先补拍/)).toBeInTheDocument();
  expect(screen.queryByText(/确认丢失/)).not.toBeInTheDocument();
});

it("shows a pending shortfall and requires human field evidence for loss registration", async () => {
  const row = { id: "check-2", job_id: "video-1", species: "cattle", pen_id: "A-2",
    expected_count: 10, observed_count: 8, current_count: 8, difference: 2,
    baseline_source: "台账", coverage: "complete", coverage_note: "四角覆盖",
    operator_name: "张三", observed_at: new Date().toISOString(), created_at: new Date().toISOString(),
    status: "discrepancy_pending", rechecks: [], lost_count: null, video_track_count: 7,
    verification_status: "user_recorded" } as InventoryCheck;
  let recheck: Record<string, unknown> | null = null;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input).endsWith("/rechecks") && init?.method === "POST") {
      recheck = JSON.parse(String(init.body));
      row.status = "loss_user_recorded"; row.lost_count = 1;
      return { ok: true, json: async () => row } as Response;
    }
    return { ok: true, json: async () => [row] } as Response;
  });
  const user = userEvent.setup();
  render(<InventoryPanel selectedJob={job} />);
  expect(await screen.findByText(/差额 2.*待复点/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "填写人工复核" }));
  await user.type(screen.getByLabelText("复点数量"), "8");
  await user.selectOptions(screen.getByLabelText("复核结论"), "loss_user_recorded");
  expect(screen.getByRole("button", { name: "保存复核" })).toBeDisabled();
  await user.type(screen.getByLabelText("人工登记丢失数量"), "1");
  await user.click(screen.getByLabelText("已核对出入栏记录"));
  await user.click(screen.getByLabelText("已完成现场查找"));
  await user.type(screen.getByLabelText("复核操作人"), "李四");
  await user.type(screen.getByLabelText("复核说明"), "现场查找记录 2026-10-15");
  await user.click(screen.getByRole("button", { name: "保存复核" }));
  await waitFor(() => expect(recheck?.lost_count).toBe(1));
  expect(screen.getByText(/人工登记丢失 1/)).toBeInTheDocument();
});

it("does not offer a recheck before the initial human count exists", async () => {
  const row = { id: "check-3", job_id: "video-1", species: "cattle", pen_id: "A-3",
    expected_count: 10, observed_count: null, current_count: null, difference: null,
    baseline_source: "台账", coverage: "complete", coverage_note: "四角覆盖",
    operator_name: "张三", observed_at: new Date().toISOString(), created_at: new Date().toISOString(),
    status: "count_needed", rechecks: [], lost_count: null, video_track_count: 7,
    verification_status: "user_recorded" } as InventoryCheck;
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true, json: async () => [row],
  } as Response);
  render(<InventoryPanel selectedJob={job} />);
  expect(await screen.findByText("覆盖完整，待人工清点")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "填写人工复核" })).not.toBeInTheDocument();
});
