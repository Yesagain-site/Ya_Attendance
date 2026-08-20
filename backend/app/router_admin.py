"""System / admin: users & roles, manager-department scoping, audit log."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import audit, auth, db

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserIn(BaseModel):
    username: str | None = None
    password: str | None = None
    role: str | None = None          # 'admin' | 'manager'
    full_name: str | None = None
    active: bool | None = None
    department_ids: list[int] | None = None


def _user_row(uid: int):
    rows = db.query(
        "SELECT id, username, role, full_name, active FROM app_user WHERE id=%s", (uid,))
    if not rows:
        return None
    u = rows[0]
    u["department_ids"] = [r["dept_id"] for r in
        db.query("SELECT dept_id FROM manager_department WHERE user_id=%s", (uid,))]
    return u


@router.get("/users")
def list_users(user: dict = Depends(auth.require_admin)):
    users = db.query("SELECT id, username, role, full_name, active FROM app_user ORDER BY id")
    for u in users:
        u["department_ids"] = [r["dept_id"] for r in
            db.query("SELECT dept_id FROM manager_department WHERE user_id=%s", (u["id"],))]
    return users


@router.post("/users")
def create_user(body: UserIn, user: dict = Depends(auth.require_admin)):
    if not body.username or not body.password:
        raise HTTPException(400, "username and password required")
    if db.query("SELECT 1 FROM app_user WHERE username=%s", (body.username,)):
        raise HTTPException(409, "username exists")
    uid = db.query(
        "INSERT INTO app_user (username, password_hash, role, full_name, active) "
        "VALUES (%s,%s,%s,%s, COALESCE(%s, TRUE)) RETURNING id",
        (body.username, auth.hash_password(body.password), body.role or "manager",
         body.full_name, body.active))[0]["id"]
    _set_depts(uid, body.department_ids)
    audit.log(user["id"], "create_user", "app_user", body.username)
    return _user_row(uid)


@router.put("/users/{uid}")
def update_user(uid: int, body: UserIn, user: dict = Depends(auth.require_admin)):
    if not db.query("SELECT 1 FROM app_user WHERE id=%s", (uid,)):
        raise HTTPException(404, "User not found")
    fields, params = [], []
    for col in ("role", "full_name", "active"):
        v = getattr(body, col)
        if v is not None:
            fields.append(f"{col}=%s"); params.append(v)
    if body.password:
        fields.append("password_hash=%s"); params.append(auth.hash_password(body.password))
    if fields:
        params.append(uid)
        db.execute(f"UPDATE app_user SET {', '.join(fields)} WHERE id=%s", tuple(params))
    if body.department_ids is not None:
        _set_depts(uid, body.department_ids)
    audit.log(user["id"], "update_user", "app_user", str(uid))
    return _user_row(uid)


@router.delete("/users/{uid}")
def delete_user(uid: int, user: dict = Depends(auth.require_admin)):
    if uid == user["id"]:
        raise HTTPException(400, "Cannot delete yourself")
    db.execute("DELETE FROM app_user WHERE id=%s", (uid,))
    audit.log(user["id"], "delete_user", "app_user", str(uid))
    return {"ok": True}


def _set_depts(uid: int, dept_ids):
    if dept_ids is None:
        return
    db.execute("DELETE FROM manager_department WHERE user_id=%s", (uid,))
    for d in dept_ids:
        db.execute("INSERT INTO manager_department (user_id, dept_id) VALUES (%s,%s) "
                   "ON CONFLICT DO NOTHING", (uid, d))


class PwIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(body: PwIn, user: dict = Depends(auth.get_current_user)):
    row = db.query("SELECT password_hash FROM app_user WHERE id=%s", (user["id"],))[0]
    if not auth.verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(400, "Current password is wrong")
    db.execute("UPDATE app_user SET password_hash=%s WHERE id=%s",
               (auth.hash_password(body.new_password), user["id"]))
    audit.log(user["id"], "change_password", "app_user", user["username"])
    return {"ok": True}


@router.get("/audit")
def audit_log(limit: int = 100, user: dict = Depends(auth.require_admin)):
    return db.query(
        "SELECT a.id, a.action, a.entity, a.detail, a.ts, u.username "
        "FROM audit_log a LEFT JOIN app_user u ON u.id = a.user_id "
        "ORDER BY a.id DESC LIMIT %s", (min(limit, 500),))
