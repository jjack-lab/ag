import csv
import html
import math
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


Point = Tuple[float, float]
BoxXYWH = Tuple[float, float, float, float]
Zone = Tuple[float, float, float, float]


@dataclass(frozen=True)
class DetectionObservation:
    track_id: int
    class_id: int
    confidence: float
    xywh: BoxXYWH


@dataclass
class HealthConfig:
    fps: float = 20.0
    cattle_class_ids: Set[int] = field(default_factory=lambda: {1})
    still_seconds: float = 20.0
    still_speed_px_s: float = 5.0
    lying_seconds: float = 10.0
    lying_aspect_ratio: float = 1.9
    isolation_seconds: float = 15.0
    isolation_distance_px: float = 180.0
    activity_window_seconds: float = 30.0
    activity_drop_ratio: float = 0.35
    feeding_zones: Sequence[Zone] = field(default_factory=tuple)
    max_zone_dwell_seconds: float = 45.0


@dataclass(frozen=True)
class HealthAlert:
    track_id: int
    alert_type: str
    severity: str
    frame_index: int
    time_seconds: float
    confidence: float
    detail: str
    suggestion: str


@dataclass(frozen=True)
class CowHealthSummary:
    track_id: int
    risk_score: int
    risk_level: str
    alert_count: int
    alert_types: Tuple[str, ...]
    average_speed_px_s: float


@dataclass
class _TrackState:
    last_center: Optional[Point] = None
    last_frame_index: Optional[int] = None
    low_motion_start: Optional[int] = None
    lying_start: Optional[int] = None
    isolation_start: Optional[int] = None
    zone_enter_frame: Optional[int] = None
    speed_history: List[float] = field(default_factory=list)
    baseline_speed: Optional[float] = None
    fired_alerts: Set[str] = field(default_factory=set)


class CattleHealthMonitor:
    def __init__(self, config: Optional[HealthConfig] = None):
        self.config = config or HealthConfig()
        self._tracks: Dict[int, _TrackState] = {}
        self.alerts: List[HealthAlert] = []

    def update(self, frame_index: int, observations: Iterable[DetectionObservation]) -> List[HealthAlert]:
        cattle = [obs for obs in observations if obs.class_id in self.config.cattle_class_ids]
        centers = {obs.track_id: self._center(obs.xywh) for obs in cattle}
        new_alerts: List[HealthAlert] = []

        for obs in cattle:
            state = self._tracks.setdefault(obs.track_id, _TrackState())
            center = centers[obs.track_id]
            speed = self._speed_px_s(state, center, frame_index)
            state.speed_history.append(speed)
            self._trim_speed_history(state)

            new_alerts.extend(self._check_still(obs, state, frame_index, speed))
            new_alerts.extend(self._check_lying(obs, state, frame_index))
            new_alerts.extend(self._check_isolation(obs, state, frame_index, centers))
            new_alerts.extend(self._check_activity_drop(obs, state, frame_index))
            new_alerts.extend(self._check_zone_dwell(obs, state, frame_index, center))

            state.last_center = center
            state.last_frame_index = frame_index

        self.alerts.extend(new_alerts)
        return new_alerts

    def export_alerts_csv(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self._csv_fields())
            writer.writeheader()
            for alert in self.alerts:
                writer.writerow(self._alert_row(alert))

    def export_alerts_html(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        rows = "\n".join(self._html_row(alert) for alert in self.alerts)
        if not rows:
            rows = "<tr><td colspan='8'>No health alerts detected.</td></tr>"
        content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Cattle Health Alerts</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; margin: 24px; background: #f7faf7; color: #1f2a1f; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    .summary {{ margin-bottom: 18px; color: #536253; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ border: 1px solid #d8e2d8; padding: 10px; text-align: left; font-size: 14px; }}
    th {{ background: #e9f3e9; }}
    .high {{ color: #b42318; font-weight: 700; }}
    .medium {{ color: #b54708; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>牛健康风险预警报告</h1>
  <div class="summary">共检测到 {len(self.alerts)} 条疑似健康风险，仅作为牧场巡检预警参考。</div>
  <table>
    <thead>
      <tr>
        <th>牛 ID</th><th>风险类型</th><th>等级</th><th>时间(s)</th>
        <th>帧号</th><th>置信度</th><th>详情</th><th>建议</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
        with open(path, "w", encoding="utf-8") as htmlfile:
            htmlfile.write(content)

    def summarize_health(self) -> List[CowHealthSummary]:
        summaries = []
        for track_id, state in sorted(self._tracks.items()):
            alerts = [alert for alert in self.alerts if alert.track_id == track_id]
            score = self._risk_score(alerts, state)
            summaries.append(
                CowHealthSummary(
                    track_id=track_id,
                    risk_score=score,
                    risk_level=self._risk_level(score),
                    alert_count=len(alerts),
                    alert_types=tuple(sorted({alert.alert_type for alert in alerts})),
                    average_speed_px_s=self._average_speed(state),
                )
            )
        return summaries

    def export_health_summary_csv(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=[
                    "track_id",
                    "risk_score",
                    "risk_level",
                    "alert_count",
                    "alert_types",
                    "average_speed_px_s",
                ],
            )
            writer.writeheader()
            for summary in self.summarize_health():
                writer.writerow(
                    {
                        "track_id": summary.track_id,
                        "risk_score": summary.risk_score,
                        "risk_level": summary.risk_level,
                        "alert_count": summary.alert_count,
                        "alert_types": ";".join(summary.alert_types),
                        "average_speed_px_s": f"{summary.average_speed_px_s:.2f}",
                    }
                )

    def _check_still(
        self, obs: DetectionObservation, state: _TrackState, frame_index: int, speed: float
    ) -> List[HealthAlert]:
        if speed <= self.config.still_speed_px_s:
            if state.low_motion_start is None:
                state.low_motion_start = frame_index
        else:
            state.low_motion_start = None

        if self._elapsed(state.low_motion_start, frame_index) >= self.config.still_seconds:
            alert = self._alert_once(
                obs,
                state,
                "still",
                "medium",
                frame_index,
                f"Speed stayed below {self.config.still_speed_px_s:.1f}px/s.",
                "建议人工查看该牛是否精神沉郁、跛行或采食异常。",
            )
            return [alert] if alert else []
        return []

    def _check_lying(self, obs: DetectionObservation, state: _TrackState, frame_index: int) -> List[HealthAlert]:
        _, _, width, height = obs.xywh
        aspect_ratio = width / max(height, 1.0)
        if aspect_ratio >= self.config.lying_aspect_ratio:
            if state.lying_start is None:
                state.lying_start = frame_index
        else:
            state.lying_start = None

        if self._elapsed(state.lying_start, frame_index) >= self.config.lying_seconds:
            alert = self._alert_once(
                obs,
                state,
                "lying",
                "high",
                frame_index,
                f"Body box aspect ratio reached {aspect_ratio:.2f}.",
                "疑似长时间卧倒或倒地，请尽快现场复核。",
            )
            return [alert] if alert else []
        return []

    def _check_isolation(
        self,
        obs: DetectionObservation,
        state: _TrackState,
        frame_index: int,
        centers: Dict[int, Point],
    ) -> List[HealthAlert]:
        if len(centers) < 3:
            state.isolation_start = None
            return []

        center = centers[obs.track_id]
        nearest_distance = min(
            self._distance(center, other_center)
            for other_track_id, other_center in centers.items()
            if other_track_id != obs.track_id
        )
        if nearest_distance >= self.config.isolation_distance_px:
            if state.isolation_start is None:
                state.isolation_start = frame_index
        else:
            state.isolation_start = None

        if self._elapsed(state.isolation_start, frame_index) >= self.config.isolation_seconds:
            alert = self._alert_once(
                obs,
                state,
                "isolated",
                "medium",
                frame_index,
                f"Nearest herd mate distance was {nearest_distance:.1f}px.",
                "该牛持续离群，建议检查应激、疾病或栏舍环境问题。",
            )
            return [alert] if alert else []
        return []

    def _check_activity_drop(
        self, obs: DetectionObservation, state: _TrackState, frame_index: int
    ) -> List[HealthAlert]:
        window_frames = max(2, int(self.config.activity_window_seconds * self.config.fps))
        if len(state.speed_history) < window_frames:
            return []

        recent_mean = sum(state.speed_history[-window_frames:]) / window_frames
        if state.baseline_speed is None:
            state.baseline_speed = max(recent_mean, 0.1)
            return []

        if recent_mean <= state.baseline_speed * self.config.activity_drop_ratio:
            alert = self._alert_once(
                obs,
                state,
                "activity_drop",
                "medium",
                frame_index,
                f"Recent activity fell to {recent_mean:.1f}px/s from baseline {state.baseline_speed:.1f}px/s.",
                "活动量明显下降，建议结合采食量和体温进一步排查。",
            )
            return [alert] if alert else []
        return []

    def _check_zone_dwell(
        self, obs: DetectionObservation, state: _TrackState, frame_index: int, center: Point
    ) -> List[HealthAlert]:
        if not self.config.feeding_zones:
            return []

        in_zone = any(self._in_zone(center, zone) for zone in self.config.feeding_zones)
        if in_zone:
            if state.zone_enter_frame is None:
                state.zone_enter_frame = frame_index
        else:
            state.zone_enter_frame = None

        if self._elapsed(state.zone_enter_frame, frame_index) >= self.config.max_zone_dwell_seconds:
            alert = self._alert_once(
                obs,
                state,
                "zone_dwell",
                "medium",
                frame_index,
                "Stayed in feeding/drinking zone for unusually long time.",
                "采食或饮水区停留异常，建议检查是否无法正常移动或被挤占。",
            )
            return [alert] if alert else []
        return []

    def _alert_once(
        self,
        obs: DetectionObservation,
        state: _TrackState,
        alert_type: str,
        severity: str,
        frame_index: int,
        detail: str,
        suggestion: str,
    ) -> HealthAlert:
        if alert_type in state.fired_alerts:
            return None
        state.fired_alerts.add(alert_type)
        return HealthAlert(
            track_id=obs.track_id,
            alert_type=alert_type,
            severity=severity,
            frame_index=frame_index,
            time_seconds=self._time(frame_index),
            confidence=obs.confidence,
            detail=detail,
            suggestion=suggestion,
        )

    def _trim_speed_history(self, state: _TrackState) -> None:
        max_len = max(2, int(self.config.activity_window_seconds * self.config.fps * 2))
        if len(state.speed_history) > max_len:
            del state.speed_history[:-max_len]

    def _risk_score(self, alerts: List[HealthAlert], state: _TrackState) -> int:
        severity_score = 0
        for alert in alerts:
            severity_score += 40 if alert.severity == "high" else 25
        low_activity_score = 15 if state.speed_history and self._average_speed(state) <= self.config.still_speed_px_s else 0
        return min(100, severity_score + low_activity_score)

    @staticmethod
    def _risk_level(score: int) -> str:
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        if score >= 15:
            return "low"
        return "normal"

    @staticmethod
    def _average_speed(state: _TrackState) -> float:
        if not state.speed_history:
            return 0.0
        return sum(state.speed_history) / len(state.speed_history)

    def _speed_px_s(self, state: _TrackState, center: Point, frame_index: int) -> float:
        if state.last_center is None or state.last_frame_index is None:
            return 0.0
        frame_delta = max(frame_index - state.last_frame_index, 1)
        return self._distance(center, state.last_center) / frame_delta * self.config.fps

    def _elapsed(self, start_frame: Optional[int], frame_index: int) -> float:
        if start_frame is None:
            return 0.0
        return max(frame_index - start_frame, 0) / max(self.config.fps, 0.001)

    def _time(self, frame_index: int) -> float:
        return frame_index / max(self.config.fps, 0.001)

    @staticmethod
    def _center(xywh: BoxXYWH) -> Point:
        return xywh[0], xywh[1]

    @staticmethod
    def _distance(a: Point, b: Point) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    @staticmethod
    def _in_zone(point: Point, zone: Zone) -> bool:
        left, top, right, bottom = zone
        return left <= point[0] <= right and top <= point[1] <= bottom

    @staticmethod
    def _csv_fields() -> List[str]:
        return [
            "track_id",
            "alert_type",
            "severity",
            "frame_index",
            "time_seconds",
            "confidence",
            "detail",
            "suggestion",
        ]

    def _alert_row(self, alert: HealthAlert) -> Dict[str, str]:
        return {
            "track_id": str(alert.track_id),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "frame_index": str(alert.frame_index),
            "time_seconds": f"{alert.time_seconds:.2f}",
            "confidence": f"{alert.confidence:.3f}",
            "detail": alert.detail,
            "suggestion": alert.suggestion,
        }

    def _html_row(self, alert: HealthAlert) -> str:
        row = self._alert_row(alert)
        return (
            "<tr>"
            f"<td>{html.escape(row['track_id'])}</td>"
            f"<td>{html.escape(row['alert_type'])}</td>"
            f"<td class='{html.escape(row['severity'])}'>{html.escape(row['severity'])}</td>"
            f"<td>{html.escape(row['time_seconds'])}</td>"
            f"<td>{html.escape(row['frame_index'])}</td>"
            f"<td>{html.escape(row['confidence'])}</td>"
            f"<td>{html.escape(row['detail'])}</td>"
            f"<td>{html.escape(row['suggestion'])}</td>"
            "</tr>"
        )
