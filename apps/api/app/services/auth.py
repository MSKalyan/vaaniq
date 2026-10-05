"""Authentication business logic: register, login, refresh, logout."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    CredentialsError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair


class AuthError(Exception):
    pass


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def register(db: AsyncSession, data: RegisterRequest) -> User:
    existing = await db.scalar(select(User).where(User.email == data.email.lower()))
    if existing is not None:
        raise AuthError("Email already registered")

    user = User(
        email=data.email.lower(),
        name=data.name,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, data: LoginRequest) -> User:
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not verify_password(data.password, user.hashed_password):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account disabled")
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> TokenPair:
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    await db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
    )
    await db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


async def rotate_refresh(db: AsyncSession, refresh_token: str) -> TokenPair:
    """Validate + rotate a refresh token, issuing a new pair."""
    token_hash = _hash_refresh(refresh_token)
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if stored is None or stored.revoked or stored.is_expired:
        raise CredentialsError("Invalid or expired refresh token")

    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except CredentialsError as exc:
        raise CredentialsError("Invalid refresh token") from exc

    user_id = uuid.UUID(payload["sub"])
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise CredentialsError("User no longer active")

    # Rotate: revoke current, issue new.
    stored.revoked = True
    return await issue_token_pair(db, user)


async def revoke_refresh(db: AsyncSession, refresh_token: str) -> None:
    token_hash = _hash_refresh(refresh_token)
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if stored is not None:
        stored.revoked = True
        await db.commit()
