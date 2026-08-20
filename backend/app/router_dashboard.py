"""Dashboard aggregates: today's stat cards + attendance-exception history."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from . import attendance_engine as eng
from . import auth, db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def dubai_today():
    # Data is stored in UAE local (GMT+4, no DST). Avoid tzdata dependency.
    return (datetime.utcnow() + timedelta(hours=4)).date()


def _scope(user):
    ids = auth.scope_dept_ids(user)
    if ids is None:
        return "", []
    if not ids:
        return "AND FALSE", []
    return "AND e.department_id = ANY(%s)", [ids]


def _ensure_computed(d):
    have = db.query("SELECT count(*) AS c FROM attendance_day WHERE work_date=%s", (d,))[0]["c"]
    if have == 0:
        eng.compute_day(d)


def _ensure_today_fresh(d):
    """Recompute today only when new punches arrived since the last compute —
    keeps late/early/status live without recomputing on every poll."""
    last = db.query("SELECT max(computed_at) AS c FROM attendance_day WHERE work_date=%s", (d,))[0]["c"]
    newest = db.query("SELECT max(created_at) AS c FROM attendance WHERE punch_time::date=%s", (d,))[0]["c"]
    if last is None or (newest is not None and newest > last):
        eng.compute_day(d)


@router.get("/stats")
def stats(user: dict = Depends(auth.get_current_user)):
    today = dubai_today()
    scope, p = _scope(user)

    emp = db.query(f"SELECT count(*) AS c FROM employees e WHERE e.active {scope}", tuple(p))[0]["c"]

    # Present + verification are LIVE from raw punches (always fresh).
    live = db.query(
        f"""SELECT count(DISTINCT a.pin) AS present, count(*) AS punches
            FROM attendance a JOIN employees e ON e.pin = a.pin
            WHERE a.punch_time::date = %s {scope}""", tuple([today] + p))[0]
    present = live["present"] or 0
    punches_today = live["punches"] or 0
    absent = max(0, emp - present)

    # Late/early/half-day come from the engine; refresh today only when new punches arrived.
    _ensure_today_fresh(today)
    agg = db.query(
        f"""SELECT
              count(*) FILTER (WHERE ad.status='halfday')  AS halfday,
              count(*) FILTER (WHERE ad.late_min > 0)      AS late,
              count(*) FILTER (WHERE ad.early_min > 0)     AS early
            FROM attendance_day ad
            JOIN employees e ON e.pin = ad.emp_code
            WHERE ad.work_date = %s {scope}""", tuple([today] + p))[0]

    dev = db.query(
        "SELECT count(*) AS total, "
        "count(*) FILTER (WHERE last_seen > now() - interval '180 seconds') AS online "
        "FROM device")[0]

    return {
        "date": str(today),
        "employees": emp,
        "present": present, "absent": absent, "halfday": agg["halfday"],
        "late": agg["late"], "early": agg["early"], "on_leave": 0,
        "verification": punches_today,
        "devices_total": dev["total"], "devices_online": dev["online"],
    }


@router.get("/exceptions")
def exceptions(days: int = 14, user: dict = Depends(auth.get_current_user)):
    days = max(1, min(days, 60))
    today = dubai_today()
    start = today - timedelta(days=days - 1)
    # compute any missing days in the window (cached afterwards)
    d = start
    while d <= today:
        _ensure_today_fresh(d) if d == today else _ensure_computed(d)
        d += timedelta(days=1)
    scope, p = _scope(user)
    rows = db.query(
        f"""SELECT ad.work_date AS date,
               count(*) FILTER (WHERE ad.late_min > 0)   AS late,
               count(*) FILTER (WHERE ad.early_min > 0)  AS early,
               count(*) FILTER (WHERE ad.status='absent') AS absent,
               count(*) FILTER (WHERE ad.status IN ('present','halfday','incomplete')) AS present
            FROM attendance_day ad
            JOIN employees e ON e.pin = ad.emp_code
            WHERE ad.work_date BETWEEN %s AND %s {scope}
            GROUP BY ad.work_date ORDER BY ad.work_date""",
        tuple([start, today] + p))
    return [{"date": str(r["date"]), "late": r["late"], "early": r["early"],
             "absent": r["absent"], "present": r["present"]} for r in rows]


@router.get("/hourly")
def hourly(user: dict = Depends(auth.get_current_user)):
    """Punches per hour for today — feeds the real-time monitor."""
    today = dubai_today()
    scope, p = _scope(user)
    rows = db.query(
        f"""SELECT extract(hour from a.punch_time)::int AS hour, count(*) AS c
            FROM attendance a JOIN employees e ON e.pin = a.pin
            WHERE a.punch_time::date = %s {scope}
            GROUP BY 1 ORDER BY 1""", tuple([today] + p))
    by_hour = {int(r["hour"]): r["c"] for r in rows}
    return [{"hour": f"{h:02d}:00", "punches": by_hour.get(h, 0)} for h in range(24)]
