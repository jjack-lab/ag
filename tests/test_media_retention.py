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

    def test_collects_only_old_unreferenced_files(self):
        media_root = self.directory / "media"
        kept_upload = self._write(media_root / "uploads" / "keep.mp4", age_days=40)
        kept_result = self._write(
            media_root / "results" / "job1" / "out.mp4", age_days=40
        )
        old_upload_orphan = self._write(
            media_root / "uploads" / "orphan.mp4", age_days=40
        )
        old_result_orphan = self._write(
            media_root / "results" / "orphan2" / "clip.mp4", age_days=40
        )
        fresh_orphan = self._write(media_root / "uploads" / "fresh.mp4", age_days=0.1)
        jobs = [
            SimpleNamespace(
                source_path=str(kept_upload),
                result={"video_path": "job1/out.mp4"},
            )
        ]

        plan = collect_orphans(media_root, jobs, older_than_days=14)

        names = {path.name for path in plan["files"]}
        self.assertEqual({"orphan.mp4", "clip.mp4"}, names)
        self.assertEqual(32, plan["total_bytes"])
        self.assertTrue(kept_result.exists())
        self.assertTrue(fresh_orphan.exists())

        result = prune(plan["files"])
        self.assertEqual(2, result["deleted"])
        self.assertFalse(old_upload_orphan.exists())
        self.assertFalse(old_result_orphan.exists())
        self.assertTrue(kept_upload.exists())
        self.assertTrue(kept_result.exists())
        self.assertTrue(fresh_orphan.exists())

    def test_missing_media_root_returns_empty_plan(self):
        plan = collect_orphans(self.directory / "missing", [])
        self.assertEqual([], plan["files"])
        self.assertEqual(0, plan["count"])


if __name__ == "__main__":
    unittest.main()
