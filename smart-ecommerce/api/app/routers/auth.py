from functools import lru_cache

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import User, utcnow
from ..schemas import Auth0In, LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from ..security import (create_access_token, create_refresh_token, decode_token, hash_password,
                        unusable_password, verify_password)
from ..services.notifications import notify

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user: User, include_user: bool = True) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user) if include_user else None,
    )


def _get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if _get_by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(name=body.name.strip(), email=body.email.lower(), password=hash_password(body.password),
                role="customer", auth_provider="local", is_active=True, is_staff=False, is_superuser=False)
    db.add(user)
    db.commit()
    notify(db, user.id, "welcome", f"Welcome to Smart Shop, {user.name}!", email_subject="Welcome to Smart Shop")
    return _tokens(user)


def _authenticate(db: Session, email: str, password: str) -> User:
    user = _get_by_email(db, email)
    if not user or not user.is_active or not verify_password(password, user.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    user.last_login = utcnow()
    db.commit()
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    return _tokens(_authenticate(db, body.email, body.password))


@router.post("/token", include_in_schema=True)
def token_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password flow - used by the Swagger 'Authorize' button (username = email)."""
    user = _authenticate(db, form.username, form.password)
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer"}


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _tokens(user, include_user=False)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@lru_cache(maxsize=1)
def _jwks_client():
    return jwt.PyJWKClient(f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json")


@router.post("/auth0", response_model=TokenOut)
def auth0_login(body: Auth0In, db: Session = Depends(get_db)):
    """
    Social login (Google / Facebook) through Auth0. The frontend redirects to Auth0 Universal
    Login and receives an ID token; we verify its signature/issuer/audience and exchange it for our own JWTs.
    """
    if not settings.AUTH0_DOMAIN or not settings.AUTH0_CLIENT_ID:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Auth0 is not configured")
    try:
        key = _jwks_client().get_signing_key_from_jwt(body.id_token).key
        claims = jwt.decode(body.id_token, key, algorithms=["RS256"], audience=settings.AUTH0_CLIENT_ID,
                            issuer=f"https://{settings.AUTH0_DOMAIN}/")
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid Auth0 token: {exc}")
    if body.nonce and claims.get("nonce") != body.nonce:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nonce mismatch")
    email = claims.get("email")
    if not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your social account did not share an email address")

    user = _get_by_email(db, email)
    if user is None:
        user = User(name=claims.get("name") or email.split("@")[0], email=email.lower(),
                    password=unusable_password(), role="customer", auth_provider="auth0",
                    is_active=True, is_staff=False, is_superuser=False)
        db.add(user)
        db.commit()
        notify(db, user.id, "welcome", f"Welcome to Smart Shop, {user.name}!", email_subject="Welcome to Smart Shop")
    elif not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    user.last_login = utcnow()
    db.commit()
    return _tokens(user)
