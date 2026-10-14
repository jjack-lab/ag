import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import RecognitionStudio from "./RecognitionStudio";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("submits sheep class and presents tracking without cattle health claims", async () => {
  let submittedClass: FormDataEntryValue | null = null;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input) === "/api/jobs/video") {
      submittedClass = (init?.body as FormData).get("class_id");
      return { ok: true, json: async () => ({ id: "sheep-job", status: "queued", progress: 0 }) } as Response;
    }
    return { ok: true, json: async () => ({
      id: "sheep-job", status: "completed", progress: 1, result: {
        video_path: "sheep-job/tracked.mp4", trajectory_csv: "sheep-job/tracks.csv",
        alert_csv: "sheep-job/alerts.csv", health_summary_csv: "sheep-job/health.csv",
        health_report_html: "sheep-job/report.html", frame_count: 30,
        tracked_cattle: 2, alert_count: 0, species: "sheep",
        health_evidence: [], behavior_model_status: "unavailable",
      },
    }) } as Response;
  });
  const user = userEvent.setup();
  render(<RecognitionStudio />);
  await user.click(screen.getByRole("button", { name: "视频识别" }));
  await user.selectOptions(screen.getByRole("combobox", { name: "识别类别" }), "0");
  fireEvent.change(screen.getByLabelText("选择羊只视频"), {
    target: { files: [new File(["video"], "sheep.mp4", { type: "video/mp4" })] },
  });
  await user.click(screen.getByRole("button", { name: "开始视频识别" }));
  expect(await screen.findByText("已追踪 2 只羊")).toBeInTheDocument();
  expect(submittedClass).toBe("0");
  expect(screen.getByText(/羊的健康规则尚未验证/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "健康报告" })).not.toBeInTheDocument();
});
