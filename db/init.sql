-- ZKT Attendance — full schema (standalone device-management app)
-- Baked into the db image; runs on first init of an empty data dir.

-- ============================ Devices ============================
CREATE TABLE IF NOT EXISTS device (
    sn                TEXT PRIMARY KEY,
    name              TEXT,
    ip                TEXT,
    area_id           INTEGER,
    direction         TEXT DEFAULT 'both',      -- 'in' | 'out' | 'both'
    firmware          TEXT,
    platform          TEXT,
    online            BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen         TIMESTAMPTZ,
    user_count        INTEGER DEFAULT 0,
    face_count        INTEGER DEFAULT 0,
    fp_count          INTEGER DEFAULT 0,
    transaction_count INTEGER DEFAULT 0,
    settings          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================ Org ===============================
CREATE TABLE IF NOT EXISTS department (
    id INTEGER PRIMARY KEY, code TEXT, name TEXT, parent_id INTEGER
);
CREATE TABLE IF NOT EXISTS position (
    id INTEGER PRIMARY KEY, code TEXT, name TEXT, parent_id INTEGER
);
CREATE TABLE IF NOT EXISTS area (
    id INTEGER PRIMARY KEY, code TEXT, name TEXT, parent_id INTEGER
);

-- ============================ Employees =========================
CREATE TABLE IF NOT EXISTS employees (
    id             SERIAL PRIMARY KEY,
    pin            TEXT NOT NULL UNIQUE,          -- device user id (PIN / emp_code)
    name           TEXT,
    first_name     TEXT,
    last_name      TEXT,
    privilege      INTEGER DEFAULT 0,
    privilege_name TEXT,
    card           TEXT,
    group_id       TEXT,
    department_id  INTEGER,
    position_id    INTEGER,
    area_id        INTEGER,
    gender         TEXT,
    mobile         TEXT,
    hire_date      DATE,
    photo          TEXT,
    active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_employees_dept ON employees (department_id);

-- ============================ Attendance (raw punches) ==========
CREATE TABLE IF NOT EXISTS attendance (
    id          BIGSERIAL PRIMARY KEY,
    device_sn   TEXT NOT NULL,
    pin         TEXT NOT NULL,
    punch_time  TIMESTAMP NOT NULL,
    punch       INTEGER,
    punch_name  TEXT,
    verify      INTEGER,
    verify_name TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_attendance UNIQUE (device_sn, pin, punch_time)
);
CREATE INDEX IF NOT EXISTS ix_attendance_pin_time ON attendance (pin, punch_time);
CREATE INDEX IF NOT EXISTS ix_attendance_time     ON attendance (punch_time);

-- ============================ Auth / roles ======================
CREATE TABLE IF NOT EXISTS app_user (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'manager',  -- 'admin' | 'manager'
    full_name     TEXT,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS manager_department (
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    dept_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, dept_id)
);

-- ============================ Attendance config =================
CREATE TABLE IF NOT EXISTS timetable (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    in_time         TIME NOT NULL,
    out_time        TIME NOT NULL,
    grace_late_min  INTEGER NOT NULL DEFAULT 0,
    grace_early_min INTEGER NOT NULL DEFAULT 0,
    work_minutes    INTEGER,                      -- expected worked minutes
    break_minutes   INTEGER NOT NULL DEFAULT 0,
    ot_after_min    INTEGER,                      -- OT threshold (worked minutes)
    ot_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS shift (
    id SERIAL PRIMARY KEY, name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS shift_detail (
    id           SERIAL PRIMARY KEY,
    shift_id     INTEGER NOT NULL REFERENCES shift(id) ON DELETE CASCADE,
    day_index    INTEGER NOT NULL,                -- 0=Mon .. 6=Sun
    timetable_id INTEGER REFERENCES timetable(id),
    is_off       BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS break_time (
    id SERIAL PRIMARY KEY, name TEXT, minutes INTEGER NOT NULL DEFAULT 0,
    mode TEXT NOT NULL DEFAULT 'auto'             -- 'auto' | 'punch'
);
CREATE TABLE IF NOT EXISTS employee_schedule (
    id            SERIAL PRIMARY KEY,
    emp_code      TEXT,                            -- null => department-level
    department_id INTEGER,                         -- null => employee-level
    shift_id      INTEGER NOT NULL REFERENCES shift(id) ON DELETE CASCADE,
    start_date    DATE,
    end_date      DATE
);
CREATE TABLE IF NOT EXISTS ot_rule (
    id SERIAL PRIMARY KEY, name TEXT, threshold_min INTEGER,
    multiplier NUMERIC NOT NULL DEFAULT 1.5
);
CREATE TABLE IF NOT EXISTS holiday (
    id SERIAL PRIMARY KEY, name TEXT, day DATE NOT NULL
);

-- ============================ Computed daily ====================
CREATE TABLE IF NOT EXISTS attendance_day (
    emp_code    TEXT NOT NULL,
    work_date   DATE NOT NULL,
    first_in    TIMESTAMP,
    last_out    TIMESTAMP,
    worked_min  INTEGER NOT NULL DEFAULT 0,
    break_min   INTEGER NOT NULL DEFAULT 0,
    late_min    INTEGER NOT NULL DEFAULT 0,
    early_min   INTEGER NOT NULL DEFAULT 0,
    ot_min      INTEGER NOT NULL DEFAULT 0,
    ot_in       TIMESTAMP,
    ot_out      TIMESTAMP,
    status      TEXT,                              -- present/absent/incomplete/dayoff/holiday
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (emp_code, work_date)
);

-- ============================ Device orders (Phase 5) ===========
CREATE TABLE IF NOT EXISTS device_command (
    id          BIGSERIAL PRIMARY KEY,
    sn          TEXT NOT NULL,
    content     TEXT NOT NULL,
    kind        TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending/sent/done/error
    queued_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at     TIMESTAMPTZ,
    return_at   TIMESTAMPTZ,
    return_code TEXT
);
CREATE INDEX IF NOT EXISTS ix_devicecmd_sn_status ON device_command (sn, status);

-- ============================ Misc ==============================
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY, user_id INTEGER, action TEXT, entity TEXT,
    detail TEXT, ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Face/bio templates we can push to devices (Phase 5). Seeded from the
-- BioTime dump so enrollment is self-contained (no runtime BioTime dependency).
CREATE TABLE IF NOT EXISTS biotemplate (
    id         BIGSERIAL PRIMARY KEY,
    pin        TEXT NOT NULL,
    bio_no     INTEGER NOT NULL DEFAULT 0,
    bio_index  INTEGER NOT NULL DEFAULT 0,
    bio_type   INTEGER NOT NULL DEFAULT 9,   -- 9 = face (ZKFace VX3.5)
    major_ver  TEXT,
    minor_ver  TEXT,
    bio_format INTEGER NOT NULL DEFAULT 0,
    valid      INTEGER NOT NULL DEFAULT 1,
    template   TEXT NOT NULL,                -- base64 template payload
    UNIQUE (pin, bio_type, bio_no, bio_index)
);
CREATE INDEX IF NOT EXISTS ix_biotemplate_pin ON biotemplate (pin);

-- Legacy sync log (kept for the pyzk pull path).
CREATE TABLE IF NOT EXISTS sync_log (
    id BIGSERIAL PRIMARY KEY, device_sn TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running', records_new INTEGER DEFAULT 0,
    records_seen INTEGER DEFAULT 0, message TEXT
);
