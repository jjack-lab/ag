from health_monitor import CattleHealthMonitor, DetectionObservation, HealthConfig


def test_stationary_track_emits_explainable_alert():
    monitor = CattleHealthMonitor(
        HealthConfig(
            fps=1.0,
            cattle_class_ids={1},
            still_seconds=2.0,
            still_speed_px_s=5.0,
        )
    )

    alerts = []
    for frame_index in range(4):
        alerts.extend(
            monitor.update(
                frame_index,
                [
                    DetectionObservation(
                        track_id=7,
                        class_id=1,
                        confidence=0.9,
                        xywh=(100.0, 100.0, 20.0, 20.0),
                    )
                ],
            )
        )

    assert [alert.alert_type for alert in alerts] == ["still"]
    assert alerts[0].severity == "medium"
    assert monitor.summarize_health()[0].risk_level == "medium"
