"""
Device sync — connect to the ZKTeco terminal over the pull SDK and upsert
users + attendance into Postgres. Idempotent (safe to run on a schedule).
"""
import os
from datetime import datetime, timezone

from zk import ZK

from . import db

ZK_DEVICE_IP = os.environ.get("ZK_DEVICE_IP", "")
ZK_DEVICE_PORT = int(os.environ.get("ZK_DEVICE_PORT", "4370"))
ZK_COMM_PASSWORD = int(os.environ.get("ZK_COMM_PASSWORD", "0"))
ZK_DEVICE_SN = os.environ.get("ZK_DEVICE_SN", "")

PUNCH_STATE = {0: "Check-In", 1: "Check-Out", 2: "Break-Out",
               3: "Break-In", 4: "OT-In", 5: "OT-Out"}
VERIFY_MODE = {0: "Password", 1: "Fingerprint", 2: "Card", 15: "Face"}
PRIVILEGE = {0: "User", 14: "Admin"}


class SyncError(Exception):
    pass


def device_status() -> dict:
    """Quick reachability + identity probe. Never raises."""
    if not ZK_DEVICE_IP:
        return {"connected": False, "error": "ZK_DEVICE_IP not set"}
    zk = ZK(ZK_DEVICE_IP, port=ZK_DEVICE_PORT, timeout=8,
            password=ZK_COMM_PASSWORD, force_udp=False, ommit_ping=True)
    conn = None
    try:
        conn = zk.connect()
        info = {
            "connected": True,
            "ip": ZK_DEVICE_IP,
            "serial": conn.get_serialnumber(),
            "name": conn.get_device_name(),
            "firmware": conn.get_firmware_version(),
        }
        return info
    except Exception as e:
        return {"connected": False, "ip": ZK_DEVICE_IP,
                "error": f"{type(e).__name__}: {e}"}
    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass


def run_sync() -> dict:
    """
    Pull users + attendance and upsert. Returns a summary dict and writes a
    sync_log row. Raises SyncError on connection failure.
    """
    log_rows = db.query(
        "INSERT INTO sync_log (device_sn, status) VALUES (%s, 'running') RETURNING id",
        (ZK_DEVICE_SN or None,),
    )
    log_id = log_rows[0]["id"]

    zk = ZK(ZK_DEVICE_IP, port=ZK_DEVICE_PORT, timeout=15,
            password=ZK_COMM_PASSWORD, force_udp=False, ommit_ping=True)
    conn = None
    try:
        conn = zk.connect()
        conn.disable_device()

        sn = conn.get_serialnumber()
        name = conn.get_device_name()
        fw = conn.get_firmware_version()
        try:
            platform = conn.get_platform()
        except Exception:
            platform = None

        # Upsert device record.
        db.execute(
            """INSERT INTO device (sn, name, firmware, platform, ip, online, last_seen)
               VALUES (%s,%s,%s,%s,%s, TRUE, now())
               ON CONFLICT (sn) DO UPDATE SET
                   name=EXCLUDED.name, firmware=EXCLUDED.firmware,
                   platform=EXCLUDED.platform, ip=EXCLUDED.ip,
                   online=TRUE, last_seen=now()""",
            (sn, name, fw, platform, ZK_DEVICE_IP),
        )

        # Upsert users.
        users = conn.get_users()
        for u in users:
            db.execute(
                """INSERT INTO employees (pin, name, privilege, privilege_name,
                                          card, group_id, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s, now())
                   ON CONFLICT (pin) DO UPDATE SET
                       name=EXCLUDED.name, privilege=EXCLUDED.privilege,
                       privilege_name=EXCLUDED.privilege_name,
                       card=EXCLUDED.card, group_id=EXCLUDED.group_id,
                       updated_at=now()""",
                (str(u.user_id), u.name, u.privilege,
                 PRIVILEGE.get(u.privilege, str(u.privilege)),
                 str(u.card), str(u.group_id)),
            )

        # Insert attendance (dedupe via ON CONFLICT DO NOTHING).
        att = conn.get_attendance()
        insert_sql = (
            """INSERT INTO attendance
                   (device_sn, pin, punch_time, punch, punch_name, verify, verify_name)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (device_sn, pin, punch_time) DO NOTHING"""
        )
        rows = []
        for a in att:
            rows.append((
                sn, str(a.user_id), a.timestamp,
                a.punch, PUNCH_STATE.get(a.punch, str(a.punch)),
                a.status, VERIFY_MODE.get(a.status, str(a.status)),
            ))
        new_count = db.executemany_returning_new(insert_sql, rows)

        summary = {
            "device_sn": sn, "device_name": name, "firmware": fw,
            "users": len(users), "attendance_on_device": len(att),
            "attendance_new": new_count,
        }
        db.execute(
            """UPDATE sync_log SET finished_at=now(), status='ok',
                   records_new=%s, records_seen=%s, device_sn=%s,
                   message=%s WHERE id=%s""",
            (new_count, len(att), sn,
             f"{len(users)} users, {new_count} new punches", log_id),
        )
        return summary

    except Exception as e:
        db.execute(
            "UPDATE sync_log SET finished_at=now(), status='error', message=%s WHERE id=%s",
            (f"{type(e).__name__}: {e}", log_id),
        )
        raise SyncError(f"{type(e).__name__}: {e}") from e
    finally:
        if conn is not None:
            try:
                conn.enable_device()
                conn.disconnect()
            except Exception:
                pass
