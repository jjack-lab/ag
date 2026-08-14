from cattle_health_app.behavior.cvb_labels import (
    CVB_LABELS,
    CVB_NAME_TO_ID,
    behavior_display,
    health_eligible,
)


def test_cvb_ids_match_official_pbtx_order():
    assert list(CVB_LABELS) == list(range(1, 13))
    expected = (
        (1, 'none'),
        (2, 'grazing'),
        (3, 'walking'),
        (4, 'ruminating-standing'),
        (5, 'ruminating-lying'),
        (6, 'resting-standing'),
        (7, 'resting-lying'),
        (8, 'drinking'),
        (9, 'grooming'),
        (10, 'other'),
        (11, 'hidden'),
        (12, 'running'),
    )

    assert [(label_id, label.name) for label_id, label in CVB_LABELS.items()] == list(expected)
    assert CVB_NAME_TO_ID == {name: label_id for label_id, name in expected}


def test_uncertain_labels_share_display_and_are_health_ineligible():
    for label_id in (1, 10, 11):
        assert behavior_display(label_id) == "无法确定"
        assert health_eligible(label_id) is False
    assert health_eligible(8) is True
