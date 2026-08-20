import csv
import json

from cattle_health_app.behavior.reporting import BehaviorObservation, build_behavior_summary, write_behavior_report, write_behavior_summary, write_behavior_timeline


def obs(frame, track, label_id, label, display, confidence, eligible, version="v1"):
    return BehaviorObservation(frame, frame / 20.0, track, label_id, label, display, confidence, eligible, version)


def test_summary_uses_observed_track_duration_and_excludes_uncertain_from_health_totals(tmp_path):
    observations = [obs(0, 7, 2, "grazing", "采食", .8, True), obs(1, 7, 2, "grazing", "采食", .6, True), obs(2, 7, 1, "none", "无法确定", .4, False), obs(3, 7, 10, "other", "无法确定", .7, False)]
    rows = build_behavior_summary(observations, fps=20.0)
    assert sum(row["percentage"] for row in rows if row["track_id"] == 7) == 100.0
    grazing = next(row for row in rows if row["label_id"] == 2)
    uncertain = next(row for row in rows if row["label_id"] == 1)
    assert grazing["duration_seconds"] == .1
    assert grazing["percentage"] == 50.0
    assert grazing["mean_confidence"] == .7
    assert uncertain["duration_seconds"] == .1
    assert uncertain["health_eligible"] is False
    report = write_behavior_report(tmp_path / "report.json", observations, rows, "ready", "v1", 20.0)
    assert report["health_statistics"]["7"]["eligible_duration_seconds"] == .1
    assert report["health_statistics"]["7"]["uncertain_duration_seconds"] == .1
    assert report["health_statistics"]["7"]["denominator"] == "eligible_behavior_duration_only"


def test_low_confidence_and_uncertain_labels_are_normalized_to_one_uncertain_bucket():
    observations = [obs(0, 1, 11, "hidden", "hidden", .9, False), obs(1, 1, 2, "grazing", "采食", .2, True)]
    rows = build_behavior_summary(observations, fps=20, confidence_threshold=.45)
    assert rows == [{"track_id": 1, "label_id": 1, "label": "none", "display_name": "无法确定", "duration_seconds": .1, "percentage": 100.0, "mean_confidence": .55, "health_eligible": False, "model_version": "v1"}]


def test_csv_and_json_writers_publish_structured_artifacts(tmp_path):
    observations = [obs(0, 3, 3, "walking", "行走", .75, True)]
    rows = build_behavior_summary(observations, 20)
    timeline, summary, report = tmp_path / "timeline.csv", tmp_path / "summary.csv", tmp_path / "report.json"
    write_behavior_timeline(timeline, observations)
    write_behavior_summary(summary, rows)
    write_behavior_report(report, observations, rows, "ready", "v1", 20)
    assert list(csv.DictReader(timeline.open(encoding="utf-8-sig")))[0]["display_name"] == "行走"
    assert list(csv.DictReader(summary.open(encoding="utf-8-sig")))[0]["mean_confidence"] == "0.75"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["behavior_model_status"] == "ready"
    assert payload["summary"] == rows
