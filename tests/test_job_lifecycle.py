import shutil
import unittest
import uuid
from pathlib import Path

from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.jobs import INTERRUPTED_MESSAGE, VideoJobService
from cattle_health_app.repository import SQLiteRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ImmediateExecutor:
    """同步执行，便于断言进度写库次数。"""

    def submit(self, function, *args, **kwargs):
        function(*args, **kwargs)
        return None


class RecordingRepository:
    def __init__(self):
        self.saved = []

    def save_video_job(self, job):
        self.saved.append(job)

    def save_alert(self, alert):
        raise AssertionError("本用例不应产生告警")


class FakeResult:
    def __init__(self, alert_csv):
        self.alert_csv = str(alert_csv)
        self.trajectory_anomaly_csv = None

    def to_dict(self, result_root):
        return {"video_path": "job/video.mp4"}


class FakeProcessor:
    def track_video(
        self,
        source_path,
        result_root,
        conf,
        iou,
        class_id,
        tracker,
        progress_callback=None,
    ):
        root = Path(result_root)
        root.mkdir(parents=True, exist_ok=True)
        alert_csv = root / "alerts.csv"
        alert_csv.write_text(
            "time_seconds,track_id,alert_type,severity,detail,suggestion,"
            "confidence,frame_index\n",
            encoding="utf-8",
        )
        for _ in range(5):
            progress_callback(0.5)
        return FakeResult(alert_csv)


def make_workspace_directory():
    """在仓库内创建临时目录（不使用 tempfile 的 0700 目录，沙盒下会被拒绝访问）。"""
    base = PROJECT_ROOT / ".test-tmp"
    base.mkdir(exist_ok=True)
    directory = base / uuid.uuid4().hex
    directory.mkdir()
    return directory


def remove_workspace_directory(directory):
    shutil.rmtree(directory, ignore_errors=True)


class VideoJobLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = make_workspace_directory()

    def tearDown(self):
        remove_workspace_directory(self.directory)

    def test_recover_marks_queued_and_running_jobs_as_failed(self):
        repository = SQLiteRepository(self.directory / "app.db")
        repository.initialize()
        stamp = "2026-10-24T10:00:00+08:00"
        for job_id, status in (("q", "queued"), ("r", "running"), ("c", "completed")):
            repository.save_video_job(
                VideoJobRecord(
                    id=job_id,
                    source_path="input.mp4",
                    status=status,
                    progress=0.5 if status != "completed" else 1.0,
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
        service = VideoJobService(repository, None, self.directory / "results")

        recovered = service.recover_interrupted()

        self.assertEqual({"q", "r"}, set(recovered))
        self.assertEqual("failed", repository.get_video_job("q").status)
        self.assertEqual(INTERRUPTED_MESSAGE, repository.get_video_job("r").error)
        self.assertEqual("completed", repository.get_video_job("c").status)
        self.assertEqual([], service.recover_interrupted())

    def test_progress_writes_are_throttled(self):
        repository = RecordingRepository()
        service = VideoJobService(
            repository,
            FakeProcessor(),
            self.directory / "results",
            executor=ImmediateExecutor(),
        )

        service.create("input.mp4", 0.25, 0.45, 0, "bytetrack")

        running = [job for job in repository.saved if job.status == "running"]
        self.assertEqual(2, len(running))
        self.assertAlmostEqual(0.5, running[-1].progress, places=3)
        self.assertEqual("completed", repository.saved[-1].status)
        self.assertEqual(1.0, repository.saved[-1].progress)


if __name__ == "__main__":
    unittest.main()
