from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.auth.dependencies import get_current_user
from app.features.auth.model import User
from app.features.auth.schema import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from app.features.auth.throttle import enforce_login_throttle
from app.features.auth.service import (
    InvalidCredentials,
    RegistrationConflict,
    login,
    register,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", status_code=201, response_model=RegisterResponse)
async def register_route(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        return await register(db, payload)
    except RegistrationConflict:
        raise HTTPException(
            status_code=409,
            detail="Email or organization slug already exists",
        ) from None


@router.post("/login", response_model=TokenResponse)
async def login_route(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    await enforce_login_throttle(request, str(payload.email))
    try:
        token = await login(db, str(payload.email), payload.password)
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me_route(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
