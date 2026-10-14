from health_monitor import CowHealthSummary, HealthAlert

from cattle_health_app.health_evidence import build_health_evidence


def test_build_health_evidence_connects_track_alert_and_review_action():
    summaries = [CowHealthSummary(7, 65, "high", 1, ("still",), 1.2)]
    alerts = [HealthAlert(7, "still", "medium", 40, 2.0, 0.91, "Low motion", "现场复核活动和采食")]

    graph = build_health_evidence(summaries, alerts)

    assert graph == [{
        "track_id": 7,
        "risk_score": 65,
        "risk_level": "high",
        "observations": [{
            "type": "still", "label": "持续低活动", "time_seconds": 2.0,
            "confidence": 0.91, "detail": "Low motion",
            "suggestion": "现场复核活动和采食",
        }],
    }]


def test_build_health_evidence_keeps_tracks_without_alerts():
    graph = build_health_evidence([CowHealthSummary(3, 0, "normal", 0, (), 10.0)], [])
    assert graph[0]["track_id"] == 3
    assert graph[0]["observations"] == []


def test_build_health_evidence_explains_low_activity_score_without_alert():
    graph = build_health_evidence([CowHealthSummary(3, 15, "low", 0, (), 2.0)], [])
    assert graph[0]["observations"][0]["type"] == "low_average_speed"
    assert graph[0]["observations"][0]["time_seconds"] is None
