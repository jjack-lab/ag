"""Conservative sheep movement summary from video-local tracking geometry.

These states describe visible displacement, not grazing, posture, illness, or
animal identity across videos. Thresholds are prototype heuristics.
"""

import math
from collections import defaultdict


def summarize_sheep_motion(rows, fps):
    if not math.isfinite(float(fps)) or fps <= 0:
        raise ValueError("fps must be positive")
    grouped = defaultdict(list)
    for row in rows:
        try:
            frame = int(row["frame_index"])
            track = int(row["track_id"])
            x, y, width = float(row["center_x"]), float(row["center_y"]), float(row["width"])
        except (KeyError, TypeError, ValueError):
            continue
        if frame < 0 or track < 0 or width <= 0 or not all(map(math.isfinite, (x, y, width))):
            continue
        grouped[track].append((frame, x, y, width))
    summaries, events = [], []
    labels = {"still": "低位移", "moving": "移动", "fast": "快速移动"}
    for track, positions in sorted(grouped.items()):
        positions.sort()
        totals = {"still": 0.0, "moving": 0.0, "fast": 0.0}
        previous_state = None
        left = positions[0]
        for right in positions[1:]:
            elapsed = (right[0] - left[0]) / fps
            if elapsed <= 0 or elapsed > 2:
                previous_state = None
                left = right
                continue
            if elapsed < .5:
                continue
            displacement = math.hypot(right[1] - left[1], right[2] - left[2])
            body_widths_per_second = displacement / ((left[3] + right[3]) / 2) / elapsed
            state = "still" if body_widths_per_second < .15 else "moving" if body_widths_per_second < 1.2 else "fast"
            totals[state] += elapsed
            if state != previous_state:
                events.append({"track_id": track, "time_seconds": round(right[0] / fps, 3),
                               "label": labels[state], "detail": "基于框中心位移的规则估计"})
            previous_state = state
            left = right
        observed = sum(totals.values())
        if observed:
            summaries.append({"track_id": track, "still_seconds": round(totals["still"], 3),
                              "moving_seconds": round(totals["moving"], 3),
                              "fast_seconds": round(totals["fast"], 3),
                              "observed_seconds": round(observed, 3)})
    events.sort(key=lambda row: (row["time_seconds"], row["track_id"]))
    return summaries, events
