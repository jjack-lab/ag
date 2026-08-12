import tempfile
import unittest
from pathlib import Path
from shutil import copyfile

from cattle_health_app.api import create_app
from cattle_health_app.domain import AlertLevel, AlertRecord
from cattle_health_app.repository import SQLiteRepository


class FakeMediaProcessor:
    def detect_image(self, source_path, result_path, conf, iou, class_id):
        copyfile(source_path, result_path)
        return 3

    def detect_video(self, source_path, result_dir, conf, iou, class_id):
        result_path = Path(result_dir) / f"{Path(source_path).stem}_detected.mp4"
        copyfile(source_path, result_path)
        return result_path


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteRepository(Path(self.directory.name) / "app.db")
        self.repository.initialize()
        self.repository.save_alert(
            AlertRecord(
                id="a1",
                cattle_id="023",
                risk_type="activity_drop",
                level=AlertLevel.HIGH,
                reason="活动量明显下降",
                suggestion="检查采食、饮水和步态",
                occurred_at="2026-07-11T10:00:00+08:00",
                confidence=0.86,
            )
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_health_and_dashboard_endpoints(self):
        from fastapi.testclient import TestClient

        client = TestClient(create_app(self.repository))

        self.assertEqual("local", client.get("/api/health").json()["mode"])
        dashboard = client.get("/api/dashboard").json()
        self.assertEqual(1, dashboard["high_risk_cattle"])
        self.assertEqual(1, dashboard["open_alerts"])

    def test_resolves_alert_with_operator_note(self):
        from fastapi.testclient import TestClient

        client = TestClient(create_app(self.repository))
        response = client.post(
            "/api/alerts/a1/resolve", json={"note": "已完成现场检查"}
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("resolved", response.json()["status"])

    def test_recognizes_uploaded_image_and_serves_result(self):
        from fastapi.testclient import TestClient

        media_root = Path(self.directory.name) / "media"
        client = TestClient(
            create_app(self.repository, FakeMediaProcessor(), media_root)
        )

        response = client.post(
            "/api/recognition/image",
            files={"file": ("cattle.jpg", b"image-bytes", "image/jpeg")},
            data={"conf": "0.25", "iou": "0.45", "class_id": "-1"},
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("image", payload["kind"])
        self.assertEqual(3, payload["detection_count"])
        self.assertEqual(200, client.get(payload["result_url"]).status_code)

    def test_recognizes_uploaded_video_and_serves_result(self):
        from fastapi.testclient import TestClient

        media_root = Path(self.directory.name) / "media"
        client = TestClient(
            create_app(self.repository, FakeMediaProcessor(), media_root)
        )

        response = client.post(
            "/api/recognition/video",
            files={"file": ("cattle.mp4", b"video-bytes", "video/mp4")},
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("video", payload["kind"])
        self.assertEqual("completed", payload["status"])
        self.assertEqual(200, client.get(payload["result_url"]).status_code)


if __name__ == "__main__":
    unittest.main()
