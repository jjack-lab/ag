from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository


def test_health_assessment_joins_rules_behavior_and_human_review(tmp_path):
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.initialize()
    repository.save_video_job(VideoJobRecord(
        id="cow-job", source_path="cow.mp4", status="completed", progress=1,
        created_at="2026-10-22T10:00:00+08:00", updated_at="2026-10-22T10:00:02+08:00",
        result={"species": "cattle", "track_ids": [7, 8], "frame_count": 210,
                "behavior_model_status": "ready", "behavior_model_version": "test-v1",
                "health_evidence": [{"track_id": 7, "risk_score": 40, "risk_level": "medium",
                                     "observations": [{"type": "still", "label": "持续低活动",
                                                       "time_seconds": 20, "confidence": 0.8,
                                                       "detail": "持续低速", "suggestion": "人工查看"}]},
                                    {"track_id": 8, "risk_score": 0, "risk_level": "normal", "observations": []}],
                "behavior_summary": [{"track_id": 7, "behavior_name": "walking",
                                      "behavior_display_name": "行走", "duration_seconds": 4,
                                      "eligible_ratio": 0.8, "uncertain_duration_seconds": 1,
                                      "model_version": "test-v1"}]},
    ))
    repository.save_video_review({"id": "review-1", "job_id": "cow-job", "species": "cattle",
                                  "issue_type": "other", "track_id": 7, "time_seconds": 20,
                                  "verdict": "uncertain", "note": "局部放大后仍被遮挡",
                                  "created_at": "2026-10-22T10:05:00+08:00"})
    client = TestClient(create_app(repository, media_root=tmp_path / "media"))

    response = client.get("/api/jobs/cow-job/health-assessment")

    assert response.status_code == 200
    data = response.json()
    assert data["model"]["type"] == "rule_based"
    assert data["summary"] == {"track_count": 2, "attention_count": 1, "review_count": 1}
    assert data["tracks"][0]["risk_score"] == 40
    assert data["tracks"][0]["behaviors"][0]["behavior_display_name"] == "行走"
    assert data["tracks"][0]["uncertain_duration_seconds"] == 1
    assert data["tracks"][0]["reviews"][0]["verdict"] == "uncertain"
    assert "持续低活动" in data["tracks"][0]["analysis"]
    assert "行走 4.0 秒" in data["tracks"][0]["analysis"]
    assert "1.0 秒无法确定" in data["tracks"][0]["analysis"]
    assert data["tracks"][1]["risk_score"] == 0


def test_health_assessment_does_not_score_sheep(tmp_path):
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.initialize()
    repository.save_video_job(VideoJobRecord(
        id="sheep-job", source_path="sheep.mp4", status="completed", progress=1,
        created_at="2026-10-22T10:00:00+08:00", updated_at="2026-10-22T10:00:02+08:00",
        result={"species": "sheep", "track_ids": [1], "health_evidence": []},
    ))
    client = TestClient(create_app(repository, media_root=tmp_path / "media"))
    assert client.get("/api/jobs/sheep-job/health-assessment").status_code == 422
