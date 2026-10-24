import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import AnimalDirectory from "./AnimalDirectory";
import AlertCenter from "./AlertCenter";
import WorkspaceAnalytics from "./WorkspaceAnalytics";
import RecentWork from "./RecentWork";
import * as api from "./api";

vi.mock("./api", async (load) => ({ ...await load<typeof import("./api")>(),
  fetchAnimals: vi.fn(), fetchAnimalProfile: vi.fn(), createAnimalFollowup: vi.fn(),
  fetchAlerts: vi.fn(), resolveAlert: vi.fn(), fetchAnalytics: vi.fn(),
  fetchVideoJobs: vi.fn(), fetchActionTasks: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("opens a stable animal profile and returns to its video evidence", async () => {
  vi.mocked(api.fetchAnimals).mockResolvedValue([{ animal_id: "C-07", species: "cattle", video_count: 1, followup_count: 0, last_seen: "2026-10-24" }]);
  vi.mocked(api.fetchAnimalProfile).mockResolvedValue({ animal_id: "C-07", species: "cattle", followups: [], visits: [{ job_id: "v1", track_id: 7, recorded_at: "2026-10-24", reviews: [] }] } as unknown as api.AnimalProfile);
  const open = vi.fn();
  render(<AnimalDirectory onOpenVideo={open} />);
  fireEvent.click(await screen.findByRole("button", { name: /C-07/ }));
  fireEvent.click(await screen.findByRole("button", { name: "打开视频证据" }));
  expect(open).toHaveBeenCalledWith("v1");
  expect(screen.getByLabelText("回访说明")).toBeInTheDocument();
  vi.mocked(api.createAnimalFollowup).mockResolvedValue({ id: "f1", kind: "field_observation", observed_at: "2026-10-24", note: "人工复查正常" } as api.AnimalFollowup);
  fireEvent.change(screen.getByLabelText("回访日期"), { target: { value: "2026-10-24" } });
  fireEvent.change(screen.getByLabelText("回访说明"), { target: { value: "人工复查正常" } });
  fireEvent.click(screen.getByRole("button", { name: "保存回访记录" }));
  expect(await screen.findByText("人工复查正常")).toBeInTheDocument();
  expect(api.createAnimalFollowup).toHaveBeenCalledWith("C-07", expect.objectContaining({ note: "人工复查正常", observed_at: "2026-10-24" }));
});

it("closes an alert with a note then queries resolved history", async () => {
  const alert = { id: "a1", cattle_id: "7", reason: "低活动", level: "medium", suggestion: "核查", occurred_at: "2026-10-24", status: "open", confidence: .9 } as api.AlertRecord;
  vi.mocked(api.fetchAlerts).mockResolvedValue([alert]);
  vi.mocked(api.resolveAlert).mockResolvedValue({ ...alert, status: "resolved" });
  const changed = vi.fn();
  render(<AlertCenter onOpenVideo={vi.fn()} onChanged={changed} />);
  fireEvent.click(await screen.findByRole("button", { name: "处理此告警" }));
  fireEvent.change(screen.getByLabelText("处置说明"), { target: { value: "现场已复查" } });
  fireEvent.click(screen.getByRole("button", { name: "确认关闭告警" }));
  await waitFor(() => expect(api.resolveAlert).toHaveBeenCalledWith("a1", "现场已复查"));
  await waitFor(() => expect(changed).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText("告警状态"), { target: { value: "resolved" } });
  await waitFor(() => expect(api.fetchAlerts).toHaveBeenLastCalledWith("resolved"));
});

it("keeps export dates consistent with the statistics query", async () => {
  vi.mocked(api.fetchAnalytics).mockResolvedValue({ timezone: "Asia/Shanghai", start: null, end: null, daily: [], totals: { videos: 0, completed_videos: 0, failed_videos: 0, cattle_videos: 0, sheep_videos: 0, alerts: 0, high_alerts: 0, resolved_alerts: 0, tasks_created: 0, tasks_closed: 0 } });
  render(<WorkspaceAnalytics onOpenVideo={vi.fn()} />);
  await screen.findByText("暂无此日期范围内的统计记录。");
  fireEvent.change(screen.getByLabelText("开始日期"), { target: { value: "2026-10-20" } });
  fireEvent.change(screen.getByLabelText("结束日期"), { target: { value: "2026-10-24" } });
  fireEvent.click(screen.getByRole("button", { name: "查询统计" }));
  await waitFor(() => expect(api.fetchAnalytics).toHaveBeenLastCalledWith("2026-10-20", "2026-10-24"));
  expect(screen.getByRole("link", { name: "导出统计 CSV" })).toHaveAttribute("href", "/api/analytics.csv?start=2026-10-20&end=2026-10-24");
});

it("opens a recent completed task and shows outstanding work", async () => {
  vi.mocked(api.fetchVideoJobs).mockResolvedValue([{ id: "v1", status: "completed", created_at: "2026-10-24", progress: 1 }] as api.VideoJob[]);
  vi.mocked(api.fetchActionTasks).mockResolvedValue([]);
  const open = vi.fn();
  render(<RecentWork onOpenVideo={open} />);
  fireEvent.click(await screen.findByRole("button", { name: "打开结果" }));
  expect(open).toHaveBeenCalledWith("v1");
});

it("keeps the last selected animal when an older request finishes late", async () => {
  const profile = (animal_id: string) => ({ animal_id, species: "cattle", visits: [], followups: [] }) as api.AnimalProfile;
  let finishA!: (row: api.AnimalProfile) => void;
  vi.mocked(api.fetchAnimals).mockResolvedValue(["A", "B"].map((animal_id) => ({ animal_id, species: "cattle", video_count: 1, followup_count: 0, last_seen: "2026-10-24" })));
  vi.mocked(api.fetchAnimalProfile).mockImplementation((id) => id === "A" ? new Promise((resolve) => { finishA = resolve; }) : Promise.resolve(profile("B")));
  render(<AnimalDirectory onOpenVideo={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: /A.*1.*次视频/ }));
  fireEvent.click(screen.getByRole("button", { name: /B.*1.*次视频/ }));
  expect(await screen.findByRole("heading", { name: "B · 牛" })).toBeInTheDocument();
  await act(async () => finishA(profile("A")));
  await waitFor(() => expect(screen.queryByRole("heading", { name: "A · 牛" })).not.toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "B · 牛" })).toBeInTheDocument();
});
