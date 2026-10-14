import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from shutil import copyfile

from cattle_health_app.api import create_app
from cattle_health_app.domain import AlertLevel, AlertRecord, VideoJobRecord
from cattle_health_app.model_registry import ModelArtifact
from cattle_health_app.repository import SQLiteRepository


class FakeMediaProcessor:
    def detect_image(self, source_path, result_path, conf, iou, class_id):
        copyfile(source_path, result_path)
        return 3


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
                reason="activity decreased",
                suggestion="inspect feeding, water intake, and gait",
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

    def test_sheep_video_does_not_inflate_cattle_dashboard_count(self):
        from fastapi.testclient import TestClient

        self.repository.save_video_job(VideoJobRecord(
            id="sheep-job", source_path="sheep.mp4", status="completed", progress=1.0,
            created_at="2026-10-14T10:00:00+08:00",
            updated_at="2026-10-14T10:01:00+08:00",
            result={"tracked_cattle": 4, "species": "sheep"},
        ))
        dashboard = TestClient(create_app(self.repository)).get("/api/dashboard").json()
        self.assertEqual(0, dashboard["monitored_cattle"])

    def test_resolves_alert_with_operator_note(self):
        from fastapi.testclient import TestClient

        client = TestClient(create_app(self.repository))
        response = client.post(
            "/api/alerts/a1/resolve", json={"note": "field inspection complete"}
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("resolved", response.json()["status"])

    def test_lists_completed_video_jobs_and_persists_review(self):
        from fastapi.testclient import TestClient

        self.repository.save_video_job(VideoJobRecord(
            id="job-1", source_path="cattle.mp4", status="completed", progress=1,
            created_at="2026-10-14T10:00:00+08:00",
            updated_at="2026-10-14T10:01:00+08:00",
            result={"species": "cattle", "tracked_cattle": 2,
                    "health_evidence": [{"track_id": 7}]},
        ))
        client = TestClient(create_app(self.repository))

        jobs = client.get("/api/jobs/video").json()
        self.assertEqual(["job-1"], [job["id"] for job in jobs])
        response = client.post("/api/jobs/job-1/reviews", json={
            "issue_type": "false_alert", "track_id": 7,
            "time_seconds": 12.5, "note": "现场复核未见异常",
            "verdict": "confirmed",
        })
        self.assertEqual(201, response.status_code)
        review = response.json()
        self.assertEqual("job-1", review["job_id"])
        self.assertEqual("cattle", review["species"])
        self.assertEqual(7, review["track_id"])
        self.assertEqual([review], client.get("/api/jobs/job-1/reviews").json())
        self.assertEqual(404, client.get("/api/jobs/missing/reviews").status_code)

    def test_review_requires_completed_job_and_valid_track(self):
        from fastapi.testclient import TestClient

        self.repository.save_video_job(VideoJobRecord(
            id="queued", source_path="sheep.mp4", status="queued", progress=0,
            created_at="2026-10-14T10:00:00+08:00",
            updated_at="2026-10-14T10:00:00+08:00",
        ))
        client = TestClient(create_app(self.repository))
        payload = {"issue_type": "id_switch", "track_id": 3,
                   "note": "两只羊在画面中互换 ID", "verdict": "confirmed"}
        self.assertEqual(409, client.post("/api/jobs/queued/reviews", json=payload).status_code)
        self.assertEqual(422, client.post("/api/jobs/queued/reviews", json={
            **payload, "issue_type": "disease_prediction"
        }).status_code)

    def test_links_tracks_from_two_days_to_one_manual_animal_profile(self):
        from fastapi.testclient import TestClient

        for day, track in [("14", 7), ("15", 3)]:
            self.repository.save_video_job(VideoJobRecord(
                id=f"job-{day}", source_path=f"cattle-{day}.mp4",
                status="completed", progress=1,
                created_at=f"2026-10-{day}T10:00:00+08:00",
                updated_at=f"2026-10-{day}T10:01:00+08:00",
                result={"species": "cattle", "track_ids": [track, 8] if day == "14" else [track],
                        "health_evidence": [{"track_id": track, "risk_score": 20}]},
            ))
        client = TestClient(create_app(self.repository))
        for day, track in [("14", 7), ("15", 3)]:
            response = client.post(f"/api/jobs/job-{day}/animal-links", json={
                "track_id": track, "animal_id": "C-023",
            })
            self.assertEqual(201, response.status_code)
        profile = client.get("/api/animals/C-023").json()
        self.assertEqual("cattle", profile["species"])
        self.assertEqual(2, len(profile["visits"]))
        self.assertEqual({3, 7}, {row["track_id"] for row in profile["visits"]})
        self.assertEqual(422, client.post("/api/jobs/job-14/animal-links", json={
            "track_id": 999, "animal_id": "C-999",
        }).status_code)
        self.assertEqual(409, client.post("/api/jobs/job-14/animal-links", json={
            "track_id": 7, "animal_id": "C-999",
        }).status_code)
        self.assertEqual(409, client.post("/api/jobs/job-14/animal-links", json={
            "track_id": 8, "animal_id": "C-023",
        }).status_code)

        self.repository.save_video_job(VideoJobRecord(
            id="sheep-job", source_path="sheep.mp4", status="completed", progress=1,
            created_at="2026-10-16T10:00:00+08:00",
            updated_at="2026-10-16T10:01:00+08:00",
            result={"species": "sheep", "track_ids": [4]},
        ))
        self.assertEqual(409, client.post("/api/jobs/sheep-job/animal-links", json={
            "track_id": 4, "animal_id": "C-023",
        }).status_code)

        invalid = client.post("/api/animals/C-023/followups", json={
            "kind": "veterinary_diagnosis", "observed_at": "2026-10-16",
            "note": "兽医检查", "diagnosis": "示例疾病",
        })
        self.assertEqual(422, invalid.status_code)
        created = client.post("/api/animals/C-023/followups", json={
            "kind": "veterinary_diagnosis", "observed_at": "2026-10-16",
            "note": "兽医检查", "diagnosis": "示例疾病",
            "source_reference": "诊疗记录-001",
        })
        self.assertEqual(201, created.status_code)
        self.assertEqual("user_recorded", created.json()["verification_status"])
        profile = client.get("/api/animals/C-023").json()
        self.assertEqual([created.json()], profile["followups"])
        self.assertEqual(204, client.delete("/api/jobs/job-14/animal-links/7").status_code)
        self.assertEqual(404, client.delete("/api/jobs/job-14/animal-links/7").status_code)
        self.assertEqual(1, len(client.get("/api/animals/C-023").json()["visits"]))
        self.assertEqual(409, client.delete("/api/jobs/job-15/animal-links/3").status_code)

    def test_recognizes_uploaded_image_and_serves_result(self):
        from fastapi.testclient import TestClient

        media_root = Path(self.directory.name) / "media"
        model_path = Path(self.directory.name) / "detector.pt"
        model_path.write_bytes(b"test-detector")
        artifact = ModelArtifact(
            name="yolo11-detector",
            path=model_path,
            sha256=sha256(b"test-detector").hexdigest(),
        )
        client = TestClient(
            create_app(
                self.repository,
                FakeMediaProcessor(),
                media_root,
                detector_artifact=artifact,
            )
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


if __name__ == "__main__":
    unittest.main()
