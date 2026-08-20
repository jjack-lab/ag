from pathlib import Path


def test_tracking_result_serializes_product_behavior_contract(tmp_path):
    from cattle_health_app.tracking_pipeline import TrackingVideoResult

    root = tmp_path / "job"
    result = TrackingVideoResult(
        video_path=root / "tracked.mp4",
        trajectory_csv=root / "tracks.csv",
        alert_csv=root / "alerts.csv",
        health_summary_csv=root / "health.csv",
        health_report_html=root / "health.html",
        frame_count=30,
        tracked_cattle=1,
        alert_count=0,
        behavior_csv=root / "behavior.csv",
        behavior_summary_csv=root / "behavior_summary.csv",
        behavior_model_status="ready",
        behavior_model_version="v1",
        behavior_model_error=None,
        behavior_summary=[
            {
                "track_id": 7,
                "label_id": 2,
                "label": "grazing",
                "display_name": "采食",
                "duration_seconds": 2.0,
                "percentage": 66.666667,
                "mean_confidence": 0.85,
                "health_eligible": True,
                "model_version": "v1",
            },
            {
                "track_id": 7,
                "label_id": 1,
                "label": "none",
                "display_name": "无法确定",
                "duration_seconds": 1.0,
                "percentage": 33.333333,
                "mean_confidence": 0.3,
                "health_eligible": False,
                "model_version": "v1",
            },
        ],
    )

    payload = result.to_dict(media_root=tmp_path)

    assert payload["behavior_csv"] == "job/behavior.csv"
    assert payload["behavior_model_error"] is None
    assert payload["behavior_summary"] == [
        {
            "track_id": 7,
            "behavior_name": "grazing",
            "behavior_display_name": "采食",
            "duration_seconds": 2.0,
            "eligible_ratio": 1.0,
            "uncertain_duration_seconds": 1.0,
            "model_version": "v1",
        }
    ]
