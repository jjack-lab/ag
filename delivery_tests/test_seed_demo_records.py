from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository
from scripts.seed_demo_records import seed_demo_records


def test_demo_seed_is_idempotent_and_does_not_claim_verified_counts(tmp_path):
    repository = SQLiteRepository(tmp_path / "site.db")
    repository.initialize()
    repository.save_video_job(VideoJobRecord(
        id="job-demo", source_path="sample.mp4", status="completed", progress=1.0,
        created_at="2026-10-25T10:00:00+08:00", updated_at="2026-10-25T10:00:00+08:00",
        result={"species": "cattle", "track_ids": [1, 2, 3]},
    ))
    first = seed_demo_records(repository, "job-demo")
    second = seed_demo_records(repository, "job-demo")
    assert first == {"animal_links_created": 2, "inventory_checks_created": 2}
    assert second == {"animal_links_created": 0, "inventory_checks_created": 0}
    assert {row["animal_id"] for row in repository.list_job_animal_links("job-demo")} == {
        "DEMO-COW-001", "DEMO-COW-002",
    }
    checks = repository.list_inventory_checks_for_job("job-demo")
    assert len(checks) == 2
    assert all(row["coverage"] == "unknown" and row["observed_count"] is None for row in checks)
    assert all("模拟" in row["baseline_source"] for row in checks)


def test_demo_seed_rejects_missing_tracks(tmp_path):
    repository = SQLiteRepository(tmp_path / "site.db")
    repository.initialize()
    repository.save_video_job(VideoJobRecord(
        id="job-demo", source_path="sample.mp4", status="completed", progress=1.0,
        created_at="2026-10-25T10:00:00+08:00", updated_at="2026-10-25T10:00:00+08:00",
        result={"species": "cattle", "track_ids": [1]},
    ))
    try:
        seed_demo_records(repository, "job-demo")
    except ValueError as error:
        assert "two cattle tracks" in str(error)
    else:
        raise AssertionError("expected missing-track rejection")
    assert repository.list_job_animal_links("job-demo") == []
