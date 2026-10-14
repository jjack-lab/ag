import { FormEvent, PointerEvent, useEffect, useRef, useState } from "react";
import {
  createVideoCorrection, deleteVideoCorrection, fetchVideoCorrections,
  NewVideoCorrection, resultMediaUrl, VideoCorrection, videoCorrectionsCsvUrl,
} from "./api";

type Box = NonNullable<VideoCorrection["box"]>;
type Props = {
  jobId: string;
  videoPath: string;
  species: "cattle" | "sheep";
  trackIds: number[];
  onCorrectionChanged?: () => void;
};

const names: Record<VideoCorrection["kind"], string> = {
  missed_detection: "漏检框", id_correction: "Track ID 修正", behavior_correction: "行为标签修正",
};
const behaviorNames = [
  ["grazing", "采食"], ["drinking", "饮水"], ["ruminating-standing", "站立反刍"],
  ["ruminating-lying", "卧姿反刍"], ["resting-standing", "站立休息"],
  ["resting-lying", "卧姿休息"], ["walking", "行走"], ["standing", "站立"], ["lying", "卧倒"],
];

export default function VideoCorrectionEditor({ jobId, videoPath, species, trackIds, onCorrectionChanged }: Props) {
  const [rows, setRows] = useState<VideoCorrection[]>([]);
  const [kind, setKind] = useState<VideoCorrection["kind"]>("missed_detection");
  const [time, setTime] = useState(0);
  const [box, setBox] = useState<Box | null>(null);
  const [trackId, setTrackId] = useState("");
  const [correctedTrackId, setCorrectedTrackId] = useState("");
  const [behaviorLabel, setBehaviorLabel] = useState("grazing");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const origin = useRef<{ x: number; y: number } | null>(null);
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let active = true;
    setRows([]);
    fetchVideoCorrections(jobId)
      .then((result) => { if (!Array.isArray(result)) throw new Error("纠错记录响应格式错误"); if (active) setRows(result); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "纠错记录加载失败"); });
    return () => { active = false; };
  }, [jobId]);

  function point(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
  }

  function updateBox(event: PointerEvent<HTMLDivElement>) {
    if (!origin.current) return;
    const end = point(event);
    setBox({ x: Math.min(origin.current.x, end.x), y: Math.min(origin.current.y, end.y),
      width: Math.abs(end.x - origin.current.x), height: Math.abs(end.y - origin.current.y) });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!video.current || !note.trim()) return;
    if (kind === "missed_detection" && (!box || box.width < 0.01 || box.height < 0.01)) {
      setError("请先在暂停画面上拖拽画出漏检框"); return;
    }
    const payload: NewVideoCorrection = {
      kind, time_seconds: time,
      track_id: kind === "missed_detection" ? null : Number(trackId),
      corrected_track_id: kind === "id_correction" ? Number(correctedTrackId) : null,
      behavior_label: kind === "behavior_correction" ? behaviorLabel : null,
      box: kind === "missed_detection" ? box : null,
      note: note.trim(),
    };
    setSaving(true);
    setError("");
    try {
      const saved = await createVideoCorrection(jobId, payload);
      setRows((previous) => [...previous, saved].sort((a, b) => a.frame_index - b.frame_index));
      setNote("");
      setBox(null);
      setDrawing(false);
      onCorrectionChanged?.();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存纠错失败");
    } finally { setSaving(false); }
  }

  async function remove(id: string) {
    try {
      await deleteVideoCorrection(jobId, id);
      setRows((previous) => previous.filter((row) => row.id !== id));
      onCorrectionChanged?.();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除纠错失败");
    }
  }

  const visibleBoxes = rows.filter((row) => row.box && Math.abs(row.time_seconds - time) < 0.12);
  return <section className="video-correction-editor" aria-label="画面人工纠错">
    <header><strong>画面人工纠错</strong><small>原结果保留；人工修正单独记录</small></header>
    <p>暂停视频后，可画出漏检框，或修正这一时刻的 Track ID 与牛只行为标签。</p>
    <div className="correction-video-shell">
      <video ref={video} src={resultMediaUrl(videoPath)} controls={!drawing} aria-label="纠错视频画面"
        onTimeUpdate={(event) => { setTime(event.currentTarget.currentTime); setBox(null); }} />
      {visibleBoxes.map((row) => <div key={row.id} className="correction-saved-box"
        style={{ left: `${row.box!.x * 100}%`, top: `${row.box!.y * 100}%`,
          width: `${row.box!.width * 100}%`, height: `${row.box!.height * 100}%` }} />)}
      {kind === "missed_detection" && drawing && <div className="correction-draw-layer"
        aria-label="拖拽绘制漏检框"
        onPointerDown={(event) => {
          if (!video.current?.paused) { setError("请先暂停视频"); return; }
          origin.current = point(event);
          setBox(null);
          event.currentTarget.setPointerCapture?.(event.pointerId);
        }}
        onPointerMove={updateBox}
        onPointerUp={(event) => { updateBox(event); origin.current = null; }}>
        {box && <div className="correction-draft-box" style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`,
          width: `${box.width * 100}%`, height: `${box.height * 100}%` }} />}
      </div>}
    </div>
    <form onSubmit={save}>
      <label>纠错类型<select value={kind} onChange={(event) => { setKind(event.target.value as VideoCorrection["kind"]); setBox(null); setDrawing(false); }}>
        <option value="missed_detection">漏检框</option>
        <option value="id_correction">Track ID 修正</option>
        {species === "cattle" && <option value="behavior_correction">行为标签修正</option>}
      </select></label>
      {kind === "missed_detection" && <button type="button" onClick={() => { video.current?.pause(); setDrawing(true); }}>
        {drawing ? "在画面中拖拽画框" : "暂停并绘制漏检框"}
      </button>}
      {kind !== "missed_detection" && <label>原 Track ID<select required value={trackId} onChange={(event) => setTrackId(event.target.value)}>
        <option value="">请选择</option>{trackIds.map((id) => <option key={id} value={id}>{id}</option>)}
      </select></label>}
      {kind === "id_correction" && <label>修正后的 Track ID<input required type="number" min="0" step="1" value={correctedTrackId} onChange={(event) => setCorrectedTrackId(event.target.value)} /></label>}
      {kind === "behavior_correction" && <label>正确行为<select value={behaviorLabel} onChange={(event) => setBehaviorLabel(event.target.value)}>
        {behaviorNames.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>}
      <label>纠错说明<textarea required maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} /></label>
      <span>当前时间 {time.toFixed(1)} 秒{box && ` · 框位置 ${(box.x * 100).toFixed(1)}%, ${(box.y * 100).toFixed(1)}%`}</span>
      <button type="submit" disabled={saving || !note.trim()}>{saving ? "保存中…" : "保存画面纠错"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    <div className="correction-history">
      <strong>已保存 {rows.length} 条</strong>
      <a href={videoCorrectionsCsvUrl(jobId)} download>导出纠错 CSV</a>
    </div>
    {rows.map((row) => <article key={row.id} className="correction-row">
      <button type="button" onClick={() => { if (video.current) video.current.currentTime = row.time_seconds; }}>
        {row.time_seconds.toFixed(1)} 秒
      </button>
      <span>{names[row.kind]}{row.track_id !== null ? ` · ID ${row.track_id}` : ""}{row.corrected_track_id !== null ? ` → ${row.corrected_track_id}` : ""}{row.behavior_label ? ` · ${row.behavior_label}` : ""}</span>
      <small>{row.note}</small>
      <button type="button" onClick={() => remove(row.id)} aria-label={`删除 ${row.time_seconds.toFixed(1)} 秒纠错`}>删除</button>
    </article>)}
  </section>;
}
