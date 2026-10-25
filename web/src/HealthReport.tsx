import { createPortal } from "react-dom";
import { FileDown, X } from "lucide-react";
import type { HealthAssessment, VideoJob } from "./api";
import { priorityLabel, priorityOf } from "./priority";
import "./health-report.css";

const verdictLabel: Record<string, string> = { confirmed: "已确认", rejected: "已排除", uncertain: "仍待判断" };

type Props = { assessment: HealthAssessment; job: VideoJob; generatedAt: string; onClose: () => void };

export default function HealthReport({ assessment, job, generatedAt, onClose }: Props) {
  return createPortal(<div className="health-report-portal" role="dialog" aria-modal="true" aria-label="牛只健康观察报告">
    <div className="health-report-actions">
      <button type="button" onClick={() => window.print()}><FileDown size={17} /> 打印或保存 PDF</button>
      <button type="button" onClick={onClose}><X size={17} /> 关闭报告</button>
    </div>
    <article className="health-report">
      <header className="health-report-header">
        <div><span>AGRINEBULA · 视频健康观察</span><h1>牛只健康观察报告</h1><p>规则型风险辅助筛查 · 单次视频</p></div>
        <strong>星牧智控<br /><small>RESEARCH PROTOTYPE</small></strong>
      </header>
      <div className="health-report-meta">
        <p><span>视频任务</span><b>{job.id}</b></p>
        <p><span>处理时间</span><b>{job.updated_at ? new Date(job.updated_at).toLocaleString("zh-CN") : "未记录"}</b></p>
        <p><span>报告生成</span><b>{new Date(generatedAt).toLocaleString("zh-CN")}</b></p>
        <p><span>分析依据</span><b>{assessment.model.name}；行为模型 {assessment.model.behavior_model_version || assessment.model.behavior_model_status}</b></p>
      </div>
      <section className="health-report-summary" aria-label="报告概览">
        <div><small>视频内 Track ID</small><strong>{assessment.summary.track_count}</strong></div>
        <div><small>需优先核查的轨迹</small><strong>{assessment.summary.attention_count}</strong></div>
        <div><small>人工复核记录</small><strong>{assessment.summary.review_count}</strong></div>
        <div><small>已处理帧数</small><strong>{job.result?.frame_count ?? "—"}</strong></div>
      </section>
      <section><h2>分析说明</h2><p>{assessment.model.score_basis}。核查优先级只表示本次视频内的核查顺序，不是疾病概率，也不能跨视频认定同一动物。</p></section>
      <section><h2>逐个体摘要</h2><div className="health-report-table-wrap"><table><thead><tr><th>视频内 ID</th><th>核查优先级</th><th>触发规则</th><th>主要行为</th><th>无法确定</th><th>人工复核</th></tr></thead><tbody>
        {assessment.tracks.map((track) => {
          const primary = [...track.behaviors].sort((a, b) => b.duration_seconds - a.duration_seconds)[0];
          const rules = track.priority_reasons.map((row) => row.label).filter(Boolean).join("、") || "未触发";
          return <tr key={track.track_id}><td>ID {track.track_id}</td><td>{priorityLabel[priorityOf(track)]}</td><td>{rules}</td>
            <td>{primary ? `${primary.behavior_display_name} ${primary.duration_seconds.toFixed(1)} 秒` : "暂无"}</td>
            <td>{track.uncertain_duration_seconds.toFixed(1)} 秒</td><td>{track.reviews.length} 条</td></tr>;
        })}
      </tbody></table></div></section>
      <section><h2>证据与人工记录</h2>{assessment.tracks.map((track) => <div className="health-report-track" key={track.track_id}>
        <h3>ID {track.track_id} · {priorityLabel[priorityOf(track)]}</h3>
        <p>{track.analysis}</p>
        {track.observations.length > 0 && <p><b>规则证据：</b>{track.observations.map((row) => `${row.label}（${row.time_seconds === null ? "全视频" : `${row.time_seconds.toFixed(1)} 秒`}）`).join("；")}</p>}
        {track.behaviors.length > 0 && <p><b>行为摘要：</b>{track.behaviors.map((row) => `${row.behavior_display_name} ${row.duration_seconds.toFixed(1)} 秒`).join("；")}</p>}
        <p><b>建议动作：</b>{track.review_hint}</p>
        {track.reviews.map((review) => <p key={review.id}><b>人工复核：</b>{verdictLabel[review.verdict] || review.verdict} · {review.note}</p>)}
      </div>)}</section>
      <footer><strong>使用边界</strong><p>本报告仅依据单次视频的检测追踪、轨迹规则、行为摘要及已有人工复核生成。开发素材未经独立牧场验证；不能用于疾病诊断、发病时间预测或代替兽医与现场人员判断。</p><small>报告任务 ID：{assessment.job_id}</small></footer>
    </article>
  </div>, document.body);
}
