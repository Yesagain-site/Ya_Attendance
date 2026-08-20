"""
ADMS enrollment server — push users + FACE templates to a ZKTeco device — v3.

The new device (.174) can't be enrolled by BioTime (license/registration block),
so WE act as the ADMS server and push the enrollment ourselves. We hold the
160 face templates from the production dump, so no photos are needed.

Flow (all over the ADMS/iclock HTTP protocol):
  1. Point the device's Cloud Server at THIS server (Menu > Comm > Cloud Server).
  2. Device handshakes  -> GET /iclock/cdata
  3. Device polls        -> GET /iclock/getrequest  -> we hand it queued commands:
        C:<id>:DATA USER PIN=..\tName=..\t...
        C:<id>:DATA UPDATE BIODATA Pin=..\tType=9\tMajorVer=35\t..\tTmp=<base64>
  4. Device reports each -> POST /iclock/devicecmd (ID=..&Return=<code>&CMD=..)
        Return=0  => command accepted. This is our success signal.

Data source: the restored biotime_prod DB (bundled PG on :7497).

Run a SMALL TEST first (default: 3 users), watch the return codes, verify a
face on the device, then roll out everyone with --all:
    py enroll_server.py --port 8080                 # test: first 3 templated users
    py enroll_server.py --port 8080 --pins 1003,1007
    py enroll_server.py --port 8080 --all           # all 160

Stdlib + psycopg2.
"""
import argparse
import ipaddress
import itertools
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import psycopg2
import psycopg2.extras

SRC = dict(host="127.0.0.1", port=7497, user="postgres",
           password="123456", dbname="biotime_prod")
DEVICE_SUBNET = ipaddress.ip_network("128.0.128.0/20")

# --- global command queue + results, guarded by a lock ---
_lock = threading.Lock()
_queue = []          # list of dicts: {id, pin, kind, cmd, status}
_results = {}        # id -> return code
_cmd_ids = itertools.count(1)


def on_subnet_ips():
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ipaddress.ip_address(ip) in DEVICE_SUBNET:
                ips.append(ip)
    except socket.gaierror:
        pass
    return sorted(set(ips))


def load_enrollment(pins=None, limit=None):
    """Return list of {pin, name, tmpl fields, b64} for users with a face template."""
    conn = psycopg2.connect(**SRC)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    q = """
        SELECT pe.emp_code AS pin,
               TRIM(BOTH ' ' FROM COALESCE(pe.first_name,'')||' '||COALESCE(pe.last_name,'')) AS name,
               b.bio_no, b.bio_index, b.bio_type, b.major_ver, b.minor_ver,
               b.bio_format, b.valid, (b.bio_tmp::jsonb->>'0') AS b64
        FROM iclock_biodata b
        JOIN personnel_employee pe ON pe.id = b.employee_id
        WHERE b.bio_type = 9 AND (b.bio_tmp::jsonb->>'0') IS NOT NULL
    """
    params = []
    if pins:
        q += " AND pe.emp_code = ANY(%s)"
        params.append(pins)
    q += " ORDER BY pe.emp_code"
    if limit:
        q += f" LIMIT {int(limit)}"
    cur.execute(q, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def build_queue(users):
    """Queue a DATA USER then a DATA UPDATE BIODATA command for each user."""
    with _lock:
        for u in users:
            pin = str(u["pin"])
            name = (u["name"] or pin).replace("\t", " ")
            # Mirror BioTime's exact USER field layout for this device family.
            user_cmd = (f"DATA USER PIN={pin}\tName={name}\tPri=0\tPasswd=\t"
                        f"Card=\t\tGrp=1\tVerify=0")
            bio_cmd = (f"DATA UPDATE BIODATA Pin={pin}\tNo={u['bio_no']}\t"
                       f"Index={u['bio_index']}\tValid={u['valid']}\tDuress=0\t"
                       f"Type={u['bio_type']}\tMajorVer={u['major_ver']}\t"
                       f"MinorVer={u['minor_ver']}\tFormat={u['bio_format']}\t"
                       f"Tmp={u['b64']}")
            for kind, cmd in (("USER", user_cmd), ("BIODATA", bio_cmd)):
                _queue.append({"id": next(_cmd_ids), "pin": pin,
                               "kind": kind, "cmd": cmd, "status": "pending"})


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _reply(self, text, code=200):
        data = text.encode("utf-8", "replace")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(n).decode("utf-8", "replace") if n > 0 else ""

    def do_GET(self):
        p = urlparse(self.path)
        qs = parse_qs(p.query)
        sn = (qs.get("SN") or ["?"])[0]

        if p.path.endswith("/cdata"):
            # Handshake — poll every 5s so the test moves quickly.
            opts = "\n".join([
                f"GET OPTION FROM: {sn}", "Stamp=0", "OpStamp=0",
                "ErrorDelay=10", "Delay=5", "TransTimes=00:00;14:05",
                "TransInterval=1", "TransFlag=1111111111", "Realtime=1",
                "TimeZone=4", "Encrypt=0",
            ]) + "\n"
            print(f"[handshake] SN={sn}", flush=True)
            self._reply(opts)

        elif p.path.endswith("/getrequest"):
            # Hand the device its pending commands.
            out = []
            with _lock:
                for item in _queue:
                    if item["status"] == "pending":
                        out.append(f"C:{item['id']}:{item['cmd']}")
                        item["status"] = "sent"
            if out:
                for item_line in out:
                    head = item_line[:70]
                    print(f"[send]  {head}...", flush=True)
                self._reply("\n".join(out) + "\n")
            else:
                self._reply("OK")
        else:
            self._reply("OK")

    def do_POST(self):
        p = urlparse(self.path)
        qs = parse_qs(p.query)
        sn = (qs.get("SN") or ["?"])[0]
        body = self._body()

        if p.path.endswith("/devicecmd"):
            # Device reports command results: lines like ID=12&Return=0&CMD=DATA
            for line in body.splitlines():
                line = line.strip()
                if not line or "ID=" not in line:
                    continue
                fields = dict(kv.split("=", 1) for kv in line.split("&") if "=" in kv)
                cid = int(fields.get("ID", -1))
                ret = fields.get("Return", "?")
                with _lock:
                    _results[cid] = ret
                    match = next((q for q in _queue if q["id"] == cid), None)
                    if match:
                        match["status"] = f"done(ret={ret})"
                        tag = "OK " if ret == "0" else "FAIL"
                        print(f"[result] {tag} id={cid} {match['kind']} "
                              f"PIN={match['pin']} Return={ret}", flush=True)
                        self._print_progress()
            self._reply("OK")
        elif p.path.endswith("/cdata"):
            # Attendance/other uploads during the test — just acknowledge.
            self._reply("OK")
        else:
            self._reply("OK")

    def _print_progress(self):
        total = len(_queue)
        done = sum(1 for q in _queue if q["status"].startswith("done"))
        ok = sum(1 for q in _queue if q["status"] == "done(ret=0)")
        if done == total and total:
            print(f"\n=== ALL {total} COMMANDS DONE — {ok} OK, "
                  f"{total-ok} failed ===\n", flush=True)


def main():
    ap = argparse.ArgumentParser(description="ADMS enrollment (users + face templates)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--pins", help="comma-separated emp_codes to enroll")
    ap.add_argument("--all", action="store_true", help="enroll all templated users")
    args = ap.parse_args()

    if args.pins:
        users = load_enrollment(pins=[p.strip() for p in args.pins.split(",")])
    elif args.all:
        users = load_enrollment()
    else:
        users = load_enrollment(limit=3)  # safe default: small test batch

    if not users:
        raise SystemExit("No templated users matched. Is biotime_prod on :7497 up?")

    build_queue(users)
    ips = on_subnet_ips()

    print("=" * 66)
    print(" ZKTeco ADMS ENROLLMENT server (v3)")
    print("=" * 66)
    print(f" Enrolling {len(users)} user(s): "
          f"{', '.join(str(u['pin']) for u in users[:10])}"
          + (" ..." if len(users) > 10 else ""))
    print(f" Queued {len(_queue)} commands (USER + BIODATA per user).")
    print("-" * 66)
    if ips:
        print(" On the NEW device (.174) set Menu > Comm > Cloud Server Setting:")
        print(f"     Server Mode : ADMS")
        print(f"     Address     : {ips[0]}")
        print(f"     Port        : {args.port}")
        print("     Domain/Proxy: OFF   (then Save)")
    print(" Watching for the device... Return=0 means a command was accepted.")
    print(" (Ctrl+C to stop)")
    print("=" * 66)

    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
