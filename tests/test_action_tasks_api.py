from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository


def client_with_video(tmp_path, *, status="completed"):
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.initialize()
    repository.save_video_job(VideoJobRecord(
        id="job-1", source_path="video.mp4", status=status,
        progress=1.0 if status == "completed" else 0.2,
        created_at="2026-10-22T09:00:00+08:00",
        updated_at="2026-10-22T09:01:00+08:00",
        result={"species": "cattle", "track_ids": [7], "tracked_cattle": 1}
        if status == "completed" else None,
    ))
    return TestClient(create_app(repository, media_root=tmp_path / "media"))


def task_payload(**changes):
    return {
        "job_id": "job-1", "title": "核查低活动提示", "track_id": 7,
        "time_seconds": 3.5, "assignee": "李四",
        "due_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        **changes,
    }


def test_action_task_lifecycle_keeps_video_evidence_and_history(tmp_path):
    client = client_with_video(tmp_path)
    created = client.post("/api/action-tasks", json=task_payload())
    assert created.status_code == 201
    task = created.json()
    assert task["job_id"] == "job-1"
    assert task["track_id"] == 7
    assert task["status"] == "pending"
    assert task["updates"] == []

    for status, next_due in (
        ("in_progress", None),
        ("followup", (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()),
        ("closed", None),
    ):
        response = client.post(f"/api/action-tasks/{task['id']}/updates", json={
            "status": status, "actor": "李四", "note": f"状态变为 {status}",
            "next_due_at": next_due,
        })
        assert response.status_code == 201
        task = response.json()
        assert task["status"] == status

    assert [row["status"] for row in task["updates"]] == [
        "in_progress", "followup", "closed",
    ]
    assert client.get(f"/api/action-tasks/{task['id']}").json() == task
    assert [row["id"] for row in client.get("/api/action-tasks?status=closed").json()] == [task["id"]]
    assert client.get("/api/action-tasks?status=pending").json() == []


def test_action_task_rejects_invalid_source_and_blank_fields(tmp_path):
    client = client_with_video(tmp_path)
    assert client.post("/api/action-tasks", json=task_payload(job_id="missing")).status_code == 404
    assert client.post("/api/action-tasks", json=task_payload(title="  ")).status_code == 422
    assert client.post("/api/action-tasks", json=task_payload(assignee="  ")).status_code == 422
    assert client.post("/api/action-tasks", json=task_payload(time_seconds=-1)).status_code == 422
    incomplete = client_with_video(tmp_path, status="running")
    assert incomplete.post("/api/action-tasks", json=task_payload()).status_code == 409


def test_action_task_followup_requires_date_and_closure_requires_note(tmp_path):
    client = client_with_video(tmp_path)
    task = client.post("/api/action-tasks", json=task_payload()).json()
    url = f"/api/action-tasks/{task['id']}/updates"
    assert client.post(url, json={"status": "followup", "actor": "李四", "note": "待复查"}).status_code == 422
    assert client.post(url, json={"status": "closed", "actor": "李四", "note": "  "}).status_code == 422
    assert client.get(f"/api/action-tasks/{task['id']}").json()["updates"] == []
