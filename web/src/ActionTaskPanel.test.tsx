import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import ActionTaskPanel from "./ActionTaskPanel";
import type { VideoJob } from "./api";
import type { VideoEvent } from "./api";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const job = { id: "job-1", status: "completed", progress: 1,
  result: { species: "cattle", tracked_cattle: 1, track_ids: [7] } } as VideoJob;

it("creates a followup task bound to the selected video", async () => {
  const requests: Record<string, unknown>[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      requests.push(body);
      return { ok: true, json: async () => ({ id: "task-1", species: "cattle", status: "pending",
        created_at: new Date().toISOString(), updated_at: new Date().toISOString(), updates: [], ...body }) } as Response;
    }
    expect(String(input)).toBe("/api/action-tasks?job_id=job-1");
    return { ok: true, json: async () => [] } as Response;
  });
  const user = userEvent.setup();
  render(<ActionTaskPanel job={job} />);
  await user.type(screen.getByLabelText("核查事项"), "检查活动情况");
  await user.type(screen.getByLabelText("负责人"), "李四");
  fireEvent.change(screen.getByLabelText("完成时间"), { target: { value: "2026-10-23T14:30" } });
  await user.selectOptions(screen.getByLabelText("视频内 ID（可选）"), "7");
  await user.click(screen.getByRole("button", { name: "创建核查事项" }));
  expect(await screen.findByText("检查活动情况 · 待核查")).toBeInTheDocument();
  expect(requests[0]).toMatchObject({ job_id: "job-1", title: "检查活动情况",
    assignee: "李四", track_id: 7 });
});

it("prefills a task from a selected video alert", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, json: async () => [] } as Response);
  const alert = { id: 2, kind: "alert", label: "持续低活动", detail: "请人工核查",
    track_id: 7, time_seconds: 12.5 } as VideoEvent;
  render(<ActionTaskPanel job={job} selectedEvent={alert} />);
  expect(await screen.findByDisplayValue("核查视频内 ID 7：持续低活动")).toBeInTheDocument();
  expect(screen.getByLabelText("视频内 ID（可选）")).toHaveValue("7");
  expect(screen.getByLabelText("证据时间点，秒（可选）")).toHaveValue(12.5);
});
