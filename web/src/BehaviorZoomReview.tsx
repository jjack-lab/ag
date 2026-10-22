import { FormEvent, useRef, useState } from "react";
import { createVideoReview, inspectionFrameUrl, resultMediaUrl } from "./api";

const behaviors = [
  ["uncertain", "仍无法判断"], ["grazing", "采食"], ["drinking", "饮水"],
  ["ruminating-standing", "站立反刍"], ["ruminating-lying", "卧姿反刍"],
  ["resting-standing", "站立休息"], ["resting-lying", "卧姿休息"],
  ["walking", "行走"], ["standing", "站立"], ["lying", "卧倒"],
] as const;

type Props = {
  jobId: string;
  videoPath: string;
  trackIds: number[];
  onReviewSaved?: () => void;
};

export default function BehaviorZoomReview({ jobId, videoPath, trackIds, onReviewSaved }: Props) {
  const [trackId, setTrackId] = useState(trackIds[0] ?? 0);
  const [time, setTime] = useState(0);
  const [behavior, setBehavior] = useState("uncertain");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [cropMissing, setCropMissing] = useState(false);
  const [saving, setSaving] = useState(false);
  const video = useRef<HTMLVideoElement>(null);

  function seek(next: number) {
    const seconds = Math.max(0, Math.round(next * 10) / 10);
    setTime(seconds);
    setCropMissing(false);
    if (video.current) video.current.currentTime = seconds;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const label = behaviors.find(([value]) => value === behavior)?.[1] ?? "仍无法判断";
    setSaving(true);
    setMessage("");
    try {
      await createVideoReview(jobId, {
        issue_type: "other", track_id: trackId, time_seconds: time,
        verdict: behavior === "uncertain" ? "uncertain" : "confirmed",
        note: `局部放大人工行为复核：${label}。${note.trim()}`,
      });
      setMessage("已保存人工复核");
      setNote("");
      onReviewSaved?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally { setSaving(false); }
  }

  return <section className="behavior-zoom-review" aria-label="行为局部放大复核">
    <header><strong>行为局部放大复核</strong><small>原视频帧与 Track ID 局部对照</small></header>
    <p>选择视频内 ID，暂停或跳到“无法确定”的时刻查看原始像素。放大不会恢复遮挡或模糊细节；人工结论单独保存，不覆盖模型输出。</p>
    <div className="behavior-zoom-controls">
      <label>放大查看的 Track ID<select value={trackId} onChange={(event) => { setTrackId(Number(event.target.value)); setCropMissing(false); }}>
        {trackIds.map((id) => <option key={id} value={id}>{id}</option>)}
      </select></label>
      <button type="button" onClick={() => seek(time - 0.5)}>前移 0.5 秒</button>
      <span>{time.toFixed(1)} 秒</span>
      <button type="button" onClick={() => seek(time + 0.5)}>后移 0.5 秒</button>
    </div>
    <div className="behavior-zoom-grid">
      <div><span>原视频全画面</span><img alt="原视频全画面" src={inspectionFrameUrl(jobId, trackId, time, false)} /></div>
      <div><span>局部放大（原始像素）</span><img alt="Track ID 局部放大"
        src={inspectionFrameUrl(jobId, trackId, time, true)}
        onError={() => setCropMissing(true)} onLoad={() => setCropMissing(false)} />
        {cropMissing && <small>此时刻没有该 ID 的检测框，请前后跳帧。</small>}
      </div>
    </div>
    <video ref={video} src={resultMediaUrl(videoPath)} controls aria-label="放大复核前后视频"
      onPause={(event) => seek(event.currentTarget.currentTime)}
      onSeeked={(event) => setTime(Math.round(event.currentTarget.currentTime * 10) / 10)} />
    <form onSubmit={save}>
      <label>人工观察结论<select value={behavior} onChange={(event) => setBehavior(event.target.value)}>
        {behaviors.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      <label>复核说明<textarea required maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} /></label>
      <button type="submit" disabled={saving || !note.trim()}>{saving ? "保存中…" : "保存放大复核"}</button>
    </form>
    {message && <p role="status">{message}</p>}
  </section>;
}
