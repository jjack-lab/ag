import os
import shutil
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from cattle_health_app.media_retention import collect_orphans, prune

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_workspace_directory():
    """在仓库内创建临时目录（不使用 tempfile 的 0700 目录，沙盒下会被拒绝访问）。"""
    base = PROJECT_ROOT / ".test-tmp"
    base.mkdir(exist_ok=True)
    directory = base / uuid.uuid4().hex
    directory.mkdir()
    return directory


def remove_workspace_directory(directory):
    shutil.rmtree(directory, ignore_errors=True)


class MediaRetentionTests(unittest.TestCase):
    def setUp(self):
        self.directory = make_workspace_directory()

    def tearDown(self):
        remove_workspace_directory(self.directory)

    def _write(self, path, *, age_days):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 16)
        stamp = time.time() - age_days * 86400
        os.utime(path, (stamp, stamp))
        return path

    def _prepare(self):
        media_root = self.directory / "media"
        keep_upload = self._write(media_root / "uploads" / "keep.mp4", age_days=40)
        self._write(media_root / "uploads" / ".gitkeep", age_days=400)
        self._write(media_root / "uploads" / "orphan.mp4", age_days=40)
        self._write(media_root / "results" / ".gitkeep", age_days=400)
        self._write(media_root / "results" / "loose.jpg", age_days=40)
        kept_result = self._write(
            media_root / "results" / "job1" / "out.mp4", age_days=40
        )
        old_result_orphan = self._write(
            media_root / "results" / "orphan2" / "clip.mp4", age_days=40
        )
        self._write(media_root / "results" / "newdir" / "fresh.mp4", age_days=0.1)
        jobs = [
            SimpleNamespace(
                id="job1",
                source_path=str(keep_upload),
                result={"video_path": "job1/out.mp4"},
            )
        ]
        return media_root, jobs, kept_result, old_result_orphan

    def test_only_prunes_orphaned_job_directories(self):
        media_root, jobs, kept_result, old_result_orphan = self._prepare()

        plan = collect_orphans(media_root, jobs, older_than_days=14)

        names = {path.name for path in plan["files"]}
        self.assertEqual({"clip.mp4"}, names)
        self.assertEqual(16, plan["total_bytes"])

        result = prune(plan["files"])

        self.assertEqual(1, result["deleted"])
        self.assertFalse(old_result_orphan.exists())
        self.assertFalse(old_result_orphan.parent.exists())
        self.assertTrue(kept_result.exists())
        self.assertTrue((media_root / "uploads" / "orphan.mp4").exists())
        self.assertTrue((media_root / "results" / "loose.jpg").exists())
        self.assertTrue((media_root / "results" / ".gitkeep").exists())

    def test_uploads_are_opt_in(self):
        media_root, jobs, _, _ = self._prepare()

        plan = collect_orphans(
            media_root, jobs, older_than_days=14, include_uploads=True
        )

        names = {path.name for path in plan["files"]}
        self.assertEqual({"clip.mp4", "orphan.mp4"}, names)

    def test_missing_media_root_returns_empty_plan(self):
        plan = collect_orphans(self.directory / "missing", [])
        self.assertEqual([], plan["files"])
        self.assertEqual(0, plan["count"])


if __name__ == "__main__":
    unittest.main()
