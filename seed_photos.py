"""
Import employee photos into our DB from the copied easy TimePro install.
Photos are named by PIN: <root>/files/biophoto/<hash>/<pin>.jpg

Stores each as a base64 data URI in employees.photo. Idempotent.

    py seed_photos.py                 # uses D:\easytime
    py seed_photos.py "D:\easytime"   # custom root
"""
import base64
import glob
import os
import sys

import psycopg2

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"D:\easytime"
DST = dict(host="127.0.0.1", port=5432, user="zkt",
           password="zkt_local_pw", dbname="zkt_attendance")


def main():
    patterns = [
        os.path.join(ROOT, "files", "biophoto", "**", "*.jpg"),
        os.path.join(ROOT, "files", "photo", "**", "*.jpg"),
    ]
    files = {}
    for pat in patterns:
        for path in glob.glob(pat, recursive=True):
            pin = os.path.splitext(os.path.basename(path))[0]
            files.setdefault(pin, path)  # first match (biophoto) wins
    print(f"found {len(files)} photo files (by PIN)")

    dst = psycopg2.connect(**DST); dst.autocommit = False
    cur = dst.cursor()
    updated = 0
    for pin, path in files.items():
        with open(path, "rb") as f:
            data = f.read()
        if not data:
            continue
        uri = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        n = cur.execute("UPDATE employees SET photo=%s WHERE pin=%s", (uri, pin))
        updated += cur.rowcount
    dst.commit()
    cur.close(); dst.close()
    print(f"photos stored on {updated} employees")


if __name__ == "__main__":
    main()
