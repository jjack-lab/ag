import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import HealthEvidence from "./HealthEvidence";

afterEach(cleanup);

it("shows the observation to risk to review chain for a cattle track", () => {
  render(<HealthEvidence species="cattle" profiles={[{
    track_id: 7, risk_score: 65, risk_level: "high", observations: [{
      type: "still", label: "持续低活动", time_seconds: 2, confidence: 0.91,
      detail: "持续低速", suggestion: "现场复核活动和采食",
    }],
  }]} />);
  const graph = screen.getByRole("region", { name: "健康证据图谱" });
  expect(within(graph).getByText("视频内 ID 7")).toBeInTheDocument();
  expect(within(graph).getByText("持续低活动 · 2.0 秒")).toBeInTheDocument();
  expect(within(graph).getByText("高风险 · 65 分")).toBeInTheDocument();
  expect(within(graph).getByText("现场复核活动和采食")).toBeInTheDocument();
  expect(within(graph).getByText(/不能判断具体疾病/)).toBeInTheDocument();
});

it("does not show cattle health scores for sheep", () => {
  render(<HealthEvidence species="sheep" profiles={[]} />);
  expect(screen.getByText(/羊的健康规则尚未验证/)).toBeInTheDocument();
  expect(screen.queryByText(/风险 ·/)).not.toBeInTheDocument();
});

it("labels a normal track and a whole-video low-speed observation accurately", () => {
  render(<HealthEvidence species="cattle" profiles={[
    { track_id: 2, risk_score: 0, risk_level: "normal", observations: [] },
    { track_id: 3, risk_score: 15, risk_level: "low", observations: [{
      type: "low_average_speed", label: "全视频平均活动速度偏低",
      time_seconds: null, confidence: null, detail: "平均速度 2.0 px/s",
      suggestion: "建议人工复核活动状态",
    }] },
  ]} />);
  expect(screen.getByText("正常 · 0 分")).toBeInTheDocument();
  expect(screen.getByText("全视频平均活动速度偏低 · 全视频")).toBeInTheDocument();
});
