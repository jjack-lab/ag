import csv
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository
from cattle_health_app.video_events import result_file
import pytest


def test_events_include_behavior_changes_alerts_and_reviews(tmp_path):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    result_root = tmp_path / "media" / "results"
    job_dir = result_root / "job-1"
    job_dir.mkdir(parents=True)
    with (job_dir / "behavior.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["time_seconds", "track_id", "label", "display_name", "health_eligible"])
        writer.writeheader()
        writer.writerows([
            {"time_seconds": 1, "track_id": 7, "label": "grazing", "display_name": "采食", "health_eligible": "True"},
            {"time_seconds": 2, "track_id": 7, "label": "grazing", "display_name": "采食", "health_eligible": "True"},
            {"time_seconds": 4, "track_id": 7, "label": "lying", "display_name": "卧倒", "health_eligible": "True"},
        ])
    repo.save_video_job(VideoJobRecord(
        id="job-1", source_path="unused.mp4", status="completed", progress=1,
        created_at="2026-10-14T10:00:00+08:00", updated_at="2026-10-14T10:01:00+08:00",
        result={"video_path": "job-1/tracked.mp4", "behavior_csv": "job-1/behavior.csv",
                "health_evidence": [{"track_id": 7, "observations": [
                    {"type": "still", "label": "持续低活动", "time_seconds": 3,
                     "detail": "连续静止", "suggestion": "人工复核"},
                    {"type": "low_average_speed", "label": "平均速度低", "time_seconds": None,
                     "detail": "全视频", "suggestion": "人工复核"}]}]},
    ))
    repo.save_video_review({"id": "review-1", "job_id": "job-1", "species": "cattle",
                            "issue_type": "id_switch", "track_id": 7, "time_seconds": 5,
                            "verdict": "confirmed", "note": "ID 互换",
                            "created_at": "2026-10-14T10:02:00+08:00"})
    client = TestClient(create_app(repo, media_root=tmp_path / "media"))
    response = client.get("/api/jobs/job-1/events")
    assert response.status_code == 200
    events = response.json()
    assert [(row["kind"], row["time_seconds"]) for row in events] == [
        ("behavior", 1), ("alert", 3), ("behavior", 4), ("review", 5)]
    assert [row["label"] for row in events if row["kind"] == "behavior"] == ["采食", "卧倒"]
    assert client.get("/api/jobs/missing/events").status_code == 404


def test_clip_download_is_bounded_to_event_and_result_video(tmp_path):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    result_root = tmp_path / "media" / "results"
    job_dir = result_root / "job-1"
    job_dir.mkdir(parents=True)
    video = job_dir / "tracked.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 5, (32, 24))
    assert writer.isOpened()
    for _ in range(30):
        writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
    writer.release()
    repo.save_video_job(VideoJobRecord(
        id="job-1", source_path="unused.mp4", status="completed", progress=1,
        created_at="2026-10-14T10:00:00+08:00", updated_at="2026-10-14T10:01:00+08:00",
        result={"video_path": "job-1/tracked.mp4", "health_evidence": [{"track_id": 7,
                "observations": [{"type": "still", "label": "低活动", "time_seconds": 3,
                                  "detail": "", "suggestion": ""}]}]},
    ))
    client = TestClient(create_app(repo, media_root=tmp_path / "media"))
    response = client.get("/api/jobs/job-1/events/0/clip")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert len(response.content) > 0
    image = client.get("/api/jobs/job-1/events/0/snapshot")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/jpeg")
    assert cv2.imdecode(np.frombuffer(image.content, dtype=np.uint8), cv2.IMREAD_COLOR).shape[:2] == (24, 32)
    assert client.get("/api/jobs/job-1/events/1/clip").status_code == 404
    assert client.get("/api/jobs/../events/0/clip").status_code != 200


def test_result_file_rejects_paths_outside_the_job(tmp_path):
    root = tmp_path / "results"
    with pytest.raises(ValueError, match="escapes"):
        result_file(root, "job-1", "../uploads/secret.mp4")
    with pytest.raises(ValueError, match="escapes"):
        result_file(root, "job-1", "job-2/tracked.mp4")
