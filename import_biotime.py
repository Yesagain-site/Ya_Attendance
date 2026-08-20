"""
One-time import: BioTime (easy TimePro) production dump  ->  our app Postgres.

Reads from the restored `biotime_prod` DB (bundled PG on :7497) and upserts
employees + attendance into our Dockerized app DB (:5432). Idempotent:
re-running adds nothing new (ON CONFLICT DO NOTHING / upsert).

NOTE on time zone: BioTime stores punches as timestamptz. We convert to the
site's wall-clock (Asia/Dubai, GMT+4) and store naive, matching how the UAE
site actually punched. Adjust SITE_TZ below if needed.

Run (with the bundled PG serving biotime_prod on 7497, and the app stack up):
    py import_biotime.py
"""
import psycopg2
import psycopg2.extras

SITE_TZ = "Asia/Dubai"

SRC = dict(host="127.0.0.1", port=7497, user="postgres",
           password="123456", dbname="biotime_prod")
DST = dict(host="127.0.0.1", port=5432, user="zkt",
           password="zkt_local_pw", dbname="zkt_attendance")

PUNCH_STATE = {0: "Check-In", 1: "Check-Out", 2: "Break-Out",
               3: "Break-In", 4: "OT-In", 5: "OT-Out"}
VERIFY_MODE = {0: "Password", 1: "Fingerprint", 2: "Card", 15: "Face"}


def main():
    src = psycopg2.connect(**SRC)
    dst = psycopg2.connect(**DST)
    src.autocommit = True
    dst.autocommit = False
    scur = src.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    dcur = dst.cursor()

    # -------- employees --------
    scur.execute("""
        SELECT emp_code,
               TRIM(BOTH ' ' FROM COALESCE(first_name,'') || ' ' ||
                    COALESCE(last_name,'')) AS name,
               COALESCE(card_no,'') AS card
        FROM personnel_employee
        WHERE emp_code IS NOT NULL AND emp_code <> ''
        ORDER BY emp_code
    """)
    emps = scur.fetchall()
    for e in emps:
        dcur.execute("""
            INSERT INTO employees (pin, name, privilege, privilege_name, card, updated_at)
            VALUES (%s,%s,0,'User',%s, now())
            ON CONFLICT (pin) DO UPDATE SET
                name=EXCLUDED.name, card=EXCLUDED.card, updated_at=now()
        """, (str(e["emp_code"]), e["name"] or None, e["card"] or None))
    dst.commit()
    print(f"employees upserted: {len(emps)}")

    # -------- attendance (batched) --------
    scur.execute(f"""
        SELECT emp_code,
               (punch_time AT TIME ZONE %s) AS local_time,
               COALESCE(NULLIF(punch_state,'')::int, 0) AS punch,
               COALESCE(verify_type, -1) AS verify,
               terminal_sn
        FROM iclock_transaction
        WHERE emp_code IS NOT NULL AND emp_code <> '' AND punch_time IS NOT NULL
    """, (SITE_TZ,))

    insert_sql = """
        INSERT INTO attendance
            (device_sn, pin, punch_time, punch, punch_name, verify, verify_name)
        VALUES %s
        ON CONFLICT (device_sn, pin, punch_time) DO NOTHING
    """
    total = 0
    batch = []
    BATCH = 2000
    while True:
        rows = scur.fetchmany(BATCH)
        if not rows:
            break
        batch = []
        for r in rows:
            batch.append((
                r["terminal_sn"] or "UNKNOWN",
                str(r["emp_code"]),
                r["local_time"],
                r["punch"],
                PUNCH_STATE.get(r["punch"], str(r["punch"])),
                r["verify"],
                VERIFY_MODE.get(r["verify"], str(r["verify"])),
            ))
        psycopg2.extras.execute_values(dcur, insert_sql, batch, page_size=BATCH)
        dst.commit()
        total += len(batch)
        print(f"  attendance processed: {total}", flush=True)

    # -------- final counts --------
    dcur.execute("SELECT count(*) FROM employees")
    emp_n = dcur.fetchone()[0]
    dcur.execute("SELECT count(*) FROM attendance")
    att_n = dcur.fetchone()[0]
    print(f"\nDONE. app DB now has {emp_n} employees, {att_n} attendance rows.")

    scur.close(); dcur.close(); src.close(); dst.close()


if __name__ == "__main__":
    main()
