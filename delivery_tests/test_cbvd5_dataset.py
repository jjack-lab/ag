from pathlib import Path

import pytest

from cattle_health_app.behavior.cbvd5 import map_cbvd5_labels, parse_ava_annotations


@pytest.mark.parametrize(
    "source,expected",
    [
        (("foraging",), "grazing"),
        (("standing", "foraging"), "grazing"),
        (("drinking",), "drinking"),
        (("standing", "rumination"), "ruminating-standing"),
        (("lying", "rumination"), "ruminating-lying"),
    ],
)
def test_strict_mapping(source, expected):
    mapped = map_cbvd5_labels(source, tier="strict")
    assert mapped.name == expected
    assert mapped.mapping_tier == "strict"


def test_posture_only_is_extended_not_strict():
    assert map_cbvd5_labels(("standing",), tier="strict") is None
    mapped = map_cbvd5_labels(("standing",), tier="extended")
    assert mapped.name == "resting-standing"
    assert mapped.mapping_tier == "extended"


def test_conflicting_postures_are_not_mapped():
    assert map_cbvd5_labels(("standing", "lying"), tier="extended") is None


def test_parser_groups_atomic_labels_and_preserves_source_values(tmp_path):
    path = tmp_path / "ava.csv"
    path.write_text(
        "618,2,0.1,0.2,0.4,0.7,1,9\n"
        "618,2,0.1,0.2,0.4,0.7,5,9\n"
        "619,3,0.2,0.3,0.5,0.8,3,4\n",
        encoding="utf-8",
    )

    annotations, exclusions = parse_ava_annotations(path)

    assert exclusions == ()
    assert len(annotations) == 2
    assert annotations[0].video_id == "618"
    assert annotations[0].timestamp == 2.0
    assert annotations[0].bbox == (0.1, 0.2, 0.4, 0.7)
    assert annotations[0].source_labels == ("standing", "rumination")
    assert annotations[0].entity_id == "9"


def test_parser_records_bad_rows_and_conflicting_group(tmp_path):
    path = tmp_path / "ava.csv"
    path.write_text(
        "618,2,0.5,0.2,0.4,0.7,1,9\n"
        "619,3,0.2,0.3,0.5,0.8,1,4\n"
        "619,3,0.2,0.3,0.5,0.8,2,4\n",
        encoding="utf-8",
    )

    annotations, exclusions = parse_ava_annotations(path)

    assert annotations == ()
    assert [item.reason for item in exclusions] == [
        "invalid_bbox",
        "conflicting_posture_labels",
    ]


def test_parser_rejects_wrong_column_count_without_aborting_file(tmp_path):
    path = tmp_path / "ava.csv"
    path.write_text(
        "bad,row\n620,4,0.1,0.1,0.2,0.2,4,1\n", encoding="utf-8"
    )

    annotations, exclusions = parse_ava_annotations(path)

    assert len(annotations) == 1
    assert exclusions[0].line_number == 1
    assert exclusions[0].reason == "expected_8_columns"
