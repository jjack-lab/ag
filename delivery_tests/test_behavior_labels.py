import pytest

from cattle_health_app.behavior.labels import (
    TRAINABLE_LABELS,
    UnknownBehaviorLabel,
    canonical_label,
)


def test_canonical_label_accepts_only_reviewed_vocabulary():
    assert TRAINABLE_LABELS == ("feeding", "lying", "standing", "walking")
    assert canonical_label(" Feeding ") == "feeding"
    assert canonical_label("unknown") == "unknown"


def test_canonical_label_rejects_unreviewed_alias():
    with pytest.raises(UnknownBehaviorLabel, match="grazing"):
        canonical_label("grazing")
