"""
ZKTeco device discovery + connection — v1.

What it does:
  1. Works out which IPv4 subnet(s) this PC is on.
  2. Scans each subnet for hosts answering on the ZK SDK port (4370).
  3. Connects to every candidate with the ZK protocol (TCP, then UDP).
  4. Reads identity info and flags the one matching our known device.

Run:
    py discover.py                # auto-scan local subnet(s)
    py discover.py 192.168.1.201  # connect straight to a known IP
    py discover.py 192.168.1.0/24 # scan a specific subnet

No ZKTeco DLL required — uses the open-source `pyzk` library, so it runs
the same on Windows, Linux and macOS.
"""

import argparse
import ipaddress
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import device_profile as prof

try:
    from zk import ZK
except ImportError:
    sys.exit(
        "Missing dependency 'pyzk'. Install it first:\n"
        "    py -m pip install -r requirements.txt"
    )


# --------------------------------------------------------------------------- #
# Network helpers
# --------------------------------------------------------------------------- #
def local_ipv4_networks():
    """Return a list of ipaddress.IPv4Network for every local /24 we sit on."""
    nets = set()
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            # Assume a /24 — the common case for office LANs.
            nets.add(ipaddress.ip_network(f"{ip}/24", strict=False))
    except socket.gaierror:
        pass

    # Fallback: ask the OS which interface reaches the internet.
    if not nets:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            nets.add(ipaddress.ip_network(f"{ip}/24", strict=False))
        except OSError:
            pass
        finally:
            s.close()
    return sorted(nets, key=str)


def port_open(ip, port, timeout=0.4):
    """True if a TCP connect to ip:port succeeds within `timeout` seconds."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((str(ip), port)) == 0


def scan_subnet(net, port, workers=128):
    """Return a list of IPs (as str) in `net` with `port` open."""
    hosts = [str(h) for h in net.hosts()]
    found = []
    print(f"  scanning {net} ({len(hosts)} hosts) on port {port} ...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(port_open, ip, port): ip for ip in hosts}
        for fut in as_completed(futures):
            ip = futures[fut]
            try:
                if fut.result():
                    found.append(ip)
            except OSError:
                pass
    return sorted(found, key=lambda x: tuple(int(o) for o in x.split(".")))


# --------------------------------------------------------------------------- #
# Device connection
# --------------------------------------------------------------------------- #
def probe_device(ip, port):
    """
    Try to connect and read identity. Returns a dict on success, else None.
    Tries TCP first, then UDP (some ZK units only answer over UDP).
    """
    for force_udp in (False, True):
        proto = "UDP" if force_udp else "TCP"
        zk = ZK(
            ip,
            port=port,
            timeout=5,
            force_udp=force_udp,
            ommit_ping=True,  # we already know the port is open
        )
        conn = None
        try:
            conn = zk.connect()
            conn.disable_device()  # freeze the terminal UI while we read
            info = {
                "ip": ip,
                "protocol": proto,
                "serial": _safe(conn.get_serialnumber),
                "firmware": _safe(conn.get_firmware_version),
                "device_name": _safe(conn.get_device_name),
                "platform": _safe(conn.get_platform),
                "mac": _safe(conn.get_mac),
                "users": _safe(lambda: len(conn.get_users())),
                "attendance": _safe(lambda: len(conn.get_attendance())),
            }
            return info
        except Exception:
            continue
        finally:
            if conn is not None:
                try:
                    conn.enable_device()
                    conn.disconnect()
                except Exception:
                    pass
    return None


def _safe(fn):
    """Call a getter, returning '?' instead of raising."""
    try:
        return fn()
    except Exception:
        return "?"


def is_our_device(info):
    """Match by serial (primary) or MAC (secondary) against the profile."""
    serial = str(info.get("serial", "")).strip()
    mac = str(info.get("mac", "")).strip().lower()
    if serial and serial == prof.SERIAL_NUMBER:
        return True
    if mac and mac == prof.MAC_ADDRESS.lower():
        return True
    return False


def print_device(info):
    ours = "  <== THIS IS OUR HORUS TL2" if is_our_device(info) else ""
    print(f"\n  Device @ {info['ip']} ({info['protocol']}){ours}")
    print(f"    Name        : {info['device_name']}")
    print(f"    Serial      : {info['serial']}")
    print(f"    MAC         : {info['mac']}")
    print(f"    Platform    : {info['platform']}")
    print(f"    Firmware    : {info['firmware']}")
    print(f"    Users       : {info['users']}")
    print(f"    Attendance  : {info['attendance']} records")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Discover & connect to ZKTeco devices")
    ap.add_argument(
        "target",
        nargs="?",
        help="Optional IP or CIDR. Omit to auto-scan local subnet(s).",
    )
    ap.add_argument("--port", type=int, default=prof.SDK_PORT, help="SDK port (default 4370)")
    args = ap.parse_args()

    print("=" * 64)
    print(" ZKTeco discovery - looking for", prof.DEVICE_NAME, f"(SN {prof.SERIAL_NUMBER})")
    print("=" * 64)

    # 1. Direct IP → skip scanning.
    if args.target and "/" not in args.target:
        candidates = [args.target]
        print(f"\nDirect connect to {args.target}:{args.port}")
    else:
        # 2. Scan a subnet (given or auto-detected).
        if args.target:
            nets = [ipaddress.ip_network(args.target, strict=False)]
        else:
            nets = local_ipv4_networks()
            if not nets:
                sys.exit("Could not determine a local subnet. Pass one explicitly, "
                         "e.g.  py discover.py 192.168.1.0/24")
        print("\nScanning for open port", args.port, "...")
        candidates = []
        for net in nets:
            candidates.extend(scan_subnet(net, args.port))
        if not candidates:
            print("\nNo hosts answered on port", args.port,
                  "\nCheck the terminal is powered on and on the same LAN,",
                  "and that Comm > Ethernet is enabled with a reachable IP.")
            return

    print(f"\n{len(candidates)} candidate host(s): {', '.join(candidates)}")

    # 3. Probe each candidate.
    found_ours = False
    for ip in candidates:
        info = probe_device(ip, args.port)
        if info:
            print_device(info)
            if is_our_device(info):
                found_ours = True
        else:
            print(f"\n  {ip}: port open but ZK handshake failed "
                  "(may be a different service).")

    print("\n" + "=" * 64)
    if found_ours:
        print(" SUCCESS - connected to the Horus TL2. Ready for v2 (pull logs).")
    else:
        print(" Finished. Our specific device was not positively matched above.")
    print("=" * 64)


if __name__ == "__main__":
    main()
