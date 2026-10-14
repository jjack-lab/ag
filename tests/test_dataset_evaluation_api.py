import csv
from hashlib import sha256

import cv2
import numpy as np
from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository


def test_evaluation_import_persists_source_hashes_and_metrics(tmp_path):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    media = tmp_path / "media"
    uploads = media / "uploads"
    result_dir = media / "results" / "job-1"
    uploads.mkdir(parents=True)
    result_dir.mkdir(parents=True)
    source = uploads / "public-sequence.mp4"
    source.write_bytes(b"public video identity")
    writer = cv2.VideoWriter(str(result_dir / "tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 5, (100, 100))
    writer.write(np.zeros((100, 100, 3), dtype=np.uint8))
    writer.release()
    with (result_dir / "tracks.csv").open("w", encoding="utf-8", newline="") as stream:
        csv_writer = csv.DictWriter(stream, fieldnames=["frame_index", "class_id", "track_id", "center_x", "center_y", "width", "height"])
        csv_writer.writeheader()
        csv_writer.writerow({"frame_index": 0, "class_id": 0, "track_id": 7,
                             "center_x": 20, "center_y": 30, "width": 20, "height": 20})
    repo.save_video_job(VideoJobRecord(
        id="job-1", source_path=str(source), status="completed", progress=1,
        created_at="2026-10-14T10:00:00+08:00", updated_at="2026-10-14T10:01:00+08:00",
        result={"video_path": "job-1/tracked.mp4", "trajectory_csv": "job-1/tracks.csv",
                "species": "sheep"},
    ))
    annotations = b"frame_index,class_id,track_id,x,y,width,height\n0,0,10,0.1,0.2,0.2,0.2\n"
    client = TestClient(create_app(repo, media_root=media))
    response = client.post("/api/evaluations", data={
        "job_id": "job-1", "dataset_name": "Example Sheep Benchmark",
        "source_url": "https://example.org/dataset", "dataset_version": "v1",
        "license_name": "CC BY 4.0", "split_name": "external_test",
    }, files={"annotations": ("labels.csv", annotations, "text/csv")})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["metrics"]["f1"] == 1
    assert result["video_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert result["annotations_sha256"] == sha256(annotations).hexdigest()
    assert client.get("/api/evaluations").json() == [result]
    rejected = client.post("/api/evaluations", data={
        "job_id": "job-1", "dataset_name": "Example", "source_url": "https://example.org",
        "dataset_version": "v1", "license_name": "CC BY 4.0", "split_name": "external_test",
    }, files={"annotations": ("bad.csv", b"frame_index,class_id,track_id,x,y,width,height\n0,1,10,0.1,0.2,0.2,0.2\n", "text/csv")})
    assert rejected.status_code == 422
    assert len(client.get("/api/evaluations").json()) == 1
