import { AnimalProfile } from "./api";

export default function AnimalTrend({ profile }: { profile: AnimalProfile }) {
  const points = profile.visits.flatMap((visit) => {
    if (profile.species === "cattle" && visit.health_evidence) {
      return [{ jobId: visit.job_id, date: visit.recorded_at,
        value: visit.health_evidence.risk_score, trackId: visit.track_id,
        reviews: visit.reviews.length }];
    }
    if (profile.species === "sheep" && visit.sheep_motion?.observed_seconds) {
      const movement = visit.sheep_motion.moving_seconds + visit.sheep_motion.fast_seconds;
      return [{ jobId: visit.job_id, date: visit.recorded_at,
        value: movement / visit.sheep_motion.observed_seconds * 100,
        trackId: visit.track_id, reviews: visit.reviews.length }];
    }
    return [];
  }).sort((a, b) => a.date.localeCompare(b.date));
  const label = profile.species === "cattle" ? "规则风险分" : "可观察时间中的移动占比";
  return <section className="animal-trend" aria-label="个体跨天趋势">
    <h4>跨天观察趋势</h4>
    <p>{profile.species === "cattle"
      ? "每次视频独立计算规则风险分；不同镜头和时长会影响数值。"
      : "按本次视频的连续追踪时间计算移动占比；这是轨迹活动量，不是羊的健康评分。"}</p>
    {points.length < 2 && <p>至少需要同一个体的两次有效视频记录，才能显示变化。</p>}
    {points.length >= 2 && <>
      <strong>{label}：{points[0].value.toFixed(1)} → {points[points.length - 1].value.toFixed(1)}{profile.species === "sheep" ? "%" : " 分"}</strong>
      <div className="animal-trend-bars">
        {points.map((point) => <div key={`${point.jobId}:${point.trackId}`} className="animal-trend-row">
          <span>{new Date(point.date).toLocaleDateString("zh-CN")}</span>
          <div className="animal-trend-track"><div style={{ width: `${Math.min(100, Math.max(0, point.value))}%` }} /></div>
          <b>{point.value.toFixed(1)}{profile.species === "sheep" ? "%" : " 分"}</b>
          <small>复核 {point.reviews} 条</small>
        </div>)}
      </div>
    </>}
  </section>;
}
