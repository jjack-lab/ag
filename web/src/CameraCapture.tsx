import { useEffect, useRef, useState } from "react";

export default function CameraCapture({ onRecorded, disabled = false }: {
  onRecorded: (file: File) => void; disabled?: boolean;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const mounted = useRef(true);
  const [ready, setReady] = useState(false);
  const [opening, setOpening] = useState(false);
  const [recording, setRecording] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  function release() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
  }
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; if (recorder.current?.state === "recording") recorder.current.stop(); release(); };
  }, []);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  async function open() {
    setError(""); setOpening(true); setFile(null); setPreview("");
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
        throw new Error("当前浏览器不支持录像，请使用新版 Chrome / Edge 或上传视频文件。");
      }
      const nextStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      if (!mounted.current) { nextStream.getTracks().forEach((track) => track.stop()); return; }
      stream.current = nextStream;
      if (video.current) { video.current.srcObject = nextStream; await video.current.play(); }
      setReady(true);
    } catch (cause) { release(); setError(`无法打开摄像头：${cause instanceof Error ? cause.message : "请检查设备和权限"}`); }
    finally { if (mounted.current) setOpening(false); }
  }
  function start() {
    if (!stream.current) return;
    setError(""); setFile(null); setPreview("");
    try {
      const mimeType = ["video/webm;codecs=vp8", "video/webm", "video/mp4"].find((type) => MediaRecorder.isTypeSupported(type));
      const next = new MediaRecorder(stream.current, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      next.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      next.onstop = () => {
        if (!mounted.current) return;
        setRecording(false);
        release(); setReady(false);
        if (!chunks.length) { setError("未录到有效画面，请重新录像。"); return; }
        const type = next.mimeType || "video/webm";
        const blob = new Blob(chunks, { type });
        setFile(new File([blob], `camera-${Date.now()}.${type.includes("mp4") ? "mp4" : "webm"}`, { type }));
        setPreview(URL.createObjectURL(blob));
      };
      next.onerror = () => { if (mounted.current) { setError("录像中断，请停止并重试。"); setRecording(false); } };
      recorder.current = next; next.start(1000); setRecording(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "无法开始录像"); }
  }
  function close() {
    if (recorder.current?.state === "recording") recorder.current.stop();
    release(); setReady(false);
  }
  return <section className="camera-capture" aria-label="摄像头录像识别">
    <h4>现场录像</h4><p>打开摄像头录一段画面，停止后交给视频识别。录像期间请保持机位稳定、让动物完整入镜。</p>
    <video ref={video} muted playsInline aria-label="摄像头预览" hidden={!ready} />
    {preview && <video src={preview} controls playsInline aria-label="已录制视频预览" />}
    <div className="feature-actions">
      {!ready && <button type="button" disabled={opening || disabled} onClick={open}>{opening ? "正在打开…" : "打开摄像头"}</button>}
      {ready && !recording && <button type="button" disabled={disabled} onClick={start}>{file ? "重新录像" : "开始录像"}</button>}
      {recording && <button type="button" onClick={() => recorder.current?.stop()}>停止录像</button>}
      {ready && <button type="button" onClick={close}>关闭摄像头</button>}
      {file && !recording && <button type="button" disabled={disabled} onClick={() => { close(); onRecorded(file); }}>使用这段录像</button>}
    </div>
    {recording && <p role="status">正在录像，点击停止后可预览。</p>}{error && <p role="alert">{error}</p>}
  </section>;
}
