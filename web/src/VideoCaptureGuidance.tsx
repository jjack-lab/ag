import { useEffect, useState } from "react";

type Metadata = { duration: number; width: number; height: number };

export function captureRecommendations(duration: number, width: number, height: number): string[] {
  const advice: string[] = [];
  if (duration < 10) advice.push("片段不足 10 秒，建议延长拍摄后补传。");
  if (Math.min(width, height) < 480) advice.push("画面短边不足 480 像素，建议靠近拍摄或提高分辨率。");
  return advice;
}

export default function VideoCaptureGuidance({ file }: { file: File }) {
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [unreadable, setUnreadable] = useState(false);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => setMetadata({
      duration: video.duration, width: video.videoWidth, height: video.videoHeight,
    });
    video.onerror = () => setUnreadable(true);
    video.src = url;
    return () => { video.removeAttribute("src"); URL.revokeObjectURL(url); };
  }, [file]);

  const advice = metadata ? captureRecommendations(metadata.duration, metadata.width, metadata.height) : [];
  return <section className="capture-guidance" aria-label="拍摄与补拍提示">
    <strong>拍摄检查</strong>
    {metadata && <p>视频约 {metadata.duration.toFixed(1)} 秒 · {metadata.width} × {metadata.height} 像素</p>}
    {advice.map((item) => <p key={item}>{item}</p>)}
    {metadata && advice.length === 0 && <p>未发现时长或分辨率问题；画面质量仍需人工确认。</p>}
    {unreadable && <p>浏览器无法读取视频元信息，请人工检查画面后再识别。</p>}
    {!metadata && !unreadable && <p>正在读取视频时长与分辨率…</p>}
    <small>请确认牛羊完整入镜、光线充足且画面稳定；覆盖不足时补拍。</small>
  </section>;
}
