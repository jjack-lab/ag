"""辅助分析固定机位视频中的区域活动与栏门穿线。"""

import csv
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def read_tracks(path: Path, width: int, height: int):
    tracks = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            tracks[int(row["track_id"])].append((
                int(row["frame_index"]), float(row["time_seconds"]),
                float(row["center_x"]) / width, float(row["center_y"]) / height,
            ))
    return {track_id: sorted(samples) for track_id, samples in tracks.items()}


def zone_activity(tracks, rectangle, fps, observed_at):
    x1, y1, x2, y2 = rectangle
    hourly = defaultdict(lambda: {"entries": 0, "dwell_seconds": 0.0})
    total_entries = 0
    total_frames = 0
    events = []
    started = datetime.fromisoformat(observed_at)
    for track_id, samples in tracks.items():
        inside_before = False
        current_event = None
        for _frame, seconds, x, y in samples:
            inside = x1 <= x <= x2 and y1 <= y <= y2
            hour = (started + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:00")
            if inside:
                total_frames += 1
                hourly[hour]["dwell_seconds"] += 1 / fps
                if not inside_before:
                    total_entries += 1
                    hourly[hour]["entries"] += 1
                    current_event = {"track_id": track_id, "time_seconds": round(seconds, 2),
                                     "dwell_seconds": 0.0}
                    events.append(current_event)
                current_event["dwell_seconds"] = round(current_event["dwell_seconds"] + 1 / fps, 2)
            inside_before = inside
    return {
        "entries": total_entries,
        "dwell_seconds": round(total_frames / fps, 2),
        "events": sorted(events, key=lambda event: event["time_seconds"]),
        "hourly": [{"hour": hour, "entries": row["entries"],
                    "dwell_seconds": round(row["dwell_seconds"], 2)}
                   for hour, row in sorted(hourly.items())],
    }


def line_crossings(tracks, line):
    x1, y1, x2, y2 = line
    entering = leaving = 0
    events = []
    for track_id, samples in tracks.items():
        for previous, current in zip(samples, samples[1:]):
            _old_frame, _old_time, old_x, old_y = previous
            _frame, seconds, x, y = current
            old_side = (x2 - x1) * (old_y - y1) - (y2 - y1) * (old_x - x1)
            side = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
            if old_side == 0 or side == 0 or old_side * side >= 0:
                continue
            ratio = old_side / (old_side - side)
            cross_x = old_x + ratio * (x - old_x)
            cross_y = old_y + ratio * (y - old_y)
            along = ((cross_x - x1) * (x2 - x1) + (cross_y - y1) * (y2 - y1)) / ((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if not 0 <= along <= 1:
                continue
            direction = "enter" if old_side > 0 else "leave"
            entering += direction == "enter"
            leaving += direction == "leave"
            events.append({"track_id": track_id, "time_seconds": round(seconds, 2),
                           "direction": direction})
    return {"enter": entering, "leave": leaving, "events": sorted(events, key=lambda event: event["time_seconds"])}


def zone_detection_gap(tracks, rectangle, duration_seconds, minimum_seconds=30):
    x1, y1, x2, y2 = rectangle
    seen = sorted(seconds for samples in tracks.values() for _frame, seconds, x, y in samples
                  if x1 <= x <= x2 and y1 <= y <= y2)
    for start, end in zip([0.0] + seen, seen + [duration_seconds]):
        if end - start >= minimum_seconds:
            return {"time_seconds": round(start + minimum_seconds, 2),
                    "label": "区域长时间无检测待核查",
                    "detail": f"画定区域连续约 {minimum_seconds} 秒无目标检测，请回看视频确认遮挡、空栏或漏检。"}
    return None


def count_drop_alert(tracks, frame_count, fps):
    if frame_count < 10 * fps:
        return None
    counts = [0] * frame_count
    for samples in tracks.values():
        for frame, _seconds, _x, _y in samples:
            if 0 <= frame < frame_count:
                counts[frame] += 1
    baseline = statistics.median(counts[:round(5 * fps)])
    if baseline < 4:
        return None
    low_frames = 0
    for frame, count in enumerate(counts[round(5 * fps):], start=round(5 * fps)):
        low_frames = low_frames + 1 if count <= baseline / 2 else 0
        if low_frames >= round(5 * fps):
            return {"time_seconds": round(frame / fps, 2),
                    "label": "画面检测数量下降待核查",
                    "detail": f"相对视频开头约 {baseline:g} 个目标，画面检测数持续下降；可能是出栏、遮挡或漏检。"}
    return None
