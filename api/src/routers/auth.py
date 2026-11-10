from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.src.auth.dependencies import get_current_user
from api.src.auth.jwt import create_access_token, verify_password
from api.src.database import get_admin_db
from api.src.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_id: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_admin_db)):
    query = db.query(User).filter(User.email == request.email)
    if request.tenant_id:
        query = query.filter(User.tenant_id == request.tenant_id)
    user = query.first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            name=user.name,
            role=user.role,
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
    )

