"""Timestamped evidence from a completed video job and short review clips."""

import csv
import math
import os
from pathlib import Path
from uuid import uuid4

import cv2


def result_file(result_root, job_id, relative_name):
    if not relative_name:
        return None
    root = Path(result_root).resolve()
    job_root = (root / job_id).resolve()
    path = (root / relative_name).resolve()
    try:
        job_root.relative_to(root)
        path.relative_to(job_root)
    except ValueError as error:
        raise ValueError("Result path escapes this video job") from error
    return path


def video_events(result, reviews, result_root, job_id, corrections=()):
    events = []
    for profile in result.get("health_evidence") or []:
        for observation in profile.get("observations") or []:
            second = observation.get("time_seconds")
            if second is None or not math.isfinite(float(second)) or float(second) < 0:
                continue  # A whole-video observation has no honest seek point.
            events.append({"kind": "alert", "time_seconds": float(second),
                           "track_id": profile.get("track_id"),
                           "label": observation.get("label") or observation.get("type") or "规则提示",
                           "detail": observation.get("detail") or ""})
    behavior_path = result_file(result_root, job_id, result.get("behavior_csv"))
    if behavior_path and behavior_path.is_file():
        previous = {}
        with behavior_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                try:
                    second, track_id = float(row["time_seconds"]), int(row["track_id"])
                except (KeyError, ValueError, TypeError):
                    continue
                if not math.isfinite(second) or second < 0:
                    continue
                label = row.get("label") or "unknown"
                if previous.get(track_id) == label:
                    continue
                previous[track_id] = label
                events.append({"kind": "behavior", "time_seconds": second,
                               "track_id": track_id,
                               "label": row.get("display_name") or label,
                               "detail": "行为片段开始（模型输出，需人工复核）"})
    for review in reviews:
        second = review.get("time_seconds")
        if second is None or not math.isfinite(float(second)) or float(second) < 0:
            continue
        events.append({"kind": "review", "time_seconds": float(second),
                       "track_id": review.get("track_id"),
                       "label": "人工复核", "detail": review.get("note") or ""})
    for correction in corrections:
        events.append({"kind": "correction", "time_seconds": float(correction["time_seconds"]),
                       "track_id": correction.get("track_id"), "label": "画面纠错",
                       "detail": correction.get("note") or ""})
    for movement in result.get("sheep_motion_events") or []:
        events.append({"kind": "movement", "time_seconds": movement["time_seconds"],
                       "track_id": movement["track_id"], "label": movement["label"],
                       "detail": movement["detail"]})
    events.sort(key=lambda item: (item["time_seconds"], item["kind"], item["track_id"] or -1))
    return [{**item, "id": index} for index, item in enumerate(events)]


def create_event_clip(result_root, job_id, result, event):
    source = result_file(result_root, job_id, result.get("video_path"))
    if source is None or not source.is_file():
        raise FileNotFoundError("Result video is unavailable")
    clip_dir = Path(result_root) / job_id / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    destination = clip_dir / f"event_{event['id']}.mp4"
    if destination.is_file() and destination.stat().st_size > 0:
        return destination
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError("Result video cannot be decoded")
    temporary = clip_dir / f".{uuid4().hex}.mp4"
    writer = None
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Result video frame rate is invalid")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if width <= 0 or height <= 0 or frame_count <= 0:
            raise ValueError("Result video metadata is invalid")
        center = min(int(event["time_seconds"] * fps), frame_count - 1)
        start = max(0, center - round(3 * fps))
        end = min(frame_count, center + round(3 * fps) + 1)
        capture.set(cv2.CAP_PROP_POS_FRAMES, start)
        writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise ValueError("Cannot encode evidence clip")
        written = 0
        for _ in range(start, end):
            ok, frame = capture.read()
            if not ok:
                break
            writer.write(frame)
            written += 1
        if written == 0:
            raise ValueError("Evidence clip contains no decodable frames")
        writer.release()
        writer = None
        os.replace(temporary, destination)
        return destination
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        temporary.unlink(missing_ok=True)
