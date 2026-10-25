import type { HealthEvidenceProfile } from "./api";
import { priorityFromRiskLevel, priorityLabel } from "./priority";

type Props = { species: "cattle" | "sheep"; profiles: HealthEvidenceProfile[] };

export default function HealthEvidence({ species, profiles }: Props) {
  return (
    <section className="health-evidence" aria-label="健康证据图谱">
      <header>
        <strong>健康证据图谱</strong>
        <small>视频内追踪 ID → 观察证据 → 核查优先级 → 人工复核</small>
      </header>
      {species === "sheep" ? (
        <p>羊的健康规则尚未验证；当前仅展示检测、追踪与轨迹，不能给出羊的健康评分或疾病预测。</p>
      ) : profiles.length === 0 ? (
        <p>本次没有可形成健康证据链的牛只轨迹。</p>
      ) : (
        <div className="health-evidence-list">
          {profiles.map((profile) => (
            <article key={profile.track_id} className="health-evidence-chain">
              <div className="health-evidence-node">
                <small>对象</small>
                <strong>视频内 ID {profile.track_id}</strong>
              </div>
              <div className="health-evidence-node">
                <small>观察证据</small>
                {profile.observations.length ? profile.observations.map((observation, index) => (
                  <span key={`${observation.type}-${index}`} title={observation.detail}>
                    {observation.label} · {observation.time_seconds === null ? "全视频" : `${observation.time_seconds.toFixed(1)} 秒`}
                  </span>
                )) : <span>未触发规则告警</span>}
              </div>
              <div className="health-evidence-node">
                <small>核查优先级</small>
                <strong>{priorityLabel[priorityFromRiskLevel(profile.risk_level)]}</strong>
              </div>
              <div className="health-evidence-node">
                <small>下一步</small>
                {profile.observations.length ? (
                  [...new Set(profile.observations.map((row) => row.suggestion))].map((suggestion) => (
                    <span key={suggestion}>{suggestion}</span>
                  ))
                ) : <span>继续观察，结合现场情况复核</span>}
              </div>
            </article>
          ))}
        </div>
      )}
      <p className="health-evidence-limit">图中优先级只表示本次视频内的核查顺序，不能判断具体疾病或预测发病时间。</p>
    </section>
  );
}
