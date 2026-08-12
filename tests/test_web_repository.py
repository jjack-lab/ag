import tempfile
import unittest
from pathlib import Path

from cattle_health_app.domain import AlertLevel, AlertRecord
from cattle_health_app.repository import SQLiteRepository


class SQLiteRepositoryTests(unittest.TestCase):
    def test_saves_lists_and_resolves_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteRepository(Path(directory) / "app.db")
            repository.initialize()
            repository.save_alert(
                AlertRecord(
                    id="a1",
                    cattle_id="023",
                    risk_type="stillness",
                    level=AlertLevel.HIGH,
                    reason="长时间不动",
                    suggestion="现场检查",
                    occurred_at="2026-07-11T10:00:00+08:00",
                    confidence=0.9,
                )
            )

            self.assertEqual("a1", repository.list_alerts()[0].id)

            resolved = repository.resolve_alert(
                "a1", "已现场检查", "2026-07-11T10:08:00+08:00"
            )

            self.assertEqual("resolved", resolved.status)
            self.assertEqual([], repository.list_alerts(status="open"))


if __name__ == "__main__":
    unittest.main()
