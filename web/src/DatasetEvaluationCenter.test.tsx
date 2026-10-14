import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import DatasetEvaluationCenter from "./DatasetEvaluationCenter";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("imports annotated public sequence and shows measured values with provenance", async () => {
  const submitted: { value: FormData | null } = { value: null };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === "/api/jobs/video") return { ok: true, json: async () => [
      { id: "job-1", status: "completed", progress: 1, result: { species: "sheep" } },
    ] } as Response;
    if (url === "/api/evaluations" && init?.method === "POST") {
      submitted.value = init.body as FormData;
      return { ok: true, json: async () => ({
        id: "eval-1", job_id: "job-1", dataset_name: "Sheep Open Data", dataset_version: "v1",
        split_name: "external_test", source_url: "https://example.org/data", license_name: "CC BY 4.0",
        video_sha256: "a".repeat(64), annotations_sha256: "b".repeat(64),
        metrics: { labeled_frames: 10, ground_truth_boxes: 10, true_positive: 8,
          false_positive: 1, false_negative: 2, precision: 8 / 9, recall: .8,
          f1: 16 / 19, id_switches: 1, iou_threshold: .5 },
      }) } as Response;
    }
    if (url === "/api/evaluations") return { ok: true, json: async () => [] } as Response;
    throw new Error(`Unexpected request ${url}`);
  });
  const user = userEvent.setup();
  render(<DatasetEvaluationCenter />);
  await user.selectOptions(await screen.findByLabelText("已完成视频任务"), "job-1");
  await user.type(screen.getByLabelText("数据集名称"), "Sheep Open Data");
  await user.type(screen.getByLabelText("来源网址"), "https://example.org/data");
  await user.type(screen.getByLabelText("数据版本"), "v1");
  await user.type(screen.getByLabelText("数据许可"), "CC BY 4.0");
  await user.upload(screen.getByLabelText("逐帧真值 CSV"),
    new File(["frame_index,class_id,track_id,x,y,width,height\n"], "truth.csv", { type: "text/csv" }));
  await user.click(screen.getByRole("button", { name: "导入并计算" }));
  await waitFor(() => expect(submitted.value).not.toBeNull());
  expect(submitted.value!.get("job_id")).toBe("job-1");
  expect(await screen.findByText("Sheep Open Data")).toBeInTheDocument();
  expect(screen.getByText("1", { selector: "strong" })).toBeInTheDocument();
  expect(screen.getByText("80.0%")).toBeInTheDocument();
});
