"""Organization structure: departments, positions, areas (read + admin CRUD)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth, db

router = APIRouter(prefix="/api", tags=["org"])


class OrgIn(BaseModel):
    code: str | None = None
    name: str
    parent_id: int | None = None


def _list(table: str):
    return db.query(f"SELECT id, code, name, parent_id FROM {table} ORDER BY name")


@router.get("/departments")
def departments(user: dict = Depends(auth.get_current_user)):
    ids = auth.scope_dept_ids(user)
    if ids is None:
        return _list("department")
    if not ids:
        return []
    return db.query(
        "SELECT id, code, name, parent_id FROM department "
        "WHERE id = ANY(%s) ORDER BY name", (ids,))


@router.get("/positions")
def positions(user: dict = Depends(auth.get_current_user)):
    return _list("position")


@router.get("/areas")
def areas(user: dict = Depends(auth.get_current_user)):
    return _list("area")


# --- admin CRUD for departments (positions/areas mirror if needed) --- #
@router.post("/departments")
def create_department(body: OrgIn, user: dict = Depends(auth.require_admin)):
    rows = db.query(
        "INSERT INTO department (id, code, name, parent_id) VALUES "
        "((SELECT COALESCE(MAX(id),0)+1 FROM department), %s,%s,%s) "
        "RETURNING id, code, name, parent_id",
        (body.code, body.name, body.parent_id))
    return rows[0]


@router.put("/departments/{dept_id}")
def update_department(dept_id: int, body: OrgIn,
                      user: dict = Depends(auth.require_admin)):
    n = db.execute("UPDATE department SET code=%s, name=%s, parent_id=%s WHERE id=%s",
                   (body.code, body.name, body.parent_id, dept_id))
    if not n:
        raise HTTPException(404, "Department not found")
    return {"ok": True}


@router.delete("/departments/{dept_id}")
def delete_department(dept_id: int, user: dict = Depends(auth.require_admin)):
    db.execute("DELETE FROM department WHERE id=%s", (dept_id,))
    return {"ok": True}
