from cattle_health_app.sheep_motion import summarize_sheep_motion

from fastapi.testclient import TestClient
from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository


def row(frame, x, track=7, width=20):
    return {"frame_index": frame, "track_id": track, "center_x": x,
            "center_y": 30, "width": width, "height": 20}


def test_sheep_motion_reports_relative_activity_and_transitions():
    rows = [row(0, 10), row(10, 10), row(20, 20), row(30, 60)]
    summary, events = summarize_sheep_motion(rows, fps=10)
    assert summary == [{"track_id": 7, "still_seconds": 1.0,
                        "moving_seconds": 1.0, "fast_seconds": 1.0,
                        "observed_seconds": 3.0}]
    assert [(event["time_seconds"], event["label"]) for event in events] == [
        (1.0, "低位移"), (2.0, "移动"), (3.0, "快速移动")]


def test_sheep_motion_ignores_large_gaps_and_invalid_tracks():
    summary, events = summarize_sheep_motion([row(0, 10), row(30, 80), row(31, 80, width=0)], fps=10)
    assert summary == []
    assert events == []


def test_sheep_motion_uses_half_second_windows_to_limit_box_jitter():
    summary, events = summarize_sheep_motion([row(frame, 10 + frame % 2) for frame in range(11)], fps=10)
    assert summary[0]["still_seconds"] == 1.0
    assert summary[0]["moving_seconds"] == 0
    assert len(events) == 1


def test_sheep_motion_is_attached_to_manual_cross_video_profile(tmp_path):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    repo.save_video_job(VideoJobRecord(
        id="sheep-1", source_path="unused.mp4", status="completed", progress=1,
        created_at="2026-10-14T10:00:00+08:00", updated_at="2026-10-14T10:01:00+08:00",
        result={"species": "sheep", "track_ids": [7], "sheep_motion_summary": [{
            "track_id": 7, "still_seconds": 2, "moving_seconds": 1,
            "fast_seconds": 0, "observed_seconds": 3}]},
    ))
    repo.save_animal_link({"job_id": "sheep-1", "track_id": 7, "animal_id": "S-1",
                           "species": "sheep", "linked_at": "2026-10-14T11:00:00+08:00"})
    response = TestClient(create_app(repo, media_root=tmp_path / "media")).get("/api/animals/S-1")
    assert response.status_code == 200
    assert response.json()["visits"][0]["sheep_motion"]["moving_seconds"] == 1
