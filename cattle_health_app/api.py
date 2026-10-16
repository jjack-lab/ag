from __future__ import annotations

from datetime import date, datetime
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
from shutil import copyfileobj
from typing import Literal, Optional
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import cv2

from cattle_health_app.domain import AlertLevel
from cattle_health_app.dataset_evaluation import evaluate_annotations
from cattle_health_app.jobs import VideoJobService
from cattle_health_app.inventory import inventory_state, validate_recheck
from cattle_health_app.media_processor import LocalMediaProcessor
from cattle_health_app.model_registry import (
    resolve_behavior_model,
    resolve_detector_model,
)
from cattle_health_app.repository import SQLiteRepository
from cattle_health_app.video_events import create_event_clip, result_file, video_events


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


class VideoReviewRequest(BaseModel):
    issue_type: Literal["missed_detection", "id_switch", "false_alert", "health_concern", "other"]
    track_id: Optional[int] = Field(default=None, ge=0)
    time_seconds: Optional[float] = Field(default=None, ge=0)
    verdict: Literal["confirmed", "rejected", "uncertain"]
    note: str = Field(min_length=1, max_length=1000)


class CorrectionBox(BaseModel):
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class VideoCorrectionRequest(BaseModel):
    kind: Literal["missed_detection", "id_correction", "behavior_correction"]
    time_seconds: float = Field(ge=0)
    track_id: Optional[int] = Field(default=None, ge=0)
    corrected_track_id: Optional[int] = Field(default=None, ge=0)
    behavior_label: Optional[Literal[
        "grazing", "drinking", "ruminating-standing", "ruminating-lying",
        "resting-standing", "resting-lying", "walking", "standing", "lying",
    ]] = None
    box: Optional[CorrectionBox] = None
    note: str = Field(min_length=1, max_length=1000)


class AnimalLinkRequest(BaseModel):
    track_id: int = Field(ge=0)
    animal_id: str = Field(min_length=1, max_length=40)


class AnimalFollowupRequest(BaseModel):
    kind: Literal["field_observation", "veterinary_diagnosis"]
    observed_at: date
    note: str = Field(min_length=1, max_length=1000)
    diagnosis: Optional[str] = Field(default=None, max_length=200)
    source_reference: Optional[str] = Field(default=None, max_length=300)


class InventoryCheckRequest(BaseModel):
    job_id: str = Field(min_length=1)
    pen_id: str = Field(min_length=1, max_length=80)
    expected_count: int = Field(ge=0)
    baseline_source: str = Field(min_length=1, max_length=300)
    observed_count: Optional[int] = Field(default=None, ge=0)
    coverage: Literal["complete", "partial", "unknown"]
    coverage_note: str = Field(min_length=1, max_length=1000)
    operator_name: str = Field(min_length=1, max_length=100)
    observed_at: datetime


class InventoryRecheckRequest(BaseModel):
    counted_count: int = Field(ge=0)
    outcome: Literal["resolved", "shortfall_pending", "surplus_pending", "loss_user_recorded"]
    movement_records_checked: bool = False
    field_search_complete: bool = False
    lost_count: Optional[int] = Field(default=None, ge=1)
    operator_name: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=1000)


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
            latest_job = repository.latest_completed_cattle_video_job()
            track_count = int(latest_job.result.get("tracked_cattle", 0))
            processed_at = latest_job.updated_at
        except KeyError:
            track_count = None
            processed_at = None
        return {
            "latest_cattle_track_count": track_count,
            "latest_cattle_processed_at": processed_at,
            "high_risk_alerts": sum(alert.level == AlertLevel.HIGH for alert in alerts),
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

    @app.get("/api/jobs/video")
    def list_video_jobs(limit: int = 20):
        if not 1 <= limit <= 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        return [job.to_dict() for job in repository.list_video_jobs(limit)]

    @app.get("/api/evaluations")
    def list_dataset_evaluations():
        return repository.list_dataset_evaluations()

    @app.post("/api/evaluations", status_code=201)
    async def create_dataset_evaluation(
        annotations: UploadFile = File(...),
        job_id: str = Form(...),
        dataset_name: str = Form(...),
        source_url: str = Form(...),
        dataset_version: str = Form(...),
        license_name: str = Form(...),
        split_name: str = Form(...),
    ):
        try:
            job = repository.get_video_job(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Video job not found") from error
        if job.status != "completed" or not job.result:
            raise HTTPException(status_code=409, detail="只能评测已完成的视频")
        metadata = [dataset_name, source_url, dataset_version, license_name, split_name]
        if any(not value.strip() or len(value) > 300 for value in metadata):
            raise HTTPException(status_code=422, detail="数据集来源、版本、许可与划分均须填写")
        parsed_url = urlparse(source_url.strip())
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            raise HTTPException(status_code=422, detail="来源网址无效")
        if split_name.strip() not in ("development", "validation", "external_test"):
            raise HTTPException(status_code=422, detail="划分必须为 development、validation 或 external_test")
        try:
            source_path = Path(job.source_path).resolve()
            source_path.relative_to(upload_dir.resolve())
            prediction_path = result_file(result_dir, job_id, job.result.get("trajectory_csv"))
            video_path = result_file(result_dir, job_id, job.result.get("video_path"))
        except ValueError as error:
            raise HTTPException(status_code=422, detail="任务文件路径无效") from error
        if not source_path.is_file() or prediction_path is None or not prediction_path.is_file() or video_path is None or not video_path.is_file():
            raise HTTPException(status_code=404, detail="原视频或结果文件不存在")
        annotation_bytes = await annotations.read(20 * 1024 * 1024 + 1)
        if not annotation_bytes or len(annotation_bytes) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="标注 CSV 必须小于 20 MB")
        evaluation_id = uuid4().hex
        annotation_dir = media_root / "evaluations" / evaluation_id
        annotation_dir.mkdir(parents=True, exist_ok=False)
        annotation_path = annotation_dir / "annotations.csv"
        annotation_path.write_bytes(annotation_bytes)
        capture = cv2.VideoCapture(str(video_path))
        try:
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        finally:
            capture.release()
        try:
            metrics = evaluate_annotations(annotation_path, prediction_path, width, height,
                                           0 if job.result.get("species") == "sheep" else 1,
                                           frame_count=frame_count)
        except (ValueError, UnicodeError) as error:
            annotation_path.unlink(missing_ok=True)
            annotation_dir.rmdir()
            raise HTTPException(status_code=422, detail=str(error)) from error
        digest = hashlib.sha256()
        with source_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        evaluation = {
            "id": evaluation_id, "job_id": job_id,
            "dataset_name": dataset_name.strip(), "source_url": source_url.strip(),
            "dataset_version": dataset_version.strip(), "license_name": license_name.strip(),
            "split_name": split_name.strip(), "video_sha256": digest.hexdigest(),
            "annotations_sha256": hashlib.sha256(annotation_bytes).hexdigest(),
            "metrics": metrics, "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        repository.save_dataset_evaluation(evaluation)
        return evaluation

    @app.get("/api/jobs/{job_id}/reviews")
    def list_video_reviews(job_id: str):
        try:
            repository.get_video_job(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Video job not found") from error
        return repository.list_video_reviews(job_id)

    @app.get("/api/jobs/{job_id}/events")
    def list_video_events(job_id: str):
        try:
            job = repository.get_video_job(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Video job not found") from error
        if job.status != "completed" or job.result is None:
            raise HTTPException(status_code=409, detail="视频任务尚未完成")
        try:
            return video_events(job.result, repository.list_video_reviews(job_id), result_dir,
                                job_id, repository.list_video_corrections(job_id))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/jobs/{job_id}/events/{event_id}/clip")
    def download_event_clip(job_id: str, event_id: int):
        events = list_video_events(job_id)
        if event_id < 0 or event_id >= len(events):
            raise HTTPException(status_code=404, detail="Event not found")
        job = repository.get_video_job(job_id)
        try:
            clip = create_event_clip(result_dir, job_id, job.result, events[event_id])
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return FileResponse(clip, media_type="video/mp4", filename=f"{job_id}-event-{event_id}.mp4")

    def completed_video_job(job_id):
        try:
            job = repository.get_video_job(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Video job not found") from error
        if job.status != "completed" or job.result is None:
            raise HTTPException(status_code=409, detail="只能纠正已完成的视频")
        return job

    @app.get("/api/jobs/{job_id}/corrections")
    def list_video_corrections(job_id: str):
        completed_video_job(job_id)
        return repository.list_video_corrections(job_id)

    @app.post("/api/jobs/{job_id}/corrections", status_code=201)
    def create_video_correction(job_id: str, request: VideoCorrectionRequest):
        job = completed_video_job(job_id)
        if not math.isfinite(request.time_seconds):
            raise HTTPException(status_code=422, detail="时间点无效")
        box = request.box.model_dump() if request.box else None
        if box and (box["x"] + box["width"] > 1 or box["y"] + box["height"] > 1):
            raise HTTPException(status_code=422, detail="标注框超出画面")
        known_tracks = set(job.result.get("track_ids") or [])
        if not known_tracks:
            known_tracks = {row.get("track_id") for row in job.result.get("health_evidence", [])}
        if request.kind == "missed_detection":
            if box is None or request.track_id is not None or request.corrected_track_id is not None or request.behavior_label is not None:
                raise HTTPException(status_code=422, detail="漏检标注需要画框且不能填 Track ID")
        elif request.kind == "id_correction":
            if (request.track_id not in known_tracks or request.corrected_track_id is None
                    or request.corrected_track_id == request.track_id or box is not None
                    or request.behavior_label is not None):
                raise HTTPException(status_code=422, detail="ID 修正需要原 Track ID 和不同的新 ID")
        else:
            if (job.result.get("species") == "sheep" or request.track_id not in known_tracks
                    or request.behavior_label is None or box is not None
                    or request.corrected_track_id is not None):
                raise HTTPException(status_code=422, detail="行为修正仅适用于已识别的牛只 Track ID")
        try:
            video_path = result_file(result_dir, job_id, job.result.get("video_path"))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if video_path is None or not video_path.is_file():
            raise HTTPException(status_code=404, detail="结果视频不存在")
        capture = cv2.VideoCapture(str(video_path))
        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        finally:
            capture.release()
        if not math.isfinite(fps) or fps <= 0 or not math.isfinite(frame_count) or frame_count <= 0:
            raise HTTPException(status_code=422, detail="视频元数据无效")
        frame_index = round(request.time_seconds * fps)
        if frame_index >= frame_count:
            raise HTTPException(status_code=422, detail="时间点超出视频")
        correction = {
            "id": uuid4().hex, "job_id": job_id,
            "species": job.result.get("species", "cattle"),
            "kind": request.kind, "frame_index": frame_index,
            "time_seconds": round(frame_index / fps, 6),
            "track_id": request.track_id, "corrected_track_id": request.corrected_track_id,
            "behavior_label": request.behavior_label, "box": box,
            "note": request.note.strip(),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        if not correction["note"]:
            raise HTTPException(status_code=422, detail="纠错说明不能为空")
        repository.save_video_correction(correction)
        return correction

    @app.delete("/api/jobs/{job_id}/corrections/{correction_id}", status_code=204)
    def delete_video_correction(job_id: str, correction_id: str):
        completed_video_job(job_id)
        try:
            repository.delete_video_correction(job_id, correction_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="纠错记录不存在") from error

    @app.get("/api/jobs/{job_id}/corrections.csv")
    def export_video_corrections(job_id: str):
        completed_video_job(job_id)
        stream = io.StringIO()
        fields = ["id", "job_id", "species", "kind", "frame_index", "time_seconds",
                  "track_id", "corrected_track_id", "behavior_label", "x", "y", "width",
                  "height", "note", "created_at"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for correction in repository.list_video_corrections(job_id):
            box = correction.pop("box") or {}
            writer.writerow({**correction, **box})
        return StreamingResponse(iter(["\ufeff" + stream.getvalue()]), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": 'attachment; filename="corrections.csv"'})

    @app.post("/api/jobs/{job_id}/reviews", status_code=201)
    def create_video_review(job_id: str, request: VideoReviewRequest):
        try:
            job = repository.get_video_job(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Video job not found") from error
        if job.status != "completed" or job.result is None:
            raise HTTPException(status_code=409, detail="只能复核已完成的视频")
        review = {
            "id": uuid4().hex,
            "job_id": job_id,
            "species": job.result.get("species", "cattle"),
            "issue_type": request.issue_type,
            "track_id": request.track_id,
            "time_seconds": request.time_seconds,
            "verdict": request.verdict,
            "note": request.note.strip(),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        if not review["note"]:
            raise HTTPException(status_code=422, detail="复核说明不能为空")
        repository.save_video_review(review)
        return review

    @app.get("/api/jobs/{job_id}/animal-links")
    def list_job_animal_links(job_id: str):
        try:
            repository.get_video_job(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Video job not found") from error
        return repository.list_job_animal_links(job_id)

    @app.post("/api/jobs/{job_id}/animal-links", status_code=201)
    def create_animal_link(job_id: str, request: AnimalLinkRequest):
        try:
            job = repository.get_video_job(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Video job not found") from error
        if job.status != "completed" or job.result is None:
            raise HTTPException(status_code=409, detail="只能关联已完成的视频")
        known_tracks = set(job.result.get("track_ids") or [])
        if not known_tracks:
            known_tracks = {
                row.get("track_id") for row in job.result.get("health_evidence", [])
            }
        if request.track_id not in known_tracks:
            raise HTTPException(status_code=422, detail="该视频结果中没有此 Track ID")
        animal_id = request.animal_id.strip()
        if not animal_id or any(char in animal_id for char in "/\\?#"):
            raise HTTPException(status_code=422, detail="个体编号格式无效")
        link = {
            "job_id": job_id,
            "track_id": request.track_id,
            "animal_id": animal_id,
            "species": job.result.get("species", "cattle"),
            "linked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        try:
            repository.save_animal_link(link)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return link

    @app.delete("/api/jobs/{job_id}/animal-links/{track_id}", status_code=204)
    def delete_animal_link(job_id: str, track_id: int):
        try:
            repository.delete_animal_link(job_id, track_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="未找到个体关联") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/animals/{animal_id}")
    def get_animal_profile(animal_id: str):
        links = repository.list_animal_links(animal_id)
        if not links:
            raise HTTPException(status_code=404, detail="未找到个体档案")
        visits = []
        for link in links:
            job = repository.get_video_job(link["job_id"])
            profiles = job.result.get("health_evidence", []) if job.result else []
            evidence = next(
                (row for row in profiles if row.get("track_id") == link["track_id"]),
                None,
            )
            sheep_motion = next(
                (row for row in (job.result.get("sheep_motion_summary", []) if job.result else [])
                 if row.get("track_id") == link["track_id"]),
                None,
            )
            reviews = [row for row in repository.list_video_reviews(job.id)
                       if row["track_id"] == link["track_id"]]
            visits.append({
                **link,
                "recorded_at": job.created_at,
                "health_evidence": evidence,
                "sheep_motion": sheep_motion,
                "reviews": reviews,
            })
        return {
            "animal_id": animal_id,
            "species": links[0]["species"],
            "visits": visits,
            "followups": repository.list_animal_followups(animal_id),
        }

    @app.post("/api/animals/{animal_id}/followups", status_code=201)
    def create_animal_followup(animal_id: str, request: AnimalFollowupRequest):
        if not repository.list_animal_links(animal_id):
            raise HTTPException(status_code=404, detail="未找到个体档案")
        diagnosis = (request.diagnosis or "").strip() or None
        source_reference = (request.source_reference or "").strip() or None
        if request.kind == "veterinary_diagnosis" and not (diagnosis and source_reference):
            raise HTTPException(status_code=422, detail="兽医结论需填写诊断和记录出处")
        if request.kind == "field_observation" and diagnosis:
            raise HTTPException(status_code=422, detail="现场观察不能填写疾病诊断")
        followup = {
            "id": uuid4().hex,
            "animal_id": animal_id,
            "kind": request.kind,
            "observed_at": request.observed_at.isoformat(),
            "note": request.note.strip(),
            "diagnosis": diagnosis,
            "source_reference": source_reference,
            "verification_status": "user_recorded",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        if not followup["note"]:
            raise HTTPException(status_code=422, detail="回访说明不能为空")
        repository.save_animal_followup(followup)
        return followup

    def inventory_response(check: dict):
        rechecks = [
            {**row,
             "movement_records_checked": bool(row["movement_records_checked"]),
             "field_search_complete": bool(row["field_search_complete"])}
            for row in repository.list_inventory_rechecks(check["id"])
        ]
        latest = rechecks[-1] if rechecks else None
        state = inventory_state(check, latest)
        job = repository.get_video_job(check["job_id"])
        return {
            **check, **state, "rechecks": rechecks,
            "lost_count": latest["lost_count"] if state["status"] == "loss_user_recorded" else None,
            "video_track_count": job.result.get("tracked_cattle", 0) if job.result else None,
            "verification_status": "user_recorded",
        }

    @app.get("/api/inventory-checks")
    def list_inventory_checks(limit: int = 100):
        if not 1 <= limit <= 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        return [inventory_response(row) for row in repository.list_inventory_checks(limit)]

    @app.get("/api/inventory-checks/page")
    def page_inventory_checks(
        limit: int = 20, offset: int = 0, pen_id: str = "", status: str = "",
    ):
        allowed_statuses = {
            "", "coverage_needed", "count_needed", "preliminary_match",
            "discrepancy_pending", "verified_match", "shortfall_pending",
            "surplus_pending", "loss_user_recorded",
        }
        if not 1 <= limit <= 100 or offset < 0 or status not in allowed_statuses:
            raise HTTPException(status_code=422, detail="盘点分页参数无效")
        rows, total = repository.page_inventory_checks(
            limit=limit, offset=offset, pen_id=pen_id.strip(), status=status,
        )
        return {"items": [inventory_response(row) for row in rows],
                "total": total, "limit": limit, "offset": offset}

    @app.post("/api/inventory-checks", status_code=201)
    def create_inventory_check(request: InventoryCheckRequest):
        try:
            job = repository.get_video_job(request.job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="视频任务不存在") from error
        if job.status != "completed" or job.result is None:
            raise HTTPException(status_code=409, detail="只能为已完成的视频建立盘点")
        if request.observed_at.tzinfo is None or request.observed_at.utcoffset() is None:
            raise HTTPException(status_code=422, detail="盘点时间必须包含时区")
        values = request.model_dump()
        for key in ("pen_id", "baseline_source", "coverage_note", "operator_name"):
            values[key] = values[key].strip()
            if not values[key]:
                raise HTTPException(status_code=422, detail=f"{key} 不能为空")
        values["id"] = uuid4().hex
        values["species"] = job.result.get("species", "cattle")
        values["observed_at"] = request.observed_at.isoformat(timespec="seconds")
        values["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        repository.save_inventory_check(values)
        return inventory_response(values)

    @app.get("/api/inventory-checks/{check_id}")
    def get_inventory_check(check_id: str):
        try:
            return inventory_response(repository.get_inventory_check(check_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="盘点记录不存在") from error

    @app.post("/api/inventory-checks/{check_id}/rechecks", status_code=201)
    def create_inventory_recheck(check_id: str, request: InventoryRecheckRequest):
        try:
            check = repository.get_inventory_check(check_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="盘点记录不存在") from error
        values = request.model_dump()
        for key in ("operator_name", "note"):
            values[key] = values[key].strip()
            if not values[key]:
                raise HTTPException(status_code=422, detail=f"{key} 不能为空")
        try:
            validate_recheck(check, values)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        values.update({
            "id": uuid4().hex, "check_id": check_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        })
        repository.save_inventory_recheck(values)
        return inventory_response(check)

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
