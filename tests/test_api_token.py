from fastapi.testclient import TestClient

from cattle_health_app.api import create_app
from cattle_health_app.domain import VideoJobRecord
from cattle_health_app.repository import SQLiteRepository
from cattle_health_app.runtime import ensure_bind_is_safe


def _client(tmp_path, token):
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.initialize()
    repository.save_video_job(VideoJobRecord(
        id="cow-job", source_path="cow.mp4", status="completed", progress=1,
        created_at="2026-10-22T10:00:00+08:00", updated_at="2026-10-22T10:00:02+08:00",
        result={"species": "cattle", "track_ids": [], "health_evidence": []},
    ))
    media = tmp_path / "media"
    (media / "results" / "cow-job").mkdir(parents=True)
    (media / "results" / "cow-job" / "tracked.mp4").write_bytes(b"video-bytes")
    return TestClient(create_app(repository, media_root=media, api_token=token))


def test_no_token_configured_keeps_local_api_open(tmp_path):
    client = _client(tmp_path, None)
    assert client.get("/api/dashboard").status_code == 200


def test_configured_token_is_required_for_private_api(tmp_path):
    client = _client(tmp_path, "s3cret")
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers={"X-API-Token": "wrong"}).status_code == 401
    assert client.get("/api/dashboard", headers={"X-API-Token": "s3cret"}).status_code == 200
    assert client.get("/api/dashboard", headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert client.get("/api/health").status_code == 200


def test_configured_token_also_covers_uploaded_media(tmp_path):
    client = _client(tmp_path, "s3cret")
    path = "/media/results/cow-job/tracked.mp4"
    assert client.get(path).status_code == 401
    assert client.get(path, params={"token": "s3cret"}).status_code == 200
    assert client.get(path, headers={"X-API-Token": "s3cret"}).status_code == 200


def test_successful_api_call_leaves_a_cookie_so_media_tags_keep_working(tmp_path):
    client = _client(tmp_path, "s3cret")
    assert client.get("/api/dashboard", headers={"X-API-Token": "s3cret"}).status_code == 200
    # 浏览器里的 <video src> 不能加自定义请求头，只能靠这个 cookie。
    assert client.get("/media/results/cow-job/tracked.mp4").status_code == 200


def test_binding_to_a_lan_address_without_a_token_is_refused():
    ensure_bind_is_safe("127.0.0.1", None)
    ensure_bind_is_safe("localhost", None)
    ensure_bind_is_safe("0.0.0.0", "s3cret")
    try:
        ensure_bind_is_safe("0.0.0.0", None)
    except ValueError as error:
        assert "AGRINEBULA_API_TOKEN" in str(error)
    else:
        raise AssertionError("lan binding without a token must fail closed")
