from __future__ import annotations


TRAINABLE_LABELS = ("feeding", "lying", "standing", "walking")
ALLOWED_LABELS = frozenset((*TRAINABLE_LABELS, "unknown"))


class UnknownBehaviorLabel(ValueError):
    pass


def canonical_label(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in ALLOWED_LABELS:
        raise UnknownBehaviorLabel(f"Unsupported behavior label: {value!r}")
    return normalized
