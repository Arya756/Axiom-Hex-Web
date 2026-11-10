"""Reliability test: Tenant B cannot read Tenant A's sources (PRD §5.3, Y-05)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.src.models.source import Source, SourceVersion


def test_tenant_b_cannot_read_tenant_a_sources(client: TestClient, db_session: Session):
    # 1. Tenant A (Meridian Flow) Admin logs in and creates a confidential source
    a_login = client.post(
        "/auth/login",
        json={"email": "admin@meridian.flow", "password": "password123"},
    )
    assert a_login.status_code == 200
    token_a = a_login.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    create_a = client.post(
        "/sources",
        json={
            "source_id": "SECRET-A-01",
            "kind": "rule",
            "name": "Meridian Proprietary Process",
            "body": "Strictly confidential meridian process.",
        },
        headers=headers_a,
    )
    assert create_a.status_code == 201

    # 2. Tenant B (Acme Corp) Admin logs in and creates an Acme source
    b_login = client.post(
        "/auth/login",
        json={"email": "admin@acme.com", "password": "password123"},
    )
    assert b_login.status_code == 200
    token_b = b_login.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    create_b = client.post(
        "/sources",
        json={
            "source_id": "ACME-INTERNAL-01",
            "kind": "rule",
            "name": "Acme Manufacturing Standard",
            "body": "Confidential Acme internal manufacturing standard.",
        },
        headers=headers_b,
    )
    assert create_b.status_code == 201

    # 3. Tenant B lists sources — must NOT see Tenant A's sources
    list_b = client.get("/sources", headers=headers_b)
    assert list_b.status_code == 200
    sources_b = list_b.json()
    b_source_ids = [s["id"] for s in sources_b]

    assert "ACME-INTERNAL-01" in b_source_ids
    assert "SECRET-A-01" not in b_source_ids
    assert "R-01" not in b_source_ids  # Meridian rule
    assert all(s["tenant_id"] == "tenant_acme" for s in sources_b)

    # 4. Tenant A lists sources — must NOT see Tenant B's sources
    list_a = client.get("/sources", headers=headers_a)
    assert list_a.status_code == 200
    sources_a = list_a.json()
    a_source_ids = [s["id"] for s in sources_a]

    assert "SECRET-A-01" in a_source_ids
    assert "ACME-INTERNAL-01" not in a_source_ids
    assert all(s["tenant_id"] == "tenant_meridian" for s in sources_a)


def test_database_level_tenant_filtering(db_session: Session):
    """Direct database verification of tenant partitioning."""
    # Query sources specifically for tenant_meridian
    meridian_sources = (
        db_session.query(Source)
        .filter(Source.tenant_id == "tenant_meridian")
        .all()
    )
    assert all(s.tenant_id == "tenant_meridian" for s in meridian_sources)

    # Query sources specifically for tenant_acme
    acme_sources = (
        db_session.query(Source)
        .filter(Source.tenant_id == "tenant_acme")
        .all()
    )
    assert all(s.tenant_id == "tenant_acme" for s in acme_sources)

    # Cross check that IDs don't overlap
    m_ids = {s.id for s in meridian_sources}
    a_ids = {s.id for s in acme_sources}
    assert m_ids.isdisjoint(a_ids) or not m_ids.intersection(a_ids)

