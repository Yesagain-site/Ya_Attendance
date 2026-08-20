"""
Attendance calculation engine (moderate).

Resolves each employee's timetable for a date (via schedule -> shift -> timetable,
falling back to a default timetable), reads that day's punches, and computes
worked / late / early / OT / status per the global calculation rules. Results
are cached in attendance_day.
"""
import json
from datetime import date, datetime, timedelta

from . import db

DEFAULT_RULES = {
    "late_exceeds_min": 540, "late_consider_as": "absent",
    "early_exceeds_min": 540, "early_consider_as": "absent",
    "halfday_under_min": 270,
    "missed_checkin_as": "present", "missed_checkout_as": "present",
    "items": {"check_in": 0, "check_out": 1, "break_out": 2,
              "break_in": 3, "ot_in": 4, "ot_out": 5},
    "default_timetable_id": None,
    # Multi-capture handling (devices spam 10-15 captures per person):
    "dedup_min": 3,           # collapse captures within N minutes of the previous
    "ot_return_gap_min": 10,  # a gap >= N min after shift end marks an OT return
    "min_ot_min": 30,         # ignore overtime shorter than this
    "ot_multiplier": 1.5,     # informational OT rate
    # Basic + week-off:
    "week_off": [],           # weekday indices off by default (0=Mon .. 6=Sun)
    "period_start_day": 1,    # payroll/attendance month cycle start day
    "first_weekday": 0,       # 0=Mon, 6=Sun (display)
    "min_present_min": 0,     # minimum worked minutes to count as present
}


def get_rules() -> dict:
    rows = db.query("SELECT value FROM settings WHERE key='calc_rules'")
    if rows:
        try:
            return {**DEFAULT_RULES, **json.loads(rows[0]["value"])}
        except Exception:
            pass
    return dict(DEFAULT_RULES)


def save_rules(rules: dict):
    merged = {**DEFAULT_RULES, **rules}
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('calc_rules', %s) "
        "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
        (json.dumps(merged),))
    return merged


def _minutes(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 60)


def _timetable_for(emp_code: str, dept_id, d: date, rules: dict):
    """Resolve the timetable for an employee on date d. Returns row or None."""
    day_index = d.weekday()  # Mon=0..Sun=6
    rows = db.query(
        """SELECT t.*
           FROM employee_schedule es
           JOIN shift_detail sd ON sd.shift_id = es.shift_id AND sd.day_index = %s
           LEFT JOIN timetable t ON t.id = sd.timetable_id
           WHERE (es.emp_code = %s OR es.department_id = %s)
             AND (es.start_date IS NULL OR es.start_date <= %s)
             AND (es.end_date IS NULL OR es.end_date >= %s)
           ORDER BY (es.emp_code = %s) DESC
           LIMIT 1""",
        (day_index, emp_code, dept_id, d, d, emp_code))
    if rows:
        if rows[0].get("is_off"):
            return "OFF"
        if rows[0].get("id"):
            return rows[0]     # explicit shift for this day wins over global week-off
    # No explicit working shift for this day → apply the global weekly-off default.
    if day_index in (rules.get("week_off") or []):
        return "OFF"
    if rules.get("default_timetable_id"):
        d2 = db.query("SELECT * FROM timetable WHERE id=%s",
                      (rules["default_timetable_id"],))
        if d2:
            return d2[0]
    return None


def compute_employee_day(emp_code: str, dept_id, d: date, rules: dict) -> dict:
    punches = db.query(
        "SELECT punch_time FROM attendance WHERE pin=%s "
        "AND punch_time::date = %s ORDER BY punch_time", (emp_code, d))
    tt = _timetable_for(emp_code, dept_id, d, rules)

    is_holiday = bool(db.query("SELECT 1 FROM holiday WHERE day=%s", (d,)))

    result = {"emp_code": emp_code, "work_date": d, "first_in": None,
              "last_out": None, "worked_min": 0, "break_min": 0,
              "late_min": 0, "early_min": 0, "ot_min": 0,
              "ot_in": None, "ot_out": None, "status": "absent"}

    if is_holiday:
        result["status"] = "holiday"
    if tt == "OFF":
        result["status"] = "dayoff"

    if not punches:
        if result["status"] not in ("holiday", "dayoff"):
            result["status"] = "absent"
        return result

    # Use raw captures for exact times. Spam captures are seconds apart, so they
    # never create a false gap; only real gaps (lunch, OT return) are large.
    caps = [p["punch_time"] for p in punches]

    first_in = caps[0]
    regular_out = caps[-1]          # last capture before any OT return-gap
    ot_in = ot_out = None

    # ---- split off an overtime session: a return-gap after the shift end ----
    if isinstance(tt, dict) and tt.get("ot_enabled"):
        sched_out = datetime.combine(d, tt["out_time"])
        gap = timedelta(minutes=rules.get("ot_return_gap_min", 10))
        for i in range(1, len(caps)):
            if caps[i] >= sched_out and (caps[i] - caps[i - 1]) >= gap:
                regular_out = caps[i - 1]     # left for the day here
                ot_in, ot_out = caps[i], caps[-1]  # returned for OT
                break

    result["first_in"] = first_in
    result["last_out"] = ot_out or regular_out

    # "Incomplete" = only seen briefly (single punch or all captures clustered at
    # one moment) — i.e. a missed check-out, not a real full day.
    incomplete = _minutes(first_in, regular_out) < 15

    # Regular worked = GROSS span from check-in to (regular) check-out.
    worked = _minutes(first_in, regular_out)
    result["worked_min"] = worked
    result["break_min"] = 0

    if ot_in is not None:
        ot = _minutes(ot_in, ot_out)
        if ot >= rules.get("min_ot_min", 30):
            result["ot_in"] = ot_in
            result["ot_out"] = ot_out
            result["ot_min"] = ot

    if isinstance(tt, dict):
        sched_in = datetime.combine(d, tt["in_time"])
        sched_out = datetime.combine(d, tt["out_time"])
        grace_late = tt.get("grace_late_min") or 0
        grace_early = tt.get("grace_early_min") or 0
        result["late_min"] = max(0, _minutes(sched_in + timedelta(minutes=grace_late), first_in))
        if not incomplete:
            result["early_min"] = max(0, _minutes(regular_out, sched_out - timedelta(minutes=grace_early)))

    # ---- status per rules ----
    if incomplete:
        # Missed check-out: we can't measure worked time; follow the rule.
        status = "present" if rules["missed_checkout_as"] == "present" else "absent"
    else:
        status = "present"
        if isinstance(tt, dict):
            if rules["halfday_under_min"] and worked < rules["halfday_under_min"]:
                status = "halfday"
            if rules["late_consider_as"] == "absent" and result["late_min"] >= rules["late_exceeds_min"]:
                status = "absent"
            if rules["early_consider_as"] == "absent" and result["early_min"] >= rules["early_exceeds_min"]:
                status = "absent"

    if result["status"] in ("holiday", "dayoff"):
        if worked > 0 or (incomplete and status == "present"):
            result["status"] = "present"  # worked on a day off / holiday
    else:
        result["status"] = status
    return result


def persist(res: dict):
    db.execute(
        """INSERT INTO attendance_day
               (emp_code, work_date, first_in, last_out, worked_min, break_min,
                late_min, early_min, ot_min, ot_in, ot_out, status, computed_at)
           VALUES (%(emp_code)s,%(work_date)s,%(first_in)s,%(last_out)s,%(worked_min)s,
                   %(break_min)s,%(late_min)s,%(early_min)s,%(ot_min)s,%(ot_in)s,%(ot_out)s,
                   %(status)s, now())
           ON CONFLICT (emp_code, work_date) DO UPDATE SET
               first_in=EXCLUDED.first_in, last_out=EXCLUDED.last_out,
               worked_min=EXCLUDED.worked_min, break_min=EXCLUDED.break_min,
               late_min=EXCLUDED.late_min, early_min=EXCLUDED.early_min,
               ot_min=EXCLUDED.ot_min, ot_in=EXCLUDED.ot_in, ot_out=EXCLUDED.ot_out,
               status=EXCLUDED.status, computed_at=now()""",
        res)


def compute_day(d: date) -> int:
    """Compute + persist attendance_day for all active employees on date d."""
    rules = get_rules()
    emps = db.query("SELECT pin, department_id FROM employees WHERE active")
    n = 0
    for e in emps:
        res = compute_employee_day(e["pin"], e["department_id"], d, rules)
        persist(res)
        n += 1
    return n
