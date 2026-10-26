"""Replay saved cattle trajectories at several still-speed thresholds.

No detector, tracker, model weights, or ground-truth labels are changed or read.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from health_monitor import CattleHealthMonitor, DetectionObservation, HealthConfig


def load_frames(path):
    frames = defaultdict(list)
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            frames[int(row["frame_index"])].append(
                DetectionObservation(
                    track_id=int(row["track_id"]),
                    class_id=int(row["class_id"]),
                    confidence=float(row["confidence"]),
                    xywh=tuple(float(row[key]) for key in ("center_x", "center_y", "width", "height")),
                )
            )
    return frames


def replay(frames, frame_count, fps, threshold):
    monitor = CattleHealthMonitor(HealthConfig(fps=fps, cattle_class_ids={1}, still_speed_px_s=threshold))
    for frame_index in range(frame_count):
        monitor.update(frame_index, frames.get(frame_index, ()))
    still = [alert for alert in monitor.alerts if alert.alert_type == "still"]
    return {"threshold_px_s": threshold, "still_alerts": len(still),
            "unique_tracks_alerted": len({alert.track_id for alert in still}),
            "all_rule_alerts": len(monitor.alerts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tracks_csv", type=Path)
    parser.add_argument("--fps", type=float, required=True)
    parser.add_argument("--frame-count", type=int, required=True)
    parser.add_argument("--thresholds", type=float, nargs="+", default=[0, 1, 2.5, 5, 7.5, 10, 20])
    parser.add_argument("--plot", type=Path, help="write a threshold vs. still-alert count PNG")
    args = parser.parse_args()
    frames = load_frames(args.tracks_csv)
    result = {"tracks_csv": str(args.tracks_csv), "fps": args.fps,
              "frame_count": args.frame_count,
              "unique_cattle_tracks": len({obs.track_id for rows in frames.values() for obs in rows if obs.class_id == 1}),
              "rows": [replay(frames, args.frame_count, args.fps, value) for value in args.thresholds]}
    if args.plot:
        import matplotlib.pyplot as plt

        figure, axes = plt.subplots(figsize=(7, 4))
        axes.plot([row["threshold_px_s"] for row in result["rows"]],
                  [row["still_alerts"] for row in result["rows"]], marker="o")
        axes.axvline(5, color="gray", linestyle="--", label="current 5.0 px/s")
        axes.set(xlabel="Still-speed threshold (px/s)", ylabel="Still alerts (count)",
                 title="One development clip: threshold sensitivity")
        axes.set_ylim(bottom=0)
        axes.grid(alpha=0.25)
        axes.legend()
        figure.tight_layout()
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(str(args.plot), dpi=160)
        plt.close(figure)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
