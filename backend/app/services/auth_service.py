import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
from typing import Any

from fastapi import HTTPException, Request, status

from app.core.config import Settings
from app.core.database import DatabaseManager

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PBKDF2_ITERATIONS = 180_000


def validate_email_format(email: str) -> str:
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Please enter a valid email address.",
        )
    return cleaned


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iter_str, salt_hex, hash_hex = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode(text + padding)


def create_access_token(user_id: str, email: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=settings.auth_token_expire_hours)
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload = _b64url_encode(
        json.dumps(
            {
                "sub": user_id,
                "email": email,
                "iat": int(now.timestamp()),
                "exp": int(exp.timestamp()),
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(settings.auth_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url_encode(sig)}"


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".", 2)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(settings.auth_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise ValueError("Invalid token signature")
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed authentication token.",
        ) from exc

    exp = int(payload.get("exp") or 0)
    if exp <= int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        )
    return payload


def _extract_token_from_request(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        tok = auth_header[7:].strip()
        if tok:
            return tok
    query_tok = request.query_params.get("token")
    if query_tok:
        return query_tok.strip()
    return None


async def get_optional_user(request: Request) -> dict[str, Any] | None:
    token = _extract_token_from_request(request)
    if not token:
        return None
    settings: Settings = request.app.state.settings
    db: DatabaseManager = request.app.state.db
    payload = decode_access_token(token, settings)
    user = await db.get_user_by_id(str(payload.get("sub", "")))
    return user


async def get_current_user(request: Request) -> dict[str, Any]:
    user = await get_optional_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
        )
    return user
