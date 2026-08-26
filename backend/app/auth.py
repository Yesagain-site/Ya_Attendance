"""
Auth: JWT login, password hashing, role + department-scope dependencies.

Roles:
  • admin   — full access, configures everything.
  • manager — scoped to assigned departments (manager_department).
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from . import db

SECRET_KEY = os.environ.get("JWT_SECRET", "dev-insecure-change-me")
ALGORITHM = "HS256"
# 0 = tokens never expire (per requirement). Set JWT_HOURS>0 to re-enable expiry.
TOKEN_HOURS = int(os.environ.get("JWT_HOURS", "0"))

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(p: str) -> str:
    # bcrypt caps input at 72 bytes; truncate defensively.
    return bcrypt.hashpw(p.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8")[:72], h.encode("utf-8"))
    except Exception:
        return False


def make_token(user: dict) -> str:
    payload = {"sub": str(user["id"]), "username": user["username"],
               "role": user["role"]}
    if TOKEN_HOURS > 0:  # otherwise no `exp` claim → token never expires
        payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def seed_admin():
    """Create a default admin on first boot if no users exist."""
    n = db.query("SELECT count(*) AS c FROM app_user")[0]["c"]
    if n == 0:
        username = os.environ.get("ADMIN_USER", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "admin123")
        db.execute(
            "INSERT INTO app_user (username, password_hash, role, full_name) "
            "VALUES (%s,%s,'admin','Administrator')",
            (username, hash_password(password)),
        )
        print(f"[auth] seeded default admin '{username}' "
              f"(password '{password}') — change it!", flush=True)


def authenticate(username: str, password: str) -> dict | None:
    rows = db.query(
        "SELECT id, username, password_hash, role, full_name, active "
        "FROM app_user WHERE username=%s", (username,))
    if not rows:
        return None
    u = rows[0]
    if not u["active"] or not verify_password(password, u["password_hash"]):
        return None
    return u


# ------------------------- dependencies ------------------------- #
def get_current_user(token: str | None = Depends(oauth2)) -> dict:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    rows = db.query(
        "SELECT id, username, role, full_name, active FROM app_user WHERE id=%s",
        (uid,))
    if not rows or not rows[0]["active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found/inactive")
    return rows[0]


def decode_token(token: str) -> dict | None:
    """Validate a raw token string (e.g. from a query param) → user row or None."""
    if not token:
        return None
    try:
        uid = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError):
        return None
    rows = db.query("SELECT id, username, role, active FROM app_user WHERE id=%s", (uid,))
    return rows[0] if rows and rows[0]["active"] else None


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


def scope_dept_ids(user: dict) -> list[int] | None:
    """None => unrestricted (admin). Otherwise the manager's department ids."""
    if user["role"] == "admin":
        return None
    rows = db.query("SELECT dept_id FROM manager_department WHERE user_id=%s",
                    (user["id"],))
    return [r["dept_id"] for r in rows]
