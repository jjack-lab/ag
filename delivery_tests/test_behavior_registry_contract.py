from hashlib import sha256


def test_missing_behavior_model_is_nonfatal(tmp_path):
    from cattle_health_app.model_registry import resolve_behavior_model

    artifact = resolve_behavior_model(project_root=tmp_path)

    assert artifact.status == "unavailable"
    assert artifact.path == (
        tmp_path / "models" / "behavior" / "cvb_x3d_v2_best.pt"
    ).resolve()
    assert artifact.sha256 is None
    assert artifact.version is None


def test_existing_behavior_model_is_fingerprinted(tmp_path):
    from cattle_health_app.model_registry import resolve_behavior_model

    weight = tmp_path / "behavior.pt"
    weight.write_bytes(b"behavior-model")

    artifact = resolve_behavior_model(weight, project_root=tmp_path)

    assert artifact.status == "ready"
    assert artifact.sha256 == sha256(b"behavior-model").hexdigest()


def test_media_processor_passes_lazily_loaded_behavior_runtime(
    tmp_path, monkeypatch
):
    import cattle_health_app.media_processor as processor_module

    detector = tmp_path / "detector.pt"
    detector.write_bytes(b"detector")
    behavior = tmp_path / "behavior.pt"
    behavior.write_bytes(b"behavior")
    runtime = object()
    captured = {}

    processor = processor_module.LocalMediaProcessor(
        model_path=detector,
        behavior_model_path=behavior,
        behavior_runtime_factory=lambda path: runtime,
    )
    monkeypatch.setattr(processor, "_load_model", lambda: object())

    def fake_process(*args, **kwargs):
        captured.update(kwargs)
        return "result"

    monkeypatch.setattr(processor_module, "process_tracked_video", fake_process)

    result = processor.track_video("source.mp4", tmp_path, 0.25, 0.45)

    assert result == "result"
    assert captured["behavior_runtime"] is runtime
    assert processor.behavior_artifact.status == "ready"
