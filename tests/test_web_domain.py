import unittest

from cattle_health_app.domain import AlertLevel, AlertRecord


class AlertRecordTests(unittest.TestCase):
    def test_serializes_operator_facing_fields(self):
        alert = AlertRecord(
            id="alert-1",
            cattle_id="023",
            risk_type="activity_drop",
            level=AlertLevel.HIGH,
            reason="24 小时活动量下降 42%",
            suggestion="检查采食、饮水和步态",
            occurred_at="2026-07-11T10:00:00+08:00",
            confidence=0.86,
            evidence_path="evidence/alert-1.jpg",
        )

        serialized = alert.to_dict()

        self.assertEqual("high", serialized["level"])
        self.assertEqual("023", serialized["cattle_id"])
        self.assertEqual("open", serialized["status"])


if __name__ == "__main__":
    unittest.main()
