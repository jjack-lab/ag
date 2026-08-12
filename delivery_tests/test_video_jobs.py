from pathlib import Path

from cattle_health_app.jobs import VideoJobService
from cattle_health_app.repository import SQLiteRepository
from cattle_health_app.tracking_pipeline import TrackingVideoResult


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
        return TrackingVideoResult(
            *paths,
            frame_count=30,
            tracked_cattle=3,
            alert_count=1,
        )


def test_video_job_reaches_completed_state(tmp_path):
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
    assert stored.progress == 1.0
    assert stored.result["tracked_cattle"] == 3
    assert repository.latest_completed_video_job().id == job.id
    alerts = repository.list_alerts(status="open")
    assert len(alerts) == 1
    assert alerts[0].cattle_id == "7"
    assert alerts[0].risk_type == "still"
