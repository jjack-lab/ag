import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from cattle_health_app.detection.waid_repro import (
    CLASS_NAMES,
    MANIFEST_FIELDS,
    ManifestError,
    load_manifest,
    parse_label,
    rebuild_dataset,
    split_counts,
    validate_dataset,
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


class WaidRebuildTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.raw = self.root / "raw"
        self.manifest = self.root / "manifest.csv"
        self.output = self.root / "waid4500_v1"

    def tearDown(self):
        self.temporary.cleanup()

    def add_source(self, split, name, image_bytes, label_text):
        image = self.raw / "images" / split / name
        label = self.raw / "labels" / split / (Path(name).stem + ".txt")
        image.parent.mkdir(parents=True, exist_ok=True)
        label.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(image_bytes)
        label.write_text(label_text, encoding="utf-8")

    @staticmethod
    def manifest_row(split, name, class_id, class_name, instances, group_id):
        label_name = Path(name).stem + ".txt"
        return {
            "split": split,
            "output_image": "images/{}/{}".format(split, name),
            "output_label": "labels/{}/{}".format(split, label_name),
            "source_image": r"E:\WAID\images\{}\{}".format(split, name),
            "source_label": r"E:\WAID\labels\{}\{}".format(split, label_name),
            "source_split": split,
            "class_id": str(class_id),
            "class_name": class_name,
            "instances": str(instances),
            "group_id": group_id,
        }

    def write_manifest(self, rows):
        with self.manifest.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def prepare_valid_fixture(self):
        self.add_source("train", "a.jpg", b"image-a", "1 0.5 0.5 0.2 0.2\n")
        self.add_source("test", "b.jpg", b"image-b", "0 0.5 0.5 0.2 0.2\n")
        self.write_manifest(
            [
                self.manifest_row("train", "a.jpg", 1, "cattle", 1, "group-a"),
                self.manifest_row("test", "b.jpg", 0, "sheep", 1, "group-b"),
            ]
        )

    def test_rebuilds_exact_manifest_partition(self):
        self.prepare_valid_fixture()

        summary = rebuild_dataset(
            raw_root=self.raw,
            manifest_path=self.manifest,
            output_root=self.output,
            expected_counts={"train": 1, "valid": 0, "test": 1},
        )

        self.assertEqual({"train": 1, "valid": 0, "test": 1}, summary["splits"])
        self.assertEqual(b"image-a", (self.output / "images/train/a.jpg").read_bytes())
        self.assertEqual(
            ["images/train/a.jpg"],
            (self.output / "splits/train.txt").read_text(encoding="utf-8").splitlines(),
        )
        data = yaml.safe_load((self.output / "data.yaml").read_text(encoding="utf-8"))
        self.assertEqual(str(self.output.resolve()), data["path"])
        self.assertEqual("images/valid", data["val"])
        self.assertEqual(CLASS_NAMES, data["names"])

    def test_refuses_existing_output(self):
        self.prepare_valid_fixture()
        self.output.mkdir()

        with self.assertRaises(FileExistsError):
            rebuild_dataset(self.raw, self.manifest, self.output)

    def test_validate_only_accepts_snapshot_and_rejects_tampering(self):
        self.prepare_valid_fixture()
        expected = {"train": 1, "valid": 0, "test": 1}
        rebuild_dataset(self.raw, self.manifest, self.output, expected)

        summary = validate_dataset(self.raw, self.manifest, self.output, expected)
        self.assertEqual(expected, summary["splits"])

        (self.output / "labels/train/a.txt").write_text(
            "2 0.5 0.5 0.2 0.2\n", encoding="utf-8"
        )
        with self.assertRaises(ManifestError):
            validate_dataset(self.raw, self.manifest, self.output, expected)

    def test_removes_staging_when_source_is_missing(self):
        self.write_manifest(
            [self.manifest_row("train", "missing.jpg", 1, "cattle", 1, "group-a")]
        )

        with self.assertRaises(ManifestError):
            rebuild_dataset(self.raw, self.manifest, self.output)

        self.assertEqual([], list(self.root.glob(".waid4500_v1.staging-*")))
        self.assertFalse(self.output.exists())

    def test_rejects_label_metadata_mismatch(self):
        self.add_source("train", "a.jpg", b"image-a", "1 0.5 0.5 0.2 0.2\n")
        self.write_manifest(
            [self.manifest_row("train", "a.jpg", 1, "cattle", 2, "group-a")]
        )

        with self.assertRaisesRegex(ManifestError, "metadata"):
            rebuild_dataset(self.raw, self.manifest, self.output)

    def test_rejects_group_leakage_between_splits(self):
        self.add_source("train", "a.jpg", b"image-a", "1 0.5 0.5 0.2 0.2\n")
        self.add_source("test", "b.jpg", b"image-b", "1 0.5 0.5 0.2 0.2\n")
        self.write_manifest(
            [
                self.manifest_row("train", "a.jpg", 1, "cattle", 1, "same-group"),
                self.manifest_row("test", "b.jpg", 1, "cattle", 1, "same-group"),
            ]
        )

        with self.assertRaisesRegex(ManifestError, "multiple splits"):
            rebuild_dataset(self.raw, self.manifest, self.output)


class WaidRebuildCliTest(unittest.TestCase):
    @classmethod
    def script(cls):
        return (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "reproducibility"
            / "rebuild_waid4500.py"
        )

    def test_help_documents_rebuild_contract(self):
        result = subprocess.run(
            [sys.executable, str(self.script()), "--help"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        for option in (
            "--raw-root",
            "--manifest",
            "--output",
            "--expected-train",
            "--expected-valid",
            "--expected-test",
            "--validate-only",
        ):
            self.assertIn(option, result.stdout)

    def test_missing_inputs_exit_one(self):
        result = subprocess.run(
            [
                sys.executable,
                str(self.script()),
                "--raw-root",
                "missing-raw",
                "--manifest",
                "missing.csv",
                "--output",
                "missing-output",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("[ERROR]", result.stderr)


if __name__ == "__main__":
    unittest.main()
