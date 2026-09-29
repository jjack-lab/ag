import contextlib
import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

from cattle_health_app.detection.waid_repro import (
    CLASS_NAMES,
    ImportSources,
    MANIFEST_FIELDS,
    ManifestError,
    build_train_kwargs,
    capture_environment,
    import_assets,
    load_manifest,
    load_checksums,
    load_training_config,
    parse_label,
    rebuild_dataset,
    split_counts,
    run_training,
    sha256_file,
    summarize_results,
    unicode_safe_save,
    unicode_safe_torch_save,
    validate_dataset,
    verify_checksums,
    write_checksums,
)


@contextlib.contextmanager
def installed_ultralytics(module):
    """Install a fake ``ultralytics`` module for the duration of a block.

    ``mock.patch.dict(sys.modules, ...)`` snapshots the whole module table and
    restores it on exit, which ejects every module imported inside the block.
    The training runtime imports ``torch`` there, so the previous form left the
    interpreter with a half-initialized ``torch`` that could not be imported
    again. Patch only the single key instead.
    """

    missing = object()
    original = sys.modules.get("ultralytics", missing)
    sys.modules["ultralytics"] = module
    try:
        yield module
    finally:
        if original is missing:
            sys.modules.pop("ultralytics", None)
        else:
            sys.modules["ultralytics"] = original


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
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("[ERROR]", result.stderr)


class WaidAssetImportTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.source = self.root / "source"

        self.raw = self.source / "raw"
        self.write(self.raw / "images/train/a.jpg", b"raw-image")
        self.write(self.raw / "labels/train/a.txt", b"1 0.5 0.5 0.2 0.2\n")

        self.frozen = self.source / "waid4500_v1"
        self.write(self.frozen / "data.yaml", b"path: old\n")
        self.write(
            self.frozen / "reports/generation_summary.json",
            b'{"splits":{"train":4500,"valid":200,"test":20}}',
        )

        self.pretrained = self.source / "yolo11s.pt"
        self.write(self.pretrained, b"pretrained")

        self.run = self.source / "run"
        self.write(self.run / "weights/best.pt", b"best")
        self.write(self.run / "results.csv", b"epoch,metric\n1,0.5\n")

        self.logs = self.source / "logs"
        self.write(self.logs / "training.stdout.log", b"training")

        self.sources = ImportSources(
            raw=self.raw,
            frozen_dataset=self.frozen,
            pretrained=self.pretrained,
            run=self.run,
            logs=self.logs,
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def test_imports_assets_to_fixed_local_destinations(self):
        report = import_assets(self.sources, self.project)

        self.assertEqual(
            b"raw-image",
            (self.project / "data/external/waid/raw/images/train/a.jpg").read_bytes(),
        )
        self.assertEqual(
            b"pretrained",
            (self.project / "data/external/waid/cache/yolo11s.pt").read_bytes(),
        )
        self.assertEqual(
            b"best",
            (
                self.project
                / "outputs/training/waid4500_yolo11s/run/weights/best.pt"
            ).read_bytes(),
        )
        self.assertEqual(2, report["components"]["raw"]["files"])
        self.assertEqual(len(b"raw-image") + len(b"1 0.5 0.5 0.2 0.2\n"), report["components"]["raw"]["bytes"])

    def test_refuses_existing_destination_without_replace(self):
        import_assets(self.sources, self.project)

        with self.assertRaises(FileExistsError):
            import_assets(self.sources, self.project)

    def test_replace_updates_existing_destination(self):
        import_assets(self.sources, self.project)
        self.write(self.raw / "images/train/a.jpg", b"updated")

        import_assets(self.sources, self.project, replace=True)

        self.assertEqual(
            b"updated",
            (self.project / "data/external/waid/raw/images/train/a.jpg").read_bytes(),
        )

    def test_copy_failure_preserves_existing_destination(self):
        import_assets(self.sources, self.project)
        destination = self.project / "data/external/waid/raw/images/train/a.jpg"

        with mock.patch(
            "cattle_health_app.detection.waid_repro.shutil.copytree",
            side_effect=OSError("copy failed"),
        ):
            with self.assertRaises(OSError):
                import_assets(self.sources, self.project, replace=True)

        self.assertEqual(b"raw-image", destination.read_bytes())


class WaidAssetImportCliTest(unittest.TestCase):
    @classmethod
    def script(cls):
        return (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "reproducibility"
            / "import_waid_assets.py"
        )

    def test_help_documents_sources_and_replace(self):
        result = subprocess.run(
            [sys.executable, str(self.script()), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        for option in ("--source-raw", "--source-training-root", "--project-root", "--replace"):
            self.assertIn(option, result.stdout)

    def test_missing_sources_exit_one(self):
        result = subprocess.run(
            [
                sys.executable,
                str(self.script()),
                "--source-raw",
                "missing-raw",
                "--source-training-root",
                "missing-training",
                "--project-root",
                str(Path.cwd()),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("[ERROR]", result.stderr)


class WaidTrainingConfigTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "training.yaml"

    def tearDown(self):
        self.temporary.cleanup()

    def write_config(self, **overrides):
        values = {
            "model": "data/external/waid/cache/yolo11s.pt",
            "data_root": "data/external/waid/derived/waid4500_v1",
            "manifest": "reproducibility/waid4500/dataset_manifest.csv",
            "project": "outputs/training/waid4500_yolo11s/reproduced",
            "name": "full_e120_seed42",
            "epochs": 120,
            "patience": 120,
            "batch": 4,
            "imgsz": 960,
            "workers": 0,
            "seed": 42,
            "deterministic": True,
            "cos_lr": True,
            "device": "auto",
        }
        values.update(overrides)
        self.config_path.write_text(
            yaml.safe_dump(values, sort_keys=False), encoding="utf-8"
        )
        return self.config_path

    def test_committed_training_config_freezes_original_protocol(self):
        project = Path(__file__).resolve().parents[1]
        config = load_training_config(
            project / "reproducibility/waid4500/training_config.yaml", project
        )

        self.assertEqual(120, config["epochs"])
        self.assertEqual(4, config["batch"])
        self.assertEqual(960, config["imgsz"])
        self.assertEqual(42, config["seed"])
        self.assertEqual("auto", config["device"])
        self.assertEqual(project / "data/external/waid/cache/yolo11s.pt", config["model"])

    def test_rejects_configured_path_outside_project(self):
        config_path = self.write_config(model="../outside.pt")

        with self.assertRaisesRegex(ValueError, "outside project root"):
            load_training_config(config_path, self.root)

    def test_builds_full_and_smoke_train_arguments(self):
        config = load_training_config(self.write_config(), self.root)

        full = build_train_kwargs(config, smoke=False, device="1")
        smoke = build_train_kwargs(config, smoke=True, device="cpu")

        self.assertEqual(120, full["epochs"])
        self.assertEqual("full_e120_seed42", full["name"])
        self.assertEqual("1", full["device"])
        self.assertNotIn("fraction", full)
        self.assertEqual(1, smoke["epochs"])
        self.assertEqual(0.02, smoke["fraction"])
        self.assertEqual("smoke_e1", smoke["name"])
        self.assertEqual("cpu", smoke["device"])
        self.assertFalse(smoke["exist_ok"])

    def test_run_training_calls_ultralytics_with_portable_yaml(self):
        config = load_training_config(self.write_config(), self.root)
        config["model"].parent.mkdir(parents=True)
        config["model"].write_bytes(b"model")
        calls = []

        class FakeModel:
            def __init__(self, model):
                calls.append(("init", model))

            def train(self, **kwargs):
                calls.append(("train", kwargs))
                return SimpleNamespace(save_dir="result")

        fake_ultralytics = SimpleNamespace(YOLO=FakeModel, __version__="test")
        runtime_yaml = self.root / "runtime-data.yaml"
        runtime_yaml.write_text("path: portable\n", encoding="utf-8")
        with installed_ultralytics(fake_ultralytics):
            with mock.patch(
                "cattle_health_app.detection.waid_repro.check_training_runtime",
                return_value={"selected_device": "cpu"},
            ):
                with mock.patch(
                    "cattle_health_app.detection.waid_repro.write_runtime_data_yaml",
                    return_value=runtime_yaml,
                ):
                    result = run_training(config, smoke=True, device="cpu", resume=None)

        self.assertEqual(("init", str(config["model"])), calls[0])
        self.assertEqual(str(runtime_yaml), calls[1][1]["data"])
        self.assertEqual("smoke_e1", calls[1][1]["name"])
        self.assertEqual("result", result.save_dir)

    def test_resume_requires_existing_checkpoint(self):
        config = load_training_config(self.write_config(), self.root)
        with self.assertRaises(FileNotFoundError):
            run_training(config, smoke=False, device="cpu", resume=self.root / "missing.pt")


class WaidUnicodeCheckpointTest(unittest.TestCase):
    """PyTorch's C++ writer rejects non-ASCII paths on Windows; training must not hit it."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def refusing_save(obj, target, *args, **kwargs):
        """Stand-in for torch.save: buffers are fine, non-ASCII paths raise."""

        payload = b"serialized-checkpoint"
        if isinstance(target, io.BytesIO):
            target.write(payload)
            return
        if not str(target).isascii():
            raise RuntimeError(
                "Parent directory {} does not exist.".format(Path(target).parent)
            )
        Path(target).write_bytes(payload)

    def test_non_ascii_destination_is_serialized_through_a_buffer(self):
        destination = self.root / "中文输出" / "weights" / "last.pt"
        destination.parent.mkdir(parents=True)
        seen = []

        def recording_save(obj, target, *args, **kwargs):
            seen.append(target)
            self.refusing_save(obj, target, *args, **kwargs)

        result = unicode_safe_save(recording_save, {"epoch": -1}, destination)

        self.assertIsNone(result)
        self.assertEqual(1, len(seen))
        self.assertIsInstance(seen[0], io.BytesIO)
        self.assertEqual(b"serialized-checkpoint", destination.read_bytes())

    def test_ascii_destination_keeps_the_direct_write(self):
        destination = self.root / "ascii" / "weights" / "last.pt"
        destination.parent.mkdir(parents=True)
        seen = []

        def recording_save(obj, target, *args, **kwargs):
            seen.append(target)
            self.refusing_save(obj, target, *args, **kwargs)

        unicode_safe_save(recording_save, {"epoch": -1}, destination)

        self.assertEqual([destination], seen)
        self.assertEqual(b"serialized-checkpoint", destination.read_bytes())

    def test_non_ascii_path_checkpoint_round_trips_with_real_torch(self):
        import torch

        destination = self.root / "中文输出" / "weights" / "last.pt"
        destination.parent.mkdir(parents=True)

        with unicode_safe_torch_save():
            torch.save({"epoch": 1, "probe": True}, destination)

        self.assertTrue(destination.is_file())
        self.assertEqual({"epoch": 1, "probe": True}, torch.load(destination))

    def test_run_training_patches_torch_save_only_while_training(self):
        import torch

        config = load_training_config(self.write_config_for_training(), self.root)
        config["model"].parent.mkdir(parents=True, exist_ok=True)
        config["model"].write_bytes(b"model")
        observed = []
        original = torch.save

        class FakeModel:
            def __init__(self, model):
                pass

            def train(self, **kwargs):
                observed.append(torch.save is not original)
                return SimpleNamespace(save_dir="result")

        fake_ultralytics = SimpleNamespace(YOLO=FakeModel, __version__="test")
        runtime_yaml = self.root / "runtime-data.yaml"
        runtime_yaml.write_text("path: portable\n", encoding="utf-8")
        with installed_ultralytics(fake_ultralytics):
            with mock.patch(
                "cattle_health_app.detection.waid_repro.check_training_runtime",
                return_value={"selected_device": "cpu"},
            ):
                with mock.patch(
                    "cattle_health_app.detection.waid_repro.write_runtime_data_yaml",
                    return_value=runtime_yaml,
                ):
                    run_training(config, smoke=True, device="cpu", resume=None)

        self.assertEqual([True], observed)
        self.assertIs(original, torch.save)

    def test_run_training_restores_torch_save_after_training_failure(self):
        import torch

        config = load_training_config(self.write_config_for_training(), self.root)
        config["model"].parent.mkdir(parents=True, exist_ok=True)
        config["model"].write_bytes(b"model")
        original = torch.save

        class ExplodingModel:
            def __init__(self, model):
                pass

            def train(self, **kwargs):
                raise RuntimeError("training failed")

        fake_ultralytics = SimpleNamespace(YOLO=ExplodingModel, __version__="test")
        runtime_yaml = self.root / "runtime-data.yaml"
        runtime_yaml.write_text("path: portable\n", encoding="utf-8")
        with installed_ultralytics(fake_ultralytics):
            with mock.patch(
                "cattle_health_app.detection.waid_repro.check_training_runtime",
                return_value={"selected_device": "cpu"},
            ):
                with mock.patch(
                    "cattle_health_app.detection.waid_repro.write_runtime_data_yaml",
                    return_value=runtime_yaml,
                ):
                    with self.assertRaisesRegex(RuntimeError, "training failed"):
                        run_training(config, smoke=True, device="cpu", resume=None)

        self.assertIs(original, torch.save)

    def write_config_for_training(self):
        values = {
            "model": "data/external/waid/cache/yolo11s.pt",
            "data_root": "data/external/waid/derived/waid4500_v1",
            "manifest": "reproducibility/waid4500/dataset_manifest.csv",
            "project": "outputs/training/waid4500_yolo11s/reproduced",
            "name": "full_e120_seed42",
            "epochs": 120,
            "patience": 120,
            "batch": 4,
            "imgsz": 960,
            "workers": 0,
            "seed": 42,
            "deterministic": True,
            "cos_lr": True,
            "device": "auto",
        }
        path = self.root / "training.yaml"
        path.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
        return path


class WaidTrainingCliTest(unittest.TestCase):
    @classmethod
    def script(cls):
        return (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "reproducibility"
            / "train_waid_yolo11s.py"
        )

    def test_help_documents_training_modes(self):
        result = subprocess.run(
            [sys.executable, str(self.script()), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        for option in ("--project-root", "--config", "--check-only", "--smoke", "--device", "--resume"):
            self.assertIn(option, result.stdout)

    def test_missing_config_exits_one(self):
        result = subprocess.run(
            [sys.executable, str(self.script()), "--config", "missing.yaml", "--check-only"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("[ERROR]", result.stderr)


class WaidEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_sha256_and_standard_checksum_round_trip(self):
        artifact = self.root / "artifact.bin"
        artifact.write_bytes(b"abc")
        checksum_path = self.root / "checksums.sha256"

        write_checksums(self.root, [artifact], checksum_path)
        checksums = load_checksums(checksum_path)
        verification = verify_checksums(self.root, checksum_path)

        self.assertEqual(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            sha256_file(artifact),
        )
        self.assertEqual({"artifact.bin": sha256_file(artifact)}, checksums)
        self.assertEqual("passed", verification[0]["status"])

    def test_checksum_verification_reports_tampering(self):
        artifact = self.root / "artifact.bin"
        artifact.write_bytes(b"before")
        checksum_path = self.root / "checksums.sha256"
        write_checksums(self.root, [artifact], checksum_path)
        artifact.write_bytes(b"after")

        verification = verify_checksums(self.root, checksum_path)

        self.assertEqual("failed", verification[0]["status"])
        self.assertNotEqual(verification[0]["expected"], verification[0]["actual"])

    def test_rejects_unsafe_or_noncanonical_checksum_lines(self):
        checksum_path = self.root / "checksums.sha256"
        invalid_lines = (
            "ABCDEF" + "0" * 58 + "  artifact.bin\n",
            "0" * 64 + " ../outside.bin\n",
            "0" * 64 + "  C:/outside.bin\n",
            "not-a-checksum\n",
        )
        for line in invalid_lines:
            with self.subTest(line=line):
                checksum_path.write_text(line, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_checksums(checksum_path)

    def test_summarize_results_selects_best_map_row(self):
        results = self.root / "results.csv"
        results.write_text(
            "epoch,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B)\n"
            "1,0.7,0.6,0.7,0.4\n"
            "2,0.9,0.8,0.9,0.6\n"
            "3,0.8,0.7,0.8,0.5\n",
            encoding="utf-8",
        )

        summary = summarize_results(results)

        self.assertEqual(3, summary["epochs_recorded"])
        self.assertEqual(2, summary["best"]["epoch"])
        self.assertEqual(0.6, summary["best"]["map50_95"])

    def test_capture_environment_has_reproduction_fields(self):
        environment = capture_environment()
        for field in ("python", "platform", "torch", "ultralytics", "cuda_available"):
            self.assertIn(field, environment)


class WaidVerifierCliTest(unittest.TestCase):
    @classmethod
    def script(cls):
        return (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "reproducibility"
            / "verify_waid_reproduction.py"
        )

    def test_help_documents_verifier_contract(self):
        result = subprocess.run(
            [sys.executable, str(self.script()), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        for option in ("--project-root", "--manifest", "--checksums", "--output-json"):
            self.assertIn(option, result.stdout)

    def test_missing_evidence_exits_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, str(self.script()), "--project-root", temporary],
                capture_output=True,
                text=True,
            )
        self.assertEqual(1, result.returncode)
        self.assertIn('"status": "failed"', result.stdout)


class WaidPowerShellWorkflowTest(unittest.TestCase):
    @classmethod
    def script(cls):
        return (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "reproducibility"
            / "run_waid_reproduction.ps1"
        )

    def test_script_uses_portable_parameter_contract(self):
        text = self.script().read_text(encoding="utf-8-sig")

        for parameter in ("$Mode", "$Python", "$ProjectRoot", "$Device", "$Resume"):
            self.assertIn(parameter, text)
        self.assertIn("$PSScriptRoot", text)
        self.assertIn("@arguments", text)
        self.assertNotIn("E:\\", text)
        for mode in ("verify", "rebuild", "smoke", "train", "resume"):
            self.assertIn("'{}'".format(mode), text)

    def test_powershell_help_does_not_run_workflow(self):
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Help -Full '{}'".format(str(self.script()).replace("'", "''")),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Mode", result.stdout)


if __name__ == "__main__":
    unittest.main()
