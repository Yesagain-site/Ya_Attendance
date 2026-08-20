"""
FastAPI backend:
  • /iclock/*  device-facing ADMS server (Phase 1, read-only)
  • /api/*     management API for the UI
"""
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import adms, attendance_engine, auth, db, reports
from . import router_auth, router_employees, router_org, router_attendance
from . import router_dashboard, router_reports, router_devices, router_admin


def _ensure_extra_schema():
    """Idempotent DDL for tables added after the initial schema (existing DBs)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS biotemplate (
            id BIGSERIAL PRIMARY KEY, pin TEXT NOT NULL,
            bio_no INTEGER NOT NULL DEFAULT 0, bio_index INTEGER NOT NULL DEFAULT 0,
            bio_type INTEGER NOT NULL DEFAULT 9, major_ver TEXT, minor_ver TEXT,
            bio_format INTEGER NOT NULL DEFAULT 0, valid INTEGER NOT NULL DEFAULT 1,
            template TEXT NOT NULL,
            UNIQUE (pin, bio_type, bio_no, bio_index))""")
    db.execute("CREATE INDEX IF NOT EXISTS ix_biotemplate_pin ON biotemplate (pin)")
    # OT session boundaries added for shift v2 (safe on existing DBs).
    db.execute("ALTER TABLE attendance_day ADD COLUMN IF NOT EXISTS ot_in TIMESTAMP")
    db.execute("ALTER TABLE attendance_day ADD COLUMN IF NOT EXISTS ot_out TIMESTAMP")
    # Device activity timestamps (upload = device→us, cmd = us→device).
    db.execute("ALTER TABLE device ADD COLUMN IF NOT EXISTS last_data_at TIMESTAMPTZ")
    db.execute("ALTER TABLE device ADD COLUMN IF NOT EXISTS last_cmd_at TIMESTAMPTZ")
from .zk_sync import SyncError, device_status, run_sync


def _seed_attendance_defaults():
    """Create a default 08:00–17:00 timetable + rule pointer if none exists."""
    if db.query("SELECT 1 FROM timetable LIMIT 1"):
        return
    tid = db.query(
        """INSERT INTO timetable (name, in_time, out_time, grace_late_min,
               grace_early_min, work_minutes, break_minutes, ot_after_min, ot_enabled)
           VALUES ('Standard Day 08-19','08:00','19:00',10,10,585,0,0,TRUE)
           RETURNING id""")[0]["id"]
    rules = attendance_engine.get_rules()
    rules["default_timetable_id"] = tid
    attendance_engine.save_rules(rules)
    print(f"[startup] seeded default timetable id={tid}", flush=True)

# A device is considered offline if we haven't heard from it in this window.
OFFLINE_AFTER_SEC = int(os.environ.get("DEVICE_OFFLINE_AFTER_SEC", "180"))
PULL_SYNC_INTERVAL = int(os.environ.get("PULL_SYNC_INTERVAL_SECONDS", "0"))  # 0 = off
scheduler = BackgroundScheduler(daemon=True)


def _mark_offline():
    try:
        db.execute(
            "UPDATE device SET online = FALSE "
            "WHERE online = TRUE AND (last_seen IS NULL "
            "OR last_seen < now() - (%s || ' seconds')::interval)",
            (OFFLINE_AFTER_SEC,),
        )
    except Exception as e:  # pragma: no cover
        print(f"[offline-job] {e}", flush=True)


def _pull_sync():
    try:
        print(f"[pull-sync] {run_sync()}", flush=True)
    except SyncError as e:
        print(f"[pull-sync] failed: {e}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_pool()
    _ensure_extra_schema()
    auth.seed_admin()
    _seed_attendance_defaults()
    scheduler.add_job(_mark_offline, "interval", seconds=30, id="offline",
                      max_instances=1, coalesce=True)
    if PULL_SYNC_INTERVAL > 0:
        scheduler.add_job(_pull_sync, "interval", seconds=PULL_SYNC_INTERVAL,
                          id="pull", max_instances=1, coalesce=True)
    scheduler.start()
    print("[startup] scheduler on (offline-check 30s"
          + (f", pull-sync {PULL_SYNC_INTERVAL}s)" if PULL_SYNC_INTERVAL else ")"),
          flush=True)
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="YA-Attendance", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(adms.router)          # device-facing /iclock/*
app.include_router(router_auth.router)   # /api/auth/*
app.include_router(router_employees.router)  # /api/employees/*
app.include_router(router_org.router)    # /api/departments, /positions, /areas
app.include_router(router_attendance.router)  # /api/attendance/* (rules, config, engine)
app.include_router(router_dashboard.router)   # /api/dashboard/*
app.include_router(router_reports.router)     # /api/reports/* (+ xlsx)
app.include_router(router_devices.router)     # /api/devices/* orders (Phase 5)
app.include_router(router_admin.router)       # /api/admin/* (users, roles, audit)


# ------------------------------- API ------------------------------- #
@app.get("/api/health")
def health():
    try:
        db.query("SELECT 1 AS ok")
        return {"status": "ok", "db": "up"}
    except Exception as e:
        raise HTTPException(500, f"db down: {e}")


@app.get("/api/devices")
def devices():
    return db.query(
        f"""SELECT sn, name, ip, area_id, direction, firmware, platform,
                   (last_seen > now() - ({OFFLINE_AFTER_SEC} || ' seconds')::interval) AS online,
                   last_seen, last_data_at, last_cmd_at,
                   user_count, face_count, fp_count, transaction_count,
                   CASE
                     WHEN last_data_at > now() - interval '20 seconds' THEN 'upload'
                     WHEN last_cmd_at  > now() - interval '20 seconds' THEN 'download'
                     ELSE NULL
                   END AS activity
            FROM device ORDER BY sn"""
    )


@app.get("/api/summary")
def summary():
    totals = db.query(
        f"""SELECT
              (SELECT count(*) FROM employees WHERE active)          AS employees,
              (SELECT count(*) FROM attendance)                      AS punches_total,
              (SELECT count(*) FROM attendance
                 WHERE punch_time::date = CURRENT_DATE)              AS punches_today,
              (SELECT count(DISTINCT pin) FROM attendance
                 WHERE punch_time::date = CURRENT_DATE)              AS present_today,
              (SELECT count(*) FROM device)                          AS devices_total,
              (SELECT count(*) FROM device
                 WHERE last_seen > now() - ({OFFLINE_AFTER_SEC} || ' seconds')::interval)
                                                                     AS devices_online
        """
    )[0]
    return totals


@app.get("/api/attendance")
def attendance(pin: str | None = None,
               date_from: str | None = Query(None, alias="from"),
               date_to: str | None = Query(None, alias="to"),
               limit: int = 500):
    return reports.attendance_rows(pin, date_from, date_to, min(limit, 5000))


@app.get("/api/reports/daily")
def daily(date: str):
    return reports.daily_report(date)


@app.get("/api/recent-punches")
def recent_punches(limit: int = 20):
    return db.query(
        f"SELECT a.pin, {db.FULLNAME} AS name, "
        "(e.photo IS NOT NULL AND e.photo<>'') AS has_photo, "
        "a.punch_time, a.punch_name, a.verify_name, a.device_sn "
        "FROM attendance a LEFT JOIN employees e ON e.pin = a.pin "
        "ORDER BY a.punch_time DESC LIMIT %s", (min(limit, 100),)
    )


# ---- on-demand pyzk pull from .174 (secondary read channel) ---- #
@app.get("/api/device/probe")
def device_probe():
    return device_status()


@app.post("/api/sync")
def sync_now():
    try:
        return {"ok": True, "summary": run_sync()}
    except SyncError as e:
        raise HTTPException(502, f"device sync failed: {e}")
