"""Reports: daily/monthly summaries + Excel (xlsx) export."""
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, Query, Response
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from . import attendance_engine as eng
from . import auth, db
from .router_dashboard import dubai_today

router = APIRouter(prefix="/api/reports", tags=["reports"])

XLSX_MT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HDR_FILL = PatternFill("solid", fgColor="1e293b")
HDR_FONT = Font(color="FFFFFF", bold=True)


def _scope(user):
    ids = auth.scope_dept_ids(user)
    if ids is None:
        return "", []
    if not ids:
        return "AND FALSE", []
    return "AND e.department_id = ANY(%s)", [ids]


def _xlsx(title: str, headers: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    for c in ws[1]:
        c.fill = HDR_FILL
        c.font = HDR_FONT
    for r in rows:
        ws.append(r)
    for i, h in enumerate(headers, 1):
        width = max(len(str(h)), *(len(str(r[i - 1])) for r in rows)) if rows else len(str(h))
        ws.column_dimensions[chr(64 + i) if i <= 26 else "AA"].width = min(width + 3, 40)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _hm(m):
    m = m or 0
    return f"{m // 60}:{m % 60:02d}"


# ------------------------------ Daily xlsx ------------------------------ #
@router.get("/daily.xlsx")
def daily_xlsx(date: str, user: dict = Depends(auth.get_current_user)):
    d = datetime.strptime(date, "%Y-%m-%d").date()
    if db.query("SELECT count(*) AS c FROM attendance_day WHERE work_date=%s", (d,))[0]["c"] == 0:
        eng.compute_day(d)
    scope, p = _scope(user)
    rows = db.query(
        f"""SELECT ad.emp_code, {db.FULLNAME} AS name, dep.name AS department, ad.status,
               ad.first_in, ad.last_out, ad.worked_min, ad.late_min, ad.early_min,
               ad.ot_in, ad.ot_out, ad.ot_min
            FROM attendance_day ad
            LEFT JOIN employees e ON e.pin = ad.emp_code
            LEFT JOIN department dep ON dep.id = e.department_id
            WHERE ad.work_date = %s {scope} ORDER BY ad.emp_code""", tuple([d] + p))
    data = [[r["emp_code"], r["name"], r["department"] or "", r["status"],
             str(r["first_in"] or "")[11:19], str(r["last_out"] or "")[11:19],
             _hm(r["worked_min"]), r["late_min"], r["early_min"],
             str(r["ot_in"] or "")[11:19], str(r["ot_out"] or "")[11:19], _hm(r["ot_min"])]
            for r in rows]
    content = _xlsx(f"Daily {date}",
                    ["PIN", "Name", "Department", "Status", "Check-In", "Check-Out",
                     "Worked", "Late (m)", "Early (m)", "OT-In", "OT-Out", "OT"], data)
    return Response(content, media_type=XLSX_MT, headers={
        "Content-Disposition": f'attachment; filename="daily_{date}.xlsx"'})


# ------------------------------ Monthly ------------------------------ #
def _month_bounds(month: str):
    first = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = nxt - timedelta(days=1)
    return first, last


def _resolve_range(month, date_from, date_to):
    """Full month (YYYY-MM) OR an explicit date range (from/to). Range wins."""
    if date_from and date_to:
        first = datetime.strptime(date_from, "%Y-%m-%d").date()
        last = datetime.strptime(date_to, "%Y-%m-%d").date()
    else:
        first, last = _month_bounds(month)
    return first, last


def _monthly_rows(user: dict, month=None, date_from=None, date_to=None, include_absent=False):
    first, last = _resolve_range(month, date_from, date_to)
    end = min(last, dubai_today())
    d = first
    while d <= end:
        if db.query("SELECT count(*) AS c FROM attendance_day WHERE work_date=%s", (d,))[0]["c"] == 0:
            eng.compute_day(d)
        d += timedelta(days=1)
    scope, p = _scope(user)
    # Skip employees with no attendance in the range (long-time absent) unless asked.
    having = "" if include_absent else \
        "HAVING count(*) FILTER (WHERE ad.status IN ('present','halfday','incomplete')) > 0"
    return db.query(
        f"""SELECT ad.emp_code, {db.FULLNAME} AS name, dep.name AS department,
               count(*) FILTER (WHERE ad.status IN ('present','halfday','incomplete')) AS present_days,
               count(*) FILTER (WHERE ad.status='absent')  AS absent_days,
               count(*) FILTER (WHERE ad.status='halfday') AS halfday_days,
               count(*) FILTER (WHERE ad.late_min > 0)     AS late_days,
               count(*) FILTER (WHERE ad.early_min > 0)    AS early_days,
               COALESCE(sum(ad.worked_min),0) AS worked_min,
               COALESCE(sum(ad.ot_min),0)     AS ot_min
            FROM attendance_day ad
            LEFT JOIN employees e ON e.pin = ad.emp_code
            LEFT JOIN department dep ON dep.id = e.department_id
            WHERE ad.work_date BETWEEN %s AND %s {scope}
            GROUP BY ad.emp_code, e.pin, e.first_name, e.last_name, e.name, dep.name
            {having}
            ORDER BY ad.emp_code""",
        tuple([first, last] + p))


@router.get("/monthly")
def monthly(user: dict = Depends(auth.get_current_user), month: str | None = None,
            date_from: str | None = Query(None, alias="from"),
            date_to: str | None = Query(None, alias="to"),
            include_absent: bool = False):
    return _monthly_rows(user, month, date_from, date_to, include_absent)


@router.get("/monthly.xlsx")
def monthly_xlsx(user: dict = Depends(auth.get_current_user), month: str | None = None,
                 date_from: str | None = Query(None, alias="from"),
                 date_to: str | None = Query(None, alias="to"),
                 include_absent: bool = False):
    rows = _monthly_rows(user, month, date_from, date_to, include_absent)
    label = f"{date_from}_to_{date_to}" if (date_from and date_to) else month
    data = [[r["emp_code"], r["name"], r["department"] or "", r["present_days"],
             r["absent_days"], r["halfday_days"], r["late_days"], r["early_days"],
             _hm(r["worked_min"]), _hm(r["ot_min"])] for r in rows]
    content = _xlsx(f"Report {label}",
                    ["PIN", "Name", "Department", "Present", "Absent", "Half-day",
                     "Late days", "Early days", "Total Worked (h:m)", "Total OT (h:m)"], data)
    return Response(content, media_type=XLSX_MT, headers={
        "Content-Disposition": f'attachment; filename="report_{label}.xlsx"'})
