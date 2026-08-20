"""Attendance reporting queries."""
from . import db


def daily_report(day: str) -> list[dict]:
    """
    Per-employee summary for one calendar day (YYYY-MM-DD):
    first punch, last punch, punch count, and worked hours (last-first).
    Because the device reports every punch as state 0, in/out is derived by
    pairing: first punch = in, last punch = out.
    """
    return db.query(
        f"""
        SELECT e.pin,
               {db.FULLNAME}                                       AS name,
               MIN(a.punch_time)                                   AS first_in,
               MAX(a.punch_time)                                   AS last_out,
               COUNT(*)                                            AS punches,
               ROUND(EXTRACT(EPOCH FROM (MAX(a.punch_time) - MIN(a.punch_time)))
                     / 3600.0, 2)                                  AS hours
        FROM attendance a
        LEFT JOIN employees e ON e.pin = a.pin
        WHERE a.punch_time::date = %s
        GROUP BY e.pin, e.first_name, e.last_name, e.name
        ORDER BY first_in
        """,
        (day,),
    )


def attendance_rows(pin: str | None, date_from: str | None,
                    date_to: str | None, limit: int = 500) -> list[dict]:
    clauses, params = [], []
    if pin:
        clauses.append("a.pin = %s")
        params.append(pin)
    if date_from:
        clauses.append("a.punch_time >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("a.punch_time <= %s")
        params.append(date_to)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    return db.query(
        f"""
        SELECT a.id, a.pin, {db.FULLNAME} AS name, a.punch_time, a.punch_name, a.verify_name
        FROM attendance a
        LEFT JOIN employees e ON e.pin = a.pin
        {where}
        ORDER BY a.punch_time DESC
        LIMIT %s
        """,
        tuple(params),
    )


def dashboard_summary() -> dict:
    totals = db.query(
        """
        SELECT
          (SELECT COUNT(*) FROM employees WHERE active) AS employees,
          (SELECT COUNT(*) FROM attendance)             AS punches_total,
          (SELECT COUNT(*) FROM attendance
             WHERE punch_time::date = CURRENT_DATE)      AS punches_today,
          (SELECT COUNT(DISTINCT pin) FROM attendance
             WHERE punch_time::date = CURRENT_DATE)      AS present_today
        """
    )[0]
    last_sync = db.query(
        "SELECT started_at, status, records_new, message FROM sync_log "
        "ORDER BY started_at DESC LIMIT 1"
    )
    totals["last_sync"] = last_sync[0] if last_sync else None
    return totals
