import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import ActionTaskInbox from "./ActionTaskInbox";
import type { ActionTask } from "./api";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const task = { id: "task-1", job_id: "video-1", species: "cattle", title: "核查低活动",
  track_id: 7, time_seconds: 3.5, assignee: "李四", status: "pending",
  due_at: "2020-01-01T10:00:00+08:00", created_at: "2026-10-22T10:00:00+08:00",
  updated_at: "2026-10-22T10:00:00+08:00", updates: [] } as ActionTask;

it("shows overdue tasks, opens their video, and records followup history", async () => {
  const onOpenVideo = vi.fn();
  const bodies: Record<string, unknown>[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      bodies.push(body);
      return { ok: true, json: async () => ({ ...task, status: body.status,
        due_at: body.next_due_at, updates: [{ id: "update-1", task_id: task.id,
          created_at: new Date().toISOString(), ...body }] }) } as Response;
    }
    return { ok: true, json: async () => [task] } as Response;
  });
  const user = userEvent.setup();
  render(<ActionTaskInbox onOpenVideo={onOpenVideo} />);
  expect(await screen.findByText("核查低活动")).toBeInTheDocument();
  expect(screen.getByText("逾期 1")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "打开视频证据" }));
  expect(onOpenVideo).toHaveBeenCalledWith("video-1");
  await user.click(screen.getByRole("button", { name: "记录处理" }));
  await user.selectOptions(screen.getByLabelText("处理状态"), "followup");
  await user.type(screen.getByLabelText("操作人"), "王五");
  await user.type(screen.getByLabelText("处理记录"), "已现场查看，明天复查");
  fireEvent.change(screen.getByLabelText("下次复查时间"), { target: { value: "2026-10-23T14:30" } });
  await user.click(screen.getByRole("button", { name: "保存处理记录" }));
  expect(await screen.findByText(/王五：已现场查看，明天复查/)).toBeInTheDocument();
  expect(bodies[0]).toMatchObject({ status: "followup", actor: "王五" });
});
