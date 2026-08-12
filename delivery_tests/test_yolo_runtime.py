from pathlib import Path


def test_delivery_runtime_does_not_use_legacy_project_yolo():
    from cattle_health_app import media_processor  # noqa: F401
    import ultralytics

    project_root = Path(__file__).resolve().parents[1]
    module_path = Path(ultralytics.__file__).resolve()
    version = tuple(int(part) for part in ultralytics.__version__.split(".")[:2])

    assert version >= (8, 3)
    assert project_root not in module_path.parents
