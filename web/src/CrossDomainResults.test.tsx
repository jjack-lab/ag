import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import CrossDomainResults from "./CrossDomainResults";
import { CrossDomainExperimentResult } from "./api";


afterEach(cleanup);

it("renders the honest not-run state", () => {
  render(
    <CrossDomainResults
      result={{
        status: "not_run",
        dataset_id: "cbvd5",
        dataset_version: "11",
        sample_counts: {},
        model_hash_prefix: null,
        quality_policy: null,
        variant_metrics: {},
        limitations: ["真实外部实验尚未完成"],
        figure_urls: {},
      }}
    />,
  );

  expect(screen.getByText("真实外部实验尚未完成")).toBeInTheDocument();
});

it("renders blocked evidence without inventing metrics", () => {
  render(
    <CrossDomainResults
      result={{
        status: "blocked",
        dataset_id: "cbvd5",
        dataset_version: "11",
        sample_counts: {},
        model_hash_prefix: null,
        quality_policy: null,
        variant_metrics: {},
        limitations: ["模型检查点缺失"],
        figure_urls: {},
      }}
    />,
  );

  expect(screen.getByText("实验受阻")).toBeInTheDocument();
  expect(screen.getByText("模型检查点缺失")).toBeInTheDocument();
});

it("shows strict evidence, quality rejection, figures, and claim boundaries", () => {
  const result: CrossDomainExperimentResult = {
    status: "complete",
    dataset_id: "cbvd5",
    dataset_version: "11",
    sample_counts: { strict: 20 },
    model_hash_prefix: "aaaaaaaaaaaa",
    quality_policy: "predeclared_heuristic",
    variant_metrics: {
      strict: {
        uncalibrated: { sample_count: 20, coverage: 1, selective_risk: 0.4 },
        calibrated: {
          sample_count: 20,
          coverage: 1,
          selective_macro_f1: 0.0047619047619047615,
          selective_risk: 0.4,
        },
        calibrated_fixed_rejection: {
          sample_count: 20,
          coverage: 0.7,
          selective_risk: 0.2,
        },
        calibrated_quality_rejection: {
          sample_count: 20,
          coverage: 0.6,
          selective_risk: 0.1,
        },
      },
    },
    limitations: ["not disease diagnosis"],
    figure_urls: {
      confusion_matrix:
        "/api/experiments/cross-domain-behavior/figures/confusion_matrix.png",
      risk_coverage:
        "/api/experiments/cross-domain-behavior/figures/risk_coverage.png",
    },
  };

  render(<CrossDomainResults result={result} />);

  expect(screen.getByText("严格映射（n=20）")).toBeInTheDocument();
  expect(screen.getByText("质量感知拒识")).toBeInTheDocument();
  expect(screen.getByText("Macro-F1")).toBeInTheDocument();
  expect(screen.getByText("0.5%")).toBeInTheDocument();
  expect(screen.getByText(/预声明启发式质量规则/)).toBeInTheDocument();
  expect(screen.getByText(/未使用 CBVD-5 标签拟合/)).toBeInTheDocument();
  expect(screen.getByText(/仅作探索性证据/)).toBeInTheDocument();
  expect(screen.getByText(/不替代兽医诊断/)).toBeInTheDocument();
  expect(screen.getByAltText("严格映射混淆矩阵")).toBeInTheDocument();
  expect(screen.getByAltText("风险与覆盖率曲线")).toBeInTheDocument();
});
