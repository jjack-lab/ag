"""Tests for LVIS-style repeat-factor sampling of the WAID4500 train split."""

import math
from pathlib import Path

import pytest

from cattle_health_app.detection.waid_repeat_factors import (
    apportion_copies,
    class_image_counts,
    repeat_factors,
    write_repeat_list,
)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _dataset(root, labels):
    """labels: {name: "class lines"} for images/<name>.jpg + labels/<name>.txt."""

    for name, content in labels.items():
        (root / "images" / "train").mkdir(parents=True, exist_ok=True)
        (root / "images" / "train" / "{}.jpg".format(name)).write_bytes(b"img-" + name.encode())
        _write(root / "labels" / "train" / "{}.txt".format(name), content)
    return root


def test_counts_images_per_class(tmp_path):
    dataset = _dataset(
        tmp_path / "waid4500_v1",
        {
            "a": "0 0.5 0.5 0.2 0.2\n",
            "b": "0 0.5 0.5 0.2 0.2\n1 0.4 0.4 0.1 0.1\n",
            "c": "1 0.5 0.5 0.2 0.2\n",
        },
    )

    counts = class_image_counts(dataset, "train")

    assert counts == {0: 2, 1: 2}


def test_counts_an_image_once_per_class(tmp_path):
    dataset = _dataset(
        tmp_path / "waid4500_v1",
        {"a": "2 0.5 0.5 0.2 0.2\n2 0.1 0.1 0.1 0.1\n"},
    )

    assert class_image_counts(dataset, "train") == {2: 1}


def test_repeat_factors_use_the_square_root_of_the_head_ratio(tmp_path):
    factors = repeat_factors({0: 1041, 3: 592, 5: 289})

    assert factors[0] == pytest.approx(1.0)
    assert factors[3] == pytest.approx(math.sqrt(1041 / 592))
    assert factors[5] == pytest.approx(math.sqrt(1041 / 289))
    assert factors[5] > factors[3] > factors[0]


def test_repeat_factors_reject_empty_or_non_positive_counts():
    with pytest.raises(ValueError):
        repeat_factors({})
    with pytest.raises(ValueError):
        repeat_factors({0: 0})


def test_apportion_copies_hits_the_requested_total_without_dropping_images():
    copies = apportion_copies([1.9, 1.9, 1.0], total=5)

    assert sum(copies) == 5
    assert all(value >= 1 for value in copies)
    assert copies[0] >= 1 and copies[1] >= 1


def test_apportion_copies_is_deterministic():
    weights = [1.9, 1.45, 1.33, 1.0, 1.0]

    assert apportion_copies(weights, total=7) == apportion_copies(weights, total=7)


def test_write_repeat_list_repeats_rare_class_images_more_often(tmp_path):
    dataset = _dataset(
        tmp_path / "waid4500_v1",
        {
            "common-1": "0 0.5 0.5 0.2 0.2\n",
            "common-2": "0 0.5 0.5 0.2 0.2\n",
            "common-3": "0 0.5 0.5 0.2 0.2\n",
            "rare-1": "5 0.5 0.5 0.2 0.2\n",
        },
    )
    destination = tmp_path / "train_rf.txt"

    written = write_repeat_list(dataset, "train", destination)

    lines = [line for line in written.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) > 4
    assert sum(1 for line in lines if "rare-1" in line) > sum(
        1 for line in lines if "common-1" in line
    )
    # Ultralytics resolves list entries against the training process CWD, so the
    # list must carry absolute paths to be usable from any working directory.
    assert all(Path(line).is_absolute() for line in lines)
    assert all(Path(line).is_file() for line in set(lines))
    assert sorted(Path(line).name for line in set(lines)) == [
        "common-1.jpg",
        "common-2.jpg",
        "common-3.jpg",
        "rare-1.jpg",
    ]


def test_write_repeat_list_is_deterministic(tmp_path):
    dataset = _dataset(
        tmp_path / "waid4500_v1",
        {"a": "0 0.5 0.5 0.2 0.2\n", "b": "5 0.5 0.5 0.2 0.2\n"},
    )

    first = write_repeat_list(dataset, "train", tmp_path / "one.txt").read_bytes()
    second = write_repeat_list(dataset, "train", tmp_path / "two.txt").read_bytes()

    assert first == second


def test_write_repeat_list_uses_the_maximum_factor_for_multiclass_images(tmp_path):
    dataset = _dataset(
        tmp_path / "waid4500_v1",
        {
            "both": "0 0.5 0.5 0.2 0.2\n5 0.4 0.4 0.1 0.1\n",
            "common-a": "0 0.5 0.5 0.2 0.2\n",
            "common-b": "0 0.5 0.5 0.2 0.2\n",
            "common-c": "0 0.5 0.5 0.2 0.2\n",
            "rare": "5 0.5 0.5 0.2 0.2\n",
        },
    )

    lines = [
        line
        for line in write_repeat_list(dataset, "train", tmp_path / "rf.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]

    # class 5 is the rare class; an image holding both classes takes its factor
    assert sum(1 for line in lines if "both" in line) >= 2
    assert sum(1 for line in lines if "common-a" in line) == 1


def test_write_repeat_list_rejects_a_missing_split(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_repeat_list(tmp_path / "absent", "train", tmp_path / "rf.txt")
