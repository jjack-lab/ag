from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.model_registry import ModelArtifact
from cattle_health_app.repository import SQLiteRepository


class FakeMediaProcessor:
    def detect_image(self, *args, **kwargs):
        return 1


class FakeJobService:
    def create(self, source_path, conf, iou, class_id, tracker):
        return VideoJobRecord(
            id="job-1",
            source_path=str(source_path),
            status="queued",
            progress=0.0,
            created_at="2026-07-29T12:00:00+08:00",
            updated_at="2026-07-29T12:00:00+08:00",
        )


@pytest.fixture
def client(tmp_path):
    repository = SQLiteRepository(tmp_path / "delivery.db")
    repository.initialize()
    model_path = tmp_path / "detector.pt"
    model_path.write_bytes(b"delivery-detector")
    artifact = ModelArtifact(
        name="yolo11-detector",
        path=model_path,
        sha256=sha256(b"delivery-detector").hexdigest(),
    )
    app = create_app(
        repository,
        media_processor=FakeMediaProcessor(),
        media_root=tmp_path / "media",
        job_service=FakeJobService(),
        detector_artifact=artifact,
    )
    return TestClient(app)


def test_create_video_job_returns_202(client):
    response = client.post(
        "/api/jobs/video",
        files={"file": ("cattle.mp4", b"video", "video/mp4")},
        data={"tracker": "bytetrack.yaml", "class_id": "1"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_missing_job_returns_404(client):
    response = client.get("/api/jobs/missing")

    assert response.status_code == 404


def test_models_endpoint_exposes_detector_hash(client):
    response = client.get("/api/models")

    assert response.status_code == 200
    assert len(response.json()["detector"]["sha256"]) == 64
