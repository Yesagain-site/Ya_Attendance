"""
Seed face templates from the BioTime snapshot into our biotemplate table, so
device enrollment (Phase 5) is self-contained. Idempotent.

    py seed_templates.py
"""
import json

import psycopg2
import psycopg2.extras

SRC = dict(host="127.0.0.1", port=7497, user="postgres",
           password="123456", dbname="biotime_prod")
DST = dict(host="127.0.0.1", port=5432, user="zkt",
           password="zkt_local_pw", dbname="zkt_attendance")


def main():
    src = psycopg2.connect(**SRC); src.autocommit = True
    dst = psycopg2.connect(**DST); dst.autocommit = False
    s = src.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    d = dst.cursor()

    s.execute("""
        SELECT pe.emp_code AS pin, b.bio_no, b.bio_index, b.bio_type,
               b.major_ver, b.minor_ver, b.bio_format, b.valid, b.bio_tmp
        FROM iclock_biodata b
        JOIN personnel_employee pe ON pe.id = b.employee_id
        WHERE b.bio_type = 9
    """)
    rows = s.fetchall()
    n = 0
    for r in rows:
        try:
            tmpl = json.loads(r["bio_tmp"]).get("0")
        except Exception:
            tmpl = None
        if not tmpl:
            continue
        d.execute(
            """INSERT INTO biotemplate (pin, bio_no, bio_index, bio_type, major_ver,
                    minor_ver, bio_format, valid, template)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (pin, bio_type, bio_no, bio_index) DO UPDATE SET
                    template=EXCLUDED.template, major_ver=EXCLUDED.major_ver,
                    minor_ver=EXCLUDED.minor_ver, valid=EXCLUDED.valid""",
            (str(r["pin"]), r["bio_no"], r["bio_index"], r["bio_type"],
             r["major_ver"], r["minor_ver"], r["bio_format"], r["valid"], tmpl))
        n += 1
    dst.commit()
    print(f"templates seeded: {n}")
    s.close(); d.close(); src.close(); dst.close()


if __name__ == "__main__":
    main()
