"""Create deterministic contact sheets for manual CBVD-5 manifest auditing."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from cattle_health_app.behavior.external_video_dataset import (
    decode_virtual_clip,
    load_external_samples,
)


def _thumbnail(image, width=220, height=170):
    scale = min(width / image.shape[1], (height - 28) / image.shape[0])
    resized = cv2.resize(
        image,
        (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale))),
        interpolation=cv2.INTER_AREA,
    )
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    left = (width - resized.shape[1]) // 2
    top = 28 + (height - 28 - resized.shape[0]) // 2
    canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    return canvas


def write_jpeg(path: Path, image: np.ndarray, quality: int = 92) -> None:
    """Encode in memory so Windows Unicode paths never reach OpenCV file I/O."""

    ok, encoded = cv2.imencode(
        ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality]
    )
    if not ok:
        raise RuntimeError("could not encode audit sheet")
    Path(path).write_bytes(encoded.tobytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--per-class", type=int, default=10)
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    samples = load_external_samples(args.manifest, root)
    grouped = {}
    for sample in samples:
        grouped.setdefault(sample.mapped_label, []).append(sample)
    audit_rows = []
    for label in sorted(grouped):
        selected = sorted(grouped[label], key=lambda row: row.sample_id)[: args.per_class]
        tiles = []
        for sample in selected:
            decoded = decode_virtual_clip(sample, root)
            tile = _thumbnail(decoded.frames[len(decoded.frames) // 2])
            cv2.putText(
                tile,
                "video={} t={:.1f}s".format(sample.source_video_id, sample.start_second),
                (5, 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            tiles.append(tile)
            audit_rows.append(
                {
                    "sample_id": sample.sample_id,
                    "mapping_tier": sample.mapping_tier,
                    "mapped_label": label,
                    "source_video_id": sample.source_video_id,
                    "start_second": sample.start_second,
                    "crop_box": list(sample.crop_box),
                    "manual_status": "pending",
                    "manual_note": "",
                }
            )
        while len(tiles) % 5:
            tiles.append(np.zeros_like(tiles[0]))
        sheet = np.concatenate(
            [np.concatenate(tiles[index : index + 5], axis=1) for index in range(0, len(tiles), 5)],
            axis=0,
        )
        destination = output / "{}_{}.jpg".format(samples[0].mapping_tier, label)
        write_jpeg(destination, sheet)
    (output / "audit_rows.json").write_text(
        json.dumps(audit_rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"classes": len(grouped), "samples": len(audit_rows), "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
