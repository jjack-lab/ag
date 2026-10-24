import { useEffect, useState, type FormEvent } from "react";
import { fetchAlerts, resolveAlert, createActionTask, type AlertRecord } from "./api";

const levels: Record<string, string> = { high: "高风险", medium: "中风险", low: "低风险" };
const nextDay = () => new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(Date.now() + 86400000)).replace(" ", "T");
export default function AlertCenter({ onOpenVideo, onChanged }: {
  onOpenVideo: (id: string) => void; onChanged: () => void;
}) {
  const [rows, setRows] = useState<AlertRecord[]>([]);
  const [status, setStatus] = useState("open");
  const [level, setLevel] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [action, setAction] = useState<"resolve" | "task">("resolve");
  const [note, setNote] = useState("");
  const [assignee, setAssignee] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [revision, setRevision] = useState(0);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true; setLoading(true); setError(""); setEditing(null);
    fetchAlerts(status).then((data) => { if (active) setRows(data); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "告警加载失败"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [status, revision]);
  async function submit(event: FormEvent, alert: AlertRecord) {
    event.preventDefault(); setSaving(true); setError(""); setMessage("");
    try {
      if (action === "resolve") {
        await resolveAlert(alert.id, note.trim()); setMessage("告警已关闭，处置记录已保存。");
      } else {
        await createActionTask({ job_id: alert.id.split(":")[0], title: `核查告警：${alert.reason}`,
          track_id: /^\d+$/.test(alert.cattle_id) ? Number(alert.cattle_id) : null,
          time_seconds: null, assignee: assignee.trim(), due_at: new Date(dueAt).toISOString() });
        setMessage("核查事项已创建，可在处置待办中继续记录。告警仍待核查。");
      }
      setEditing(null); setRevision((n) => n + 1); onChanged();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "操作失败"); }
    finally { setSaving(false); }
  }
  const visible = rows.filter((row) => !level || row.level === level);
  return <section className="workspace-feature" aria-label="告警处置中心">
    <header><span className="feature-eyebrow">EVIDENCE & ACTION / 告警处置</span><h3>让每条提示都有后续。</h3><p>查看视频证据、安排核查并保存处理说明。风险提示需由人员结合现场情况复核。</p></header>
    <div className="feature-toolbar"><label>告警状态<select value={status} onChange={(e) => setStatus(e.target.value)}><option value="open">待处理</option><option value="resolved">已处理</option><option value="">全部</option></select></label><label>风险等级<select value={level} onChange={(e) => setLevel(e.target.value)}><option value="">全部风险</option>{Object.entries(levels).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label><button onClick={() => setRevision((n) => n + 1)}>刷新告警</button><span>{visible.length} 条</span></div>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {loading ? <p>正在加载告警…</p> : !visible.length && !error && <p>暂无符合条件的告警。</p>}
    <div className="feature-list">{visible.map((alert) => <article className="feature-record" key={alert.id}>
      <header><strong>{alert.reason}</strong><span className={`risk-chip risk-${alert.level}`}>{levels[alert.level]}</span></header>
      <p>视频内 ID {alert.cattle_id} · {new Date(alert.occurred_at).toLocaleString("zh-CN")} · {alert.status === "resolved" ? "已处理" : "待处理"}</p><p>{alert.suggestion}</p>
      {alert.resolution && <p>处置说明：{alert.resolution}<small> · {alert.resolved_at && new Date(alert.resolved_at).toLocaleString("zh-CN")}</small></p>}
      <div className="feature-actions">{alert.id.includes(":") && <button type="button" onClick={() => onOpenVideo(alert.id.split(":")[0])}>打开视频证据</button>}
        {alert.status === "open" && <button type="button" onClick={() => { setEditing(alert.id); setAction("resolve"); setNote(""); setMessage(""); }}>处理此告警</button>}
        {alert.id.includes(":") && <button type="button" onClick={() => { setEditing(alert.id); setAction("task"); setAssignee(""); setDueAt(nextDay()); }}>创建核查事项</button>}</div>
      {editing === alert.id && <form onSubmit={(e) => submit(e, alert)}>
        {action === "resolve" ? <label>处置说明<textarea required maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} /></label> : <><label>负责人<input required value={assignee} onChange={(e) => setAssignee(e.target.value)} /></label><label>完成时间<input required type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} /></label></>}
        <button disabled={saving}>{saving ? "保存中…" : action === "resolve" ? "确认关闭告警" : "保存核查事项"}</button><button type="button" onClick={() => setEditing(null)}>取消</button>
      </form>}
    </article>)}</div>
  </section>;
}
