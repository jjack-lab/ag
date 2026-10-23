import { useEffect, useRef, useState } from "react";
import { addSpatialMissed, completeSpatialAudit, createSpatialReport, fetchSpatialAudit, fetchSpatialHistory, fetchSpatialReports, resultMediaUrl, saveSpatialVerdict, SpatialAudit, SpatialReport } from "./api";

type Kind = SpatialReport["kind"];
type Props = { jobId: string; videoPath: string; onReportSaved?: () => void };
const names: Record<Kind, string> = { feeding: "采食区", water: "饮水区", gate: "栏门线" };
const localNow = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);

export default function SpatialAnalysisPanel({ jobId, videoPath, onReportSaved }: Props) {
  const [kind, setKind] = useState<Kind>("feeding");
  const [penId, setPenId] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [observedAt, setObservedAt] = useState(localNow);
  const [geometry, setGeometry] = useState<number[]>([]);
  const [reverse, setReverse] = useState(false);
  const [reports, setReports] = useState<SpatialReport[]>([]);
  const [history, setHistory] = useState<SpatialReport[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [audit, setAudit] = useState<SpatialAudit | null>(null);
  const [reviewer, setReviewer] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [missedTime, setMissedTime] = useState("");
  const [missedDirection, setMissedDirection] = useState<"enter" | "leave">("enter");
  const [missedNote, setMissedNote] = useState("");
  const start = useRef<[number, number] | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    fetchSpatialReports(jobId).then((rows) => setReports(Array.isArray(rows) ? rows : [])).catch(() => setReports([]));
  }, [jobId]);
  useEffect(() => {
    const saved = reports.find((report) => report.kind === kind);
    setGeometry(saved?.geometry || []);
    setReverse(saved?.reverse || false);
    if (saved) { setPenId(saved.pen_id); setCameraId(saved.camera_id); }
  }, [kind, reports]);
  const current = reports.find((report) => report.kind === kind);
  useEffect(() => {
    if (!reports.some((report) => report.kind === kind)) { setAudit(null); return; }
    fetchSpatialAudit(jobId, kind).then(setAudit).catch(() => setAudit(null));
  }, [jobId, kind, reports]);

  function seek(seconds: number) {
    if (!video.current) return;
    video.current.currentTime = seconds;
    video.current.play();
  }

  async function markEvent(index: number, verdict: "correct" | "false_positive" | "wrong_direction") {
    try {
      setAudit(await saveSpatialVerdict(jobId, kind, { event_index: index, verdict,
        reviewer: reviewer.trim(), note: reviewNote.trim() }));
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "保存核对失败"); }
  }

  async function addMissed(event: React.FormEvent) {
    event.preventDefault();
    try {
      setAudit(await addSpatialMissed(jobId, kind, { time_seconds: Number(missedTime),
        ...(kind === "gate" ? { direction: missedDirection } : {}), reviewer: reviewer.trim(), note: missedNote.trim() }));
      setMissedTime(""); setMissedNote(""); setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "补录失败"); }
  }

  async function confirmCoverage() {
    try { setAudit(await completeSpatialAudit(jobId, kind, reviewer.trim())); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "完成核对失败"); }
  }

  function point(event: React.PointerEvent<HTMLDivElement>): [number, number] {
    const box = stage.current!.getBoundingClientRect();
    return [Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)),
            Math.max(0, Math.min(1, (event.clientY - box.top) / box.height))];
  }
  function finish(event: React.PointerEvent<HTMLDivElement>) {
    if (!start.current) return;
    const [x1, y1] = start.current;
    const [x2, y2] = point(event);
    setGeometry(kind === "gate" ? [x1, y1, x2, y2] :
      [Math.min(x1, x2), Math.min(y1, y2), Math.max(x1, x2), Math.max(y1, y2)]);
    start.current = null;
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (geometry.length !== 4) { setError("先在视频画面上拖出区域或栏门线"); return; }
    setSaving(true);
    setError("");
    try {
      const report = await createSpatialReport(jobId, {
        pen_id: penId.trim(), camera_id: cameraId.trim(), observed_at: new Date(observedAt).toISOString(),
        kind, geometry, reverse,
      });
      setReports((rows) => [...rows.filter((row) => row.kind !== kind), report]);
      onReportSaved?.();
      setHistory(await fetchSpatialHistory(report.pen_id, report.camera_id, kind));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "区域分析失败");
    } finally { setSaving(false); }
  }
  async function showHistory() {
    if (!current) return;
    try { setHistory(await fetchSpatialHistory(current.pen_id, current.camera_id, kind)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "历史加载失败"); }
  }
  async function loadLastArea() {
    if (!penId.trim() || !cameraId.trim()) { setError("先填写圈舍和固定机位编号"); return; }
    try {
      const rows = await fetchSpatialHistory(penId.trim(), cameraId.trim(), kind);
      if (!rows.length) { setError("该机位还没有保存过此类画区"); return; }
      setGeometry(rows[0].geometry);
      setReverse(rows[0].reverse || false);
      setHistory(rows);
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "历史画区加载失败"); }
  }
  const comparable = history.filter((row) => row.job_id !== jobId &&
    JSON.stringify(row.geometry) === JSON.stringify(current?.geometry) &&
    Date.parse(row.observed_at) < Date.parse(current?.observed_at || "") &&
    Date.parse(row.observed_at) >= Date.parse(current?.observed_at || "") - 7 * 86400000);
  const rateRows = comparable.filter((row) => row.duration_seconds >= 600);
  const average = rateRows.length && kind !== "gate" ?
    rateRows.reduce((sum, row) => sum + (row.metrics.entries || 0) * 3600 / row.duration_seconds, 0) / rateRows.length : null;
  const currentRate = current && current.duration_seconds >= 600 ? (current.metrics.entries || 0) * 3600 / current.duration_seconds : null;
  const sameDay = history.filter((row) => row.kind === "gate" && row.observed_at.slice(0, 10) === current?.observed_at.slice(0, 10) &&
    JSON.stringify(row.geometry) === JSON.stringify(current?.geometry) && row.reverse === current?.reverse);

  return <section className="spatial-panel" aria-label="固定机位空间分析">
    <header><h4>固定机位空间分析</h4><small>拖动画面画区域或栏门线；仅作视频辅助统计，需人工核对。</small></header>
    <div className="spatial-kind">
      {(Object.keys(names) as Kind[]).map((value) => <button key={value} type="button" aria-pressed={kind === value}
        onClick={() => { setKind(value); setHistory([]); }}>{names[value]}</button>)}
    </div>
    <div ref={stage} className="spatial-stage" onPointerDown={(event) => {
      start.current = point(event); event.currentTarget.setPointerCapture(event.pointerId);
    }} onPointerUp={finish}>
      <video ref={video} src={resultMediaUrl(videoPath)} muted playsInline preload="metadata" />
      {geometry.length === 4 && <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="画出的区域或线">
        {kind === "gate" ? <line x1={geometry[0] * 100} y1={geometry[1] * 100} x2={geometry[2] * 100} y2={geometry[3] * 100} /> :
          <rect x={geometry[0] * 100} y={geometry[1] * 100} width={(geometry[2] - geometry[0]) * 100} height={(geometry[3] - geometry[1]) * 100} />}
      </svg>}
    </div>
    <div className="spatial-kind"><button type="button" onClick={() => video.current?.paused ? video.current.play() : video.current?.pause()}>播放 / 暂停画面</button>
      <button type="button" onClick={loadLastArea}>沿用该机位上次画区</button></div>
    <form onSubmit={save}>
      <label>圈舍编号<input required value={penId} onChange={(event) => setPenId(event.target.value)} placeholder="例如 A-01" /></label>
      <label>固定机位编号<input required value={cameraId} onChange={(event) => setCameraId(event.target.value)} placeholder="例如 栏门摄像头" /></label>
      <label>拍摄开始时间<input required type="datetime-local" value={observedAt} onChange={(event) => setObservedAt(event.target.value)} /></label>
      {kind === "gate" && <label className="spatial-reverse"><input type="checkbox" checked={reverse} onChange={(event) => setReverse(event.target.checked)} />反转进出方向（默认按画线起点→终点的右侧至左侧计进入）</label>}
      <button type="submit" disabled={saving}>{saving ? "分析中…" : `保存${names[kind]}统计`}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {current && <div className="spatial-results">
      <strong>{names[kind]} · {current.pen_id} · {current.camera_id}</strong>
      <small>拍摄开始：{new Date(current.observed_at).toLocaleString("zh-CN")}</small>
      {current.alerts?.map((hint) => <p key={hint.label} role="status">待核查：{hint.label}（视频 {hint.time_seconds} 秒）。{hint.detail} 可在上方事件时间轴查看截图和片段。</p>)}
      {kind === "gate" ? <><p>本段视频辅助计数：进入 {current.metrics.enter} 次，离开 {current.metrics.leave} 次。请结合出入栏台账复核。</p>
        <ul>{current.metrics.events?.map((row, index) => <li key={`${row.track_id}-${index}`}>
          {new Date(Date.parse(current.observed_at) + row.time_seconds * 1000).toLocaleString("zh-CN")}：
          ID {row.track_id} {row.direction === "enter" ? "进入" : "离开"}
        </li>)}</ul></> :
        <><p>进入区域 {current.metrics.entries} 次，累计停留 {current.metrics.dwell_seconds} 秒。</p>
          <ul>{current.metrics.hourly?.map((row) => <li key={row.hour}>{row.hour}：进入 {row.entries} 次，停留 {row.dwell_seconds} 秒</li>)}</ul></>}
      {audit && <div className="spatial-audit">
        <h5>逐事件人工核对</h5>
        <p>人工核对 {audit.summary.reviewed}/{audit.summary.automatic}；正确 {audit.summary.correct}，误报 {audit.summary.false_positive}，方向错误 {audit.summary.wrong_direction}，漏计 {audit.summary.missed}。</p>
        <label>核对人<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>
        <label>核对备注<input value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} /></label>
        <ol>{audit.events.map((row, index) => <li key={`${row.track_id}-${row.time_seconds}-${index}`}>
          <button type="button" onClick={() => seek(row.time_seconds)}>回看 {row.time_seconds} 秒</button>
          ID {row.track_id} {row.direction === "enter" ? "进入" : row.direction === "leave" ? "离开" : `停留 ${row.dwell_seconds ?? 0} 秒`}
          <span> {audit.audit.verdicts[String(index)]?.verdict === "correct" ? "已确认" :
            audit.audit.verdicts[String(index)]?.verdict === "false_positive" ? "误报" :
            audit.audit.verdicts[String(index)]?.verdict === "wrong_direction" ? "方向错误" : "待核对"}</span>
          <div className="spatial-audit-actions">
            <button type="button" disabled={!reviewer.trim() || !reviewNote.trim()} onClick={() => markEvent(index, "correct")}>确认正确</button>
            <button type="button" disabled={!reviewer.trim() || !reviewNote.trim()} onClick={() => markEvent(index, "false_positive")}>标记误报</button>
            {kind === "gate" && <button type="button" disabled={!reviewer.trim() || !reviewNote.trim()} onClick={() => markEvent(index, "wrong_direction")}>方向错误</button>}
          </div>
        </li>)}</ol>
        <form onSubmit={addMissed} className="spatial-audit-missed">
          <label>漏计时间（秒）<input type="number" min="0" max={current.duration_seconds} step="0.1" required value={missedTime} onChange={(event) => setMissedTime(event.target.value)} /></label>
          {kind === "gate" && <label>实际方向<select value={missedDirection} onChange={(event) => setMissedDirection(event.target.value as "enter" | "leave")}><option value="enter">进入</option><option value="leave">离开</option></select></label>}
          <label>漏计备注<input required value={missedNote} onChange={(event) => setMissedNote(event.target.value)} /></label>
          <button type="submit" disabled={!reviewer.trim()}>补录漏计</button>
        </form>
        <button type="button" disabled={!reviewer.trim() || audit.summary.reviewed !== audit.summary.automatic} onClick={confirmCoverage}>确认已回看完整视频</button>
        <p>{audit.summary.complete ? `事件级 Precision ${(audit.summary.precision! * 100).toFixed(1)}%，Recall ${(audit.summary.recall! * 100).toFixed(1)}%（本视频人工核对）` : "尚未完成全段核对，不显示完整精度。"}</p>
      </div>}
      <button type="button" onClick={showHistory}>{kind === "gate" ? "查看同日栏门汇总" : "与过去 7 天相同机位比较"}</button>
      {history.length > 0 && (kind === "gate" ? <p>同日 {sameDay.length} 段视频辅助汇总：进入 {sameDay.reduce((sum, row) => sum + (row.metrics.enter || 0), 0)} 次，离开 {sameDay.reduce((sum, row) => sum + (row.metrics.leave || 0), 0)} 次。交接班请以人工台账核对。</p> :
        <p>{average === null || currentRate === null ? "趋势比较需本段和历史视频均至少 10 分钟，且使用同机位、同画区；当前尚无可比数据。" :
          `过去 ${rateRows.length} 段可比视频平均每小时进入 ${average.toFixed(1)} 次；本段每小时 ${currentRate.toFixed(1)} 次。`}</p>)}
    </div>}
    <small>仅统计视频内 Track ID 的轨迹；遮挡、漏检、镜头移动和 ID 切换可能影响结果。区域活动不能直接等同实际采食或饮水。</small>
  </section>;
}
