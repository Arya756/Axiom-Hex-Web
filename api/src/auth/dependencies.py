from typing import Callable, Generator, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from api.src.auth.jwt import decode_access_token
from api.src.database import get_admin_db, get_tenant_db
from api.src.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_admin_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        if user_id is None or tenant_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if user is None:
        raise credentials_exception
    return user


def get_db(
    current_user: User = Depends(get_current_user),
) -> Generator[Session, None, None]:
    """Database dependency executing SET LOCAL app.tenant_id = :tenant_id at transaction start."""
    yield from get_tenant_db(current_user.tenant_id)


def require_roles(allowed_roles: List[str]) -> Callable[[User], User]:
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: one of {allowed_roles}, got: '{current_user.role}'",
            )
        return current_user

    return role_checker


# Role dependencies for the 4 PRD seeded roles:
require_admin = require_roles(["admin"])
require_creator = require_roles(["creator", "admin"])
require_reviewer = require_roles(["reviewer", "admin"])
require_legal_reviewer = require_roles(["legal_reviewer", "admin"])

