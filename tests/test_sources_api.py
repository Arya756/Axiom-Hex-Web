from fastapi.testclient import TestClient


def test_create_source_and_idempotency(client: TestClient):
    # 1. Login as admin
    admin_login = client.post(
        "/auth/login",
        json={"email": "admin@meridian.flow", "password": "password123"},
    )
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Create source R-01
    source_payload = {
        "source_id": "R-01",
        "kind": "rule",
        "name": "Product Terminology",
        "description": "Terminology guidelines",
        "body": "Always use 'Meridian Flow Platform', never 'MFP'.",
    }

    create_resp = client.post("/sources", json=source_payload, headers=headers)
    assert create_resp.status_code == 201, create_resp.text
    data = create_resp.json()
    assert data["id"] == "R-01"
    assert data["tenant_id"] == "tenant_meridian"
    assert data["current_version"] == 1
    assert len(data["versions"]) == 1
    assert data["versions"][0]["body"] == "Always use 'Meridian Flow Platform', never 'MFP'."

    # 3. Idempotency test: Re-import identical payload
    reimport_resp = client.post("/sources", json=source_payload, headers=headers)
    assert reimport_resp.status_code == 201
    reimport_data = reimport_resp.json()
    # Must NOT have created a second version
    assert reimport_data["current_version"] == 1
    assert len(reimport_data["versions"]) == 1

    # 4. New version with changed body
    v2_payload = {
        "source_id": "R-01",
        "kind": "rule",
        "name": "Product Terminology",
        "description": "Terminology guidelines",
        "body": "Always use 'Meridian Flow Platform', never 'MFP' or 'M-Flow'.",
    }
    v2_resp = client.post("/sources", json=v2_payload, headers=headers)
    assert v2_resp.status_code == 201
    v2_data = v2_resp.json()
    assert v2_data["current_version"] == 2
    assert len(v2_data["versions"]) == 2


def test_sources_rbac_non_admin_blocked(client: TestClient):
    # Login as creator (creator role cannot create sources, only admin can)
    creator_login = client.post(
        "/auth/login",
        json={"email": "creator@meridian.flow", "password": "password123"},
    )
    creator_token = creator_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {creator_token}"}

    source_payload = {
        "source_id": "R-99",
        "kind": "rule",
        "name": "Unauthorized Rule",
        "body": "This should be blocked.",
    }

    resp = client.post("/sources", json=source_payload, headers=headers)
    assert resp.status_code == 403
    assert "Operation not permitted" in resp.json()["detail"]


def test_list_sources(client: TestClient):
    # Login as reviewer
    login_resp = client.post(
        "/auth/login",
        json={"email": "reviewer@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/sources", headers=headers)
    assert resp.status_code == 200
    sources = resp.json()
    assert isinstance(sources, list)
    assert any(s["id"] == "R-01" for s in sources)

