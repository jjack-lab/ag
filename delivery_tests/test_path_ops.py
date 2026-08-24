from __future__ import annotations

import pytest

import cattle_health_app.path_ops as path_ops


def test_replace_path_retries_permission_error_then_succeeds(monkeypatch):
    calls = []
    delays = []

    def flaky_replace(source, destination):
        calls.append((source, destination))
        if len(calls) < 3:
            raise PermissionError("temporarily locked")

    monkeypatch.setattr(path_ops.os, "replace", flaky_replace)
    monkeypatch.setattr(path_ops.time, "sleep", delays.append)

    path_ops.replace_path_with_retry("staging", "output")

    assert calls == [
        ("staging", "output"),
        ("staging", "output"),
        ("staging", "output"),
    ]
    assert delays == [0.05, 0.1]


def test_replace_path_preserves_final_permission_error(monkeypatch):
    calls = []
    delays = []
    error = PermissionError("persistently locked")

    def always_denied(source, destination):
        calls.append((source, destination))
        raise error

    monkeypatch.setattr(path_ops.os, "replace", always_denied)
    monkeypatch.setattr(path_ops.time, "sleep", delays.append)

    with pytest.raises(PermissionError) as caught:
        path_ops.replace_path_with_retry("staging", "output")

    assert caught.value is error
    assert len(calls) == 6
    assert delays == [0.05, 0.1, 0.2, 0.4, 0.8]


def test_replace_path_does_not_retry_other_errors(monkeypatch):
    calls = []
    delays = []
    error = OSError("not a permission failure")

    def fail_once(source, destination):
        calls.append((source, destination))
        raise error

    monkeypatch.setattr(path_ops.os, "replace", fail_once)
    monkeypatch.setattr(path_ops.time, "sleep", delays.append)

    with pytest.raises(OSError) as caught:
        path_ops.replace_path_with_retry("staging", "output")

    assert caught.value is error
    assert calls == [("staging", "output")]
    assert delays == []
