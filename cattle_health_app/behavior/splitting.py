from __future__ import annotations

from hashlib import sha256
from typing import Iterable, Iterator


def _ordered_groups(group_ids: Iterable[str], seed: int) -> list[str]:
    unique = set(group_ids)
    return sorted(
        unique,
        key=lambda group: sha256(
            f"{seed}:{group}".encode("utf-8")
        ).hexdigest(),
    )


def assign_group_splits(
    group_ids: Iterable[str],
    seed: int,
) -> dict[str, str]:
    ordered = _ordered_groups(group_ids, seed)
    count = len(ordered)
    if count == 0:
        return {}
    if count == 1:
        return {ordered[0]: "train"}
    if count == 2:
        return {ordered[0]: "train", ordered[1]: "test"}

    train_count = max(1, int(count * 0.70))
    val_count = max(1, int(count * 0.15))
    test_count = count - train_count - val_count
    if test_count < 1:
        train_count -= 1

    split = {}
    for index, group in enumerate(ordered):
        if index < train_count:
            split[group] = "train"
        elif index < train_count + val_count:
            split[group] = "val"
        else:
            split[group] = "test"
    return split


def stable_clip_id(
    segment_id: str,
    source_id: str,
    track_id: int,
    start_second: float,
    end_second: float,
    label: str,
    version: str = "behavior-v1",
) -> str:
    identity = "|".join(
        (
            version,
            segment_id,
            source_id,
            str(track_id),
            f"{start_second:.6f}",
            f"{end_second:.6f}",
            label,
        )
    )
    return sha256(identity.encode("utf-8")).hexdigest()[:20]


def iter_windows(
    start_second: float,
    end_second: float,
    length: float,
    stride: float,
) -> Iterator[tuple[float, float]]:
    if length <= 0 or stride <= 0:
        raise ValueError("Window length and stride must be positive")
    cursor = start_second
    while cursor + length <= end_second + 1e-9:
        yield (round(cursor, 6), round(cursor + length, 6))
        cursor += stride
