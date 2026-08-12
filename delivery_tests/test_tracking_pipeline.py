from cattle_health_app.tracking_pipeline import TrackingVideoResult


def test_tracking_result_serializes_relative_artifacts(tmp_path):
    result_dir = tmp_path / "job-1"
    result = TrackingVideoResult(
        video_path=result_dir / "tracked.mp4",
        trajectory_csv=result_dir / "tracks.csv",
        alert_csv=result_dir / "alerts.csv",
        health_summary_csv=result_dir / "health.csv",
        health_report_html=result_dir / "health.html",
        frame_count=90,
        tracked_cattle=5,
        alert_count=2,
    )

    payload = result.to_dict(media_root=tmp_path)

    assert payload["video_path"] == "job-1/tracked.mp4"
    assert payload["trajectory_csv"] == "job-1/tracks.csv"
    assert payload["frame_count"] == 90
    assert payload["tracked_cattle"] == 5
    assert payload["alert_count"] == 2
