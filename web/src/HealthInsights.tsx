import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, CircleHelp, HeartPulse, ScanLine, Sparkles } from "lucide-react";
import { fetchHealthAssessment, fetchVideoJobs, type HealthAssessment, type VideoJob } from "./api";
import HealthReport from "./HealthReport";
import { priorityLabel, priorityOf, priorityShort } from "./priority";
import "./health-insights.css";

const riskText: Record<string, string> = { normal: "未触发规则", low: "低风险提示", medium: "中风险提示", high: "高风险提示", unavailable: "暂无规则评分" };
const particles = Array.from({ length: 30 }, (_, index) => ({
  left: `${(index * 37 + 11) % 100}%`,
  top: `${(index * 53 + 19) % 100}%`,
  delay: `${(index % 9) * -0.7}s`,
  size: `${2 + index % 3}px`,
}));

export default function HealthInsights({ onOpenVideo }: { onOpenVideo?: (jobId: string) => void }) {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [jobId, setJobId] = useState("");
  const [assessment, setAssessment] = useState<HealthAssessment | null>(null);
  const [trackId, setTrackId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [reportGeneratedAt, setReportGeneratedAt] = useState("");

  useEffect(() => {
    fetchVideoJobs().then((rows) => {
      const cattle = rows.filter((row) => row.status === "completed" && row.result?.species !== "sheep");
      setJobs(cattle);
      setJobId(cattle[0]?.id || "");
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "视频列表加载失败"));
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    setAssessment(null);
    setError("");
    fetchHealthAssessment(jobId).then((data) => {
      if (!active) return;
      setAssessment(data);
      setTrackId((data.tracks.find((row) => row.behaviors.length > 0) || data.tracks[0])?.track_id ?? null);
    }).catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "健康分析加载失败"); });
    return () => { active = false; };
  }, [jobId]);

  const track = assessment?.tracks.find((row) => row.track_id === trackId);
  const attention = assessment?.tracks.filter((row) => priorityOf(row) === "high" || priorityOf(row) === "medium") || [];
  const selectedJob = jobs.find((row) => row.id === jobId);

  return <section className="health-insights" aria-label="健康模型分析">
    <div className="health-particles" aria-hidden="true">{particles.map((particle, index) =>
      <i key={index} style={{ left: particle.left, top: particle.top, width: particle.size, height: particle.size, animationDelay: particle.delay }} />
    )}</div>
    <div className="health-insights-content">
      <header className="health-insights-hero">
        <div><span className="health-overline"><Sparkles size={15} /> HERD INTELLIGENCE / 健康观察</span>
          <h3>从视频轨迹，读懂<br /><em>需要复核的信号。</em></h3>
          <p>把规则命中的轨迹按“先看哪一头”排序，并写清证据与下一步。优先级不是疾病概率，行为模型只作旁证。</p>
        </div>
        <div className="health-orbit" aria-hidden="true"><span><HeartPulse size={42} /></span></div>
      </header>

      <div className="health-insights-toolbar">
        <label>分析视频<select value={jobId} onChange={(event) => setJobId(event.target.value)}>
          {jobs.map((job) => <option value={job.id} key={job.id}>{new Date(job.created_at || "").toLocaleString("zh-CN")} · {job.id.slice(0, 8)}</option>)}
        </select></label>
        {jobId && onOpenVideo && <button type="button" onClick={() => onOpenVideo(jobId)}>查看原视频 <ArrowUpRight size={16} /></button>}
        {assessment && <button type="button" onClick={() => setReportGeneratedAt(new Date().toISOString())}>生成健康报告</button>}
      </div>
      {error && <p role="alert" className="health-insights-error">{error}</p>}
      {!jobId && !error && <p className="health-insights-empty">暂无已完成的牛视频。先在“实时监控”上传或打开演示视频。</p>}
      {jobId && !assessment && !error && <p className="health-insights-empty">正在汇总健康数据…</p>}

      {assessment && <>
        <div className="health-kpis">
          <article><ScanLine size={20} /><span>视频内追踪 ID</span><strong>{assessment.summary.track_count}</strong><small>仅在本次视频有效</small></article>
          <article><Activity size={20} /><span>需优先核查的轨迹</span><strong>{assessment.summary.attention_count}</strong><small>命中中、高优先级规则</small></article>
          <article><CircleHelp size={20} /><span>人工复核记录</span><strong>{assessment.summary.review_count}</strong><small>与模型结果分开保存</small></article>
        </div>

        <div className="health-insights-layout">
          <aside className="health-track-list"><div className="health-panel-heading"><span>个体轨迹</span><small>{assessment.tracks.length} 个视频内 ID</small></div>
            {assessment.tracks.map((row) => {
              const priority = priorityOf(row);
              return <button key={row.track_id} type="button" className={trackId === row.track_id ? "selected" : ""} onClick={() => setTrackId(row.track_id)}>
                <span className="health-track-avatar">{row.track_id}</span><span><strong>Track ID {row.track_id}</strong><small>{riskText[row.risk_level] || row.risk_level}</small></span><b className={`health-priority-dot ${priority}`}>{priorityShort[priority]}</b>
              </button>;
            })}
          </aside>

          {track && <div className="health-track-detail">
            <div className="health-detail-top"><div><span className="health-overline">TRACK / {track.track_id}</span><h4>个体核查线索</h4><p>{riskText[track.risk_level] || track.risk_level} · 规则型辅助筛查，不是疾病概率</p></div>
              <span className={`health-priority-badge ${priorityOf(track)}`}>{priorityLabel[priorityOf(track)]}</span>
            </div>
            <section className="health-why" aria-label="为什么被标出来">
              <h5>为什么被标出来</h5>
              {track.priority_reasons.length ? <ul>{track.priority_reasons.map((reason, index) =>
                <li key={`${reason.label}-${index}`}><strong>{reason.label}</strong><small>{reason.time_seconds === null ? "全视频" : `${reason.time_seconds.toFixed(1)} 秒`} · {reason.detail}</small><p>{reason.suggestion}</p></li>
              )}</ul> : <p className="health-muted">本次轨迹未形成规则告警；仍需结合现场观察。</p>}
            </section>
            <p className="health-next-step"><strong>下一步</strong>{track.review_hint}</p>
            <div className="health-detail-grid">
              <section><h5>行为模型旁证</h5><div className="health-behavior-list">{track.behaviors.length ? track.behaviors.map((row, index) =>
                <div key={`${row.behavior_name}-${index}`}><div><span>{row.behavior_display_name}</span><b>{row.duration_seconds.toFixed(1)} 秒</b></div><span className="health-behavior-bar"><i style={{ width: `${Math.min(100, row.eligible_ratio * 100)}%` }} /></span></div>
              ) : <p className="health-muted">此 ID 暂无可用行为摘要。</p>}</div>
                {track.uncertain_duration_seconds > 0 && <p className="health-uncertain">无法确定：{track.uncertain_duration_seconds.toFixed(1)} 秒，可回原视频放大复核。</p>}
                <small className="health-muted">行为模型：{assessment.model.behavior_model_version || assessment.model.behavior_model_status}；只作旁证，不决定核查优先级。</small>
              </section>
              <section className="health-review-strip"><h5>人工复核</h5>{track.reviews.length ? track.reviews.map((review) =>
                <p key={review.id}><strong>{review.verdict === "confirmed" ? "已确认" : review.verdict === "rejected" ? "误报" : "仍待判断"}</strong> · {review.time_seconds === null ? "全视频" : `${review.time_seconds.toFixed(1)} 秒`} · {review.note}</p>
              ) : <p className="health-muted">暂无人工复核。可在视频结果页记录现场判断。</p>}</section>
            </div>
          </div>}
        </div>
        {attention.length > 0 && <p className="health-insights-foot">本次 {attention.length} 个视频内 ID 命中中、高优先级规则。建议先看 {attention.slice(0, 5).map((row) => `ID ${row.track_id}`).join("、")}{attention.length > 5 ? " 等" : ""}，再用原视频和现场状况确认；优先级只表示核查顺序，不是疾病判断。</p>}
        <p className="health-insights-limit">该模型是规则型风险筛查，不能判断具体疾病或预测发病时间；开发素材上的结果未经独立牧场验证。</p>
      </>}
    </div>
    {reportGeneratedAt && assessment && selectedJob && <HealthReport assessment={assessment} job={selectedJob} generatedAt={reportGeneratedAt} onClose={() => setReportGeneratedAt("")} />}
  </section>;
}
