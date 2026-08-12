from pathlib import Path

import uvicorn

from cattle_health_app.api import create_app
from cattle_health_app.jobs import VideoJobService
from cattle_health_app.media_processor import LocalMediaProcessor
from cattle_health_app.model_registry import resolve_detector_model
from cattle_health_app.repository import SQLiteRepository


def build_app():
    project_root = Path(__file__).resolve().parent
    media_root = project_root / "data" / "media"
    repository = SQLiteRepository(project_root / "data" / "agrinebula.db")
    repository.initialize()
    artifact = resolve_detector_model(project_root=project_root)
    processor = LocalMediaProcessor(artifact.path)
    jobs = VideoJobService(
        repository,
        processor,
        media_root / "results",
    )
    return create_app(
        repository,
        media_processor=processor,
        media_root=media_root,
        job_service=jobs,
        detector_artifact=artifact,
    )


app = build_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
