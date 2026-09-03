#!/usr/bin/env python3
"""download.py -- pull telemetry logs from /flash to host tmp/telemetry.

This uses the REPL over USB, so it is for AFTER an untethered run has stopped. It sends Ctrl-C to get
the prompt and therefore is intentionally separate from the BLE/slot tools that keep Hub OS alive.

    python3 hub_programmer/download.py --list
    python3 hub_programmer/download.py --all
    python3 hub_programmer/download.py /flash/tmp/telemetry/run-0000012345.csv

Exit codes: 0 ok · 2 no prompt · 3 no port · 4 busy · 5 no pyserial · 64 usage
"""
import ast
import base64
import hashlib
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "probes"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402
from upload import Session, hub_path_exists                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HUB_DIR = "/flash/tmp/telemetry"
DEFAULT_DEST = os.path.join(ROOT, "tmp", "telemetry")
DEFAULT_CHUNK = 512


def usage():
    print(__doc__.strip())
    return 64


def opt(argv, flag, default):
    if flag in argv:
        i = argv.index(flag)
        if i + 1 >= len(argv):
            raise ValueError("%s needs a value" % flag)
        return argv[i + 1]
    return default


def last_line(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def safe_hub_path(path):
    if "\x00" in path or "\n" in path or "\r" in path or "'" in path:
        raise ValueError("invalid hub path")
    if path != "/flash" and not path.startswith("/flash/"):
        raise ValueError("refusing to read outside /flash: %s" % path)
    return path


def safe_leaf(path):
    leaf = os.path.basename(path.rstrip("/")) or "flash"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", leaf)


def hub_eval(sess, expr, timeout=8.0):
    text = sess.cmd(expr, timeout=timeout)
    if "Traceback" in text:
        raise RuntimeError(text)
    return last_line(text)


def hub_listdir(sess, directory):
    directory = safe_hub_path(directory.rstrip("/") or "/flash")
    text = sess.cmd("import os; print(os.listdir(%r))" % directory, timeout=8.0)
    if "Traceback" in text:
        return []
    try:
        names = ast.literal_eval(last_line(text))
    except Exception:
        return []
    return [n for n in names if isinstance(n, str)]


def hub_size(sess, path):
    path = safe_hub_path(path)
    return int(hub_eval(sess, "import os; print(os.stat(%r)[6])" % path))


def hub_sha256(sess, path):
    path = safe_hub_path(path)
    code = (
        "import hashlib,binascii\n"
        "h=hashlib.sha256()\n"
        "f=open(%r,'rb')\n"
        "while True:\n"
        " b=f.read(512)\n"
        " if not b: break\n"
        " h.update(b)\n"
        "f.close()\n"
        "print(binascii.hexlify(h.digest()).decode())"
    ) % path
    return hub_eval(sess, "exec(%r)" % code, timeout=20.0)


def hub_read_chunk(sess, path, offset, size):
    path = safe_hub_path(path)
    code = (
        "import binascii\n"
        "f=open(%r,'rb')\n"
        "f.seek(%d)\n"
        "print(binascii.b2a_base64(f.read(%d)).decode().strip())\n"
        "f.close()"
    ) % (path, offset, size)
    token = hub_eval(sess, "exec(%r)" % code, timeout=10.0)
    return base64.b64decode(token.encode("ascii"), validate=True)


def download_one(sess, path, dest, chunk_size):
    path = safe_hub_path(path)
    os.makedirs(dest, exist_ok=True)
    size = hub_size(sess, path)
    hub_hash = hub_sha256(sess, path) if size else hashlib.sha256(b"").hexdigest()
    stamp = time.strftime("%Y%m%dT%H%M%S")
    out = os.path.join(dest, "%s-%s" % (stamp, safe_leaf(path)))
    part = out + ".part"
    h = hashlib.sha256()
    with open(part, "wb") as fh:
        offset = 0
        while offset < size:
            chunk = hub_read_chunk(sess, path, offset, min(chunk_size, size - offset))
            fh.write(chunk)
            h.update(chunk)
            offset += len(chunk)
    got_hash = h.hexdigest()
    if got_hash != hub_hash:
        raise RuntimeError("sha256 mismatch for %s: hub %s host %s" % (path, hub_hash, got_hash))
    os.replace(part, out)
    print("downloaded %s -> %s  (%d bytes sha256 %s)" % (path, out, size, got_hash))
    return out


def list_logs(sess, directory):
    print("hub log dir: %s" % directory)
    names = hub_listdir(sess, directory)
    if not names:
        print("  (empty or missing)")
    for name in sorted(names):
        path = directory.rstrip("/") + "/" + name
        try:
            print("  %8d  %s" % (hub_size(sess, path), path))
        except Exception:
            print("  directory? %s" % path)
    try:
        free = hub_eval(sess, "import os; s=os.statvfs('/flash'); print(s[0]*s[3])")
        print("flash free bytes: %s" % free)
    except Exception:
        pass


def main(argv):
    try:
        hub_dir = opt(argv, "--dir", DEFAULT_HUB_DIR)
        dest = opt(argv, "--dest", DEFAULT_DEST)
        chunk_size = int(opt(argv, "--chunk", str(DEFAULT_CHUNK)))
    except ValueError as exc:
        print(exc)
        return 64
    if chunk_size <= 0:
        print("--chunk must be positive")
        return 64

    flags_with_values = {"--dir", "--dest", "--chunk"}
    files = []
    skip_next = False
    for a in argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if a in flags_with_values:
            skip_next = True
            continue
        if a.startswith("--"):
            continue
        files.append(a)

    if not files and "--list" not in argv and "--all" not in argv:
        return usage()

    try:
        import serial
    except ImportError:
        print("NO_PYSERIAL: python3 -m pip install pyserial")
        return 5

    port = _hubio.find_port()
    if port is None:
        print("UNKNOWN: no /dev/spike or /dev/ttyACM0 -- hub not enumerated.")
        return 3

    try:
        sess = Session(port, serial)
    except Exception as exc:
        print("BUSY_OR_DENIED: %s: %s" % (port, exc))
        return 4
    try:
        if not sess.wake():
            print("No '>>>' prompt. The hub is not presenting a REPL; refusing to read.")
            return 2
        if "--list" in argv:
            list_logs(sess, hub_dir)
        if "--all" in argv:
            if not hub_path_exists(sess, hub_dir):
                print("no telemetry directory on hub: %s" % hub_dir)
            else:
                for name in sorted(hub_listdir(sess, hub_dir)):
                    download_one(sess, hub_dir.rstrip("/") + "/" + name, dest, chunk_size)
        for path in files:
            download_one(sess, path, dest, chunk_size)
    except Exception as exc:
        print("ERROR: %s: %s" % (type(exc).__name__, exc))
        return 1
    finally:
        sess.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
