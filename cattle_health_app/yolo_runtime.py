from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _resolved_import_path(entry: str) -> Path:
    return Path(entry or Path.cwd()).resolve()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def load_delivery_yolo_class():
    """Load the installed YOLO11-capable package, not the bundled YOLOv8 tree."""
    project_root = Path(__file__).resolve().parents[1]
    existing = sys.modules.get("ultralytics")
    if existing is not None:
        existing_path = Path(existing.__file__).resolve()
        if not _inside(existing_path, project_root):
            return existing.YOLO
        for name in tuple(sys.modules):
            if name == "ultralytics" or name.startswith("ultralytics."):
                sys.modules.pop(name, None)

    original_path = list(sys.path)
    sys.path[:] = [
        entry
        for entry in original_path
        if _resolved_import_path(entry) != project_root
    ]
    try:
        module = importlib.import_module("ultralytics")
    finally:
        sys.path[:] = original_path

    module_path = Path(module.__file__).resolve()
    if _inside(module_path, project_root):
        raise RuntimeError(
            "The legacy project-local Ultralytics package shadows the "
            "YOLO11-capable installed runtime."
        )
    version = tuple(int(part) for part in module.__version__.split(".")[:2])
    if version < (8, 3):
        raise RuntimeError(
            f"Ultralytics {module.__version__} cannot load the delivery "
            "YOLO11 model. Install ultralytics>=8.3."
        )
    return module.YOLO
