import csv


def test_behavior_summary_csv_contains_product_ratios_and_uncertain_time(tmp_path):
    from cattle_health_app.behavior.reporting import (
        BehaviorObservation,
        build_behavior_summary,
        write_behavior_summary,
    )

    observations = [
        BehaviorObservation(0, 0.0, 7, 2, "grazing", "采食", 0.9, True, "v1"),
        BehaviorObservation(1, 1.0, 7, 2, "grazing", "采食", 0.8, True, "v1"),
        BehaviorObservation(2, 2.0, 7, 1, "none", "无法确定", 0.3, False, "v1"),
    ]
    rows = build_behavior_summary(observations, fps=1.0)
    path = tmp_path / "behavior_summary.csv"

    write_behavior_summary(path, rows)

    with path.open(encoding="utf-8-sig", newline="") as source:
        exported = list(csv.DictReader(source))
    grazing = next(row for row in exported if row["behavior_name"] == "grazing")
    assert grazing["behavior_display_name"] == "采食"
    assert float(grazing["eligible_ratio"]) == 1.0
    assert float(grazing["uncertain_duration_seconds"]) == 1.0

