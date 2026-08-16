from pathlib import Path

import pytest

import cattle_health_app.tracking_pipeline as pipeline
from delivery_tests.test_tracking_behavior_integration import Model, Writer, install_video_fakes


def test_writer_exception_releases_before_removing_partial_video(tmp_path, monkeypatch):
    holder = {}
    class FailingWriter(Writer):
        def __init__(self, path, *args):
            super().__init__(); self.path = Path(path); self.path.write_bytes(b"partial"); holder["writer"] = self
        def write(self, frame): raise RuntimeError("disk full")
    install_video_fakes(monkeypatch, FailingWriter)
    original_unlink = Path.unlink
    def windows_unlink(path, *args, **kwargs):
        if path.name.endswith("_tracked.mp4") and not holder["writer"].released:
            raise PermissionError("file is still open")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", windows_unlink)
    with pytest.raises(RuntimeError, match="disk full"):
        pipeline.process_tracked_video(Model(), tmp_path / "in.mp4", tmp_path / "out", .2, .5)
    assert holder["writer"].released
    assert not (tmp_path / "out" / "in_tracked.mp4").exists()
