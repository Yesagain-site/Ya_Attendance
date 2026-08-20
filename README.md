# ZKT Attendance — standalone attendance & device-management system

A self-hosted, BioTime-class attendance app for **ZKTeco Horus TL2** face
terminals. Our app **is the device server** (speaks the ADMS/iclock push
protocol) — it does not depend on BioTime / easy TimePro at runtime. BioTime is
used only as a one-time reference for seed data.

Stack: **Postgres + FastAPI + React (Ant Design)**, all in Docker.

## Features (6 phases, all complete)

1. **Device layer** — receives punches/roster/status from terminals over ADMS
   (`/iclock/*`, port 85); on-demand pyzk pull for the check-out unit.
2. **Auth & management** — JWT login, **Admin + Managers** (department-scoped),
   employee CRUD, organization (departments/positions/areas).
3. **Attendance engine** — timetables, shifts (weekly patterns), breaks,
   schedules, and a **Global Rule / Calculation Settings** screen; computes
   worked / late / early / OT / present-absent per day.
4. **Live dashboard** — stat cards, device-status donut, 14-day exception chart,
   live punch feed, real-time hourly monitor; **Excel export** (daily + monthly).
5. **Device orders** — enroll / update / delete users, **push face templates**,
   device-menu commands, per-device command log (self-contained: 160 face
   templates stored locally).
6. **System/admin** — users & roles, manager↔department scoping, employee Excel
   import/export, audit log, change password.

## Run

```bash
docker compose up -d --build
```

- App: **http://localhost:8090**  ·  login **admin / admin123** (change it)
- API: http://localhost:8000/api/health
- Device ADMS endpoint: `:85/iclock/*`

## Seeding from the BioTime dump (one-time)

The bundled Postgres snapshot must be running on `127.0.0.1:7497`, then:

```bash
py import_biotime.py     # employees + attendance history
py seed_org.py           # departments/positions/areas + enrich employees
py seed_templates.py     # 160 face templates (for device enrollment)
```

## Connecting the real devices (cutover test)

Devices push to `.170:85`. To point them at our app without changing device
config: set this PC's IP to **128.0.128.170**, disconnect BioTime from the
network, and our app receives the terminals. Reversible (reconnect BioTime,
restore the IP). Read-only ingest happens automatically; orders queued in
**Device → Device Commands** are delivered when a device polls.

## Navigation

Fixed top navbar (**Dashboard · Personnel · Device · Attendance · System**) with
a dynamic per-section sidebar. The page never scrolls — only the content region
does; the sidebar is static.

## Standalone CLI tools

`discover.py`, `pull_data.py`, `adms_server.py`, `enroll_server.py` remain as
direct-to-device utilities.
