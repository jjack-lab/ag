import { FormEvent, useEffect, useState } from "react";
import { ActionTask, createActionTask, fetchActionTasks, VideoEvent, VideoJob } from "./api";

const labels = { pending: "待核查", in_progress: "处理中", followup: "待复查", closed: "已关闭" };

export default function ActionTaskPanel({ job, selectedEvent }: { job: VideoJob; selectedEvent?: VideoEvent | null }) {
  const [tasks, setTasks] = useState<ActionTask[]>([]);
  const [title, setTitle] = useState("");
  const [assignee, setAssignee] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [trackId, setTrackId] = useState("");
  const [timeSeconds, setTimeSeconds] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!selectedEvent) return;
    setTitle(`核查视频内 ID ${selectedEvent.track_id ?? "未知"}：${selectedEvent.label}`);
    setTrackId(selectedEvent.track_id === null ? "" : String(selectedEvent.track_id));
    setTimeSeconds(String(selectedEvent.time_seconds));
    document.querySelector(".action-task-panel")?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [selectedEvent]);

  useEffect(() => {
    let active = true;
    setTasks([]);
    setError("");
    fetchActionTasks({ jobId: job.id })
      .then((rows) => {
        if (active) setTasks(rows);
      })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "事项加载失败"); });
    return () => { active = false; };
  }, [job.id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const saved = await createActionTask({
        job_id: job.id, title: title.trim(), assignee: assignee.trim(),
        due_at: new Date(dueAt).toISOString(),
        track_id: trackId === "" ? null : Number(trackId),
        time_seconds: timeSeconds === "" ? null : Number(timeSeconds),
      });
      setTasks((rows) => [saved, ...rows]);
      setTitle("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "事项创建失败");
    } finally {
      setSaving(false);
    }
  }

  return <section className="action-task-panel" aria-label="视频核查事项">
    <header><h4>人工核查事项</h4><small>从视频发现的问题安排现场处理，结论由工作人员填写。</small></header>
    <form onSubmit={submit}>
      <label>核查事项<input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <label>负责人<input required maxLength={100} value={assignee} onChange={(event) => setAssignee(event.target.value)} /></label>
      <label>完成时间<input required type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label>
      <label>视频内 ID（可选）<select value={trackId} onChange={(event) => setTrackId(event.target.value)}>
        <option value="">整段视频</option>
        {Array.from(new Set([...(job.result?.track_ids || []), ...(trackId ? [Number(trackId)] : [])])).map((id) => <option key={id} value={id}>{id}</option>)}
      </select></label>
      <label>证据时间点，秒（可选）<input type="number" min="0" step="0.1" value={timeSeconds} onChange={(event) => setTimeSeconds(event.target.value)} /></label>
      <button type="submit" disabled={saving}>{saving ? "保存中…" : "创建核查事项"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {tasks.length === 0 && !error && <p>此视频暂无核查事项。</p>}
    {tasks.map((task) => <article key={task.id}>
      <strong>{task.title} · {labels[task.status]}</strong>
      <small>负责人：{task.assignee} · 完成时间：{new Date(task.due_at).toLocaleString("zh-CN")}</small>
      {task.track_id !== null && <small>视频内 ID {task.track_id}{task.time_seconds === null ? "" : ` · ${task.time_seconds} 秒`}</small>}
    </article>)}
  </section>;
}
