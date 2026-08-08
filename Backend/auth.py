"""auth.py — password hashing + JWT helpers, and a FastAPI dependency
that resolves the current user from the Authorization header."""

import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException
from db import get_cursor

JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set. Add a long random string to your environment.")

JWT_ALGO = "HS256"
JWT_EXPIRES_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRES_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    token = authorization.removeprefix("Bearer ").strip()
    user_id = decode_token(token)

    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


def require_admin(user=None):
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required for this action.")
    return user


def public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "name": u["name"],
        "email": u["email"],
        "role": u["role"],
        "z_threshold": u["z_threshold"],
    }
