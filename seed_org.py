"""
Seed org structure (departments/positions/areas) and enrich employees from the
BioTime snapshot into our app DB. Run after import_biotime.py. Idempotent.

    py seed_org.py
"""
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

    # --- org tables ---
    for table, code_col, name_col, parent_col, dst_table in [
        ("personnel_department", "dept_code", "dept_name", "parent_dept_id", "department"),
        ("personnel_position", "position_code", "position_name", "parent_position_id", "position"),
        ("personnel_area", "area_code", "area_name", "parent_area_id", "area"),
    ]:
        s.execute(f"SELECT id, {code_col} AS code, {name_col} AS name, "
                  f"{parent_col} AS parent_id FROM {table}")
        rows = s.fetchall()
        for r in rows:
            d.execute(
                f"""INSERT INTO {dst_table} (id, code, name, parent_id)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        code=EXCLUDED.code, name=EXCLUDED.name, parent_id=EXCLUDED.parent_id""",
                (r["id"], r["code"], r["name"], r["parent_id"]))
        dst.commit()
        print(f"{dst_table}: {len(rows)}")

    # --- enrich employees ---
    s.execute("""SELECT emp_code, first_name, last_name, department_id, position_id,
                        gender, mobile, hire_date
                 FROM personnel_employee WHERE emp_code IS NOT NULL AND emp_code<>''""")
    emps = s.fetchall()
    updated = 0
    for e in emps:
        n = d.execute(
            """UPDATE employees SET
                   first_name=%s, last_name=%s, department_id=%s, position_id=%s,
                   gender=%s, mobile=%s, hire_date=%s, updated_at=now()
               WHERE pin=%s""",
            (e["first_name"], e["last_name"], e["department_id"], e["position_id"],
             e["gender"], e["mobile"], e["hire_date"], str(e["emp_code"])))
        updated += d.rowcount
    dst.commit()
    print(f"employees enriched: {updated}")

    s.close(); d.close(); src.close(); dst.close()


if __name__ == "__main__":
    main()
