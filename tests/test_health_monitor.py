import csv
import os
import tempfile
import unittest

from health_monitor import CattleHealthMonitor, DetectionObservation, HealthConfig


class CattleHealthMonitorTest(unittest.TestCase):
    def test_raises_still_and_lying_alerts_for_cattle(self):
        monitor = CattleHealthMonitor(
            HealthConfig(
                fps=10.0,
                cattle_class_ids={1},
                still_seconds=0.2,
                still_speed_px_s=2.0,
                lying_seconds=0.2,
                lying_aspect_ratio=1.8,
                isolation_seconds=10.0,
            )
        )

        alerts = []
        for frame_index in range(3):
            alerts.extend(
                monitor.update(
                    frame_index,
                    [
                        DetectionObservation(
                            track_id=7,
                            class_id=1,
                            confidence=0.91,
                            xywh=(100.0, 120.0, 90.0, 40.0),
                        )
                    ],
                )
            )

        alert_types = {alert.alert_type for alert in alerts}
        self.assertIn("still", alert_types)
        self.assertIn("lying", alert_types)
        self.assertTrue(all(alert.track_id == 7 for alert in alerts))
        self.assertTrue(all(alert.severity in {"medium", "high"} for alert in alerts))

    def test_raises_isolation_alert_when_cattle_stays_far_from_herd(self):
        monitor = CattleHealthMonitor(
            HealthConfig(
                fps=5.0,
                cattle_class_ids={1},
                still_seconds=99.0,
                lying_seconds=99.0,
                isolation_seconds=0.4,
                isolation_distance_px=80.0,
            )
        )

        alerts = []
        for frame_index in range(3):
            alerts.extend(
                monitor.update(
                    frame_index,
                    [
                        DetectionObservation(1, 1, 0.9, (100.0, 100.0, 50.0, 50.0)),
                        DetectionObservation(2, 1, 0.9, (110.0, 100.0, 50.0, 50.0)),
                        DetectionObservation(3, 1, 0.9, (400.0, 400.0, 50.0, 50.0)),
                    ],
                )
            )

        isolated_alerts = [alert for alert in alerts if alert.alert_type == "isolated"]
        self.assertEqual(1, len(isolated_alerts))
        self.assertEqual(3, isolated_alerts[0].track_id)

    def test_exports_alerts_to_csv_with_required_fields(self):
        monitor = CattleHealthMonitor(
            HealthConfig(
                fps=10.0,
                cattle_class_ids={1},
                still_seconds=0.1,
                still_speed_px_s=2.0,
                lying_seconds=99.0,
                isolation_seconds=99.0,
            )
        )
        for frame_index in range(2):
            monitor.update(
                frame_index,
                [DetectionObservation(4, 1, 0.87, (50.0, 60.0, 40.0, 80.0))],
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "health_alerts.csv")
            monitor.export_alerts_csv(csv_path)
            with open(csv_path, newline="", encoding="utf-8") as csvfile:
                rows = list(csv.DictReader(csvfile))

        self.assertEqual(1, len(rows))
        self.assertEqual("4", rows[0]["track_id"])
        self.assertEqual("still", rows[0]["alert_type"])
        self.assertIn("suggestion", rows[0])

    def test_does_not_repeat_same_alert_while_condition_persists(self):
        monitor = CattleHealthMonitor(
            HealthConfig(
                fps=10.0,
                cattle_class_ids={1},
                still_seconds=0.1,
                still_speed_px_s=2.0,
                lying_seconds=99.0,
                isolation_seconds=99.0,
            )
        )

        returned_alerts = []
        for frame_index in range(5):
            returned_alerts.extend(
                monitor.update(
                    frame_index,
                    [DetectionObservation(5, 1, 0.87, (50.0, 60.0, 40.0, 80.0))],
                )
            )

        self.assertEqual(1, len(returned_alerts))
        self.assertEqual(1, len(monitor.alerts))
        self.assertEqual("still", returned_alerts[0].alert_type)

    def test_summarizes_per_cow_risk_score_and_level(self):
        monitor = CattleHealthMonitor(
            HealthConfig(
                fps=10.0,
                cattle_class_ids={1},
                still_seconds=0.2,
                still_speed_px_s=2.0,
                lying_seconds=0.2,
                lying_aspect_ratio=1.8,
                isolation_seconds=99.0,
            )
        )
        for frame_index in range(3):
            monitor.update(
                frame_index,
                [DetectionObservation(9, 1, 0.95, (80.0, 90.0, 100.0, 40.0))],
            )

        summaries = monitor.summarize_health()

        self.assertEqual(1, len(summaries))
        self.assertEqual(9, summaries[0].track_id)
        self.assertGreaterEqual(summaries[0].risk_score, 70)
        self.assertEqual("high", summaries[0].risk_level)
        self.assertIn("lying", summaries[0].alert_types)


if __name__ == "__main__":
    unittest.main()
