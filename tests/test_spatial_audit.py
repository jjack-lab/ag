from cattle_health_app.spatial_audit import add_missed, audit_summary, new_audit, set_verdict


def test_event_audit_reports_partial_then_full_directional_error():
    report = {"kind": "gate", "metrics": {"events": [
        {"track_id": 1, "time_seconds": 2, "direction": "enter"},
        {"track_id": 2, "time_seconds": 4, "direction": "leave"},
        {"track_id": 3, "time_seconds": 6, "direction": "enter"},
    ]}}
    audit = new_audit(report)
    audit = set_verdict(audit, report, 0, "correct", "张三", "视频确认")
    audit = set_verdict(audit, report, 1, "false_positive", "张三", "只是靠近线")
    assert audit_summary(audit, report)["complete"] is False
    audit = set_verdict(audit, report, 2, "wrong_direction", "张三", "实际离开")
    audit = add_missed(audit, report, 8.0, "enter", "张三", "遮挡后进入")
    assert audit_summary(audit, report) == {
        "automatic": 3, "reviewed": 3, "correct": 1, "false_positive": 1,
        "wrong_direction": 1, "missed": 1, "complete": False,
        "precision": None, "recall": None,
    }
    audit["coverage_confirmed"] = True
    assert audit_summary(audit, report) == {
        "automatic": 3, "reviewed": 3, "correct": 1, "false_positive": 1,
        "wrong_direction": 1, "missed": 1, "complete": True,
        "precision": 1 / 3, "recall": 1 / 3,
    }


def test_report_change_invalidates_old_audit():
    first = {"kind": "feeding", "geometry": [0.1, 0.1, 0.4, 0.4], "metrics": {"events": []}}
    second = {"kind": "feeding", "geometry": [0.2, 0.2, 0.5, 0.5], "metrics": {"events": []}}
    assert new_audit(first)["report_hash"] != new_audit(second)["report_hash"]
