import json
from pathlib import Path

from cattle_health_app.version import PROJECT_VERSION


def test_api_and_frontend_use_project_version():
    root = Path(__file__).resolve().parents[1]
    package = json.loads((root / "web" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "web" / "package-lock.json").read_text(encoding="utf-8"))

    assert PROJECT_VERSION == (root / "VERSION").read_text(encoding="utf-8").strip()
    assert package["version"] == lock["version"] == lock["packages"][""]["version"] == PROJECT_VERSION
