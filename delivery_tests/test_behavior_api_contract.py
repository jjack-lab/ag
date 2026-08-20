from hashlib import sha256

from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.model_registry import BehaviorModelArtifact, ModelArtifact
from cattle_health_app.repository import SQLiteRepository


class FakeMediaProcessor:
    def detect_image(self, *args, **kwargs):
        return 1


class FakeJobService:
    pass


def test_models_endpoint_exposes_behavior_status_version_and_hash(tmp_path):
    repository = SQLiteRepository(tmp_path / "api.db")
    repository.initialize()
    detector_path = tmp_path / "detector.pt"
    detector_path.write_bytes(b"detector")
    behavior_path = tmp_path / "behavior.pt"
    behavior_path.write_bytes(b"behavior")
    detector = ModelArtifact(
        name="yolo11-detector",
        path=detector_path,
        sha256=sha256(b"detector").hexdigest(),
    )
    behavior = BehaviorModelArtifact(
        name="cvb-x3d-behavior",
        path=behavior_path,
        sha256=sha256(b"behavior").hexdigest(),
        status="ready",
        version="cvb-x3d-v1",
    )
    app = create_app(
        repository,
        media_processor=FakeMediaProcessor(),
        media_root=tmp_path / "media",
        job_service=FakeJobService(),
        detector_artifact=detector,
        behavior_artifact=behavior,
    )

    payload = TestClient(app).get("/api/models").json()

    assert payload["behavior"]["status"] == "ready"
    assert payload["behavior"]["version"] == "cvb-x3d-v1"
    assert payload["behavior"]["sha256"] == sha256(b"behavior").hexdigest()
