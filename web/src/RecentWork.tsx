import { useEffect, useState } from "react";
import { fetchVideoJobs, fetchActionTasks, type VideoJob, type ActionTask } from "./api";

const statusLabels: Record<string, string> = { completed: "已完成", failed: "失败", running: "处理中", queued: "排队中" };
export default function RecentWork({ onOpenVideo, revision = 0 }: { onOpenVideo: (id: string) => void; revision?: number }) {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [tasks, setTasks] = useState<ActionTask[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true; setError("");
    Promise.all([fetchVideoJobs(), fetchActionTasks()]).then(([nextJobs, nextTasks]) => { if (active) { setJobs(nextJobs); setTasks(nextTasks); } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "最近工作加载失败"); });
    return () => { active = false; };
  }, [revision]);
  return <section className="recent-work workspace-feature" aria-label="最近工作记录">
    <div className="feature-toolbar"><h3>最近任务与待办</h3><a href="#/module/tasks">查看全部处置待办 →</a></div>
    {error && <p role="alert">{error}</p>}
    <div className="feature-card-grid kpi-cards"><article><span>待处理事项</span><strong>{tasks.filter((r) => r.status === "pending" || r.status === "in_progress").length}</strong></article><article><span>待复查事项</span><strong>{tasks.filter((r) => r.status === "followup").length}</strong></article></div>
    {!jobs.length && !error && <p>暂无视频任务，<a href="#/module/monitor">上传视频开始识别</a>。</p>}
    {jobs.slice(0, 6).map((job) => <article className="feature-record" key={job.id}>
      <header><strong>{job.id.slice(0, 8)} · {statusLabels[job.status]}</strong><span>{job.created_at && new Date(job.created_at).toLocaleString("zh-CN")}</span></header>
      {job.status === "completed" ? <button type="button" onClick={() => onOpenVideo(job.id)}>打开结果</button> : <p>{job.status === "failed" ? job.error || "处理失败，可重新上传" : `进度 ${Math.round(job.progress * 100)}%，刷新以查看最新状态`}</p>}
    </article>)}
  </section>;
}
