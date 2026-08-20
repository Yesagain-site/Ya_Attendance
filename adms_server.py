"""
ADMS / iclock push server for the ZKTeco Horus TL2 — v2.

Our device runs the "-NF" push firmware: the pull SDK (TCP 4370) is disabled,
but ADMS push is ON. Instead of us connecting to the device, the DEVICE
connects to US and streams its data over HTTP. This server receives it.

It implements the ZKTeco "iclock" / ADMS protocol endpoints:

    GET  /iclock/cdata        -> handshake: device asks for its options
    POST /iclock/cdata        -> device uploads ATTLOG / OPERLOG / USERINFO ...
    GET  /iclock/getrequest   -> device polls for commands (we reply OK = none)
    POST /iclock/devicecmd    -> device reports command results

Everything is logged raw to ./data/raw.log so we can see exactly what the
firmware sends and adapt. Parsed attendance is appended to ./data/attendance.csv
and ./data/attendance.jsonl. Users are saved to ./data/users.jsonl.

Run:
    py adms_server.py                 # listen on 0.0.0.0:8080
    py adms_server.py --port 8080

Then on the terminal:  Menu > Comm. > Cloud Server Setting
    Server Mode    : ADMS
    Server Address : <this PC's IP printed at startup>
    Server Port    : <the port printed at startup>
    (Enable Domain Name: OFF, Enable Proxy: OFF)
Save and the device reconnects within ~30s.

Stdlib only — no external dependencies.
"""

import argparse
import csv
import ipaddress
import json
import os
import socket
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
RAW_LOG = os.path.join(DATA_DIR, "raw.log")
ATT_CSV = os.path.join(DATA_DIR, "attendance.csv")
ATT_JSONL = os.path.join(DATA_DIR, "attendance.jsonl")
USERS_JSONL = os.path.join(DATA_DIR, "users.jsonl")

DEVICE_SUBNET = ipaddress.ip_network("128.0.128.0/20")

# Punch state / verify-mode lookups (for human-readable output).
PUNCH_STATE = {
    "0": "Check-In", "1": "Check-Out", "2": "Break-Out", "3": "Break-In",
    "4": "OT-In", "5": "OT-Out",
}
VERIFY_MODE = {
    "0": "Password", "1": "Fingerprint", "2": "Card", "15": "Face",
}


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def raw_log(text):
    line = f"[{ts()}] {text}"
    print(line, flush=True)
    with open(RAW_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def on_subnet_ips():
    """All local IPv4s that sit on the device's /20 (device can reach these)."""
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ipaddress.ip_address(ip) in DEVICE_SUBNET:
                ips.append(ip)
    except socket.gaierror:
        pass
    return sorted(set(ips))


# --------------------------------------------------------------------------- #
# Data parsing / persistence
# --------------------------------------------------------------------------- #
def save_attendance(sn, body):
    """
    Parse tab-separated ATTLOG lines and append to CSV + JSONL.
    Line layout: PIN \t datetime \t state \t verify \t workcode \t [extras...]
    Returns the number of records parsed.
    """
    count = 0
    csv_exists = os.path.exists(ATT_CSV)
    with open(ATT_CSV, "a", newline="", encoding="utf-8") as fcsv, \
         open(ATT_JSONL, "a", encoding="utf-8") as fjson:
        writer = csv.writer(fcsv)
        if not csv_exists:
            writer.writerow(
                ["device_sn", "pin", "timestamp", "state", "state_name",
                 "verify", "verify_name", "workcode", "received_at"]
            )
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            pin = parts[0]
            when = parts[1]
            state = parts[2] if len(parts) > 2 else ""
            verify = parts[3] if len(parts) > 3 else ""
            workcode = parts[4] if len(parts) > 4 else ""
            rec = {
                "device_sn": sn,
                "pin": pin,
                "timestamp": when,
                "state": state,
                "state_name": PUNCH_STATE.get(state, state),
                "verify": verify,
                "verify_name": VERIFY_MODE.get(verify, verify),
                "workcode": workcode,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            writer.writerow([rec["device_sn"], rec["pin"], rec["timestamp"],
                             rec["state"], rec["state_name"], rec["verify"],
                             rec["verify_name"], rec["workcode"], rec["received_at"]])
            fjson.write(json.dumps(rec) + "\n")
            print(f"    PUNCH  user={pin:>6}  {when}  "
                  f"{rec['state_name']:<10} via {rec['verify_name']}", flush=True)
            count += 1
    return count


def save_users(sn, body):
    """Persist USERINFO lines (key=value pairs, tab or space separated)."""
    count = 0
    with open(USERS_JSONL, "a", encoding="utf-8") as f:
        for line in body.splitlines():
            line = line.strip()
            if not line.startswith("USER"):
                continue
            fields = {}
            for tok in line.replace("USER", "", 1).split("\t"):
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    fields[k.strip()] = v.strip()
            if fields:
                fields["device_sn"] = sn
                fields["received_at"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(fields) + "\n")
                print(f"    USER   PIN={fields.get('PIN','?')}  "
                      f"Name={fields.get('Name','?')}", flush=True)
                count += 1
    return count


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #
class ADMSHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # Silence the default noisy logging; we do our own.
    def log_message(self, fmt, *args):
        pass

    def _reply(self, text, code=200):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return ""
        return self.rfile.read(length).decode("utf-8", errors="replace")

    def _sn(self, qs):
        return (qs.get("SN") or qs.get("sn") or ["UNKNOWN"])[0]

    # ---- GET: handshake + command poll ---- #
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        sn = self._sn(qs)
        raw_log(f"GET  {self.path}  from {self.client_address[0]}")

        if parsed.path.endswith("/cdata"):
            # Initial handshake — tell the device what to send.
            # TransFlag=1111111111 -> transmit everything (attlog, users, ...).
            # Realtime=1 -> push punches as they happen.
            opts = "\n".join([
                f"GET OPTION FROM: {sn}",
                "Stamp=0",
                "OpStamp=0",
                "ErrorDelay=30",
                "Delay=10",
                "TransTimes=00:00;14:05",
                "TransInterval=1",
                "TransFlag=1111111111",
                "Realtime=1",
                "TimeZone=4",
                "Encrypt=0",
            ]) + "\n"
            raw_log(f"  -> handshake OK for SN={sn}")
            self._reply(opts)

        elif parsed.path.endswith("/getrequest"):
            # Device polls for commands to run. Nothing queued -> "OK".
            self._reply("OK")

        else:
            self._reply("OK")

    # ---- POST: data upload + command results ---- #
    def do_POST(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        sn = self._sn(qs)
        table = (qs.get("table") or [""])[0]
        body = self._read_body()
        raw_log(f"POST {self.path}  from {self.client_address[0]}  "
                f"({len(body)} bytes, table={table or '-'})")
        if body:
            with open(RAW_LOG, "a", encoding="utf-8") as f:
                f.write(body + "\n")

        if parsed.path.endswith("/cdata"):
            table_up = table.upper()
            if table_up == "ATTLOG":
                n = save_attendance(sn, body)
                raw_log(f"  -> stored {n} attendance record(s)")
                self._reply(f"OK: {n}")
            elif table_up in ("USERINFO", "OPERLOG"):
                n = save_users(sn, body)
                raw_log(f"  -> stored {n} user record(s) (table={table})")
                self._reply(f"OK: {n}")
            else:
                # Unknown table — logged raw above so we can learn the format.
                self._reply("OK")

        elif parsed.path.endswith("/devicecmd"):
            self._reply("OK")
        else:
            self._reply("OK")


def main():
    ap = argparse.ArgumentParser(description="ZKTeco ADMS / iclock push server")
    ap.add_argument("--host", default="0.0.0.0", help="bind address (default all)")
    ap.add_argument("--port", type=int, default=8080, help="listen port (default 8080)")
    args = ap.parse_args()

    ips = on_subnet_ips()
    print("=" * 66)
    print(" ZKTeco ADMS push server  (v2)")
    print("=" * 66)
    print(f" Listening on {args.host}:{args.port}")
    print(f" Data folder : {DATA_DIR}")
    print("-" * 66)
    if ips:
        print(" On the terminal set  Menu > Comm. > Cloud Server Setting:")
        print(f"     Server Mode    : ADMS")
        print(f"     Server Address : {ips[0]}"
              + (f"   (or {', '.join(ips[1:])})" if len(ips) > 1 else ""))
        print(f"     Server Port    : {args.port}")
        print("     Enable Domain Name / Proxy : OFF")
    else:
        print(" WARNING: no local IP found on the device subnet 128.0.128.0/20.")
        print(" Check this PC is on the same LAN as the terminal.")
    print("-" * 66)
    print(" Waiting for the device to connect...  (Ctrl+C to stop)")
    print("=" * 66)

    server = ThreadingHTTPServer((args.host, args.port), ADMSHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
