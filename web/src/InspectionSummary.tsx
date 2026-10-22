import { useState } from "react";
import { ActionTask, fetchActionTasks, fetchVideoReviews, resultMediaUrl, VideoJob, VideoReview } from "./api";

const taskLabels = { pending: "待核查", in_progress: "处理中", followup: "待复查", closed: "已关闭" };
const issueLabels = { missed_detection: "漏检", id_switch: "ID 切换", false_alert: "误告警",
  health_concern: "现场健康关注", other: "其他" };
const verdictLabels = { confirmed: "已确认", rejected: "已排除", uncertain: "待确认" };

export default function InspectionSummary({ job }: { job: VideoJob }) {
  const [tasks, setTasks] = useState<ActionTask[] | null>(null);
  const [reviews, setReviews] = useState<VideoReview[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function generate() {
    setLoading(true);
    setError("");
    try {
      const [taskRows, reviewRows] = await Promise.all([
        fetchActionTasks({ jobId: job.id }), fetchVideoReviews(job.id),
      ]);
      setTasks(taskRows);
      setReviews(reviewRows);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "摘要加载失败");
    } finally {
      setLoading(false);
    }
  }

  const result = job.result;
  return <section className="inspection-summary-section" aria-label="巡检摘要">
    <button type="button" onClick={generate} disabled={loading}>{loading ? "生成中…" : "生成巡检摘要"}</button>
    {error && <p role="alert">{error}</p>}
    {tasks && result && <article className="inspection-summary">
      <header>
        <div><small>星牧智控 · 人工巡检记录</small><h4>视频巡检摘要</h4></div>
        <button type="button" onClick={() => window.print()}>打印摘要</button>
      </header>
      <p>任务编号：{job.id} · {result.species === "sheep" ? "羊" : "牛"} · 处理时间：{job.updated_at ? new Date(job.updated_at).toLocaleString("zh-CN") : "未记录"}</p>
      <p>视频结果：{result.frame_count} 帧 · {result.tracked_cattle} 个视频内 Track ID · {result.alert_count} 条规则提示</p>
      <a href={resultMediaUrl(result.video_path)} target="_blank" rel="noreferrer">查看结果视频</a>
      <h5>人工复核（{reviews.length}）</h5>
      {reviews.length === 0 && <p>暂无人工复核记录。</p>}
      {reviews.map((review) => <p key={review.id}>{issueLabels[review.issue_type]} · {verdictLabels[review.verdict]}{review.track_id === null ? "" : ` · 视频内 ID ${review.track_id}`}：{review.note}</p>)}
      <h5>核查事项（{tasks.length}）</h5>
      {tasks.length === 0 && <p>暂无核查事项。</p>}
      {tasks.map((task) => <p key={task.id}>{task.title} · {taskLabels[task.status]} · 负责人 {task.assignee} · 完成时间 {new Date(task.due_at).toLocaleString("zh-CN")}{task.updates.length ? ` · 最新记录：${task.updates[task.updates.length - 1].note}` : ""}</p>)}
      <footer>规则提示仅供人工核查，视频内 Track ID 不代表跨天身份；不能据此诊断疾病。</footer>
    </article>}
  </section>;
}
