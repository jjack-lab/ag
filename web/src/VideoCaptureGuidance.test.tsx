import { expect, it } from "vitest";
import { captureRecommendations } from "./VideoCaptureGuidance";

it("suggests a longer, clearer capture for short low-resolution video", () => {
  expect(captureRecommendations(6, 640, 360)).toEqual([
    "片段不足 10 秒，建议延长拍摄后补传。",
    "画面短边不足 480 像素，建议靠近拍摄或提高分辨率。",
  ]);
});

it("does not claim image quality from duration and resolution alone", () => {
  expect(captureRecommendations(20, 1920, 1080)).toEqual([]);
});
