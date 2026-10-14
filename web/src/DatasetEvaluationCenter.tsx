import { FormEvent, useEffect, useState } from "react";
import {
  createDatasetEvaluation, DatasetEvaluation, fetchDatasetEvaluations,
  fetchVideoJobs, VideoJob,
} from "./api";

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

export default function DatasetEvaluationCenter() {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [evaluations, setEvaluations] = useState<DatasetEvaluation[]>([]);
  const [jobId, setJobId] = useState("");
  const [datasetName, setDatasetName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [datasetVersion, setDatasetVersion] = useState("");
  const [licenseName, setLicenseName] = useState("");
  const [splitName, setSplitName] = useState<DatasetEvaluation["split_name"]>("external_test");
  const [annotations, setAnnotations] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([fetchVideoJobs(), fetchDatasetEvaluations()])
      .then(([nextJobs, nextEvaluations]) => {
        if (!Array.isArray(nextJobs) || !Array.isArray(nextEvaluations)) throw new Error("评测数据响应格式错误");
        if (active) { setJobs(nextJobs.filter((job) => job.status === "completed")); setEvaluations(nextEvaluations); }
      })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "评测中心加载失败"); });
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!annotations || !jobId) return;
    setSaving(true);
    setError("");
    try {
      const saved = await createDatasetEvaluation({
        jobId, datasetName, sourceUrl, datasetVersion, licenseName, splitName, annotations,
      });
      setEvaluations((rows) => [saved, ...rows]);
      setAnnotations(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "评测失败");
    } finally { setSaving(false); }
  }

  return <section className="dataset-evaluation-center" aria-label="公开数据评测中心">
    <header><h3>公开数据评测中心</h3><span>逐帧真值 · 可复算指标</span></header>
    <p>先在识别工作台上传公开数据原视频并完成追踪，再导入同一视频的逐帧人工标注。来源、版本、许可与划分由使用者登记，系统保存原视频和标注的 SHA-256。</p>
    <p>标注 CSV 列：<code>frame_index,class_id,track_id,x,y,width,height</code>。帧号从 0 开始；坐标为左上角起点与宽高，均归一化到 0–1；仅评测有标注的帧。牛 class_id=1，羊 class_id=0。</p>
    <form onSubmit={submit}>
      <label>已完成视频任务<select required value={jobId} onChange={(event) => setJobId(event.target.value)}>
        <option value="">请选择</option>
        {jobs.map((job) => <option key={job.id} value={job.id}>{job.result?.species === "sheep" ? "羊" : "牛"} · {job.created_at ? new Date(job.created_at).toLocaleString("zh-CN") : job.id.slice(0, 8)} · {job.id.slice(0, 8)}</option>)}
      </select></label>
      <label>数据集名称<input required maxLength={300} value={datasetName} onChange={(event) => setDatasetName(event.target.value)} /></label>
      <label>来源网址<input required type="url" maxLength={300} value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></label>
      <label>数据版本<input required maxLength={300} value={datasetVersion} onChange={(event) => setDatasetVersion(event.target.value)} /></label>
      <label>数据许可<input required maxLength={300} value={licenseName} onChange={(event) => setLicenseName(event.target.value)} /></label>
      <label>数据划分<select value={splitName} onChange={(event) => setSplitName(event.target.value as DatasetEvaluation["split_name"])}>
        <option value="development">开发</option><option value="validation">验证</option><option value="external_test">外部测试</option>
      </select></label>
      <label>逐帧真值 CSV<input type="file" accept=".csv,text/csv" onChange={(event) => setAnnotations(event.target.files?.[0] || null)} /></label>
      <button type="submit" disabled={saving || !annotations || !jobId}>{saving ? "计算中…" : "导入并计算"}</button>
    </form>
    {jobs.length === 0 && <p>暂无已完成视频任务，请先到识别工作台上传并处理视频。</p>}
    {error && <p role="alert">{error}</p>}
    <div className="dataset-evaluation-list">
      {evaluations.length === 0 && <p>尚无评测记录；没有导入数据时不显示基准分数。</p>}
      {evaluations.map((evaluation) => <article key={evaluation.id}>
        <div><strong>{evaluation.dataset_name}</strong><span>{evaluation.dataset_version} · {evaluation.split_name}</span></div>
        <a href={evaluation.source_url} target="_blank" rel="noreferrer">数据来源</a>
        <div className="evaluation-metrics">
          <span>Precision <strong>{percent(evaluation.metrics.precision)}</strong></span>
          <span>Recall <strong>{percent(evaluation.metrics.recall)}</strong></span>
          <span>F1 <strong>{percent(evaluation.metrics.f1)}</strong></span>
          <span>ID 切换 <strong>{evaluation.metrics.id_switches}</strong></span>
        </div>
        <small>{evaluation.metrics.labeled_frames} 个有标注帧 · {evaluation.metrics.ground_truth_boxes} 个真值框 · IoU ≥ {evaluation.metrics.iou_threshold} · TP {evaluation.metrics.true_positive} / FP {evaluation.metrics.false_positive} / FN {evaluation.metrics.false_negative}；ID 切换仅在已标注且匹配成功的帧间计算。</small>
        <small>许可（用户登记）：{evaluation.license_name}</small>
        <small>原视频 SHA-256：<code>{evaluation.video_sha256}</code></small>
        <small>标注 SHA-256：<code>{evaluation.annotations_sha256}</code></small>
      </article>)}
    </div>
  </section>;
}
