"""Convert AUTH-Sheep COCO HBB and CVAT track IDs to delivery GT CSV."""

import argparse
import csv
import json
import math
from decimal import Decimal
from pathlib import Path


FIELDS = ("frame_index", "class_id", "track_id", "x", "y", "width", "height")


def _load(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite box coordinate")
    return result


def _fraction(value):
    return format(value, ".15g")


def _normalized_axis(start, end, extent):
    normalized_start = _fraction(start / extent)
    normalized_size = _fraction((end - start) / extent)
    while float(normalized_start) + float(normalized_size) > 1.0:
        normalized_size = str(Decimal(normalized_size) - Decimal("0.000000000000001"))
    return normalized_start, normalized_size


def convert_annotations(hbb_path, cvat_path, output_path):
    hbb = _load(hbb_path)
    cvat = _load(cvat_path)
    images = {int(image["id"]): image for image in hbb["images"]}
    if len(images) != len(hbb["images"]):
        raise ValueError("duplicate image ID")
    tracks = {int(item["id"]): item for item in cvat["annotations"]}
    if len(tracks) != len(cvat["annotations"]):
        raise ValueError("duplicate annotation ID")
    if set(tracks) != {int(item["id"]) for item in hbb["annotations"]}:
        raise ValueError("HBB/CVAT annotation ID mismatch")

    rows = []
    human_count = clipped_count = 0
    seen = set()
    for box in hbb["annotations"]:
        item = tracks[int(box["id"])]
        if (int(box["image_id"]), int(box["category_id"])) != (
            int(item["image_id"]), int(item["category_id"])
        ):
            raise ValueError("HBB/CVAT annotation mismatch")
        if int(box["category_id"]) == 2:
            human_count += 1
            continue
        if int(box["category_id"]) != 1:
            raise ValueError("unexpected AUTH-Sheep category")
        image_id = int(box["image_id"])
        if image_id not in images:
            raise ValueError("annotation references unknown image")
        image = images[image_id]
        frame = image_id - 1
        width, height = int(image["width"]), int(image["height"])
        if frame < 0 or width <= 0 or height <= 0:
            raise ValueError("invalid image metadata")
        track = int(item["attributes"]["track_id"])
        if track < 0 or (frame, track) in seen:
            raise ValueError("invalid or repeated sheep track ID in frame")
        seen.add((frame, track))
        x, y, box_width, box_height = map(_number, box["bbox"])
        if box_width <= 0 or box_height <= 0:
            raise ValueError("invalid HBB dimensions")
        x1, y1 = max(0.0, x), max(0.0, y)
        x2, y2 = min(float(width), x + box_width), min(float(height), y + box_height)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("sheep box is fully outside image")
        if x1 != x or y1 != y or x2 != x + box_width or y2 != y + box_height:
            clipped_count += 1
        normalized_x, normalized_width = _normalized_axis(x1, x2, width)
        normalized_y, normalized_height = _normalized_axis(y1, y2, height)
        rows.append({
            "frame_index": frame, "class_id": 0, "track_id": track,
            "x": normalized_x, "y": normalized_y,
            "width": normalized_width, "height": normalized_height,
        })

    rows.sort(key=lambda row: (row["frame_index"], row["track_id"]))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)
    return {
        "labeled_frames": len({row["frame_index"] for row in rows}),
        "sheep_boxes": len(rows),
        "human_boxes_skipped": human_count,
        "clipped_boxes": clipped_count,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hbb", type=Path, required=True)
    parser.add_argument("--cvat", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(convert_annotations(arguments.hbb, arguments.cvat, arguments.output)))


if __name__ == "__main__":
    main()
