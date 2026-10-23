from cattle_health_app.spatial_analysis import count_drop_alert, line_crossings, zone_activity, zone_detection_gap
from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository
from fastapi.testclient import TestClient
import csv
import cv2
import numpy as np


def test_zone_counts_entry_dwell_and_hours():
    tracks = {7: [(0, 0.0, 0.1, 0.2), (1, 0.5, 0.5, 0.5),
                  (2, 1.0, 0.6, 0.5), (3, 1.5, 0.9, 0.5),
                  (4, 2.0, 0.5, 0.5)]}
    result = zone_activity(tracks, [0.3, 0.3, 0.7, 0.7], 2, "2026-10-22T10:00:00+08:00")
    assert result["entries"] == 2
    assert result["dwell_seconds"] == 1.5
    assert result["hourly"][0]["entries"] == 2


def test_zone_entry_events_include_dwell():
    tracks = {7: [(0, 0.0, 0.1, 0.2), (1, 0.5, 0.5, 0.5),
                  (2, 1.0, 0.6, 0.5), (3, 1.5, 0.9, 0.5),
                  (4, 2.0, 0.5, 0.5)]}
    result = zone_activity(tracks, [0.3, 0.3, 0.7, 0.7], 2,
                           "2026-10-22T10:00:00+08:00")
    assert result["events"] == [
        {"track_id": 7, "time_seconds": 0.5, "dwell_seconds": 1.0},
        {"track_id": 7, "time_seconds": 2.0, "dwell_seconds": 0.5},
    ]


def test_gate_counts_both_directions_only_on_finite_line():
    tracks = {
        7: [(0, 0, 0.5, 0.2), (1, 1, 0.5, 0.8), (2, 2, 0.5, 0.2)],
        8: [(0, 0, 0.9, 0.2), (1, 1, 0.9, 0.8)],
    }
    result = line_crossings(tracks, [0.2, 0.5, 0.8, 0.5])
    assert result["enter"] == 1
    assert result["leave"] == 1
    assert len(result["events"]) == 2


def test_spatial_hints_require_sustained_gap_or_drop():
    assert zone_detection_gap({}, [0.2, 0.2, 0.8, 0.8], 35)["time_seconds"] == 30
    assert zone_detection_gap({}, [0.2, 0.2, 0.8, 0.8], 12) is None
    tracks = {track: [(frame, float(frame), 0.5, 0.5)
                      for frame in range(5)] for track in range(4)}
    tracks[0] += [(frame, float(frame), 0.5, 0.5) for frame in range(5, 15)]
    assert count_drop_alert(tracks, 15, 1)["label"] == "画面检测数量下降待核查"


def test_spatial_report_is_saved_and_found_for_same_camera(tmp_path):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    job_dir = tmp_path / "media" / "results" / "job-1"
    job_dir.mkdir(parents=True)
    writer = cv2.VideoWriter(str(job_dir / "tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 2, (100, 100))
    for _ in range(70):
        writer.write(np.zeros((100, 100, 3), dtype=np.uint8))
    writer.release()
    with (job_dir / "tracks.csv").open("w", encoding="utf-8", newline="") as stream:
        csv_writer = csv.DictWriter(stream, fieldnames=["frame_index", "time_seconds", "track_id", "center_x", "center_y"])
        csv_writer.writeheader()
        csv_writer.writerows([
            {"frame_index": 0, "time_seconds": 0, "track_id": 7, "center_x": 20, "center_y": 20},
            {"frame_index": 1, "time_seconds": 0.5, "track_id": 7, "center_x": 50, "center_y": 50},
            {"frame_index": 2, "time_seconds": 1, "track_id": 7, "center_x": 60, "center_y": 50},
        ])
    repo.save_video_job(VideoJobRecord(
        id="job-1", source_path="source.mp4", status="completed", progress=1,
        created_at="2026-10-22T10:00:00+08:00", updated_at="2026-10-22T10:01:00+08:00",
        result={"video_path": "job-1/tracked.mp4", "trajectory_csv": "job-1/tracks.csv"},
    ))
    client = TestClient(create_app(repo, media_root=tmp_path / "media"))
    response = client.post("/api/jobs/job-1/spatial-report", json={
        "pen_id": "A-01", "camera_id": "C-01", "observed_at": "2026-10-22T09:00:00+08:00",
        "kind": "feeding", "geometry": [0.3, 0.3, 0.7, 0.7],
    })
    assert response.status_code == 200
    assert response.json()["metrics"]["entries"] == 1
    assert response.json()["alerts"][0]["label"] == "区域长时间无检测待核查"
    events = client.get("/api/jobs/job-1/events").json()
    assert events[0]["kind"] == "spatial"
    assert client.get("/api/jobs/job-1/events/0/snapshot").status_code == 200
    assert client.get("/api/jobs/job-1/spatial-reports").json()[0]["pen_id"] == "A-01"
    assert len(client.get("/api/spatial-reports/history", params={
        "pen_id": "A-01", "camera_id": "C-01", "kind": "feeding",
    }).json()) == 1
    audit_url = "/api/jobs/job-1/spatial-reports/feeding/audit"
    assert client.get(audit_url).json()["summary"]["automatic"] == 1
    verdict = client.post(audit_url + "/verdicts", json={
        "event_index": 0, "verdict": "correct", "reviewer": "张三", "note": "完整回看确认",
    })
    assert verdict.status_code == 200
    assert verdict.json()["summary"]["reviewed"] == 1
    missed = client.post(audit_url + "/missed", json={
        "time_seconds": 2.0, "reviewer": "张三", "note": "漏掉一次靠近饲槽",
    })
    assert missed.status_code == 200
    assert missed.json()["summary"]["missed"] == 1
    completed = client.post(audit_url + "/complete", json={"reviewer": "张三"})
    assert completed.json()["summary"]["complete"] is True
    assert completed.json()["summary"]["recall"] == 0.5
    changed = client.post("/api/jobs/job-1/spatial-report", json={
        "pen_id": "A-01", "camera_id": "C-01", "observed_at": "2026-10-22T09:00:00+08:00",
        "kind": "feeding", "geometry": [0.4, 0.4, 0.8, 0.8],
    })
    assert changed.status_code == 200
    refreshed = client.get(audit_url).json()
    assert refreshed["summary"]["reviewed"] == 0
    assert refreshed["summary"]["missed"] == 0
