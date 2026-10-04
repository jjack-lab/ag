"""Tests for pointing WAID training at a repeat-factor train list (H1 variant)."""

import contextlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

from cattle_health_app.detection.waid_repro import (
    load_training_config,
    run_training,
    write_runtime_data_yaml,
)


@contextlib.contextmanager
def fake_ultralytics(module):
    """Install a fake ``ultralytics`` without snapshotting all of sys.modules."""

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


class WaidTrainListTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "training.yaml"

    def tearDown(self):
        self.temporary.cleanup()

    def write_config(self, **overrides):
        values = {
            "model": "data/external/waid/cache/yolo11s.pt",
            "data_root": "waid4500_v1",
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

    def make_train_list(self):
        dataset = self.root / "waid4500_v1"
        (dataset / "splits").mkdir(parents=True, exist_ok=True)
        path = dataset / "splits" / "train_rf_h1.txt"
        path.write_text("images/train/a.jpg\nimages/train/a.jpg\n", encoding="utf-8")
        return path

    def test_binds_an_optional_train_list_inside_the_project(self):
        path = self.make_train_list()

        config = load_training_config(
            self.write_config(train_list="waid4500_v1/splits/train_rf_h1.txt"), self.root
        )

        self.assertEqual(path, config["train_list"])

    def test_reads_a_config_written_with_a_byte_order_mark(self):
        self.write_config()
        content = self.config_path.read_bytes()
        self.config_path.write_bytes(b"\xef\xbb\xbf" + content)

        config = load_training_config(self.config_path, self.root)

        self.assertEqual(960, config["imgsz"])

    def test_rejects_a_train_list_outside_the_project(self):
        with self.assertRaisesRegex(ValueError, "outside project root"):
            load_training_config(self.write_config(train_list="../outside.txt"), self.root)

    def test_rejects_a_train_list_that_is_not_a_txt_file(self):
        with self.assertRaisesRegex(ValueError, "txt"):
            load_training_config(
                self.write_config(train_list="waid4500_v1/train_rf.json"), self.root
            )

    def test_runtime_data_yaml_can_point_train_at_a_repeat_list(self):
        dataset = self.root / "waid4500_v1"
        destination = self.root / "runtime.yaml"

        write_runtime_data_yaml(dataset, destination, train="splits/train_rf_h1.txt")

        payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
        self.assertEqual("splits/train_rf_h1.txt", payload["train"])
        self.assertEqual("images/valid", payload["val"])
        self.assertEqual(str(dataset.resolve()), payload["path"])

    def test_runtime_data_yaml_defaults_to_the_plain_train_directory(self):
        destination = self.root / "runtime-default.yaml"

        write_runtime_data_yaml(self.root / "waid4500_v1", destination)

        payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
        self.assertEqual("images/train", payload["train"])

    def test_run_training_writes_the_configured_train_list(self):
        self.make_train_list()
        config = load_training_config(
            self.write_config(train_list="waid4500_v1/splits/train_rf_h1.txt"), self.root
        )
        config["model"].parent.mkdir(parents=True, exist_ok=True)
        config["model"].write_bytes(b"model")
        captured = {}

        class FakeModel:
            def __init__(self, model):
                pass

            def train(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(save_dir="result")

        with fake_ultralytics(SimpleNamespace(YOLO=FakeModel, __version__="test")):
            with mock.patch(
                "cattle_health_app.detection.waid_repro.check_training_runtime",
                return_value={"selected_device": "cpu"},
            ):
                run_training(config, smoke=False, device="cpu", resume=None)

        runtime_yaml = config["project"] / "waid4500_runtime_data.yaml"
        self.assertEqual(
            "splits/train_rf_h1.txt",
            yaml.safe_load(runtime_yaml.read_text(encoding="utf-8"))["train"],
        )
        self.assertEqual(str(runtime_yaml), captured["data"])

    def test_run_training_requires_the_train_list_to_exist(self):
        config = load_training_config(
            self.write_config(train_list="waid4500_v1/splits/train_rf_h1.txt"), self.root
        )
        config["model"].parent.mkdir(parents=True, exist_ok=True)
        config["model"].write_bytes(b"model")

        with self.assertRaises(FileNotFoundError):
            run_training(config, smoke=False, device="cpu", resume=None)


if __name__ == "__main__":
    unittest.main()
