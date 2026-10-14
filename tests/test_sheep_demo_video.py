import csv

import cv2
import numpy as np
import pytest

from cattle_health_app.sheep_demo_video import render_sheep_demo_video


def test_demo_video_keeps_tracking_frames_and_adds_activity_panel(tmp_path):
    tracked = tmp_path / "tracked.mp4"
    writer = cv2.VideoWriter(str(tracked), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(11):
        writer.write(np.zeros((48, 64, 3), dtype="uint8"))
    writer.release()

    tracks = tmp_path / "tracks.csv"
    with tracks.open("w", newline="", encoding="utf-8") as stream:
        csv_writer = csv.DictWriter(stream, fieldnames=[
            "frame_index", "track_id", "class_id", "center_x", "center_y", "width", "height"
        ])
        csv_writer.writeheader()
        for frame in range(11):
            csv_writer.writerow({"frame_index": frame, "track_id": 7, "class_id": 0,
                                 "center_x": 10 + frame * 2, "center_y": 20,
                                 "width": 20, "height": 15})

    output = tmp_path / "demo.mp4"
    summary = render_sheep_demo_video(tracked, tracks, output, model_name="Test sheep model")

    capture = cv2.VideoCapture(str(output))
    assert capture.isOpened()
    assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) == 11
    assert int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) > 64
    ok, first = capture.read()
    assert ok and first[:, 64:].max() > 0
    assert first[:, :64].max() > 0  # The demo draws its own compact track box.
    capture.release()
    assert summary["frames"] == 11
    assert summary["tracked_ids"] == 1
    assert summary["movement_events"] >= 1
    assert summary["codec"] in {"h264", "mp4v"}

    with tracks.open("a", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow([11, 7, 0, 20, 20, 20, 15])
    with pytest.raises(ValueError, match="outside source video"):
        render_sheep_demo_video(tracked, tracks, tmp_path / "invalid.mp4")
