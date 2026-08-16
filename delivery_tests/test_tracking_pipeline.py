import numpy as np

from cattle_health_app.tracking_pipeline import TrackingVideoResult, _crop_xywh


def test_tracking_result_serializes_relative_artifacts(tmp_path):
    result_dir = tmp_path / "job-1"
    result = TrackingVideoResult(
        video_path=result_dir / "tracked.mp4", trajectory_csv=result_dir / "tracks.csv",
        alert_csv=result_dir / "alerts.csv", health_summary_csv=result_dir / "health.csv",
        health_report_html=result_dir / "health.html", frame_count=90, tracked_cattle=5,
        alert_count=2, behavior_csv=result_dir / "behavior.csv",
        behavior_summary_csv=result_dir / "behavior_summary.csv",
        behavior_report_json=result_dir / "behavior_report.json", behavior_model_status="ready",
        behavior_model_version="cvb-x3d-v1",
        behavior_summary=[{"track_id": 7, "display_name": "采食", "duration_seconds": 12.5, "percentage": 62.5}],
    )
    payload = result.to_dict(media_root=tmp_path)
    assert payload["video_path"] == "job-1/tracked.mp4"
    assert payload["trajectory_csv"] == "job-1/tracks.csv"
    assert payload["frame_count"] == 90
    assert payload["tracked_cattle"] == 5
    assert payload["alert_count"] == 2
    assert payload["behavior_csv"] == "job-1/behavior.csv"
    assert payload["behavior_summary_csv"] == "job-1/behavior_summary.csv"
    assert payload["behavior_report_json"] == "job-1/behavior_report.json"
    assert payload["behavior_model_status"] == "ready"
    assert payload["behavior_model_version"] == "cvb-x3d-v1"
    assert payload["behavior_summary"] == [{"track_id": 7, "display_name": "采食", "duration_seconds": 12.5, "percentage": 62.5}]


def test_crop_xywh_adds_context_clamps_to_frame_and_rejects_empty_boxes():
    frame = np.arange(10 * 20 * 3, dtype=np.uint8).reshape(10, 20, 3)
    crop = _crop_xywh(frame, (1.0, 1.0, 4.0, 4.0), context=0.15)
    assert crop is not None
    assert crop.shape == (4, 4, 3)
    assert _crop_xywh(frame, (5.0, 5.0, 0.0, 3.0)) is None
    assert _crop_xywh(frame, (100.0, 100.0, 2.0, 2.0)) is None
