from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository


def client_with_job(tmp_path, *, status="completed", species="sheep"):
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.initialize()
    repository.save_video_job(VideoJobRecord(
        id="job-1", source_path="video.mp4", status=status,
        progress=1.0 if status == "completed" else 0.2,
        created_at="2026-10-15T10:00:00+08:00",
        updated_at="2026-10-15T10:01:00+08:00",
        result={"species": species, "tracked_cattle": 1} if status == "completed" else None,
    ))
    return TestClient(create_app(repository, media_root=tmp_path / "media"))


def payload(**changes):
    return {
        "job_id": "job-1", "pen_id": "A-1", "expected_count": 20,
        "baseline_source": "圈舍台账 2026-10-15", "observed_count": 18,
        "coverage": "complete", "coverage_note": "全圈舍均已拍摄",
        "operator_name": "张三", "observed_at": "2026-10-15T10:00:00+08:00",
        **changes,
    }


def review_payload(**changes):
    return {
        "counted_count": 18, "outcome": "loss_user_recorded",
        "movement_records_checked": True, "field_search_complete": True,
        "lost_count": 2, "operator_name": "李四",
        "note": "核对出入栏记录并现场查找后仍缺 2 只", **changes,
    }


def test_check_preserves_video_species_and_does_not_infer_loss(tmp_path):
    client = client_with_job(tmp_path)
    created = client.post("/api/inventory-checks", json=payload())
    assert created.status_code == 201
    row = created.json()
    assert row["species"] == "sheep"
    assert row["video_track_count"] == 1
    assert row["status"] == "discrepancy_pending"
    assert row["difference"] == 2
    assert row["verification_status"] == "user_recorded"
    assert client.get(f"/api/inventory-checks/{row['id']}").json()["status"] == "discrepancy_pending"
    assert client.get("/api/inventory-checks").json()[0]["id"] == row["id"]


def test_partial_coverage_prevents_loss_review(tmp_path):
    client = client_with_job(tmp_path)
    row = client.post("/api/inventory-checks", json=payload(coverage="partial")).json()
    assert row["status"] == "coverage_needed"
    response = client.post(f"/api/inventory-checks/{row['id']}/rechecks", json=review_payload())
    assert response.status_code == 422


def test_missing_initial_count_prevents_any_recheck(tmp_path):
    client = client_with_job(tmp_path)
    row = client.post(
        "/api/inventory-checks", json=payload(observed_count=None)
    ).json()
    assert row["status"] == "count_needed"
    response = client.post(
        f"/api/inventory-checks/{row['id']}/rechecks", json=review_payload()
    )
    assert response.status_code == 422
    assert "首次人工清点" in response.json()["detail"]


def test_loss_review_requires_recount_and_field_evidence(tmp_path):
    client = client_with_job(tmp_path)
    check = client.post("/api/inventory-checks", json=payload()).json()
    url = f"/api/inventory-checks/{check['id']}/rechecks"
    for invalid in (
        review_payload(movement_records_checked=False),
        review_payload(field_search_complete=False),
        review_payload(lost_count=3),
        review_payload(counted_count=20),
    ):
        assert client.post(url, json=invalid).status_code == 422
    saved = client.post(url, json=review_payload())
    assert saved.status_code == 201
    row = saved.json()
    assert row["status"] == "loss_user_recorded"
    assert row["lost_count"] == 2
    assert row["verification_status"] == "user_recorded"
    assert len(client.get(f"/api/inventory-checks/{check['id']}").json()["rechecks"]) == 1


def test_recount_can_clear_a_preliminary_gap(tmp_path):
    client = client_with_job(tmp_path)
    check = client.post("/api/inventory-checks", json=payload()).json()
    response = client.post(f"/api/inventory-checks/{check['id']}/rechecks", json=review_payload(
        counted_count=20, outcome="resolved", lost_count=None,
        movement_records_checked=False, field_search_complete=False,
    ))
    assert response.status_code == 201
    assert response.json()["status"] == "verified_match"
    assert response.json()["difference"] == 0


def test_incomplete_job_unknown_job_and_invalid_counts_are_rejected(tmp_path):
    client = client_with_job(tmp_path, status="running")
    assert client.post("/api/inventory-checks", json=payload()).status_code == 409
    assert client.post("/api/inventory-checks", json=payload(job_id="missing")).status_code == 404
    complete = client_with_job(tmp_path)
    assert complete.post("/api/inventory-checks", json=payload(expected_count=-1)).status_code == 422
    assert complete.post("/api/inventory-checks", json=payload(operator_name="  ")).status_code == 422
    zero = complete.post("/api/inventory-checks", json=payload(observed_count=0))
    assert zero.status_code == 201
    assert zero.json()["difference"] == 20


def test_inventory_history_pages_beyond_first_hundred_and_filters_latest_state(tmp_path):
    client = client_with_job(tmp_path)
    for index in range(105):
        result = client.post("/api/inventory-checks", json=payload(
            pen_id=f"A-{index:03}",
            observed_count=20 if index % 2 == 0 else 18,
            observed_at=f"2026-10-15T10:{index // 60:02}:{index % 60:02}+08:00",
        ))
        assert result.status_code == 201

    first = client.get("/api/inventory-checks/page?limit=20&offset=0")
    assert first.status_code == 200
    assert first.json()["total"] == 105
    assert len(first.json()["items"]) == 20
    second = client.get("/api/inventory-checks/page?limit=20&offset=100")
    assert second.json()["total"] == 105
    assert len(second.json()["items"]) == 5
    assert set(item["id"] for item in first.json()["items"]).isdisjoint(
        item["id"] for item in second.json()["items"]
    )

    specific = client.get("/api/inventory-checks/page?pen_id=A-001")
    assert specific.json()["total"] == 1
    check = specific.json()["items"][0]
    assert check["status"] == "discrepancy_pending"
    saved = client.post(f"/api/inventory-checks/{check['id']}/rechecks", json=review_payload(
        counted_count=20, outcome="resolved", lost_count=None,
        movement_records_checked=False, field_search_complete=False,
    ))
    assert saved.status_code == 201
    matched = client.get("/api/inventory-checks/page?pen_id=A-001&status=verified_match")
    assert matched.json()["total"] == 1
    assert matched.json()["items"][0]["id"] == check["id"]
    assert client.get("/api/inventory-checks/page?pen_id=A-001&status=discrepancy_pending").json()["total"] == 0


def test_inventory_history_page_rejects_invalid_parameters(tmp_path):
    client = client_with_job(tmp_path)
    for query in ("limit=0", "limit=101", "offset=-1", "status=unknown"):
        assert client.get(f"/api/inventory-checks/page?{query}").status_code == 422
