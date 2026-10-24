import csv
import io

from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import AlertLevel, AlertRecord, VideoJobRecord
from cattle_health_app.repository import SQLiteRepository


def setup_client(tmp_path):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    return repo, TestClient(create_app(repo, media_root=tmp_path / "media"))


def add_job(repo, number, species="cattle"):
    repo.save_video_job(VideoJobRecord(
        id=f"v{number}", source_path="video.mp4", status="completed", progress=1,
        created_at="2026-10-23T23:30:00Z", updated_at="2026-10-24T08:00:00+08:00",
        result={"species": species, "track_ids": [7], "tracked_cattle": 1},
    ))


def test_animal_directory_lists_only_linked_animals_and_literal_search(tmp_path):
    repo, client = setup_client(tmp_path)
    assert client.get("/api/animals").json() == []
    for i, species, animal in [(1, "cattle", "C_01"), (2, "sheep", "S-02")]:
        add_job(repo, i, species)
        repo.save_animal_link({"job_id": f"v{i}", "track_id": 7,
                               "animal_id": animal, "species": species,
                               "linked_at": "2026-10-24T08:00:00+08:00"})
    rows = client.get("/api/animals?species=cattle&q=_").json()
    assert [r["animal_id"] for r in rows] == ["C_01"]
    assert rows[0]["video_count"] == 1
    assert rows[0]["followup_count"] == 0
    assert client.get("/api/animals?q=%25").json() == []
    assert len(client.get("/api/animals").json()) == 2


def test_analytics_counts_full_history_in_shanghai_days_and_exports_same_filter(tmp_path):
    repo, client = setup_client(tmp_path)
    for i in range(31):
        add_job(repo, i, "sheep" if i == 30 else "cattle")
    repo.save_alert(AlertRecord(id="v1:0", cattle_id="7", risk_type="still",
        level=AlertLevel.HIGH, reason="still", suggestion="review",
        occurred_at="2026-10-24T01:00:00+08:00", confidence=0.9))
    repo.resolve_alert("v1:0", "checked", "2026-10-24T10:00:00+08:00")
    query = "?start=2026-10-24&end=2026-10-24"
    response = client.get("/api/analytics" + query)
    assert response.status_code == 200
    data = response.json()
    assert data["timezone"] == "Asia/Shanghai"
    assert data["totals"]["videos"] == 31
    assert data["totals"]["cattle_videos"] == 30
    assert data["totals"]["sheep_videos"] == 1
    assert data["totals"]["alerts"] == 1
    assert data["totals"]["resolved_alerts"] == 1
    assert client.get("/api/analytics?end=2026-10-23").json()["totals"]["videos"] == 0
    exported = client.get("/api/analytics.csv" + query)
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0]["date"] == "2026-10-24"
    assert int(rows[0]["videos"]) == data["daily"][0]["videos"]
    assert client.get("/api/analytics?start=2026-10-25&end=2026-10-24").status_code == 422


def test_browser_webm_uses_existing_video_job_endpoint(tmp_path):
    repo, _ = setup_client(tmp_path)
    class Jobs:
        def create(self, source, *parameters):
            assert source.suffix == ".webm"
            assert source.read_bytes() == b"webm-video"
            return VideoJobRecord(id="camera-job", source_path=str(source), status="queued", progress=0,
                                  created_at="2026-10-24T08:00:00+08:00", updated_at="2026-10-24T08:00:00+08:00")
    client = TestClient(create_app(repo, media_root=tmp_path / "media", job_service=Jobs()))
    result = client.post("/api/jobs/video", files={"file": ("camera.webm", b"webm-video", "video/webm")},
                         data={"class_id": 1, "tracker": "bytetrack.yaml"})
    assert result.status_code == 202
    assert result.json()["id"] == "camera-job"
