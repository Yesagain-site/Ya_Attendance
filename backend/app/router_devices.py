"""Device management + orders (Phase 5, admin write actions)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import audit, auth, commands, db

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _queue(sn: str, content: str, kind: str) -> int:
    return db.query(
        "INSERT INTO device_command (sn, content, kind, status) "
        "VALUES (%s,%s,%s,'pending') RETURNING id", (sn, content, kind))[0]["id"]


def _device_or_404(sn: str):
    if not db.query("SELECT 1 FROM device WHERE sn=%s", (sn,)):
        raise HTTPException(404, "Device not found")


class DeviceIn(BaseModel):
    name: str | None = None
    ip: str | None = None
    area_id: int | None = None
    direction: str | None = None   # 'in' | 'out' | 'both'


@router.put("/{sn}")
def update_device(sn: str, body: DeviceIn, user: dict = Depends(auth.require_admin)):
    _device_or_404(sn)
    fields, params = [], []
    for col in ("name", "ip", "area_id", "direction"):
        v = getattr(body, col)
        if v is not None:
            fields.append(f"{col}=%s")
            params.append(v)
    if fields:
        params.append(sn)
        db.execute(f"UPDATE device SET {', '.join(fields)} WHERE sn=%s", tuple(params))
        audit.log(user["id"], "update_device", f"device:{sn}", str(body.dict(exclude_none=True)))
    return {"ok": True}


# ------------------------------ commands log ------------------------------ #
@router.get("/{sn}/commands")
def list_commands(sn: str, limit: int = 50, user: dict = Depends(auth.get_current_user)):
    return db.query(
        "SELECT id, kind, status, return_code, queued_at, sent_at, return_at, "
        "left(content, 80) AS preview FROM device_command "
        "WHERE sn=%s ORDER BY id DESC LIMIT %s", (sn, min(limit, 500)))


@router.delete("/{sn}/commands/pending")
def clear_pending(sn: str, user: dict = Depends(auth.require_admin)):
    n = db.execute("DELETE FROM device_command WHERE sn=%s AND status='pending'", (sn,))
    return {"ok": True, "cleared": n}


# ------------------------------ orders ------------------------------ #
class EnrollIn(BaseModel):
    pins: list[str]
    with_face: bool = True


@router.post("/{sn}/enroll")
def enroll(sn: str, body: EnrollIn, user: dict = Depends(auth.require_admin)):
    _device_or_404(sn)
    queued, faces = 0, 0
    for pin in body.pins:
        emp = db.query("SELECT pin, name, privilege, card FROM employees WHERE pin=%s", (pin,))
        if not emp:
            continue
        _queue(sn, commands.user_body(emp[0]), "user")
        queued += 1
        if body.with_face:
            tmpls = db.query(
                "SELECT pin, bio_no, bio_index, bio_type, major_ver, minor_ver, "
                "bio_format, valid, template FROM biotemplate WHERE pin=%s", (pin,))
            for t in tmpls:
                _queue(sn, commands.biodata_body(t), "biodata")
                faces += 1
    audit.log(user["id"], "enroll", f"device:{sn}", f"{queued} users, {faces} faces")
    return {"ok": True, "users_queued": queued, "faces_queued": faces}


@router.post("/{sn}/sync-all")
def sync_all(sn: str, with_face: bool = True, user: dict = Depends(auth.require_admin)):
    _device_or_404(sn)
    pins = [r["pin"] for r in db.query("SELECT pin FROM employees WHERE active ORDER BY pin")]
    return enroll(sn, EnrollIn(pins=pins, with_face=with_face), user)


class PinsIn(BaseModel):
    pins: list[str]


@router.post("/{sn}/delete-users")
def delete_users(sn: str, body: PinsIn, user: dict = Depends(auth.require_admin)):
    _device_or_404(sn)
    for pin in body.pins:
        _queue(sn, commands.delete_user_body(pin), "delete")
    return {"ok": True, "queued": len(body.pins)}


class MenuIn(BaseModel):
    command: str


@router.post("/{sn}/menu")
def menu(sn: str, body: MenuIn, user: dict = Depends(auth.require_admin)):
    _device_or_404(sn)
    raw = commands.menu_body(body.command)
    if raw is None:
        raise HTTPException(400, f"Unknown/again-not-allowed command: {body.command}")
    cid = _queue(sn, raw, "menu")
    audit.log(user["id"], "device_menu", f"device:{sn}", raw)
    return {"ok": True, "command_id": cid, "sent": raw}
