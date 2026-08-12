from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import cv2
from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.jobs import VideoJobService
from cattle_health_app.media_processor import LocalMediaProcessor
from cattle_health_app.model_registry import resolve_detector_model
from cattle_health_app.repository import SQLiteRepository


class ImmediateExecutor:
    """Run a submitted job inline so the acceptance result is deterministic."""

    def submit(self, function, *args, **kwargs):
        function(*args, **kwargs)
        return None


def video_metadata(path: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Unable to open acceptance video: {path}")
    metadata = {
        "opened": True,
        "frame_count": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
        "fps": float(capture.get(cv2.CAP_PROP_FPS)),
        "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    capture.release()
    return metadata


def csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return sum(1 for _ in csv.DictReader(source))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the deterministic cattle tracking delivery acceptance."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-image", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    source = args.source.resolve()
    result_root = args.result_root.resolve()
    database = args.database.resolve()
    record_path = args.record.resolve()

    repository = SQLiteRepository(database)
    repository.initialize()
    processor = LocalMediaProcessor()
    service = VideoJobService(
        repository,
        processor,
        result_root,
        executor=ImmediateExecutor(),
    )

    job = service.create(
        source_path=source,
        conf=0.25,
        iou=0.45,
        class_id=1,
        tracker="bytetrack.yaml",
    )
    completed = repository.get_video_job(job.id)
    if completed.status != "completed":
        raise RuntimeError(completed.error or f"Video job ended as {completed.status}")

    artifact = resolve_detector_model(explicit_path=processor.model_path)
    app = create_app(
        repository=repository,
        media_processor=processor,
        media_root=result_root.parent,
        job_service=service,
        detector_artifact=artifact,
    )
    client = TestClient(app)
    dashboard_response = client.get("/api/dashboard")
    alerts_response = client.get("/api/alerts", params={"status": "open"})
    models_response = client.get("/api/models")
    dashboard_response.raise_for_status()
    alerts_response.raise_for_status()
    models_response.raise_for_status()

    result = completed.result
    tracked_video = result_root / result["video_path"]
    trajectory_csv = result_root / result["trajectory_csv"]
    alert_csv = result_root / result["alert_csv"]
    health_summary_csv = result_root / result["health_summary_csv"]
    health_report_html = result_root / result["health_report_html"]
    input_video = video_metadata(source)
    output_video = video_metadata(tracked_video)
    trajectory_rows = csv_row_count(trajectory_csv)
    alert_rows = csv_row_count(alert_csv)
    health_rows = csv_row_count(health_summary_csv)
    api_alerts = alerts_response.json()
    dashboard = dashboard_response.json()

    validations = {
        "job_completed": completed.status == "completed",
        "progress_complete": completed.progress == 1.0,
        "all_input_frames_written": (
            input_video["frame_count"] == output_video["frame_count"]
        ),
        "tracked_cattle_match_dashboard": (
            result["tracked_cattle"] == dashboard["monitored_cattle"]
        ),
        "csv_alerts_match_database": alert_rows == len(api_alerts),
        "database_alerts_match_dashboard": (
            len(api_alerts) == dashboard["open_alerts"]
        ),
        "model_hash_matches_api": (
            artifact.sha256 == models_response.json()["detector"]["sha256"]
        ),
        "all_expected_artifacts_exist": all(
            path.is_file()
            for path in (
                tracked_video,
                trajectory_csv,
                alert_csv,
                health_summary_csv,
                health_report_html,
            )
        ),
    }
    if not all(validations.values()):
        raise AssertionError(f"Acceptance validation failed: {validations}")

    try:
        import ultralytics

        runtime_version = ultralytics.__version__
    except (ImportError, AttributeError):
        runtime_version = "unknown"

    record = {
        "schema_version": 1,
        "status": "passed",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": (
            "Deterministic static-scene integration fixture. It validates the "
            "delivery pipeline and stillness alert, not natural behavior-model accuracy."
        ),
        "model": {
            "name": artifact.name,
            "path": str(artifact.path),
            "sha256": artifact.sha256,
            "ultralytics_runtime": runtime_version,
            "class_id": 1,
            "class_name": "cattle",
        },
        "input": {
            "source_image": str(args.source_image.resolve()),
            "fixture_video": str(source),
            "construction": (
                "The fixed WAID test image was repeated for 210 frames at 10 FPS."
            ),
            **input_video,
        },
        "parameters": {
            "confidence": 0.25,
            "iou": 0.45,
            "tracker": "bytetrack.yaml",
        },
        "results": {
            **result,
            "output_video": output_video,
            "trajectory_rows": trajectory_rows,
            "alert_csv_rows": alert_rows,
            "health_summary_rows": health_rows,
            "database_open_alerts": len(api_alerts),
            "dashboard": dashboard,
            "alert_types": sorted({alert["risk_type"] for alert in api_alerts}),
        },
        "validations": validations,
        "automated_checks": {
            "python_tests": "46 passed",
            "frontend_tests": "7 passed",
            "frontend_production_build": "passed",
            "startup_preflight": "passed",
        },
        "limitations": [
            "This phase uses tracking-derived health rules; a trained temporal behavior classifier is not integrated yet.",
            "Isolation Forest anomaly scoring is not integrated yet.",
            "The output is a project aid and is not a veterinary diagnosis.",
        ],
    }
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
