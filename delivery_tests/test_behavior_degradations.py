import numpy as np
import pytest

from cattle_health_app.behavior.degradations import (
    DEGRADATION_NAMES,
    DegradationError,
    apply_degradation,
)
from cattle_health_app.behavior.quality import frame_quality


def _frames(count=8, size=48):
    yy, xx = np.indices((size, size))
    base = (((xx // 3) + (yy // 3)) % 2 * 255).astype(np.uint8)
    return [np.repeat(np.roll(base, index, axis=1)[:, :, None], 3, axis=2) for index in range(count)]


@pytest.mark.parametrize("name", DEGRADATION_NAMES)
def test_level_zero_is_an_identity_copy(name):
    source = _frames(4)

    output, record = apply_degradation(source, name=name, level=0, seed=20260823)

    assert len(output) == len(source)
    assert all(np.array_equal(left, right) for left, right in zip(output, source))
    assert all(left is not right for left, right in zip(output, source))
    assert record.level == 0
    assert record.input_frame_count == record.output_frame_count == len(source)


@pytest.mark.parametrize("name", ["occlusion", "frame_drop"])
def test_seeded_stochastic_degradations_are_reproducible(name):
    source = _frames()

    first, first_record = apply_degradation(source, name=name, level=2, seed=17)
    second, second_record = apply_degradation(source, name=name, level=2, seed=17)

    assert all(np.array_equal(left, right) for left, right in zip(first, second))
    assert first_record == second_record


def test_increasing_blur_never_increases_laplacian_variance():
    source = _frames(1)
    scores = []
    for level in range(4):
        output, _ = apply_degradation(source, name="blur", level=level, seed=1)
        scores.append(frame_quality(output[0]).laplacian_variance)

    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("name", DEGRADATION_NAMES)
def test_degradation_contract_preserves_model_input_shape_and_count(name):
    source = _frames(7, 40)

    output, record = apply_degradation(source, name=name, level=3, seed=123)

    assert len(output) == len(source)
    assert [frame.shape for frame in output] == [frame.shape for frame in source]
    assert [frame.dtype for frame in output] == [frame.dtype for frame in source]
    assert record.preserves_shape is True
    assert record.input_frame_count == record.output_frame_count == 7
    assert record.to_dict()["name"] == name


def test_degradations_do_not_modify_input_arrays():
    source = _frames()
    originals = [frame.copy() for frame in source]

    for name in DEGRADATION_NAMES:
        apply_degradation(source, name=name, level=3, seed=99)

    assert all(np.array_equal(left, right) for left, right in zip(source, originals))


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"name": "invented", "level": 1, "seed": 1}, "name"),
        ({"name": "blur", "level": 4, "seed": 1}, "level"),
        ({"name": "blur", "level": 1, "seed": True}, "seed"),
    ],
)
def test_invalid_degradation_contract_is_rejected(kwargs, match):
    with pytest.raises(DegradationError, match=match):
        apply_degradation(_frames(2), **kwargs)
