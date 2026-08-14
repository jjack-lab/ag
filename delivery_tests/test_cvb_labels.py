from cattle_health_app.behavior.cvb_labels import (
    CVB_LABELS,
    behavior_display,
    health_eligible,
)


def test_cvb_ids_match_official_pbtx_order():
    assert list(CVB_LABELS) == list(range(1, 13))
    assert CVB_LABELS[2].name == "grazing"
    assert CVB_LABELS[12].name == "running"


def test_uncertain_labels_share_display_and_are_health_ineligible():
    for label_id in (1, 10, 11):
        assert behavior_display(label_id) == "无法确定"
        assert health_eligible(label_id) is False
    assert health_eligible(8) is True
