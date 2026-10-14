from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
from shutil import copyfileobj
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
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
CROSS_DOMAIN_VARIANTS = {
    "uncalibrated",
    "calibrated",
    "calibrated_fixed_rejection",
    "calibrated_quality_rejection",
}
CROSS_DOMAIN_FIGURES = {
    "confusion_matrix": "confusion_matrix.png",
    "risk_coverage": "risk_coverage.png",
    "stress_curves": "stress_curves.png",
}


def _validated_cross_domain_summary(payload):
    if not isinstance(payload, dict) or payload.get("status") not in {
        "not_run",
        "blocked",
        "complete",
    }:
        raise ValueError("status must be not_run, blocked, or complete")
    status = payload["status"]
    if status != "complete":
        limitations = payload.get("claim_boundaries", payload.get("limitations", []))
        if not isinstance(limitations, list) or any(
            not isinstance(item, str) for item in limitations
        ):
            raise ValueError("limitations must be a list of text")
        return {
            "status": status,
            "dataset_id": payload.get("dataset_id", "cbvd5"),
            "dataset_version": payload.get("dataset_version", "11"),
            "sample_counts": {},
            "model_hash_prefix": None,
            "quality_policy": None,
            "variant_metrics": {},
            "limitations": limitations,
        }
    protocol = payload.get("protocol")
    counts = payload.get("sample_counts")
    metrics = payload.get("metrics")
    limitations = payload.get("claim_boundaries")
    if not isinstance(protocol, dict):
        raise ValueError("complete result requires protocol")
    checkpoint_hash = protocol.get("checkpoint_sha256")
    if (
        not isinstance(checkpoint_hash, str)
        or len(checkpoint_hash) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in checkpoint_hash)
    ):
        raise ValueError("complete result requires checkpoint_sha256")
    if not isinstance(counts, dict) or not counts:
        raise ValueError("complete result requires sample_counts")
    if not isinstance(metrics, dict) or set(metrics) != set(counts):
        raise ValueError("metrics tiers must match sample_counts")
    safe_metrics = {}
    for tier, count in counts.items():
        if tier not in {"strict", "extended"} or isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("sample_counts must contain positive strict/extended counts")
        tier_metrics = metrics[tier]
        if not isinstance(tier_metrics, dict) or set(tier_metrics) != CROSS_DOMAIN_VARIANTS:
            raise ValueError("each tier must contain the four frozen variants")
        safe_metrics[tier] = {}
        for variant in sorted(CROSS_DOMAIN_VARIANTS):
            row = tier_metrics[variant]
            if not isinstance(row, dict) or row.get("sample_count") != count:
                raise ValueError("variant sample_count mismatch")
            coverage = row.get("coverage")
            risk = row.get("selective_risk")
            if not isinstance(coverage, (int, float)) or isinstance(coverage, bool) or not 0 <= coverage <= 1:
                raise ValueError("variant coverage must be within [0, 1]")
            if risk is not None and (
                not isinstance(risk, (int, float))
                or isinstance(risk, bool)
                or not 0 <= risk <= 1
            ):
                raise ValueError("variant selective_risk must be within [0, 1]")
            safe_metrics[tier][variant] = {
                key: row.get(key)
                for key in (
                    "sample_count",
                    "accepted_count",
                    "coverage",
                    "selective_accuracy",
                    "selective_macro_f1",
                    "selective_risk",
                )
                if key in row
            }
    if not isinstance(limitations, list) or any(
        not isinstance(item, str) for item in limitations
    ):
        raise ValueError("claim_boundaries must be a list of text")
    quality_policy = protocol.get("quality_gate_policy")
    if quality_policy not in {"predeclared_heuristic", "validation_logistic"}:
        raise ValueError("complete result requires a known quality_gate_policy")
    return {
        "status": "complete",
        "dataset_id": protocol.get("dataset_id"),
        "dataset_version": protocol.get("dataset_version"),
        "sample_counts": counts,
        "model_hash_prefix": checkpoint_hash[:12].lower(),
        "quality_policy": quality_policy,
        "variant_metrics": safe_metrics,
        "limitations": limitations,
    }


class ResolveAlertRequest(BaseModel):
    note: str = Field(min_length=1, max_length=500)


def create_app(
    repository: SQLiteRepository,
    media_processor=None,
    media_root: str | Path = Path("data") / "media",
    job_service=None,
    detector_artifact=None,
    behavior_artifact=None,
    cross_domain_result_root: str | Path | None = None,
):
    media_processor = media_processor or LocalMediaProcessor()
    media_root = Path(media_root)
    upload_dir = media_root / "uploads"
    result_dir = media_root / "results"
    upload_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    cross_domain_result_root = Path(
        cross_domain_result_root
        if cross_domain_result_root is not None
        else Path("outputs") / "cross_domain" / "cvb_to_cbvd5"
    ).expanduser().resolve()
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
            monitored_cattle = (
                int(latest_job.result.get("tracked_cattle", 0))
                if latest_job.result.get("species", "cattle") == "cattle" else 0
            )
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
        current_behavior_artifact = getattr(
            media_processor, "behavior_artifact", behavior_artifact
        )
        return {
            "detector": detector_artifact.to_dict(),
            "behavior": current_behavior_artifact.to_dict(),
        }

    @app.get("/api/experiments/cross-domain-behavior")
    def cross_domain_behavior_results():
        metrics_path = cross_domain_result_root / "metrics.json"
        if not metrics_path.is_file():
            return {
                "status": "not_run",
                "dataset_id": "cbvd5",
                "dataset_version": "11",
                "sample_counts": {},
                "model_hash_prefix": None,
                "quality_policy": None,
                "variant_metrics": {},
                "limitations": ["真实外部实验尚未完成"],
                "figure_urls": {},
            }
        try:
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            validated = _validated_cross_domain_summary(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise HTTPException(
                status_code=503,
                detail="跨域实验结果文件无效: {}".format(error),
            ) from error
        figures = {}
        for stem, filename in CROSS_DOMAIN_FIGURES.items():
            if (cross_domain_result_root / filename).is_file():
                figures[stem] = (
                    "/api/experiments/cross-domain-behavior/figures/{}".format(
                        filename
                    )
                )
        validated["figure_urls"] = figures
        return validated

    @app.get("/api/experiments/cross-domain-behavior/figures/{filename}")
    def cross_domain_behavior_figure(filename: str):
        if filename not in CROSS_DOMAIN_FIGURES.values():
            raise HTTPException(status_code=404, detail="Figure not found")
        path = cross_domain_result_root / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Figure not found")
        return FileResponse(path, media_type="image/png")

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
        if class_id not in {0, 1}:
            raise HTTPException(status_code=422, detail="Video tracking supports cattle or sheep only")
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
