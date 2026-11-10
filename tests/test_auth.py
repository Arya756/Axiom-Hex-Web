from fastapi.testclient import TestClient

from api.src.auth.jwt import decode_access_token


def test_login_successful_and_jwt_claims(client: TestClient):
    response = client.post(
        "/auth/login",
        json={"email": "admin@meridian.flow", "password": "password123"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@meridian.flow"
    assert data["user"]["role"] == "admin"
    assert data["user"]["tenant_id"] == "tenant_meridian"

    # Decode and verify JWT claims
    claims = decode_access_token(data["access_token"])
    assert claims["sub"] == "u_admin"
    assert claims["role"] == "admin"
    assert claims["tenant_id"] == "tenant_meridian"


def test_login_four_seeded_roles(client: TestClient):
    roles_to_test = [
        ("admin@meridian.flow", "admin"),
        ("creator@meridian.flow", "creator"),
        ("reviewer@meridian.flow", "reviewer"),
        ("legal@meridian.flow", "legal_reviewer"),
    ]
    for email, expected_role in roles_to_test:
        response = client.post(
            "/auth/login",
            json={"email": email, "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["role"] == expected_role


def test_login_invalid_password(client: TestClient):
    response = client.post(
        "/auth/login",
        json={"email": "admin@meridian.flow", "password": "wrong_password"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_get_me_endpoint(client: TestClient):
    login_resp = client.post(
        "/auth/login",
        json={"email": "creator@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "creator@meridian.flow"
    assert user_data["role"] == "creator"
    assert user_data["tenant_id"] == "tenant_meridian"

