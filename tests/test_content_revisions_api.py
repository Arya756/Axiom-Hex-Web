import hashlib
import io
from fastapi.testclient import TestClient


def test_content_upload_and_revision(client: TestClient):
    # 1. Login as creator
    login_resp = client.post(
        "/auth/login",
        json={"email": "creator@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload valid markdown draft
    content_bytes = b"# Meridian Product Brief\nMeridian Flow Platform delivers 99.95% uptime."
    expected_hash = hashlib.sha256(content_bytes).hexdigest()

    resp = client.post(
        "/content",
        data={"title": "Q3 Marketing Draft", "sensitivity": "internal"},
        files={"file": ("draft.md", io.BytesIO(content_bytes), "text/markdown")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    content_id = data["id"]
    assert data["title"] == "Q3 Marketing Draft"
    assert data["sensitivity"] == "internal"
    assert data["file_type"] == "md"
    assert len(data["revisions"]) == 1
    rev1 = data["revisions"][0]
    assert rev1["version_num"] == 1
    assert rev1["content_hash"] == expected_hash
    assert rev1["status"] == "draft"

    # 3. Create Revision 2 via POST /content/{id}/revisions
    v2_bytes = b"# Meridian Product Brief\nUpdated revision content."
    v2_hash = hashlib.sha256(v2_bytes).hexdigest()

    rev2_resp = client.post(
        f"/content/{content_id}/revisions",
        files={"file": ("draft_v2.md", io.BytesIO(v2_bytes), "text/markdown")},
        headers=headers,
    )
    assert rev2_resp.status_code == 201, rev2_resp.text
    rev2_data = rev2_resp.json()
    assert rev2_data["version_num"] == 2
    assert rev2_data["content_hash"] == v2_hash
    assert rev2_data["status"] == "draft"

    # 4. GET /content returns list with revisions
    list_resp = client.get("/content", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    matching = [item for item in items if item["id"] == content_id]
    assert len(matching) == 1
    assert len(matching[0]["revisions"]) == 2


def test_content_upload_type_allowlist_enforced(client: TestClient):
    login_resp = client.post(
        "/auth/login",
        json={"email": "creator@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Disallowed executable file
    resp = client.post(
        "/content",
        data={"title": "Malicious Executable"},
        files={"file": ("exploit.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 415
    assert "Unsupported file type" in resp.json()["detail"]


def test_content_upload_invalid_sensitivity(client: TestClient):
    login_resp = client.post(
        "/auth/login",
        json={"email": "creator@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/content",
        data={"title": "Bad Sensitivity", "sensitivity": "top_secret_invalid"},
        files={"file": ("draft.md", io.BytesIO(b"sample text"), "text/markdown")},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "Invalid sensitivity" in resp.json()["detail"]

