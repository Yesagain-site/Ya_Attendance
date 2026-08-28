"""Attendance configuration + engine endpoints."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import attendance_engine as eng
from . import auth, db

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


# ------------------------------ Global rules ------------------------------ #
@router.get("/rules")
def get_rules(user: dict = Depends(auth.get_current_user)):
    return eng.get_rules()


@router.put("/rules")
def put_rules(body: dict, user: dict = Depends(auth.require_admin)):
    return eng.save_rules(body)


# ------------------------------ Timetables ------------------------------ #
class TimetableIn(BaseModel):
    name: str
    in_time: str
    out_time: str
    grace_late_min: int = 0
    grace_early_min: int = 0
    work_minutes: int | None = None
    break_minutes: int = 0
    ot_after_min: int | None = None
    ot_enabled: bool = False


@router.get("/timetables")
def timetables(user: dict = Depends(auth.get_current_user)):
    return db.query("SELECT * FROM timetable ORDER BY name")


@router.post("/timetables")
def create_timetable(b: TimetableIn, user: dict = Depends(auth.require_admin)):
    return db.query(
        """INSERT INTO timetable (name,in_time,out_time,grace_late_min,grace_early_min,
                work_minutes,break_minutes,ot_after_min,ot_enabled)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (b.name, b.in_time, b.out_time, b.grace_late_min, b.grace_early_min,
         b.work_minutes, b.break_minutes, b.ot_after_min, b.ot_enabled))[0]


@router.put("/timetables/{tid}")
def update_timetable(tid: int, b: TimetableIn, user: dict = Depends(auth.require_admin)):
    n = db.execute(
        """UPDATE timetable SET name=%s,in_time=%s,out_time=%s,grace_late_min=%s,
               grace_early_min=%s,work_minutes=%s,break_minutes=%s,ot_after_min=%s,
               ot_enabled=%s WHERE id=%s""",
        (b.name, b.in_time, b.out_time, b.grace_late_min, b.grace_early_min,
         b.work_minutes, b.break_minutes, b.ot_after_min, b.ot_enabled, tid))
    if not n:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@router.delete("/timetables/{tid}")
def delete_timetable(tid: int, user: dict = Depends(auth.require_admin)):
    db.execute("DELETE FROM timetable WHERE id=%s", (tid,))
    return {"ok": True}


# ------------------------------ Shifts ------------------------------ #
class ShiftDetailIn(BaseModel):
    day_index: int
    timetable_id: int | None = None
    is_off: bool = False


class ShiftIn(BaseModel):
    name: str
    details: list[ShiftDetailIn] = []


@router.get("/shifts")
def shifts(user: dict = Depends(auth.get_current_user)):
    rows = db.query("SELECT * FROM shift ORDER BY name")
    for s in rows:
        s["details"] = db.query(
            "SELECT id, day_index, timetable_id, is_off FROM shift_detail "
            "WHERE shift_id=%s ORDER BY day_index", (s["id"],))
    return rows


@router.post("/shifts")
def create_shift(b: ShiftIn, user: dict = Depends(auth.require_admin)):
    sid = db.query("INSERT INTO shift (name) VALUES (%s) RETURNING id", (b.name,))[0]["id"]
    for d in b.details:
        db.execute(
            "INSERT INTO shift_detail (shift_id, day_index, timetable_id, is_off) "
            "VALUES (%s,%s,%s,%s)", (sid, d.day_index, d.timetable_id, d.is_off))
    return {"ok": True, "id": sid}


@router.put("/shifts/{sid}")
def update_shift(sid: int, b: ShiftIn, user: dict = Depends(auth.require_admin)):
    db.execute("UPDATE shift SET name=%s WHERE id=%s", (b.name, sid))
    db.execute("DELETE FROM shift_detail WHERE shift_id=%s", (sid,))
    for d in b.details:
        db.execute(
            "INSERT INTO shift_detail (shift_id, day_index, timetable_id, is_off) "
            "VALUES (%s,%s,%s,%s)", (sid, d.day_index, d.timetable_id, d.is_off))
    return {"ok": True}


@router.delete("/shifts/{sid}")
def delete_shift(sid: int, user: dict = Depends(auth.require_admin)):
    db.execute("DELETE FROM shift WHERE id=%s", (sid,))
    return {"ok": True}


# ------------------------------ Breaks ------------------------------ #
class BreakIn(BaseModel):
    name: str
    minutes: int = 0
    mode: str = "auto"


@router.get("/breaks")
def breaks(user: dict = Depends(auth.get_current_user)):
    return db.query("SELECT * FROM break_time ORDER BY name")


@router.post("/breaks")
def create_break(b: BreakIn, user: dict = Depends(auth.require_admin)):
    return db.query("INSERT INTO break_time (name,minutes,mode) VALUES (%s,%s,%s) "
                    "RETURNING *", (b.name, b.minutes, b.mode))[0]


@router.delete("/breaks/{bid}")
def delete_break(bid: int, user: dict = Depends(auth.require_admin)):
    db.execute("DELETE FROM break_time WHERE id=%s", (bid,))
    return {"ok": True}


# ------------------------------ Schedules ------------------------------ #
class ScheduleIn(BaseModel):
    emp_code: str | None = None
    department_id: int | None = None
    shift_id: int
    start_date: str | None = None
    end_date: str | None = None


@router.get("/schedules")
def schedules(user: dict = Depends(auth.get_current_user)):
    return db.query(
        """SELECT es.*, s.name AS shift_name, d.name AS department
           FROM employee_schedule es
           LEFT JOIN shift s ON s.id = es.shift_id
           LEFT JOIN department d ON d.id = es.department_id
           ORDER BY es.id DESC""")


@router.post("/schedules")
def create_schedule(b: ScheduleIn, user: dict = Depends(auth.require_admin)):
    if not b.emp_code and not b.department_id:
        raise HTTPException(400, "emp_code or department_id required")
    return db.query(
        """INSERT INTO employee_schedule (emp_code, department_id, shift_id, start_date, end_date)
           VALUES (%s,%s,%s,%s,%s) RETURNING id""",
        (b.emp_code, b.department_id, b.shift_id, b.start_date or None, b.end_date or None))[0]


@router.delete("/schedules/{sid}")
def delete_schedule(sid: int, user: dict = Depends(auth.require_admin)):
    db.execute("DELETE FROM employee_schedule WHERE id=%s", (sid,))
    return {"ok": True}


# ------------------------------ Engine + grid ------------------------------ #
@router.post("/compute")
def compute(date: str, user: dict = Depends(auth.require_admin)):
    d = datetime.strptime(date, "%Y-%m-%d").date()
    n = eng.compute_day(d)
    return {"ok": True, "date": date, "employees": n}


@router.post("/recompute-range")
def recompute_range(date_from: str = Query(..., alias="from"),
                    date_to: str = Query(..., alias="to"),
                    user: dict = Depends(auth.require_admin)):
    """Force-recompute every day in the range (use after a deploy / rule change)."""
    a = datetime.strptime(date_from, "%Y-%m-%d").date()
    b = datetime.strptime(date_to, "%Y-%m-%d").date()
    if (b - a).days > 92:
        raise HTTPException(400, "Range too large (max ~3 months)")
    n = eng.compute_range(a, b)
    return {"ok": True, "from": date_from, "to": date_to, "days": n}


@router.get("/daily")
def daily_grid(date: str, user: dict = Depends(auth.get_current_user)):
    """Computed daily attendance for a date (auto-computes if missing)."""
    d = datetime.strptime(date, "%Y-%m-%d").date()
    eng.recompute_if_stale(d)
    ids = auth.scope_dept_ids(user)
    scope = ""
    params = [d]
    if ids is not None:
        if not ids:
            return []
        scope = "AND e.department_id = ANY(%s)"
        params.append(ids)
    return db.query(
        f"""SELECT ad.emp_code AS pin, {db.FULLNAME} AS name, e.department_id,
                   dep.name AS department, ad.first_in, ad.last_out, ad.worked_min,
                   ad.late_min, ad.early_min, ad.ot_min, ad.ot_in, ad.ot_out, ad.status,
                   round(ad.worked_min/60.0, 2) AS worked_hours
            FROM attendance_day ad
            LEFT JOIN employees e ON e.pin = ad.emp_code
            LEFT JOIN department dep ON dep.id = e.department_id
            WHERE ad.work_date = %s {scope}
            ORDER BY ad.emp_code""", tuple(params))
