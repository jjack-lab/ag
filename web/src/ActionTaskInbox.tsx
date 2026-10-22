import { FormEvent, useEffect, useMemo, useState } from "react";
import { ActionTask, ActionTaskStatus, fetchActionTasks, updateActionTask } from "./api";

const labels: Record<ActionTaskStatus, string> = {
  pending: "待核查", in_progress: "处理中", followup: "待复查", closed: "已关闭",
};

type Props = { onOpenVideo: (jobId: string) => void; openingJobId?: string | null; videoOpenError?: string };

export default function ActionTaskInbox({ onOpenVideo, openingJobId, videoOpenError }: Props) {
  const [tasks, setTasks] = useState<ActionTask[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [nextStatus, setNextStatus] = useState<ActionTaskStatus>("in_progress");
  const [actor, setActor] = useState("");
  const [note, setNote] = useState("");
  const [nextDue, setNextDue] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    fetchActionTasks().then((rows) => {
      if (!Array.isArray(rows)) throw new Error("事项列表响应格式错误");
      if (active) setTasks(rows);
    }).catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "事项加载失败"); });
    return () => { active = false; };
  }, []);

  const overdue = tasks.filter((task) => task.status !== "closed" && new Date(task.due_at).getTime() < Date.now()).length;
  const pending = tasks.filter((task) => task.status === "pending" || task.status === "in_progress").length;
  const followup = tasks.filter((task) => task.status === "followup").length;
  const visible = useMemo(() => tasks.filter((task) =>
    (!statusFilter || task.status === statusFilter) &&
    (!assigneeFilter || task.assignee.includes(assigneeFilter.trim()))
  ), [tasks, statusFilter, assigneeFilter]);

  function edit(task: ActionTask) {
    setEditingId(task.id);
    setNextStatus(task.status === "pending" ? "in_progress" : task.status);
    setActor("");
    setNote("");
    setNextDue("");
    setError("");
  }

  async function submit(event: FormEvent, taskId: string) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const updated = await updateActionTask(taskId, {
        status: nextStatus, actor: actor.trim(), note: note.trim(),
        next_due_at: nextStatus === "followup" ? new Date(nextDue).toISOString() : null,
      });
      setTasks((rows) => rows.map((row) => row.id === taskId ? updated : row));
      setEditingId(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "处理记录保存失败");
    } finally {
      setSaving(false);
    }
  }

  return <section className="action-task-inbox" aria-label="处置待办">
    <header><h3>处置待办</h3><p>视频提示需经人工核查；这里记录负责人、处理过程和复查结果。</p></header>
    <div className="action-task-stats"><span>待处理 {pending}</span><span>逾期 {overdue}</span><span>待复查 {followup}</span></div>
    <div className="action-task-filters">
      <label>筛选状态<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
        <option value="">全部</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      <label>筛选负责人<input value={assigneeFilter} onChange={(event) => setAssigneeFilter(event.target.value)} /></label>
    </div>
    {error && <p role="alert">{error}</p>}
    {videoOpenError && <p role="alert">{videoOpenError}</p>}
    {visible.length === 0 && !error && <p>暂无符合条件的核查事项。</p>}
    {visible.map((task) => <article key={task.id}>
      <strong>{task.title}</strong>
      <span>{labels[task.status]} · {task.species === "sheep" ? "羊" : "牛"} · 负责人 {task.assignee}</span>
      <small>完成时间：{new Date(task.due_at).toLocaleString("zh-CN")}{task.status !== "closed" && new Date(task.due_at).getTime() < Date.now() ? " · 已逾期" : ""}</small>
      <small>{task.track_id === null ? "整段视频" : `视频内 ID ${task.track_id}`}{task.time_seconds === null ? "" : ` · ${task.time_seconds} 秒`}</small>
      <div className="action-task-actions">
        <button type="button" onClick={() => onOpenVideo(task.job_id)} disabled={openingJobId === task.job_id}>{openingJobId === task.job_id ? "打开中…" : "打开视频证据"}</button>
        <button type="button" onClick={() => edit(task)}>记录处理</button>
      </div>
      {task.updates.map((update) => <small key={update.id}>{new Date(update.created_at).toLocaleString("zh-CN")} · {update.actor}：{update.note}（{labels[update.status]}）</small>)}
      {editingId === task.id && <form className="action-task-update-form" onSubmit={(event) => submit(event, task.id)}>
        <label>处理状态<select value={nextStatus} onChange={(event) => setNextStatus(event.target.value as ActionTaskStatus)}>
          {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label>操作人<input required value={actor} onChange={(event) => setActor(event.target.value)} /></label>
        <label>处理记录<textarea required maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} /></label>
        {nextStatus === "followup" && <label>下次复查时间<input required type="datetime-local" value={nextDue} onChange={(event) => setNextDue(event.target.value)} /></label>}
        <button type="submit" disabled={saving}>{saving ? "保存中…" : "保存处理记录"}</button>
      </form>}
    </article>)}
  </section>;
}
