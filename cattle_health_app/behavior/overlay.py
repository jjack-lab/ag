"""CJK-safe, batched behavior overlays for OpenCV frames."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # ASCII fallback remains available without Pillow.
    Image = None
    ImageDraw = None
    ImageFont = None


def discover_cjk_font():
    configured = os.environ.get("CATTLE_HEALTH_CJK_FONT")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates.extend(
        windows_fonts / name
        for name in (
            "msyh.ttc", "msyhl.ttc", "simhei.ttf", "simsun.ttc", "Deng.ttf"
        )
    )
    candidates.extend(
        Path(path)
        for path in (
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        )
    )
    if ImageFont is None:
        return None
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            ImageFont.truetype(str(candidate), 20)
        except (OSError, ValueError):
            continue
        return candidate
    return None


@lru_cache(maxsize=4)
def get_cjk_font(size=20):
    path = discover_cjk_font()
    if path is None or ImageFont is None:
        return None
    try:
        return ImageFont.truetype(str(path), size)
    except (OSError, ValueError):
        return None


def draw_statuses(frame, statuses, font_getter=get_cjk_font) -> None:
    """Draw all statuses using one frame conversion or stable ASCII fallback."""
    statuses = list(statuses)
    if not statuses:
        return
    font = font_getter()
    if font is not None and Image is not None and ImageDraw is not None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        drawer = ImageDraw.Draw(image)
        for anchor, chinese_text, _ in statuses:
            drawer.text(
                anchor,
                chinese_text,
                font=font,
                fill=(255, 255, 0),
                stroke_width=1,
                stroke_fill=(0, 0, 0),
            )
        frame[:] = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        return
    for anchor, _, fallback_text in statuses:
        cv2.putText(
            frame,
            fallback_text,
            anchor,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
