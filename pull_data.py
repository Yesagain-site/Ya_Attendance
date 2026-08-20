"""
Pull users + attendance from the ZKTeco Horus TL2 over the SDK (TCP 4370) — v2.

The device's pull SDK is reachable, so we connect and read everything out,
then export to CSV/JSON. Reading is non-destructive: we NEVER clear the
device's own logs here (that's a separate, explicit action).

Run:
    py pull_data.py 128.0.128.174          # connect to this IP
    py pull_data.py 128.0.128.174 --port 4370

Outputs (in ./data):
    users.csv        one row per enrolled user
    attendance.csv   one row per punch (deduped on re-runs)
    attendance.jsonl append-only raw log of every pull

Stdlib + pyzk only.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

import device_profile as prof

try:
    from zk import ZK
except ImportError:
    sys.exit("Missing 'pyzk'. Run:  py -m pip install -r requirements.txt")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
USERS_CSV = os.path.join(DATA_DIR, "users.csv")
ATT_CSV = os.path.join(DATA_DIR, "attendance.csv")
ATT_JSONL = os.path.join(DATA_DIR, "attendance.jsonl")

PUNCH_STATE = {0: "Check-In", 1: "Check-Out", 2: "Break-Out",
               3: "Break-In", 4: "OT-In", 5: "OT-Out"}
VERIFY_MODE = {0: "Password", 1: "Fingerprint", 2: "Card", 15: "Face"}
PRIVILEGE = {0: "User", 14: "Admin"}


def dedupe_key(sn, pin, when):
    return f"{sn}|{pin}|{when}"


def load_seen_keys():
    """Read existing attendance.csv so re-runs don't duplicate rows."""
    seen = set()
    if os.path.exists(ATT_CSV):
        with open(ATT_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen.add(dedupe_key(row["device_sn"], row["pin"], row["timestamp"]))
    return seen


def main():
    ap = argparse.ArgumentParser(description="Pull users + attendance from ZKTeco")
    ap.add_argument("ip", help="device IP, e.g. 128.0.128.174")
    ap.add_argument("--port", type=int, default=prof.SDK_PORT)
    ap.add_argument("--password", type=int, default=0, help="comm key if set (default 0)")
    args = ap.parse_args()

    print("=" * 68)
    print(f" Pulling from {args.ip}:{args.port}")
    print("=" * 68)

    zk = ZK(args.ip, port=args.port, timeout=10, password=args.password,
            force_udp=False, ommit_ping=True)
    conn = None
    try:
        conn = zk.connect()
        conn.disable_device()  # freeze UI so data is consistent while we read

        sn = conn.get_serialnumber()
        name = conn.get_device_name()
        fw = conn.get_firmware_version()
        match = " (OUR DEVICE)" if sn == prof.SERIAL_NUMBER else ""
        print(f" Device : {name}  SN={sn}{match}")
        print(f" Firmware: {fw}")
        print("-" * 68)

        # ---- Users ----
        users = conn.get_users()
        with open(USERS_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["device_sn", "uid", "pin", "name", "privilege",
                        "privilege_name", "card", "group_id", "pulled_at"])
            for u in users:
                w.writerow([sn, u.uid, u.user_id, u.name, u.privilege,
                            PRIVILEGE.get(u.privilege, u.privilege),
                            u.card, u.group_id,
                            datetime.now(timezone.utc).isoformat()])
        print(f" USERS: {len(users)}")
        for u in users:
            print(f"    PIN {u.user_id:>6}  {u.name or '(no name)':<20} "
                  f"[{PRIVILEGE.get(u.privilege, u.privilege)}]")

        # ---- Attendance ----
        att = conn.get_attendance()
        seen = load_seen_keys()
        new_rows = 0
        csv_exists = os.path.exists(ATT_CSV)
        with open(ATT_CSV, "a", newline="", encoding="utf-8") as fcsv, \
             open(ATT_JSONL, "a", encoding="utf-8") as fjson:
            w = csv.writer(fcsv)
            if not csv_exists:
                w.writerow(["device_sn", "pin", "timestamp", "punch",
                            "punch_name", "verify", "verify_name", "pulled_at"])
            print("-" * 68)
            print(f" ATTENDANCE: {len(att)} record(s) on device")
            for a in sorted(att, key=lambda x: x.timestamp):
                when = a.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                key = dedupe_key(sn, a.user_id, when)
                punch_name = PUNCH_STATE.get(a.punch, str(a.punch))
                verify_name = VERIFY_MODE.get(a.status, str(a.status))
                flag = " " if key in seen else "+"
                print(f"   {flag} PIN {a.user_id:>6}  {when}  "
                      f"{punch_name:<10} via {verify_name}")
                if key in seen:
                    continue
                w.writerow([sn, a.user_id, when, a.punch, punch_name,
                            a.status, verify_name,
                            datetime.now(timezone.utc).isoformat()])
                fjson.write(json.dumps({
                    "device_sn": sn, "pin": a.user_id, "timestamp": when,
                    "punch": a.punch, "punch_name": punch_name,
                    "verify": a.status, "verify_name": verify_name,
                    "pulled_at": datetime.now(timezone.utc).isoformat(),
                }) + "\n")
                new_rows += 1

        print("-" * 68)
        print(f" Done. {new_rows} new record(s) added "
              f"({len(att) - new_rows} already had).")
        print(f" Files: {USERS_CSV}")
        print(f"        {ATT_CSV}")
        print("=" * 68)

    except Exception as e:
        print(f"\n ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        if conn is not None:
            try:
                conn.enable_device()
                conn.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()
