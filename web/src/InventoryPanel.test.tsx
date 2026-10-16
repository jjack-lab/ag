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
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true, json: async () => [historicalCheck],
  } as Response);
  const onOpenVideo = vi.fn();
  const user = userEvent.setup();

  render(<InventoryPanel onOpenVideo={onOpenVideo} />);

  await user.click(await screen.findByRole("button", { name: "打开视频证据" }));
  expect(onOpenVideo).toHaveBeenCalledWith("video-1");
});

it("does not offer duplicate video navigation inside a selected video job", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true, json: async () => [historicalCheck],
  } as Response);

  render(<InventoryPanel selectedJob={job} onOpenVideo={vi.fn()} />);

  expect(await screen.findByText(/数量初步相符/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "打开视频证据" })).not.toBeInTheDocument();
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
