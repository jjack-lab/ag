from dataclasses import dataclass


@dataclass(frozen=True)
class BehaviorLabel:
    id: int
    name: str
    display_name: str
    uncertain: bool = False


_ROWS = (
    (1, "none", "无法确定", True),
    (2, "grazing", "采食", False),
    (3, "walking", "行走", False),
    (4, "ruminating-standing", "站立反刍", False),
    (5, "ruminating-lying", "卧姿反刍", False),
    (6, "resting-standing", "站立休息", False),
    (7, "resting-lying", "卧姿休息", False),
    (8, "drinking", "饮水", False),
    (9, "grooming", "梳理", False),
    (10, "other", "无法确定", True),
    (11, "hidden", "无法确定", True),
    (12, "running", "奔跑", False),
)

CVB_LABELS = {row[0]: BehaviorLabel(*row) for row in _ROWS}
CVB_NAME_TO_ID = {item.name: item.id for item in CVB_LABELS.values()}


def behavior_display(label_id: int) -> str:
    return CVB_LABELS[label_id].display_name


def health_eligible(label_id: int) -> bool:
    return not CVB_LABELS[label_id].uncertain
