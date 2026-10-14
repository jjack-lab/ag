from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository


def client_with_video(tmp_path, species="cattle"):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    job_dir = tmp_path / "media" / "results" / "job-1"
    job_dir.mkdir(parents=True)
    writer = cv2.VideoWriter(str(job_dir / "tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 5, (40, 30))
    for _ in range(20):
        writer.write(np.zeros((30, 40, 3), dtype=np.uint8))
    writer.release()
    repo.save_video_job(VideoJobRecord(
        id="job-1", source_path="unused.mp4", status="completed", progress=1,
        created_at="2026-10-14T10:00:00+08:00", updated_at="2026-10-14T10:01:00+08:00",
        result={"video_path": "job-1/tracked.mp4", "species": species, "track_ids": [7]},
    ))
    return TestClient(create_app(repo, media_root=tmp_path / "media"))


def test_visual_corrections_persist_and_export(tmp_path):
    client = client_with_video(tmp_path)
    missed = client.post("/api/jobs/job-1/corrections", json={
        "kind": "missed_detection", "time_seconds": 1.2, "track_id": None,
        "box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
        "note": "画面左侧漏检",
    })
    assert missed.status_code == 201, missed.text
    assert missed.json()["frame_index"] == 6
    id_fix = client.post("/api/jobs/job-1/corrections", json={
        "kind": "id_correction", "time_seconds": 2, "track_id": 7,
        "corrected_track_id": 8, "note": "遮挡后切换",
    })
    assert id_fix.status_code == 201, id_fix.text
    behavior = client.post("/api/jobs/job-1/corrections", json={
        "kind": "behavior_correction", "time_seconds": 2.4, "track_id": 7,
        "behavior_label": "grazing", "note": "实际在采食",
    })
    assert behavior.status_code == 201, behavior.text
    listed = client.get("/api/jobs/job-1/corrections").json()
    assert [row["kind"] for row in listed] == ["missed_detection", "id_correction", "behavior_correction"]
    export = client.get("/api/jobs/job-1/corrections.csv")
    assert export.status_code == 200
    assert "grazing" in export.text and "0.3" in export.text
    assert client.delete(f"/api/jobs/job-1/corrections/{missed.json()['id']}").status_code == 204
    assert len(client.get("/api/jobs/job-1/corrections").json()) == 2


def test_correction_validation_rejects_invalid_frames_and_labels(tmp_path):
    client = client_with_video(tmp_path, species="sheep")
    base = {"kind": "missed_detection", "time_seconds": 1, "note": "漏检",
            "box": {"x": 0.8, "y": 0.2, "width": 0.3, "height": 0.4}}
    assert client.post("/api/jobs/job-1/corrections", json=base).status_code == 422
    assert client.post("/api/jobs/job-1/corrections", json={**base, "time_seconds": 100,
        "box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}}).status_code == 422
    assert client.post("/api/jobs/job-1/corrections", json={
        "kind": "behavior_correction", "time_seconds": 1, "track_id": 7,
        "behavior_label": "grazing", "note": "采食",
    }).status_code == 422
    assert client.post("/api/jobs/job-1/corrections", json={
        "kind": "id_correction", "time_seconds": 1, "track_id": 999,
        "corrected_track_id": 8, "note": "ID 错误",
    }).status_code == 422
