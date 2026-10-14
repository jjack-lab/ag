import { FormEvent, useEffect, useState } from "react";

import {
  createVideoReview,
  fetchVideoJobs,
  fetchVideoReviews,
  NewVideoReview,
  VideoJob,
  VideoReview,
} from "./api";

const ISSUE_LABELS: Record<VideoReview["issue_type"], string> = {
  missed_detection: "漏检",
  id_switch: "ID 切换",
  false_alert: "误告警",
  health_concern: "现场健康关注",
  other: "其他",
};

const VERDICT_LABELS: Record<VideoReview["verdict"], string> = {
  confirmed: "已确认",
  rejected: "已排除",
  uncertain: "待确认",
};

type Props = {
  selectedJob: VideoJob | null;
  onSelectJob: (job: VideoJob) => void;
};

export default function VideoReviewWorkspace({ selectedJob, onSelectJob }: Props) {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [reviews, setReviews] = useState<VideoReview[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [reviewError, setReviewError] = useState("");
  const [saving, setSaving] = useState(false);
  const [issueType, setIssueType] = useState<VideoReview["issue_type"]>("missed_detection");
  const [verdict, setVerdict] = useState<VideoReview["verdict"]>("confirmed");
  const [trackId, setTrackId] = useState("");
  const [timeSeconds, setTimeSeconds] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    let active = true;
    fetchVideoJobs()
      .then((rows) => {
        if (!Array.isArray(rows)) throw new Error("历史任务响应格式错误");
        if (active) { setJobs(rows); setHistoryError(""); }
      })
      .catch((error) => { if (active) setHistoryError(error instanceof Error ? error.message : "任务历史加载失败"); });
    return () => { active = false; };
  }, [selectedJob?.id]);

  useEffect(() => {
    let active = true;
    setReviews([]);
    setReviewError("");
    if (selectedJob?.status === "completed") {
      fetchVideoReviews(selectedJob.id)
        .then((rows) => {
          if (!Array.isArray(rows)) throw new Error("复核记录响应格式错误");
          if (active) setReviews(rows);
        })
        .catch((error) => { if (active) setReviewError(error instanceof Error ? error.message : "复核记录加载失败"); });
    }
    return () => { active = false; };
  }, [selectedJob?.id, selectedJob?.status]);

  async function submitReview(event: FormEvent) {
    event.preventDefault();
    if (!selectedJob || !note.trim()) return;
    const review: NewVideoReview = {
      issue_type: issueType,
      verdict,
      track_id: trackId === "" ? null : Number(trackId),
      time_seconds: timeSeconds === "" ? null : Number(timeSeconds),
      note: note.trim(),
    };
    setSaving(true);
    setReviewError("");
    try {
      const saved = await createVideoReview(selectedJob.id, review);
      setReviews((rows) => [...rows, saved]);
      setNote("");
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "保存复核记录失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="video-review-workspace" aria-label="视频任务与人工复核">
      <h4>最近视频任务</h4>
      {historyError && <p role="status">历史任务暂不可用：{historyError}</p>}
      {jobs.length === 0 && !historyError && <p>暂无历史任务。上传视频后可在这里重新打开结果。</p>}
      {jobs.length > 0 && <div className="video-job-list">
        {jobs.map((job) => (
          <button key={job.id} type="button" disabled={job.status !== "completed"}
            aria-pressed={selectedJob?.id === job.id} onClick={() => onSelectJob(job)}>
            <strong>{job.result?.species === "sheep" ? "羊" : "牛"} · {job.created_at ? new Date(job.created_at).toLocaleString("zh-CN") : job.id.slice(0, 8)}</strong>
            <span>{job.status === "completed" ? `已完成 · ${job.result?.tracked_cattle ?? 0} 个视频内 ID` : job.status === "failed" ? "失败" : "处理中"}</span>
          </button>
        ))}
      </div>}

      {selectedJob?.status === "completed" && <div className="video-review-panel">
        <h4>人工复核记录</h4>
        <p>记录漏检、ID 切换和误告警；视频内 ID 不等于跨天个体身份。现场健康关注仅作观察记录。</p>
        <form onSubmit={submitReview}>
          <label>问题类型
            <select value={issueType} onChange={(event) => setIssueType(event.target.value as VideoReview["issue_type"])}>
              {Object.entries(ISSUE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>复核结论
            <select value={verdict} onChange={(event) => setVerdict(event.target.value as VideoReview["verdict"])}>
              {Object.entries(VERDICT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>视频内 Track ID（可选）
            <input type="number" min="0" step="1" value={trackId} onChange={(event) => setTrackId(event.target.value)} />
          </label>
          <label>时间点，秒（可选）
            <input type="number" min="0" step="0.1" value={timeSeconds} onChange={(event) => setTimeSeconds(event.target.value)} />
          </label>
          <label>现场说明
            <textarea required maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <button type="submit" disabled={saving || !note.trim()}>{saving ? "保存中…" : "保存复核记录"}</button>
        </form>
        {reviewError && <p role="alert">{reviewError}</p>}
        {reviews.length === 0 && <p>尚无复核记录。</p>}
        {reviews.map((review) => <article key={review.id} className="video-review-item">
          <strong>{ISSUE_LABELS[review.issue_type]} · {VERDICT_LABELS[review.verdict]}</strong>
          <span>{review.track_id === null ? "整段视频" : `视频内 ID ${review.track_id}`}{review.time_seconds === null ? "" : ` · ${review.time_seconds} 秒`}</span>
          <p>{review.note}</p>
        </article>)}
      </div>}
    </section>
  );
}
