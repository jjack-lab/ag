import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import AnimalTrend from "./AnimalTrend";
import { AnimalProfile } from "./api";

const base = { animal_id: "C-1", species: "cattle" as const, followups: [] };
afterEach(cleanup);

it("shows actual cattle risk scores from two manually linked visits", () => {
  const profile: AnimalProfile = { ...base, visits: [
    { job_id: "a", animal_id: "C-1", species: "cattle", track_id: 7,
      linked_at: "2026-10-14", recorded_at: "2026-10-14T10:00:00+08:00", reviews: [], sheep_motion: null,
      health_evidence: { track_id: 7, risk_score: 15, risk_level: "low", observations: [] } },
    { job_id: "b", animal_id: "C-1", species: "cattle", track_id: 3,
      linked_at: "2026-10-15", recorded_at: "2026-10-15T10:00:00+08:00", reviews: [], sheep_motion: null,
      health_evidence: { track_id: 3, risk_score: 40, risk_level: "medium", observations: [] } },
  ] };
  render(<AnimalTrend profile={profile} />);
  expect(screen.getByRole("region", { name: "个体跨天趋势" })).toHaveTextContent("15.0 → 40.0 分");
  expect(screen.queryByText("至少需要同一个体的两次有效视频记录，才能显示变化。")).toBeNull();
});

it("keeps sheep movement percentage separate from health scores", () => {
  const profile: AnimalProfile = { animal_id: "S-1", species: "sheep", followups: [], visits: [
    { job_id: "a", animal_id: "S-1", species: "sheep", track_id: 1,
      linked_at: "2026-10-14", recorded_at: "2026-10-14T10:00:00+08:00", reviews: [], health_evidence: null,
      sheep_motion: { track_id: 1, still_seconds: 3, moving_seconds: 1, fast_seconds: 1, observed_seconds: 5 } },
    { job_id: "b", animal_id: "S-1", species: "sheep", track_id: 2,
      linked_at: "2026-10-15", recorded_at: "2026-10-15T10:00:00+08:00", reviews: [], health_evidence: null,
      sheep_motion: { track_id: 2, still_seconds: 2, moving_seconds: 3, fast_seconds: 0, observed_seconds: 5 } },
  ] };
  render(<AnimalTrend profile={profile} />);
  expect(screen.getByRole("region", { name: "个体跨天趋势" })).toHaveTextContent("40.0 → 60.0%");
  expect(screen.getByText(/不是羊的健康评分/)).toBeInTheDocument();
});
