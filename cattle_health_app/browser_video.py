"""Convert derived MP4 files to H.264 for browser playback when FFmpeg exists."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


LOGGER = logging.getLogger(__name__)


def ffmpeg_binary() -> Path | None:
    installed = shutil.which("ffmpeg")
    if installed:
        return Path(installed)
    bundled = Path(sys.executable).parent / "Library" / "bin" / "ffmpeg.exe"
    return bundled if bundled.is_file() else None


def ensure_browser_playable(video_path: Path) -> bool:
    """Atomically replace an OpenCV mp4v result with H.264, preserving it on failure."""
    video_path = Path(video_path)
    encoder = ffmpeg_binary()
    if encoder is None or not video_path.is_file():
        LOGGER.warning("Browser video conversion skipped: FFmpeg or video missing: %s", video_path)
        return False

    with tempfile.NamedTemporaryFile(dir=video_path.parent, suffix=".mp4", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        result = subprocess.run(
            [str(encoder), "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(video_path), "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             str(temporary)],
            capture_output=True, text=True, timeout=300, check=False,
        )
        if result.returncode != 0 or temporary.stat().st_size == 0:
            LOGGER.warning("Browser video conversion failed for %s: %s", video_path, result.stderr)
            return False
        os.replace(temporary, video_path)
        return True
    except (OSError, subprocess.TimeoutExpired) as error:
        LOGGER.warning("Browser video conversion failed for %s: %s", video_path, error)
        return False
    finally:
        temporary.unlink(missing_ok=True)
