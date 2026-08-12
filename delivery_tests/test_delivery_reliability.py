from hashlib import sha256
from pathlib import Path

import pytest

from cattle_health_app.jobs import VideoJobService
from cattle_health_app.model_registry import (
    EXPECTED_DELIVERY_MODEL_SHA256,
    ModelIntegrityError,
    resolve_detector_model,
)
from cattle_health_app.repository import SQLiteRepository
from cattle_health_app.tracking_pipeline import TrackingVideoResult


def test_packaged_detector_rejects_unexpected_hash(tmp_path):
    model = tmp_path / "models" / "detection" / "yolo11s-waid.pt"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"wrong-model")

    with pytest.raises(ModelIntegrityError, match="SHA-256"):
        resolve_detector_model(project_root=tmp_path)


def test_expected_delivery_hash_is_fixed():
    assert EXPECTED_DELIVERY_MODEL_SHA256 == (
        "46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64"
    )


class ImmediateExecutor:
    def submit(self, function, *args, **kwargs):
        function(*args, **kwargs)


class ProgressProcessor:
    def track_video(
        self,
        source_path,
        result_dir,
        conf,
        iou,
        class_id,
        tracker,
        progress_callback=None,
    ):
        progress_callback(0.5)
        root = Path(result_dir)
        root.mkdir(parents=True, exist_ok=True)
        paths = [root / name for name in ("video.mp4", "tracks.csv", "alerts.csv", "health.csv", "health.html")]
        for path in paths:
            path.write_bytes(b"result")
        paths[2].write_text(
            "track_id,alert_type,severity,frame_index,time_seconds,confidence,detail,suggestion\n",
            encoding="utf-8",
        )
        return TrackingVideoResult(*paths, frame_count=10, tracked_cattle=1, alert_count=0)


def test_video_job_persists_intermediate_progress(tmp_path):
    repository = SQLiteRepository(tmp_path / "jobs.db")
    repository.initialize()
    observed = []
    original_save = repository.save_video_job

    def record(job):
        observed.append(job.progress)
        original_save(job)

    repository.save_video_job = record
    service = VideoJobService(
        repository,
        ProgressProcessor(),
        tmp_path / "results",
        executor=ImmediateExecutor(),
    )

    service.create(tmp_path / "video.mp4", 0.25, 0.45, 1, "bytetrack.yaml")

    assert 0.5 in observed
    assert observed[-1] == 1.0
