import { useEffect, useState } from "react";
import { fetchVideoEvents, VideoEvent, videoEventClipUrl, videoEventSnapshotUrl } from "./api";

type Props = { jobId: string; refreshKey?: number; onSeek: (seconds: number) => void;
  onCreateTask?: (event: VideoEvent) => void };

function timestamp(seconds: number) {
  const whole = Math.floor(seconds);
  return `${String(Math.floor(whole / 60)).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}

const kindLabels: Record<VideoEvent["kind"], string> = {
  alert: "规则提示", behavior: "行为切换", review: "人工复核", correction: "画面纠错", movement: "活动状态",
};

export default function VideoEventTimeline({ jobId, refreshKey, onSeek, onCreateTask }: Props) {
  const [events, setEvents] = useState<VideoEvent[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [previewId, setPreviewId] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setEvents([]);
    setPreviewId(null);
    fetchVideoEvents(jobId)
      .then((rows) => { if (active) { setEvents(rows); setError(""); } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "事件加载失败"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [jobId, refreshKey]);

  return <section className="video-event-timeline" aria-label="视频事件时间轴">
    <header><strong>事件时间轴</strong><small>点击时间定位结果视频；片段用于人工核查</small></header>
    {loading && <p>正在加载事件…</p>}
    {error && <p role="status">事件加载失败：{error}</p>}
    {!loading && !error && events.length === 0 && <p>此视频暂无带时间点的行为、规则提示或复核记录。</p>}
    {events.length > 0 && <ol>
      {events.map((event) => <li key={event.id}>
        <button type="button" onClick={() => onSeek(event.time_seconds)} aria-label={`跳转到 ${timestamp(event.time_seconds)} ${event.label}`}>
          {timestamp(event.time_seconds)}
        </button>
        <span>{kindLabels[event.kind]}{event.track_id !== null ? ` · ID ${event.track_id}` : ""}</span>
        <strong>{event.label}</strong>
        {event.detail && <small>{event.detail}</small>}
        {event.kind === "alert" && onCreateTask && <button type="button" onClick={() => onCreateTask(event)}>
          根据此提示创建核查事项
        </button>}
        <button type="button" onClick={() => setPreviewId(previewId === event.id ? null : event.id)}>
          {previewId === event.id ? "收起证据" : "查看截图与前后片段"}
        </button>
        {previewId === event.id && <div className="event-evidence">
          <img src={videoEventSnapshotUrl(jobId, event.id)} alt={`${event.label}发生时的识别画面`} />
          <video controls preload="metadata" src={videoEventClipUrl(jobId, event.id)} />
          <small>视频片段约为提示前后各 3 秒，供人工核查。</small>
        </div>}
        <a href={videoEventClipUrl(jobId, event.id)} download>下载证据片段</a>
      </li>)}
    </ol>}
  </section>;
}
