import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.database import DatabaseManager, utc_now
from app.models.schemas import AuthTokenOut, UserLoginIn, UserOut, UserRegisterIn
from app.services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    validate_email_format,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _serialize_user(doc: dict) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        created_at=doc["created_at"],
    )


@router.post("/register", response_model=AuthTokenOut, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserRegisterIn, request: Request) -> AuthTokenOut:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings

    email = validate_email_format(payload.email)
    existing = await db.get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Please sign in instead.",
        )

    user_id = uuid.uuid4().hex[:16]
    user_doc = {
        "_id": user_id,
        "name": payload.name.strip(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "created_at": utc_now(),
    }
    try:
        await db.create_user(user_doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    token = create_access_token(user_id, email, settings)
    return AuthTokenOut(access_token=token, user=_serialize_user(user_doc))


@router.post("/login", response_model=AuthTokenOut)
async def login_user(payload: UserLoginIn, request: Request) -> AuthTokenOut:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings

    email = validate_email_format(payload.email)
    user_doc = await db.get_user_by_email(email)
    if not user_doc or not verify_password(payload.password, user_doc.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(str(user_doc["_id"]), email, settings)
    return AuthTokenOut(access_token=token, user=_serialize_user(user_doc))


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)) -> UserOut:
    return _serialize_user(current_user)
