from cattle_health_app.behavior.splitting import (
    assign_group_splits,
    iter_windows,
    stable_clip_id,
)


def test_group_split_is_deterministic_and_has_no_leakage():
    groups = [f"video-{index}" for index in range(20)]

    first = assign_group_splits(groups, seed=20260730)
    second = assign_group_splits(reversed(groups), seed=20260730)

    assert first == second
    assert set(first) == set(groups)
    assert set(first.values()) == {"train", "val", "test"}
    assert sum(value == "train" for value in first.values()) == 14
    assert sum(value == "val" for value in first.values()) == 3
    assert sum(value == "test" for value in first.values()) == 3


def test_three_groups_keep_each_split_represented():
    split = assign_group_splits(["a", "b", "c"], seed=7)
    assert sorted(split.values()) == ["test", "train", "val"]


def test_clip_identity_and_window_order_are_stable():
    clip_id = stable_clip_id(
        segment_id="segment-1",
        source_id="video-1",
        track_id=4,
        start_second=2.0,
        end_second=6.0,
        label="feeding",
    )

    assert clip_id == stable_clip_id(
        "segment-1", "video-1", 4, 2.0, 6.0, "feeding"
    )
    assert len(clip_id) == 20
    assert list(iter_windows(1.0, 10.0, length=4.0, stride=2.0)) == [
        (1.0, 5.0),
        (3.0, 7.0),
        (5.0, 9.0),
    ]
