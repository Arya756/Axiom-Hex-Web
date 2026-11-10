import os
import sys

# Ensure repository root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import api.src.database as db_module
from api.src.auth.dependencies import get_admin_db, get_db
from api.src.auth.jwt import hash_password
from api.src.database import Base
from api.src.main import app
from api.src.models.tenant import Tenant
from api.src.models.user import User

# Use in-memory SQLite for fast, self-contained testing when Postgres is not running
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DB_URL else {},
    poolclass=StaticPool if "sqlite" in TEST_DB_URL else None,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Monkey-patch database SessionLocal so background tasks use test_engine
db_module.SessionLocal = TestingSessionLocal
db_module.AdminSessionLocal = TestingSessionLocal
db_module.engine = test_engine
db_module.admin_engine = test_engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)

    # Seed initial tenants and users for testing
    with TestingSessionLocal() as session:
        t_meridian = Tenant(id="tenant_meridian", name="Meridian Flow", ruleset_version=1)
        t_acme = Tenant(id="tenant_acme", name="Acme Corporation", ruleset_version=1)
        session.add_all([t_meridian, t_acme])
        session.flush()

        pwd_hash = hash_password("password123")
        users = [
            User(id="u_admin", tenant_id="tenant_meridian", email="admin@meridian.flow", hashed_password=pwd_hash, name="Admin", role="admin"),
            User(id="u_creator", tenant_id="tenant_meridian", email="creator@meridian.flow", hashed_password=pwd_hash, name="Creator", role="creator"),
            User(id="u_reviewer", tenant_id="tenant_meridian", email="reviewer@meridian.flow", hashed_password=pwd_hash, name="Reviewer", role="reviewer"),
            User(id="u_legal", tenant_id="tenant_meridian", email="legal@meridian.flow", hashed_password=pwd_hash, name="Legal", role="legal_reviewer"),
            # Tenant B users
            User(id="u_acme_admin", tenant_id="tenant_acme", email="admin@acme.com", hashed_password=pwd_hash, name="Acme Admin", role="admin"),
            User(id="u_acme_creator", tenant_id="tenant_acme", email="creator@acme.com", hashed_password=pwd_hash, name="Acme Creator", role="creator"),
        ]
        session.add_all(users)
        session.commit()

    yield

    Base.metadata.drop_all(bind=test_engine)



@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_admin_db():
        yield db_session

    def override_get_db():
        # In real Postgres, SET LOCAL app.tenant_id is executed.
        # In SQLite, test_engine is connected.
        yield db_session

    app.dependency_overrides[get_admin_db] = override_admin_db
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
