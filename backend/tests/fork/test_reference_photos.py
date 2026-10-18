"""reference photo store and /api/fork routes."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.api.routes as routes
from app.config import ensure_user_dirs
from app.fork.reference_photos import ReferencePhotoStore, refs_dir_for_image, session_id_from_image
from app.main import app
from app.models.schemas import Session


def _jpeg(color="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(buf, format="JPEG")
    return buf.getvalue()


def test_refs_dir_derives_from_corrected_image(tmp_path):
    image = tmp_path / "processed" / "abc-123_corrected.jpg"
    assert session_id_from_image(image) == "abc-123"
    assert refs_dir_for_image(image) == tmp_path / "processed" / "abc-123_refs"


def test_store_add_list_delete_and_cap(tmp_path):
    store = ReferencePhotoStore(tmp_path / "refs", max_photos=2)
    a = store.add(_jpeg(), ".jpg", "side", "flat on the bench")
    store.add(_jpeg("blue"), ".jpg", "detail")
    assert [p.kind for p in store.list()] == ["side", "detail"]
    with pytest.raises(ValueError, match="at most 2"):
        store.add(_jpeg(), ".jpg", "top")
    assert store.delete(a.id) is True
    assert store.delete(a.id) is False
    assert [p.kind for p in store.list()] == ["detail"]
    with pytest.raises(ValueError, match="kind"):
        store.add(_jpeg(), ".jpg", "underneath")
    store.clear()
    assert store.list() == []


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(routes.settings, "storage_path", tmp_path)
    routes._store_cache.clear()
    ensure_user_dirs(tmp_path / "default")
    sessions, _, _ = routes.get_stores("default")
    sessions.set("s1", Session(id="s1", corrected_image_path="default/processed/s1_corrected.jpg"))
    return TestClient(app)


def test_routes_upload_list_delete(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    url = "/api/fork/sessions/s1/reference-photos"

    resp = client.post(url, files={"image": ("side.jpg", _jpeg(), "image/jpeg")}, data={"kind": "side"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kinds"] == ["top", "side", "detail"]
    [photo] = body["photos"]
    assert photo["kind"] == "side"
    assert photo["url"].startswith("/storage/default/processed/s1_refs/")
    assert (tmp_path / photo["url"].removeprefix("/storage/")).exists()

    assert len(client.get(url).json()["photos"]) == 1
    assert client.delete(f"{url}/{photo['id']}").json()["photos"] == []
    assert client.delete(f"{url}/{photo['id']}").status_code == 404


def test_routes_reject_unknown_session_and_bad_kind(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    files = {"image": ("a.jpg", _jpeg(), "image/jpeg")}
    assert client.get("/api/fork/sessions/nope/reference-photos").status_code == 404
    bad = client.post("/api/fork/sessions/s1/reference-photos", files=files, data={"kind": "x"})
    assert bad.status_code == 400


def test_session_delete_removes_reference_photos(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    files = {"image": ("a.jpg", _jpeg(), "image/jpeg")}
    client.post("/api/fork/sessions/s1/reference-photos", files=files, data={"kind": "detail"})
    refs = tmp_path / "default" / "processed" / "s1_refs"
    assert refs.exists()
    assert client.delete("/api/sessions/s1").status_code == 200
    assert not refs.exists()
