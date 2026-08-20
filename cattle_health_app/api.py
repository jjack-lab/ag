from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from shutil import copyfileobj
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cattle_health_app.domain import AlertLevel
from cattle_health_app.jobs import VideoJobService
from cattle_health_app.media_processor import LocalMediaProcessor
from cattle_health_app.model_registry import (
    resolve_behavior_model,
    resolve_detector_model,
)
from cattle_health_app.repository import SQLiteRepository


MAX_UPLOAD_BYTES = int(os.environ.get("AGRINEBULA_MAX_UPLOAD_MB", "512")) * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


class ResolveAlertRequest(BaseModel):
    note: str = Field(min_length=1, max_length=500)


def create_app(
    repository: SQLiteRepository,
    media_processor=None,
    media_root: str | Path = Path("data") / "media",
    job_service=None,
    detector_artifact=None,
    behavior_artifact=None,
):
    media_processor = media_processor or LocalMediaProcessor()
    media_root = Path(media_root)
    upload_dir = media_root / "uploads"
    result_dir = media_root / "results"
    upload_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    detector_artifact = detector_artifact or resolve_detector_model(
        explicit_path=media_processor.model_path
    )
    behavior_artifact = (
        behavior_artifact
        or getattr(media_processor, "behavior_artifact", None)
        or resolve_behavior_model()
    )
    job_service = job_service or VideoJobService(
        repository,
        media_processor,
        result_dir,
    )

    app = FastAPI(
        title="星牧智控本地服务",
        version="0.3.0",
        description="牛只识别、健康预警与本地数据接口",
    )
    app.mount("/media", StaticFiles(directory=media_root), name="media")

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "mode": "local",
            "message": "本地识别服务运行正常",
        }

    @app.get("/api/dashboard")
    def dashboard():
        alerts = repository.list_alerts(status="open")
        try:
            latest_job = repository.latest_completed_video_job()
            monitored_cattle = int(latest_job.result.get("tracked_cattle", 0))
        except KeyError:
            monitored_cattle = 0
        high_risk_cattle = {
            alert.cattle_id for alert in alerts if alert.level == AlertLevel.HIGH
        }
        return {
            "monitored_cattle": monitored_cattle,
            "high_risk_cattle": len(high_risk_cattle),
            "open_alerts": len(alerts),
            "model_status": "ready",
        }

    @app.get("/api/models")
    def models():
        return {
            "detector": detector_artifact.to_dict(),
            "behavior": behavior_artifact.to_dict(),
        }

    @app.get("/api/alerts")
    def list_alerts(status: Optional[str] = None):
        return [alert.to_dict() for alert in repository.list_alerts(status=status)]

    @app.post("/api/alerts/{alert_id}/resolve")
    def resolve_alert(alert_id: str, request: ResolveAlertRequest):
        try:
            alert = repository.resolve_alert(
                alert_id,
                request.note,
                datetime.now().astimezone().isoformat(timespec="seconds"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="未找到该告警") from error
        return alert.to_dict()

    @app.post("/api/recognition/image")
    def recognize_image(
        file: UploadFile = File(...),
        conf: float = Form(0.25),
        iou: float = Form(0.45),
        class_id: int = Form(-1),
    ):
        suffix = _validated_suffix(
            file.filename, {".jpg", ".jpeg", ".png", ".bmp"}
        )
        token = uuid4().hex
        source_path = upload_dir / f"{token}{suffix}"
        result_path = result_dir / f"{token}_detected.jpg"
        _save_upload(file, source_path)
        try:
            detection_count = media_processor.detect_image(
                source_path, result_path, conf, iou, class_id
            )
        except Exception as error:
            raise HTTPException(status_code=422, detail=f"图片识别失败: {error}") from error
        return {
            "kind": "image",
            "status": "completed",
            "detection_count": detection_count,
            "source_url": f"/media/uploads/{source_path.name}",
            "result_url": f"/media/results/{result_path.name}",
        }

    def enqueue_video(file, conf, iou, class_id, tracker):
        if tracker not in {"bytetrack.yaml", "botsort.yaml"}:
            raise HTTPException(status_code=422, detail="Unsupported tracker")
        suffix = _validated_suffix(
            file.filename, {".mp4", ".avi", ".mov", ".mkv"}
        )
        source_path = upload_dir / f"{uuid4().hex}{suffix}"
        _save_upload(file, source_path)
        return job_service.create(
            source_path,
            conf,
            iou,
            class_id,
            tracker,
        ).to_dict()

    @app.post("/api/jobs/video", status_code=202)
    def create_video_job(
        file: UploadFile = File(...),
        conf: float = Form(0.25),
        iou: float = Form(0.45),
        class_id: int = Form(1),
        tracker: str = Form("bytetrack.yaml"),
    ):
        return enqueue_video(file, conf, iou, class_id, tracker)

    @app.get("/api/jobs/{job_id}")
    def get_video_job(job_id: str):
        try:
            return repository.get_video_job(job_id).to_dict()
        except KeyError as error:
            raise HTTPException(
                status_code=404,
                detail="Video job not found",
            ) from error

    @app.post("/api/recognition/video", status_code=202, deprecated=True)
    def recognize_video(
        file: UploadFile = File(...),
        conf: float = Form(0.25),
        iou: float = Form(0.45),
        class_id: int = Form(1),
        tracker: str = Form("bytetrack.yaml"),
    ):
        return enqueue_video(file, conf, iou, class_id, tracker)

    return app


def _validated_suffix(filename, allowed_suffixes):
    suffix = Path(filename or "").suffix.lower()
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=415, detail="不支持的文件格式")
    return suffix


def _save_upload(file, destination):
    destination = Path(destination)
    written = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = file.file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Uploaded file is too large",
                    )
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
