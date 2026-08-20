"""
Device-facing ADMS / iclock server (Phase 1 — READ ONLY).

The 2 Horus TL2 terminals push to us over the ZKTeco ADMS/iclock HTTP protocol.
This router receives that traffic and writes it into our DB:

    GET  /iclock/cdata       handshake  -> options; upsert device, mark online
    POST /iclock/cdata       uploads    -> ATTLOG => attendance, USER => employees
    GET  /iclock/getrequest  cmd poll   -> read-only: no orders yet ("OK")
    POST /iclock/devicecmd   cmd result -> (Phase 5) update device_command

Read-only: getrequest never dispenses commands in this phase, so we never
change anything on the devices.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from . import db

router = APIRouter(prefix="/iclock", tags=["adms"])

PUNCH_STATE = {0: "Check-In", 1: "Check-Out", 2: "Break-Out",
               3: "Break-In", 4: "OT-In", 5: "OT-Out"}
VERIFY_MODE = {0: "Password", 1: "Fingerprint", 2: "Card", 15: "Face"}
PRIVILEGE = {0: "User", 14: "Admin"}


def _sn(request: Request) -> str:
    q = request.query_params
    return q.get("SN") or q.get("sn") or "UNKNOWN"


def touch_device(sn: str, ip: str | None = None):
    """Mark the device online on any contact. NOTE: `ip` is ignored — behind
    Docker the source IP is the bridge gateway, not the terminal's LAN IP.
    The real IP comes from the device INFO push or a manual edit."""
    db.execute(
        """INSERT INTO device (sn, online, last_seen)
           VALUES (%s, TRUE, now())
           ON CONFLICT (sn) DO UPDATE SET online = TRUE, last_seen = now()""",
        (sn,),
    )


def mark_data(sn: str):
    db.execute("UPDATE device SET last_data_at = now() WHERE sn = %s", (sn,))


def mark_cmd(sn: str):
    db.execute("UPDATE device SET last_cmd_at = now() WHERE sn = %s", (sn,))


def _apply_device_info(sn: str, info: dict):
    """Update counts / firmware from a device INFO push when present."""
    def as_int(*keys):
        for k in keys:
            if k in info:
                try:
                    return int(info[k])
                except ValueError:
                    return None
        return None
    users = as_int("UserCount", "userCount")
    faces = as_int("FaceCount", "faceCount")
    fps = as_int("FPCount", "fpCount")
    trans = as_int("TransactionCount", "transactionCount", "AttLogCount")
    fw = info.get("FWVersion") or info.get("FirmwareVersion")
    ip = info.get("IPAddress") or info.get("IP") or info.get("ip")
    db.execute(
        """UPDATE device SET
               user_count = COALESCE(%s, user_count),
               face_count = COALESCE(%s, face_count),
               fp_count   = COALESCE(%s, fp_count),
               transaction_count = COALESCE(%s, transaction_count),
               firmware   = COALESCE(%s, firmware),
               ip         = COALESCE(NULLIF(%s,''), ip),
               settings   = settings || %s::jsonb
           WHERE sn = %s""",
        (users, faces, fps, trans, fw, ip, _json(info), sn),
    )


def _json(d: dict) -> str:
    import json
    # keep it small; only string-ish values
    return json.dumps({k: v for k, v in d.items() if len(str(v)) < 200})


# --------------------------- parsers --------------------------- #
def ingest_attlog(sn: str, body: str) -> int:
    n = 0
    sql = """INSERT INTO attendance
                 (device_sn, pin, punch_time, punch, punch_name, verify, verify_name)
             VALUES (%s,%s,%s,%s,%s,%s,%s)
             ON CONFLICT (device_sn, pin, punch_time) DO NOTHING"""
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        p = line.split("\t")
        if len(p) < 2:
            continue
        pin, when = p[0], p[1]
        state = _int(p[2]) if len(p) > 2 else None
        verify = _int(p[3]) if len(p) > 3 else None
        n += db.execute(sql, (
            sn, pin, when, state, PUNCH_STATE.get(state, str(state)),
            verify, VERIFY_MODE.get(verify, str(verify)),
        ))
    return n


def ingest_users(sn: str, body: str) -> int:
    """Parse USER lines (tab-separated key=value) and upsert employees."""
    n = 0
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("USER"):
            continue
        fields = {}
        for tok in line[4:].split("\t"):
            if "=" in tok:
                k, v = tok.split("=", 1)
                fields[k.strip()] = v.strip()
        pin = fields.get("PIN")
        if not pin:
            continue
        pri = _int(fields.get("Pri", "0")) or 0
        db.execute(
            """INSERT INTO employees (pin, name, privilege, privilege_name, card, group_id, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s, now())
               ON CONFLICT (pin) DO UPDATE SET
                   name = COALESCE(NULLIF(EXCLUDED.name,''), employees.name),
                   privilege = EXCLUDED.privilege,
                   privilege_name = EXCLUDED.privilege_name,
                   card = COALESCE(NULLIF(EXCLUDED.card,''), employees.card),
                   updated_at = now()""",
            (pin, fields.get("Name") or None, pri, PRIVILEGE.get(pri, str(pri)),
             fields.get("Card") or None, fields.get("Grp") or None),
        )
        n += 1
    return n


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _store_photo(pin, jpeg_bytes) -> int:
    """Store a JPEG as a data-URI on the employee. Auto-syncs device photos."""
    if not pin or not jpeg_bytes:
        return 0
    import base64
    uri = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii")
    n = db.execute("UPDATE employees SET photo=%s, updated_at=now() WHERE pin=%s",
                   (uri, str(pin)))
    if n:
        print(f"[adms] synced photo for PIN={pin} ({len(jpeg_bytes)} bytes)", flush=True)
    return n


def _fields(text: str) -> dict:
    out = {}
    for tok in text.replace("\r", "\n").replace("\n", "\t").split("\t"):
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k.strip()] = v
    return out


def ingest_photo(qs, raw: bytes) -> int:
    """Store a photo pushed by the device (raw JPEG, or key=value with base64 Content)."""
    import base64
    pin = qs.get("PIN") or qs.get("pin")
    if raw[:3] == b"\xff\xd8\xff":
        return _store_photo(pin, raw)
    f = _fields(raw.decode("utf-8", "replace"))
    pin = pin or f.get("PIN") or f.get("Pin")
    content = f.get("Content") or f.get("content")
    if content:
        try:
            return _store_photo(pin, base64.b64decode(content))
        except Exception:
            return 0
    return 0


def ingest_inline_photos(body: str) -> int:
    """Some firmware embeds photo lines inside OPERLOG (BIOPHOTO/USERPIC ...)."""
    import base64
    n = 0
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("BIOPHOTO") or s.startswith("USERPIC"):
            f = _fields(s)
            pin = f.get("PIN") or f.get("Pin")
            content = f.get("Content") or f.get("content")
            if pin and content:
                try:
                    n += _store_photo(pin, base64.b64decode(content))
                except Exception:
                    pass
    return n


# --------------------------- endpoints --------------------------- #
@router.get("/cdata", response_class=PlainTextResponse)
async def cdata_handshake(request: Request):
    sn = _sn(request)
    touch_device(sn, request.client.host if request.client else None)
    # Capture any INFO passed as query params (some firmwares do this).
    info = {k: v for k, v in request.query_params.items()
            if k not in ("SN", "sn", "options", "pushver", "language")}
    if info:
        _apply_device_info(sn, info)
    opts = "\n".join([
        f"GET OPTION FROM: {sn}", "Stamp=0", "OpStamp=0",
        "ErrorDelay=30", "Delay=10", "TransTimes=00:00;14:05",
        "TransInterval=1", "TransFlag=1111111111", "Realtime=1",
        "TimeZone=4", "Encrypt=0",
    ]) + "\n"
    return opts


@router.post("/cdata", response_class=PlainTextResponse)
async def cdata_upload(request: Request):
    sn = _sn(request)
    touch_device(sn, request.client.host if request.client else None)
    table = (request.query_params.get("table") or "").upper()
    raw = await request.body()

    # Debug: log every upload's shape so we can confirm the firmware's photo format.
    print(f"[adms] POST cdata SN={sn} table={table or '-'} len={len(raw)} "
          f"prefix={raw[:24]!r}", flush=True)

    mark_data(sn)  # device→server data activity (drives the "uploading" icon)

    # ---- Photo uploads (BIOPHOTO/USERPIC, or a raw JPEG) ----
    if table in ("BIOPHOTO", "USERPIC", "USERPHOTO") or raw[:3] == b"\xff\xd8\xff":
        n = ingest_photo(request.query_params, raw)
        return f"OK: {n}"

    body = raw.decode("utf-8", "replace")
    if table == "ATTLOG":
        return f"OK: {ingest_attlog(sn, body)}"
    if table in ("OPERLOG", "USERINFO", "USER"):
        # OPERLOG can also carry inline photo lines on some firmware.
        photos = ingest_inline_photos(body)
        users = ingest_users(sn, body)
        return f"OK: {users + photos}"
    if table == "OPTIONS" or body.startswith("~") or "=" in body[:40]:
        info = {}
        for line in body.replace("\r", "\n").split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip().lstrip("~")] = v.strip()
        if info:
            _apply_device_info(sn, info)
    return "OK"


@router.get("/getrequest", response_class=PlainTextResponse)
async def getrequest(request: Request):
    sn = _sn(request)
    touch_device(sn, request.client.host if request.client else None)
    # Dispense any queued orders for this device (empty => behaves read-only).
    pending = db.query(
        "SELECT id, content FROM device_command "
        "WHERE sn=%s AND status='pending' ORDER BY id LIMIT 20", (sn,))
    if not pending:
        return "OK"
    lines = []
    for cmd in pending:
        lines.append(f"C:{cmd['id']}:{cmd['content']}")
        db.execute("UPDATE device_command SET status='sent', sent_at=now() WHERE id=%s",
                   (cmd["id"],))
    mark_cmd(sn)  # server→device activity (drives the "sending" icon)
    return "\n".join(lines) + "\n"


@router.post("/devicecmd", response_class=PlainTextResponse)
async def devicecmd(request: Request):
    sn = _sn(request)
    touch_device(sn, request.client.host if request.client else None)
    body = (await request.body()).decode("utf-8", "replace")
    # Phase 5 will match these to device_command rows. For now just log.
    for line in body.splitlines():
        if "ID=" in line and "Return=" in line:
            fields = dict(kv.split("=", 1) for kv in line.split("&") if "=" in kv)
            cid = _int(fields.get("ID"))
            ret = fields.get("Return")
            if cid is not None:
                db.execute(
                    "UPDATE device_command SET status='done', return_at=now(), "
                    "return_code=%s WHERE id=%s",
                    (ret, cid),
                )
    return "OK"


@router.post("/fdata", response_class=PlainTextResponse)
async def fdata(request: Request):
    """Some firmware uploads photo/file data here."""
    sn = _sn(request)
    touch_device(sn, request.client.host if request.client else None)
    raw = await request.body()
    print(f"[adms] POST fdata SN={sn} len={len(raw)} prefix={raw[:24]!r}", flush=True)
    mark_data(sn)
    return f"OK: {ingest_photo(request.query_params, raw)}"
