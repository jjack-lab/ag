"""Render a readable sheep detection and tracking demo from video and trajectory CSV."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from cattle_health_app.behavior.overlay import draw_statuses
from cattle_health_app.sheep_motion import summarize_sheep_motion


PANEL_WIDTH = 520
REQUIRED_COLUMNS = {"frame_index", "track_id", "class_id", "center_x", "center_y", "width", "height"}
MOTION_LABELS = {"低位移": "Still", "移动": "Moving", "快速移动": "Fast"}
DISPLAY_LABELS = {"低位移": "低位移", "移动": "中位移", "快速移动": "高位移", "待累计": "待累计"}


def _read_tracks(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError("trajectory CSV is missing required columns")
        rows = list(reader)
    if any(int(row["class_id"]) != 0 for row in rows):
        raise ValueError("sheep demo only accepts sheep tracks (class_id=0)")
    return rows


def _draw_track_boxes(frame, rows):
    frame_height, frame_width = frame.shape[:2]
    for row in rows:
        track_id = int(row["track_id"])
        x, y, box_width, box_height = (float(row[key]) for key in ("center_x", "center_y", "width", "height"))
        left = max(0, min(frame_width - 1, round(x - box_width / 2)))
        top = max(0, min(frame_height - 1, round(y - box_height / 2)))
        right = max(0, min(frame_width - 1, round(x + box_width / 2)))
        bottom = max(0, min(frame_height - 1, round(y + box_height / 2)))
        if right <= left or bottom <= top:
            continue
        color = (70 + track_id * 31 % 160, 135 + track_id * 17 % 110, 75 + track_id * 53 % 150)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        text = "ID {}".format(track_id)
        text_width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.43, 1)[0][0]
        text_top = max(0, top - 18)
        cv2.rectangle(frame, (left, text_top), (min(frame_width - 1, left + text_width + 6), text_top + 17), color, -1)
        cv2.putText(frame, text, (left + 3, text_top + 13), cv2.FONT_HERSHEY_SIMPLEX,
                    0.43, (0, 0, 0), 1, cv2.LINE_AA)


def _panel(height, frame_index, total_frames, fps, active_rows, states, model_name):
    panel = np.empty((height, PANEL_WIDTH, 3), dtype=np.uint8)
    panel[:] = (32, 29, 22)
    cv2.rectangle(panel, (0, 0), (PANEL_WIDTH - 1, 8), (91, 202, 236), -1)
    active_ids = {int(row["track_id"]) for row in active_rows}
    confidence_by_track = {int(row["track_id"]): row.get("confidence") for row in active_rows}
    counts = {"低位移": 0, "移动": 0, "快速移动": 0, "待累计": 0}
    for track_id in active_ids:
        counts[states.get(track_id, "待累计")] += 1
    lines = [
        (52, "星牧智控 | 羊只识别演示", "Sheep recognition demo"),
        (100, "模型：{}".format(model_name), "Model: {}".format(model_name)),
        (155, "时间 {:.1f} 秒 | 第 {}/{} 帧".format(frame_index / fps, frame_index + 1, total_frames),
         "Time {:.1f}s | Frame {}/{}".format(frame_index / fps, frame_index + 1, total_frames)),
        (200, "本帧检测 {} 只 | 活跃 ID {} 个".format(len(active_rows), len(active_ids)),
         "Detected {} | Active IDs {}".format(len(active_rows), len(active_ids))),
        (265, "画面位移（未做镜头补偿）", "Screen displacement (no camera compensation)"),
        (308, "低 {} | 中 {} | 高 {}".format(counts["低位移"], counts["移动"], counts["快速移动"]),
         "Low {} | Medium {} | High {}".format(counts["低位移"], counts["移动"], counts["快速移动"])),
        (348, "待累计 {} 个".format(counts["待累计"]), "Pending {}".format(counts["待累计"])),
        (418, "视频中可见的功能", "Visible functions"),
        (458, "1. 羊只检测框与置信度", "1. Sheep boxes and confidence"),
        (496, "2. 视频内 Track ID", "2. Video-local track IDs"),
        (534, "3. 实时数量与画面位移", "3. Counts and screen displacement"),
        (628, "位移不等于采食/卧姿/疾病", "Displacement is not behavior/diagnosis"),
        (668, "公开无人机视频；非牧场验收", "Public drone video; not ranch validation"),
        (740, "本帧 ID 状态（前 7 个）", "Track states (first 7)"),
    ]
    for offset, track_id in enumerate(sorted(active_ids)[:7]):
        label = states.get(track_id, "待累计")
        confidence = confidence_by_track.get(track_id)
        confidence_text = " {:.0f}%".format(float(confidence) * 100) if confidence else ""
        lines.append((780 + offset * 36,
                      "ID {}{}：{}".format(track_id, confidence_text, DISPLAY_LABELS[label]),
                      "ID {}{}: {}".format(track_id, confidence_text, MOTION_LABELS.get(label, "Pending"))))
    draw_statuses(panel, [((22, y), chinese, english) for y, chinese, english in lines if y < height])
    return panel


def render_sheep_demo_video(source_video, trajectory_csv, output_video, model_name="Sheep detector"):
    """Render model boxes/IDs alongside counts and camera-relative displacement."""
    source_video = Path(source_video)
    output_video = Path(output_video)
    if source_video.absolute() == output_video.absolute():
        raise ValueError("output video must differ from source video")
    rows = _read_tracks(trajectory_csv)
    grouped = defaultdict(list)
    for row in rows:
        grouped[int(row["frame_index"])].append(row)
    capture = cv2.VideoCapture(str(source_video))
    if not capture.isOpened():
        raise ValueError("unable to open source video")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or width <= 0 or height <= 0 or total_frames <= 0:
        capture.release()
        raise ValueError("invalid source video metadata")
    if any(frame < 0 or frame >= total_frames for frame in grouped):
        capture.release()
        raise ValueError("trajectory frame is outside source video")
    _, events = summarize_sheep_motion(rows, fps)
    output_video.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_video), cv2.CAP_MSMF,
                             cv2.VideoWriter_fourcc(*"avc1"), fps, (width + PANEL_WIDTH, height))
    codec = "h264"
    if not writer.isOpened():
        writer.release()
        writer = cv2.VideoWriter(str(output_video), cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps, (width + PANEL_WIDTH, height))
        codec = "mp4v"
    if not writer.isOpened():
        capture.release()
        writer.release()
        raise ValueError("unable to create demo video")
    state_by_track = {}
    last_seen = {}
    event_index = 0
    frame_index = 0
    failed = False
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            active_rows = grouped.get(frame_index, [])
            active_ids = {int(row["track_id"]) for row in active_rows}
            for track_id in active_ids:
                if frame_index - last_seen.get(track_id, frame_index) > 2 * fps:
                    state_by_track.pop(track_id, None)
                last_seen[track_id] = frame_index
            while event_index < len(events) and events[event_index]["time_seconds"] <= frame_index / fps + 0.001:
                event = events[event_index]
                state_by_track[event["track_id"]] = event["label"]
                event_index += 1
            _draw_track_boxes(frame, active_rows)
            panel = _panel(height, frame_index, total_frames, fps, active_rows, state_by_track, model_name)
            writer.write(np.concatenate((frame, panel), axis=1))
            frame_index += 1
        if frame_index != total_frames:
            raise ValueError("source video ended before metadata frame count")
    except BaseException:
        failed = True
        raise
    finally:
        capture.release()
        writer.release()
        if failed:
            output_video.unlink(missing_ok=True)
    return {"frames": frame_index, "tracked_ids": len({int(row["track_id"]) for row in rows}),
            "detection_rows": len(rows), "movement_events": len(events),
            "codec": codec, "video_path": str(output_video)}


def main():
    parser = argparse.ArgumentParser(description="Render sheep tracking evidence video")
    parser.add_argument("--source-video", type=Path, required=True)
    parser.add_argument("--tracks-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-name", default="Sheep detector")
    args = parser.parse_args()
    print(json.dumps(render_sheep_demo_video(args.source_video, args.tracks_csv,
                                             args.output, args.model_name), ensure_ascii=False))


if __name__ == "__main__":
    main()
