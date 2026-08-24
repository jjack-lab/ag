import { useEffect, useState } from "react";

import {
  CrossDomainExperimentResult,
  fetchCrossDomainExperiment,
} from "./api";


const variantLabels = {
  uncalibrated: "未校准",
  calibrated: "温度校准",
  calibrated_fixed_rejection: "固定阈值拒识",
  calibrated_quality_rejection: "质量感知拒识",
} as const;

const variantOrder = Object.keys(variantLabels) as Array<keyof typeof variantLabels>;

type Props = {
  result?: CrossDomainExperimentResult;
};

function percentage(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export default function CrossDomainResults({ result: suppliedResult }: Props) {
  const [loadedResult, setLoadedResult] = useState<CrossDomainExperimentResult | null>(
    suppliedResult || null,
  );
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (suppliedResult) {
      setLoadedResult(suppliedResult);
      return;
    }
    let active = true;
    fetchCrossDomainExperiment()
      .then((next) => {
        if (active) setLoadedResult(next);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [suppliedResult]);

  return (
    <section className="cross-domain-results" aria-labelledby="cross-domain-title">
      <header>
        <div>
          <p>EXTERNAL ROBUSTNESS</p>
          <h3 id="cross-domain-title">跨域鲁棒性证据</h3>
        </div>
        <span>研究答辩视图</span>
      </header>

      {!loadedResult && !failed && <p className="cross-domain-state">正在读取冻结实验结果…</p>}
      {failed && <p className="cross-domain-state">结果接口暂不可用。</p>}
      {loadedResult?.status === "not_run" && (
        <div className="cross-domain-state">
          <strong>真实外部实验尚未完成</strong>
          <span>当前只展示协议准备状态，不把代码测试当作跨域效果。</span>
        </div>
      )}
      {loadedResult?.status === "blocked" && (
        <div className="cross-domain-state blocked">
          <strong>实验受阻</strong>
          {loadedResult.limitations.map((item) => <span key={item}>{item}</span>)}
        </div>
      )}
      {loadedResult?.status === "complete" && (
        <>
          <div className="cross-domain-meta">
            <span>数据集 {loadedResult.dataset_id} v{loadedResult.dataset_version}</span>
            <span>模型 {loadedResult.model_hash_prefix}</span>
          </div>
          {(["strict", "extended"] as const).map((tier) => {
            const metrics = loadedResult.variant_metrics[tier];
            const count = loadedResult.sample_counts[tier];
            if (!metrics || !count) return null;
            return (
              <article key={tier} className="cross-domain-tier">
                <h4>{tier === "strict" ? "严格映射" : "扩展映射"}（n={count}）</h4>
                <div className="cross-domain-table" role="table" aria-label={`${tier} 协议比较`}>
                  <div role="row" className="head">
                    <span>协议</span><span>Macro-F1</span><span>覆盖率</span><span>选择性风险</span>
                  </div>
                  {variantOrder.map((variant) => (
                    <div role="row" key={variant}>
                      <strong>{variantLabels[variant]}</strong>
                      <span>{percentage(metrics[variant].selective_macro_f1)}</span>
                      <span>{percentage(metrics[variant].coverage)}</span>
                      <span>{percentage(metrics[variant].selective_risk)}</span>
                    </div>
                  ))}
                </div>
              </article>
            );
          })}
          <p className="quality-gate-note">
            {loadedResult.quality_policy === "predeclared_heuristic"
              ? "本次使用查看外部指标前冻结的预声明启发式质量规则，未使用 CBVD-5 标签拟合；仅作探索性证据。"
              : "质量门仅使用已验证的 CVB 验证质量行训练，未使用 CBVD-5 标签拟合。"}
          </p>
          <div className="cross-domain-figures">
            {loadedResult.figure_urls.confusion_matrix && (
              <img src={loadedResult.figure_urls.confusion_matrix} alt="严格映射混淆矩阵" />
            )}
            {loadedResult.figure_urls.risk_coverage && (
              <img src={loadedResult.figure_urls.risk_coverage} alt="风险与覆盖率曲线" />
            )}
            {loadedResult.figure_urls.stress_curves && (
              <img src={loadedResult.figure_urls.stress_curves} alt="视频退化压力曲线" />
            )}
          </div>
          <ul className="cross-domain-limitations">
            {loadedResult.limitations.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </>
      )}
      <footer>仅用于公开数据条件下的研究评估与风险筛查，不替代兽医诊断。</footer>
    </section>
  );
}
