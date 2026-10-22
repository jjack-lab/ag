import csv

import cv2
import numpy as np
from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository


def test_original_frame_and_track_crop_use_source_video(tmp_path):
    media = tmp_path / "media"
    uploads = media / "uploads"
    results = media / "results" / "job-1"
    uploads.mkdir(parents=True)
    results.mkdir(parents=True)
    source = uploads / "source.avi"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 5, (160, 120))
    for _ in range(10):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[40:80, 60:100] = (0, 0, 255)
        writer.write(frame)
    writer.release()
    with (results / "tracks.csv").open("w", newline="", encoding="utf-8") as stream:
        rows = csv.writer(stream)
        rows.writerow(["frame_index", "time_seconds", "track_id", "class_id", "confidence",
                       "center_x", "center_y", "width", "height"])
        rows.writerow([0, 0, 7, 1, 0.9, 80, 60, 40, 40])
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    repo.save_video_job(VideoJobRecord(
        id="job-1", source_path=str(source), status="completed", progress=1,
        created_at="2026-10-22T10:00:00+08:00", updated_at="2026-10-22T10:00:02+08:00",
        result={"species": "cattle", "trajectory_csv": "job-1/tracks.csv", "track_ids": [7]},
    ))
    client = TestClient(create_app(repo, media_root=media))

    full = client.get("/api/jobs/job-1/inspection-frame?track_id=7&time_seconds=0")
    crop = client.get("/api/jobs/job-1/inspection-frame?track_id=7&time_seconds=0&crop=true")
    assert full.status_code == crop.status_code == 200
    full_image = cv2.imdecode(np.frombuffer(full.content, np.uint8), cv2.IMREAD_COLOR)
    crop_image = cv2.imdecode(np.frombuffer(crop.content, np.uint8), cv2.IMREAD_COLOR)
    assert full_image.shape[:2] == (120, 160)
    assert crop_image.shape[0] < 120 and crop_image.shape[1] < 160
    assert crop_image[crop_image.shape[0] // 2, crop_image.shape[1] // 2, 2] > 200
    assert client.get("/api/jobs/job-1/inspection-frame?track_id=9&time_seconds=0&crop=true").status_code == 404
