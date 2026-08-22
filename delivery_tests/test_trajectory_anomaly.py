"""Unit and integration tests for Isolation Forest trajectory anomaly detection."""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path

from cattle_health_app.anomaly.detector import (
    TrackAnomalyResult,
    TrajectoryAnomalyReport,
    detect_trajectory_anomalies,
    write_anomaly_csv,
)
from cattle_health_app.anomaly.trajectory_features import (
    FEATURE_NAMES,
    extract_track_features,
    feature_vector,
)
from cattle_health_app.jobs import VideoJobService
from cattle_health_app.repository import SQLiteRepository
from cattle_health_app.tracking_pipeline import TrackingVideoResult


def _synthetic_rows(
    fps=10.0,
    normal_tracks=20,
    isolated_track=None,
    still_track=None,
    seed=11,
):
    """Build a synthetic trajectory row set.

    - ``normal_tracks`` cows walk slowly in a line (moving right).
    - ``isolated_track`` (if given) stays far away from the herd.
    - ``still_track`` (if given) stays at a fixed spot while the herd moves.
    """
    random.seed(seed)
    rows = []
    for frame in range(10, 301, 10):
        base_x = 100 + frame * 1.2
        for track_id in range(1, normal_tracks + 1):
            rows.append(
                {
                    "frame_index": frame,
                    "time_seconds": frame / fps,
                    "track_id": track_id,
                    "class_id": 1,
                    "confidence": 0.9,
                    "center_x": base_x + track_id * 10 + random.uniform(-3, 3),
                    "center_y": 300 + math.sin(track_id) * 15 + random.uniform(-3, 3),
                    "width": 80,
                    "height": 60,
                }
            )
        if isolated_track is not None:
            rows.append(
                {
                    "frame_index": frame,
                    "time_seconds": frame / fps,
                    "track_id": isolated_track,
                    "class_id": 1,
                    "confidence": 0.9,
                    "center_x": 950 + random.uniform(-4, 4),
                    "center_y": 700 + random.uniform(-4, 4),
                    "width": 80,
                    "height": 60,
                }
            )
        if still_track is not None:
            rows.append(
                {
                    "frame_index": frame,
                    "time_seconds": frame / fps,
                    "track_id": still_track,
                    "class_id": 1,
                    "confidence": 0.9,
                    "center_x": 300 + random.uniform(-1, 1),
                    "center_y": 300 + random.uniform(-1, 1),
                    "width": 80,
                    "height": 60,
                }
            )
    return rows


class TestFeatureExtraction:
    def test_extracts_one_feature_vector_per_track(self):
        rows = _synthetic_rows(normal_tracks=20)
        features = extract_track_features(rows, fps=10.0)
        assert set(features) == set(range(1, 21))
        sample = features[1]
        for name in FEATURE_NAMES:
            assert name in sample
            assert isinstance(sample[name], float)
            assert math.isfinite(sample[name])
        assert sample["_sample_count"] > 0

    def test_feature_vector_matches_fixed_order(self):
        rows = _synthetic_rows(normal_tracks=5)
        features = extract_track_features(rows, fps=10.0)[1]
        vector = feature_vector(features)
        assert len(vector) == len(FEATURE_NAMES)
        for name, value in zip(FEATURE_NAMES, vector):
            assert value == features[name]

    def test_still_track_has_low_speed_and_displacement(self):
        rows = _synthetic_rows(normal_tracks=10, still_track=88)
        features = extract_track_features(rows, fps=10.0)
        still = features[88]
        normal = features[1]
        assert still["mean_speed_px_s"] < normal["mean_speed_px_s"]
        assert still["total_displacement_px"] < normal["total_displacement_px"]
        assert still["_sample_count"] > 0

    def test_isolated_track_has_large_herd_distance(self):
        rows = _synthetic_rows(normal_tracks=10, isolated_track=99)
        features = extract_track_features(rows, fps=10.0)
        isolated = features[99]
        normal = features[1]
        assert isolated["mean_distance_to_herd_px"] > normal["mean_distance_to_herd_px"]
        assert isolated["mean_nearest_neighbor_px"] > normal["mean_nearest_neighbor_px"]


class TestDetector:
    def test_returns_ok_with_outliers_for_isolated_and_still(self):
        rows = _synthetic_rows(
            normal_tracks=20, isolated_track=99, still_track=88
        )
        report = detect_trajectory_anomalies(rows, fps=10.0)
        assert report.status == "ok"
        assert report.reason is None
        assert 99 in report.outlier_track_ids
        assert 88 in report.outlier_track_ids
        assert report.outlier_count >= 2
        assert len(report.tracks) == 22

    def test_scores_are_normalized_zero_to_one(self):
        rows = _synthetic_rows(normal_tracks=20, isolated_track=99)
        report = detect_trajectory_anomalies(rows, fps=10.0)
        for track in report.tracks:
            assert 0.0 <= track.anomaly_score <= 1.0
        isolated = next(t for t in report.tracks if t.track_id == 99)
        assert isolated.anomaly_score > 0.5

    def test_top_contributors_are_meaningful_for_isolated_track(self):
        rows = _synthetic_rows(normal_tracks=20, isolated_track=99)
        report = detect_trajectory_anomalies(rows, fps=10.0)
        isolated = next(t for t in report.tracks if t.track_id == 99)
        assert len(isolated.top_contributors) == 3
        assert all(name in FEATURE_NAMES for name in isolated.top_contributors)
        assert "mean_distance_to_herd_px" in isolated.top_contributors

    def test_skipped_below_minimum_tracks(self):
        rows = _synthetic_rows(normal_tracks=3)
        report = detect_trajectory_anomalies(rows, fps=10.0, min_tracks=5)
        assert report.status == "skipped"
        assert report.reason is not None
        assert report.tracks == []

    def test_deterministic_with_fixed_seed(self):
        rows = _synthetic_rows(normal_tracks=20, isolated_track=99)
        first = detect_trajectory_anomalies(rows, fps=10.0)
        second = detect_trajectory_anomalies(rows, fps=10.0)
        assert [t.track_id for t in first.tracks] == [t.track_id for t in second.tracks]
        assert [t.is_outlier for t in first.tracks] == [
            t.is_outlier for t in second.tracks
        ]


class TestAnomalyCsv:
    def test_write_anomaly_csv_contains_outlier_rows(self, tmp_path):
        rows = _synthetic_rows(
            normal_tracks=20, isolated_track=99, still_track=88
        )
        report = detect_trajectory_anomalies(rows, fps=10.0)
        path = write_anomaly_csv(tmp_path / "anomaly.csv", report)
        assert path.exists()
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            header = reader.fieldnames
            for name in FEATURE_NAMES:
                assert name in header
            assert "is_outlier" in header
            assert "anomaly_score" in header
            outlier_ids = [
                int(row["track_id"])
                for row in reader
                if row["is_outlier"] == "1"
            ]
        assert 99 in outlier_ids
        assert 88 in outlier_ids

    def test_write_anomaly_csv_skipped_returns_path_without_file(self, tmp_path):
        rows = _synthetic_rows(normal_tracks=3)
        report = detect_trajectory_anomalies(rows, fps=10.0, min_tracks=5)
        path = write_anomaly_csv(tmp_path / "anomaly.csv", report)
        assert not path.exists()


class ImmediateExecutor:
    def submit(self, function, *args, **kwargs):
        function(*args, **kwargs)


class FakeProcessor:
    def track_video(self, source_path, result_dir, conf, iou, class_id, tracker):
        root = Path(result_dir)
        root.mkdir(parents=True, exist_ok=True)
        paths = [
            root / name
            for name in (
                "tracked.mp4",
                "tracks.csv",
                "alerts.csv",
                "health.csv",
                "health.html",
            )
        ]
        for path in paths:
            path.write_bytes(b"result")
        paths[2].write_text(
            "track_id,alert_type,severity,frame_index,time_seconds,"
            "confidence,detail,suggestion\n"
            "7,still,medium,20,2.0,0.9,Low activity,Inspect on site\n",
            encoding="utf-8",
        )
        anomaly_csv = root / "trajectory_anomaly.csv"
        anomaly_csv.write_text(
            "track_id,is_outlier,anomaly_score,top_contributors,sample_count,"
            "duration_seconds\n"
            "3,1,0.92,mean_distance_to_herd_px,30,29.0\n"
            "7,0,0.10,,30,29.0\n",
            encoding="utf-8",
        )
        return TrackingVideoResult(
            *paths,
            frame_count=30,
            tracked_cattle=3,
            alert_count=1,
            trajectory_anomaly_csv=anomaly_csv,
            trajectory_anomaly_count=1,
            trajectory_anomaly_status="ok",
            trajectory_anomalies=[
                {
                    "track_id": 3,
                    "is_outlier": True,
                    "anomaly_score": 0.92,
                    "top_contributors": ["mean_distance_to_herd_px"],
                }
            ],
        )


class TestJobsPersistence:
    def test_trajectory_anomaly_alert_persisted_to_sqlite(self, tmp_path):
        repository = SQLiteRepository(tmp_path / "jobs.db")
        repository.initialize()
        service = VideoJobService(
            repository=repository,
            processor=FakeProcessor(),
            result_root=tmp_path / "results",
            executor=ImmediateExecutor(),
        )

        job = service.create(
            source_path=tmp_path / "cattle.mp4",
            conf=0.25,
            iou=0.45,
            class_id=1,
            tracker="bytetrack.yaml",
        )

        stored = repository.get_video_job(job.id)
        assert stored.status == "completed"
        assert stored.result["trajectory_anomaly_count"] == 1
        alerts = repository.list_alerts(status="open")
        anomaly_alerts = [
            alert for alert in alerts if alert.risk_type == "trajectory_anomaly"
        ]
        assert len(anomaly_alerts) == 1
        anomaly = anomaly_alerts[0]
        assert anomaly.cattle_id == "3"
        assert anomaly.level.value == "medium"
        assert "Isolation Forest" in anomaly.reason
        assert abs(anomaly.confidence - 0.92) < 1e-6

    def test_no_anomaly_csv_means_no_anomaly_alerts(self, tmp_path):
        repository = SQLiteRepository(tmp_path / "jobs.db")
        repository.initialize()

        class NoAnomalyProcessor(FakeProcessor):
            def track_video(self, source_path, result_dir, conf, iou, class_id, tracker):
                result = super().track_video(
                    source_path, result_dir, conf, iou, class_id, tracker
                )
                return TrackingVideoResult(
                    result.video_path,
                    result.trajectory_csv,
                    result.alert_csv,
                    result.health_summary_csv,
                    result.health_report_html,
                    result.frame_count,
                    result.tracked_cattle,
                    result.alert_count,
                )

        service = VideoJobService(
            repository=repository,
            processor=NoAnomalyProcessor(),
            result_root=tmp_path / "results",
            executor=ImmediateExecutor(),
        )
        job = service.create(
            source_path=tmp_path / "cattle.mp4",
            conf=0.25,
            iou=0.45,
            class_id=1,
            tracker="bytetrack.yaml",
        )
        stored = repository.get_video_job(job.id)
        assert stored.status == "completed"
        alerts = repository.list_alerts(status="open")
        assert all(
            alert.risk_type != "trajectory_anomaly" for alert in alerts
        )


class TestResultSerialization:
    def test_to_dict_includes_anomaly_fields(self, tmp_path):
        root = tmp_path / "job-1"
        root.mkdir(parents=True)
        paths = [root / name for name in ("a.mp4", "b.csv", "c.csv", "d.csv", "e.html")]
        anomaly_csv = root / "trajectory_anomaly.csv"
        result = TrackingVideoResult(
            *paths,
            frame_count=30,
            tracked_cattle=3,
            alert_count=1,
            trajectory_anomaly_csv=anomaly_csv,
            trajectory_anomaly_count=1,
            trajectory_anomaly_status="ok",
            trajectory_anomalies=[
                {"track_id": 3, "is_outlier": True, "anomaly_score": 0.92}
            ],
        )
        payload = result.to_dict(media_root=tmp_path)
        assert payload["trajectory_anomaly_csv"] == "job-1/trajectory_anomaly.csv"
        assert payload["trajectory_anomaly_count"] == 1
        assert payload["trajectory_anomaly_status"] == "ok"
        assert payload["trajectory_anomalies"][0]["track_id"] == 3

    def test_default_fields_are_safe(self, tmp_path):
        root = tmp_path / "job-1"
        root.mkdir(parents=True)
        paths = [root / name for name in ("a.mp4", "b.csv", "c.csv", "d.csv", "e.html")]
        result = TrackingVideoResult(*paths, frame_count=1, tracked_cattle=1, alert_count=0)
        payload = result.to_dict(media_root=tmp_path)
        assert payload["trajectory_anomaly_csv"] is None
        assert payload["trajectory_anomaly_count"] == 0
        assert payload["trajectory_anomaly_status"] == "unavailable"
        assert payload["trajectory_anomalies"] == []
