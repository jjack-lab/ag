import pytest

from cattle_health_app.behavior.cvb_labels import (
    CVB_LABELS,
    CVB_NAME_TO_ID,
    behavior_display,
    health_eligible,
)


def test_cvb_ids_match_official_pbtx_order():
    expected = (
        (1, 'none', '无法确定', True),
        (2, 'grazing', '采食', False),
        (3, 'walking', '行走', False),
        (4, 'ruminating-standing', '站立反刍', False),
        (5, 'ruminating-lying', '卧姿反刍', False),
        (6, 'resting-standing', '站立休息', False),
        (7, 'resting-lying', '卧姿休息', False),
        (8, 'drinking', '饮水', False),
        (9, 'grooming', '梳理', False),
        (10, 'other', '无法确定', True),
        (11, 'hidden', '无法确定', True),
        (12, 'running', '奔跑', False),
    )

    assert [
        (label_id, label.name, label.display_name, label.uncertain)
        for label_id, label in CVB_LABELS.items()
    ] == list(expected)
    assert CVB_NAME_TO_ID == {name: label_id for label_id, name, _, _ in expected}

    for label_id, _, display_name, uncertain in expected:
        assert behavior_display(label_id) == display_name
        assert health_eligible(label_id) is (not uncertain)


def test_uncertain_labels_share_display_and_are_health_ineligible():
    for label_id in (1, 10, 11):
        assert behavior_display(label_id) == "无法确定"
        assert health_eligible(label_id) is False
    assert health_eligible(8) is True


def test_public_label_mappings_are_read_only():
    with pytest.raises(TypeError):
        CVB_LABELS[13] = CVB_LABELS[12]
    with pytest.raises(TypeError):
        del CVB_LABELS[1]
    with pytest.raises(TypeError):
        CVB_NAME_TO_ID['running'] = 1
    with pytest.raises(TypeError):
        del CVB_NAME_TO_ID['running']
