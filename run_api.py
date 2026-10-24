from pathlib import Path

import uvicorn

from cattle_health_app.api import create_app
from cattle_health_app.jobs import VideoJobService
from cattle_health_app.media_processor import LocalMediaProcessor
from cattle_health_app.model_registry import resolve_detector_model
from cattle_health_app.repository import SQLiteRepository
from cattle_health_app.runtime import server_host, server_port


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
    # 进程重启后，内存队列里的任务不会自动恢复：把遗留的 queued/running
    # 标记为中断，避免前端永远停在“处理中”。
    jobs.recover_interrupted()
    return create_app(
        repository,
        media_processor=processor,
        media_root=media_root,
        job_service=jobs,
        detector_artifact=artifact,
    )


app = build_app()


if __name__ == "__main__":
    uvicorn.run(app, host=server_host(), port=server_port())
