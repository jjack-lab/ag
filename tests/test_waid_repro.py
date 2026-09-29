import csv
import tempfile
import unittest
from pathlib import Path

from cattle_health_app.detection.waid_repro import (
    CLASS_NAMES,
    MANIFEST_FIELDS,
    ManifestError,
    load_manifest,
    parse_label,
    split_counts,
)


class WaidManifestTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write_manifest(self, rows, fields=MANIFEST_FIELDS):
        path = self.root / "manifest.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(
                {key: value for key, value in row.items() if key in fields}
                for row in rows
            )
        return path

    @staticmethod
    def row(**overrides):
        values = {
            "split": "train",
            "output_image": "images/train/cattle.jpg",
            "output_label": "labels/train/cattle.txt",
            "source_image": r"E:\dataset\images\train\cattle.jpg",
            "source_label": r"E:\dataset\labels\train\cattle.txt",
            "source_split": "train",
            "class_id": "1",
            "class_name": "cattle",
            "instances": "2",
            "group_id": "cattle-group",
        }
        values.update(overrides)
        return values

    def assert_manifest_error(self, row=None, fields=MANIFEST_FIELDS):
        manifest = self.write_manifest([] if row is None else [row], fields=fields)
        with self.assertRaises(ManifestError):
            load_manifest(manifest)

    def test_load_manifest_preserves_rows_and_normalizes_source_names(self):
        second = self.row(
            split="test",
            output_image="images/test/sheep.jpg",
            output_label="labels/test/sheep.txt",
            source_image=r"E:\dataset\images\test\sheep.jpg",
            source_label=r"E:\dataset\labels\test\sheep.txt",
            source_split="test",
            class_id="0",
            class_name="sheep",
            instances="1",
            group_id="sheep-group",
        )
        rows = load_manifest(self.write_manifest([self.row(), second]))

        self.assertEqual(2, len(rows))
        self.assertEqual("images/train/cattle.jpg", rows[0].output_image.as_posix())
        self.assertEqual("cattle.jpg", rows[0].source_image_name)
        self.assertEqual("cattle.txt", rows[0].source_label_name)
        self.assertEqual({"train": 1, "valid": 0, "test": 1}, split_counts(rows))
        self.assertEqual("test", rows[1].split)

    def test_class_contract_is_frozen(self):
        self.assertEqual(
            {
                0: "sheep",
                1: "cattle",
                2: "seal",
                3: "camelus",
                4: "kiang",
                5: "zebra",
            },
            CLASS_NAMES,
        )

    def test_rejects_empty_manifest(self):
        self.assert_manifest_error()

    def test_rejects_changed_schema(self):
        self.assert_manifest_error(self.row(), fields=MANIFEST_FIELDS[:-1])

    def test_rejects_duplicate_output_path(self):
        manifest = self.write_manifest([self.row(), self.row(group_id="other")])
        with self.assertRaisesRegex(ManifestError, "duplicate output"):
            load_manifest(manifest)

    def test_rejects_unsafe_or_inconsistent_paths(self):
        invalid_rows = (
            self.row(output_image="../escape.jpg"),
            self.row(output_image="C:/absolute.jpg"),
            self.row(output_image="images/test/cattle.jpg"),
            self.row(output_label="labels/test/cattle.txt"),
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                self.assert_manifest_error(row)

    def test_rejects_invalid_split_and_source_split(self):
        for row in (self.row(split="dev"), self.row(source_split="dev")):
            with self.subTest(row=row):
                self.assert_manifest_error(row)

    def test_rejects_invalid_class_and_instance_metadata(self):
        invalid_rows = (
            self.row(class_id="6", class_name="cattle"),
            self.row(class_id="1", class_name="sheep"),
            self.row(class_id="one"),
            self.row(instances="0"),
            self.row(instances="many"),
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                self.assert_manifest_error(row)


class WaidLabelTest(unittest.TestCase):
    def test_parses_valid_single_class_label(self):
        self.assertEqual(
            (1, 2),
            parse_label(b"1 0.5 0.5 0.2 0.2\n1 0.4 0.4 0.1 0.1\n"),
        )

    def test_rejects_invalid_labels(self):
        invalid = (
            b"",
            b"1 0.5 0.5 0.2\n",
            b"one 0.5 0.5 0.2 0.2\n",
            b"1.5 0.5 0.5 0.2 0.2\n",
            b"6 0.5 0.5 0.2 0.2\n",
            b"1 1.1 0.5 0.2 0.2\n",
            b"1 0.5 0.5 0.2 0.2\n2 0.5 0.5 0.2 0.2\n",
        )
        for content in invalid:
            with self.subTest(content=content):
                with self.assertRaises(ManifestError):
                    parse_label(content)


if __name__ == "__main__":
    unittest.main()
