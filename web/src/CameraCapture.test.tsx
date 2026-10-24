import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import CameraCapture from "./CameraCapture";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("explains camera permission refusal without submitting a task", async () => {
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: vi.fn().mockRejectedValue(new Error("denied")) } });
  vi.stubGlobal("MediaRecorder", class {});
  const selected = vi.fn();
  render(<CameraCapture onRecorded={selected} />);
  fireEvent.click(screen.getByRole("button", { name: "打开摄像头" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("无法打开摄像头");
  expect(selected).not.toHaveBeenCalled();
});

it("records a video file for the existing uploader and releases the camera", async () => {
  const stop = vi.fn();
  const stream = { getTracks: () => [{ stop }] };
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(stream) } });
  let recorder: { ondataavailable: ((e: { data: Blob }) => void) | null; onstop: (() => void) | null; state: string };
  class Recorder {
    static isTypeSupported() { return true; }
    mimeType = "video/webm"; state = "inactive";
    ondataavailable = null; onstop = null;
    constructor() { recorder = this; }
    start() { this.state = "recording"; }
    stop() { this.state = "inactive"; recorder.ondataavailable?.({ data: new Blob(["video"]) }); recorder.onstop?.(); }
  }
  vi.stubGlobal("MediaRecorder", Recorder);
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:recording");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const selected = vi.fn();
  const view = render(<CameraCapture onRecorded={selected} />);
  fireEvent.click(screen.getByRole("button", { name: "打开摄像头" }));
  fireEvent.click(await screen.findByRole("button", { name: "开始录像" }));
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "停止录像" })));
  expect(stop).toHaveBeenCalled();
  fireEvent.click(await screen.findByRole("button", { name: "使用这段录像" }));
  await waitFor(() => expect(selected).toHaveBeenCalledWith(expect.any(File)));
  expect(selected.mock.calls[0][0].name).toMatch(/\.webm$/);
  view.unmount();
  expect(stop).toHaveBeenCalled();
});
