from cattle_health_app.behavior.reporting import build_behavior_summary, write_behavior_report
from delivery_tests.test_behavior_reporting import obs


def test_health_percentages_use_only_eligible_duration_as_denominator(tmp_path):
    observations = [
        obs(0, 7, 2, "grazing", "采食", .8, True),
        obs(1, 7, 3, "walking", "行走", .8, True),
        obs(2, 7, 1, "none", "无法确定", .8, False),
        obs(3, 7, 11, "hidden", "无法确定", .8, False),
    ]
    summary = build_behavior_summary(observations, 20)
    report = write_behavior_report(tmp_path / "report.json", observations, summary, "ready", "v1", 20)
    health = report["health_statistics"]["7"]
    assert health["eligible_behavior_percentages"] == {"grazing": 50.0, "walking": 50.0}
    assert sum(health["eligible_behavior_percentages"].values()) == 100.0
