# YA-Attendance — Production migration (keep the same data)

Move the app to the production PC and bring the **current database** with it
(employees, attendance, photos, face templates, shifts/schedules, users,
settings — everything lives in the app's Postgres, so one dump captures it all).

## A. On the CURRENT PC — back up the live database

Do the redirection **inside the container** and copy the file out — this keeps
the dump as clean UTF-8 in any shell. (PowerShell's `>` writes UTF-16, which
psql later rejects with `invalid byte sequence for encoding "UTF8": 0xff` — avoid it.)

```powershell
cd D:\web\zkt-attendance
docker compose exec -T db sh -c "pg_dump -U zkt --clean --if-exists zkt_attendance > /tmp/backup.sql"
docker compose cp db:/tmp/backup.sql ya_attendance_backup.sql
```

Copy two things to the production PC:
- `ya_attendance_backup.sql`  (the data — keep it private; it contains PII + biometric templates)
- your `.env` file            (config/credentials — never commit it)

> Take the backup right before cutover so it's the freshest snapshot.

## B. On the PRODUCTION PC — set up

1. Install **Docker Desktop** (and enable "start on login").
2. Get the code:
   ```bash
   git clone https://github.com/Yesagain-site/Ya_Attendance.git
   cd Ya_Attendance
   ```
   (or copy the project folder over — but never the `dumped db from easyTP/`,
   `import/`, `data/`, or `node_modules/` folders).
3. Put the `.env` file in the project root (or copy `.env.example` → `.env` and edit).
   For production, set strong values:
   ```
   POSTGRES_PASSWORD=<strong>
   JWT_SECRET=<random-long-string>
   ADMIN_PASSWORD=<only used if the DB has no users; your restored admin password wins>
   ```

## C. Restore the data, then start everything

```powershell
# 1) start ONLY the database first
docker compose up -d db

# 2) wait ~10s until healthy, then restore the snapshot.
#    Copy the file into the container and let psql read it (works in any shell,
#    no '<' redirection, no encoding surprises):
docker compose cp ya_attendance_backup.sql db:/tmp/restore.sql
docker compose exec -T db psql -U zkt -d zkt_attendance -f /tmp/restore.sql

# 3) start the rest
docker compose up -d --build
```

(bash alternative for step 2: `docker compose exec -T db psql -U zkt -d zkt_attendance < ya_attendance_backup.sql`)

- The restore's `--clean` drops the fresh seed and replaces it with the **exact
  current state**, so the prod DB is identical (same admin password, employees,
  attendance history, shifts, device names/IPs, calculation rules, photos).
- App: **http://localhost:8090** · API: `:8000` · device ADMS: `:85`.

## D. Point the terminals at the production PC

Same as your current working setup:
- Give the production PC the IP the devices push to (e.g. **128.0.128.170**) —
  ideally a **static IP / DHCP reservation** so it never changes.
- Make sure BioTime is **not** also bound to `:85` on that machine (only one ADMS
  server per port). If BioTime is being retired, stop its `bio-server` service.
- The terminals (already configured to push to `.170:85`) will connect to
  YA-Attendance automatically.

## E. Verify

- Dashboard shows employees/attendance (same numbers as before).
- Devices page shows both terminals; when they push you'll see the ↑ "Uploading".
- Log in with your existing admin password (carried over in the restore).

## Ongoing backups (recommended)

```bash
docker compose exec -T db pg_dump -U zkt --clean --if-exists zkt_attendance > backup_%DATE%.sql
```
Schedule this daily (Windows Task Scheduler) and keep copies off the machine.

## Notes
- `docker compose down` stops the app but **keeps** the data volume.
  `docker compose down -v` **deletes** the database — never use `-v` in production
  unless you have a fresh backup.
- Upgrading later: `git pull` then `docker compose up -d --build` (the schema
  auto-migrates via `IF NOT EXISTS`/`ALTER` on startup; your data is untouched).
