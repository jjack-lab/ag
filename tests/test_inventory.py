from cattle_health_app.inventory import inventory_state, validate_recheck
from cattle_health_app.repository import SQLiteRepository


def check(**changes):
    return {
        "id": "check-1", "job_id": "job-1", "species": "sheep", "pen_id": "A-1",
        "expected_count": 20, "baseline_source": "2026-10-15 圈舍台账",
        "observed_count": 18, "coverage": "complete", "coverage_note": "全圈舍均在画面内",
        "operator_name": "operator", "observed_at": "2026-10-15T10:00:00+08:00",
        "created_at": "2026-10-15T10:01:00+08:00", **changes,
    }


def recheck(**changes):
    return {
        "id": "review-1", "check_id": "check-1", "counted_count": 18,
        "outcome": "shortfall_pending", "movement_records_checked": False,
        "field_search_complete": False, "lost_count": None,
        "operator_name": "operator", "note": "second count", "created_at": "2026-10-15T11:00:00+08:00",
        **changes,
    }


def test_coverage_precedes_a_numerical_gap():
    result = inventory_state(check(coverage="partial"), None)
    assert result == {"status": "coverage_needed", "difference": 2, "current_count": 18}


def test_absent_count_is_distinct_from_zero_and_equal_count_is_not_loss():
    assert inventory_state(check(observed_count=None), None)["status"] == "count_needed"
    assert inventory_state(check(observed_count=0), None)["difference"] == 20
    assert inventory_state(check(observed_count=20), None)["status"] == "preliminary_match"
    assert inventory_state(check(), None)["status"] == "discrepancy_pending"


def test_recheck_does_not_create_automatic_loss():
    assert inventory_state(check(), recheck())["status"] == "shortfall_pending"
    assert inventory_state(check(), recheck(counted_count=20, outcome="resolved"))["status"] == "verified_match"
    assert inventory_state(check(), recheck(outcome="loss_user_recorded", lost_count=2))[
        "status"] == "loss_user_recorded"


def test_loss_registration_requires_field_and_movement_evidence():
    candidate = recheck(outcome="loss_user_recorded", lost_count=2)
    for changes in (
        {}, {"movement_records_checked": True},
        {"movement_records_checked": True, "field_search_complete": True, "lost_count": 3},
    ):
        invalid = {**candidate, **changes}
        try:
            validate_recheck(check(), invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("unverified loss was accepted")
    valid = {**candidate, "movement_records_checked": True, "field_search_complete": True}
    validate_recheck(check(), valid)


def test_recheck_rejects_incomplete_coverage_and_inconsistent_outcome():
    for original, candidate in (
        (check(coverage="unknown"), recheck()),
        (check(), recheck(outcome="resolved")),
        (check(), recheck(counted_count=20, outcome="shortfall_pending")),
    ):
        try:
            validate_recheck(original, candidate)
        except ValueError:
            pass
        else:
            raise AssertionError("inconsistent recheck was accepted")


def test_inventory_storage_is_append_only_and_persists(tmp_path):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    repo.save_inventory_check(check())
    repo.save_inventory_recheck(recheck())
    reopened = SQLiteRepository(tmp_path / "app.db")
    assert reopened.get_inventory_check("check-1")["expected_count"] == 20
    assert reopened.list_inventory_checks()[0]["id"] == "check-1"
    assert reopened.list_inventory_rechecks("check-1")[0]["counted_count"] == 18


def test_later_recheck_wins_when_submitted_in_same_second(tmp_path):
    repo = SQLiteRepository(tmp_path / "app.db")
    repo.initialize()
    repo.save_inventory_check(check())
    repo.save_inventory_recheck(recheck(id="z-first"))
    repo.save_inventory_recheck(recheck(id="a-second", counted_count=20, outcome="resolved"))
    assert repo.list_inventory_rechecks("check-1")[-1]["id"] == "a-second"
