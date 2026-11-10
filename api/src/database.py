from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from api.src.config import settings


class Base(DeclarativeBase):
    pass


# Application engine connects as non-owner role (axiom_app)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

# Admin engine connects as table owner (postgres) for migrations and setup
admin_engine = create_engine(
    settings.ADMIN_DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AdminSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=admin_engine)


def set_tenant_context(session: Session, tenant_id: str) -> None:
    """Sets PostgreSQL local tenant_id for transaction-scoped Row-Level Security."""
    bind = session.get_bind()
    if bind and bind.dialect.name == "postgresql":
        session.execute(
            text("SET LOCAL app.tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )


def get_tenant_db(tenant_id: str) -> Generator[Session, None, None]:
    """Database session generator scoped to a specific tenant via RLS."""
    session = SessionLocal()
    try:
        set_tenant_context(session, tenant_id)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_admin_db() -> Generator[Session, None, None]:
    """Admin database session generator (table owner role, bypasses RLS for admin maintenance)."""
    session = AdminSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

