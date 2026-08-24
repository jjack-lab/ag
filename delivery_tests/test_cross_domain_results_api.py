import json
from pathlib import Path

from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.repository import SQLiteRepository


class FakeProcessor:
    model_path = None


class FakeArtifact:
    def to_dict(self):
        return {"status": "unavailable", "sha256": None}


def _client(tmp_path, result_root):
    repository = SQLiteRepository(tmp_path / "api.db")
    repository.initialize()
    app = create_app(
        repository,
        media_processor=FakeProcessor(),
        media_root=tmp_path / "media",
        job_service=object(),
        detector_artifact=FakeArtifact(),
        behavior_artifact=FakeArtifact(),
        cross_domain_result_root=result_root,
    )
    return TestClient(app)


def test_results_endpoint_returns_not_run_when_summary_is_absent(tmp_path):
    response = _client(tmp_path, tmp_path / "missing").get(
        "/api/experiments/cross-domain-behavior"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "not_run"
    assert response.json()["quality_policy"] is None
    assert response.json()["variant_metrics"] == {}


def test_results_endpoint_returns_only_validated_defense_fields(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    for name in ("confusion_matrix.png", "risk_coverage.png"):
        (root / name).write_bytes(b"\x89PNG\r\n")
    payload = {
        "status": "complete",
        "protocol": {
            "dataset_id": "cbvd5",
            "dataset_version": "11",
            "checkpoint_sha256": "a" * 64,
            "quality_gate_policy": "predeclared_heuristic",
            "figure_urls": {"evil": "../../secret.txt"},
        },
        "sample_counts": {"strict": 20},
        "metrics": {
            "strict": {
                "uncalibrated": {"sample_count": 20, "coverage": 1.0, "selective_risk": 0.4},
                "calibrated": {"sample_count": 20, "coverage": 1.0, "selective_risk": 0.4},
                "calibrated_fixed_rejection": {"sample_count": 20, "coverage": 0.7, "selective_risk": 0.2},
                "calibrated_quality_rejection": {"sample_count": 20, "coverage": 0.6, "selective_risk": 0.1},
            }
        },
        "claim_boundaries": ["not disease diagnosis"],
        "ignored_secret": "must not be served",
    }
    (root / "metrics.json").write_text(json.dumps(payload), encoding="utf-8")

    response = _client(tmp_path, root).get("/api/experiments/cross-domain-behavior")

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "complete"
    assert result["dataset_version"] == "11"
    assert result["model_hash_prefix"] == "a" * 12
    assert result["quality_policy"] == "predeclared_heuristic"
    assert result["sample_counts"] == {"strict": 20}
    assert "ignored_secret" not in result
    assert "evil" not in result["figure_urls"]
    assert set(result["figure_urls"]) == {"confusion_matrix", "risk_coverage"}


def test_figure_endpoint_uses_a_fixed_allowlist(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    (root / "confusion_matrix.png").write_bytes(b"\x89PNG\r\n")
    client = _client(tmp_path, root)

    allowed = client.get(
        "/api/experiments/cross-domain-behavior/figures/confusion_matrix.png"
    )
    rejected = client.get(
        "/api/experiments/cross-domain-behavior/figures/protocol.json"
    )

    assert allowed.status_code == 200
    assert allowed.headers["content-type"] == "image/png"
    assert rejected.status_code == 404


def test_real_cross_domain_artifacts_match_the_defense_api_contract(tmp_path):
    result_root = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "cross_domain"
        / "cvb_to_cbvd5"
    )

    result = _client(tmp_path, result_root).get(
        "/api/experiments/cross-domain-behavior"
    )

    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "complete"
    assert payload["dataset_version"] == "kaggle-version-11"
    assert payload["model_hash_prefix"] == "731c6ed39dcf"
    assert payload["quality_policy"] == "predeclared_heuristic"
    assert payload["sample_counts"] == {"strict": 400, "extended": 600}
    assert payload["variant_metrics"]["strict"]["calibrated"][
        "selective_macro_f1"
    ] == 0.0047619047619047615
    assert set(payload["figure_urls"]) == {
        "confusion_matrix",
        "risk_coverage",
        "stress_curves",
    }
