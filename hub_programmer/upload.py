#!/usr/bin/env python3
"""hub_upload.py — put a Python file onto the hub over USB, with no LEGO app.

This is the ONLY script in this project that writes to the hub. Everything in
probes/ is read-only; this is not, and it is deliberately kept separate for
that reason.

    ./scripts/hub_upload.py src/config.py                    # DRY RUN, writes nothing
    ./scripts/hub_upload.py src/config.py --apply            # actually write it
    ./scripts/hub_upload.py src/config.py --apply --to /flash/lib/config.py
    ./scripts/hub_upload.py --list                           # what is on the hub now
    ./scripts/hub_upload.py --remove /flash/lib/config.py --apply

HOW IT WORKS
    The hub runs stock MicroPython with a REPL on /dev/ttyACM0 and a writable
    filesystem at /flash, with /flash/lib already on sys.path. So a file gets
    there by opening it at the REPL and writing base64 chunks, which the hub
    decodes with binascii. No LEGO app, no firmware change, no slot protocol.

WHAT IT REFUSES TO DO
    * Overwrite a stock file (boot.py, README.txt, pybcdc.inf) -- ever.
    * Overwrite main.py without --force, because that is the file the hub runs
      on boot and the pristine copy lives in docs/archives/hub-baseline/.
    * Touch /flash/program, /flash/config, or anything resembling firmware.
    * Anything at all without --apply.

VERIFICATION
    After writing, it reads the file back off the hub and compares SHA-256
    against the local file. A write is reported as successful only when the
    hashes match -- never merely because no exception was raised.

Exit codes: 0 ok · 1 verify failed · 2 refused · 3 no port · 4 busy · 5 no pyserial · 64 usage
"""

import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "probes"))
import _hubio                                                # noqa: E402

BAUD = 115200
PROMPT = b">>>"
CHUNK = 192                    # raw bytes per REPL line; base64 expands ~4/3
DEFAULT_DIR = "/flash/lib"

# Files that ship with the board. Never overwritten, no flag available.
STOCK = {"/flash/boot.py", "/flash/README.txt", "/flash/pybcdc.inf"}
# Needs --force: it is what runs on boot.
GUARDED = {"/flash/main.py"}
# Directories we do not write into at all.
FORBIDDEN_DIRS = ("/flash/program", "/flash/config")


class Session(object):
    """A REPL session that always closes and never blocks forever."""

    def __init__(self, port, serial_mod):
        self.ser = serial_mod.Serial(port, BAUD, timeout=2.0, write_timeout=5.0)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def wake(self):
        self.ser.reset_input_buffer()
        self.ser.write(b"\x03")
        time.sleep(0.3)
        self.ser.write(b"\r\n")
        time.sleep(0.3)
        return PROMPT in self.ser.read(4096)

    def cmd(self, expr, timeout=6.0):
        """Send one expression, return the hub's reply with the echo stripped."""
        self.ser.write((expr + "\r\n").encode("ascii"))
        self.ser.timeout = timeout
        raw = self.ser.read_until(PROMPT, size=65536).decode("utf-8", errors="replace")
        out = []
        for ln in raw.splitlines():
            s = ln.strip()
            if not s or s == ">>>" or s == expr.strip():
                continue
            out.append(s)
        return "\n".join(out)


def sha_of(data):
    return hashlib.sha256(data).hexdigest()


def hub_path_exists(sess, path):
    """Does `path` exist on the hub? os.stat raises when it does not, so the
    hub answers with a bool rather than us parsing a traceback."""
    # exec() keeps this to ONE physical REPL line. A real multi-line try/except
    # would put the REPL into continuation mode and make the reply hard to parse.
    reply = sess.cmd(
        'import os; exec("try:\\n os.stat(\'%s\')\\n print(\'YES\')\\n'
        'except OSError:\\n print(\'NO\')")' % path
    )
    if "YES" in reply:
        return True
    if "NO" in reply:
        return False
    return "unknown (%s)" % reply.replace("\n", " ")[:60]


def check_target(target, force):
    if target in STOCK:
        return "REFUSED: %s is a stock board file. It is never overwritten." % target
    if target in GUARDED and not force:
        return ("REFUSED: %s is what the hub runs on boot. Pass --force if you mean it.\n"
                "         The pristine copy is in docs/archives/hub-baseline/05-stock-files.txt" % target)
    for d in FORBIDDEN_DIRS:
        if target.startswith(d):
            return "REFUSED: %s is inside %s, which this script will not touch." % (target, d)
    if not target.startswith("/flash/"):
        return "REFUSED: %s is outside /flash." % target
    return None


def do_list(sess):
    print(sess.cmd("import os; print(sorted(os.listdir('/flash')))"))
    print("/flash/lib:")
    print("  " + sess.cmd(
        "import os; print(sorted(os.listdir('/flash/lib')) if 'lib' in os.listdir('/flash') else 'NO /flash/lib')"))
    print("/flash/program:")
    print("  " + sess.cmd("import os; print(sorted(os.listdir('/flash/program')))"))
    print("free bytes:")
    print("  " + sess.cmd("import os; s=os.statvfs('/flash'); print(s[0]*s[3])"))
    return 0


def do_remove(sess, target, apply_it):
    err = check_target(target, force=False)
    if err:
        print(err)
        return 2
    if not apply_it:
        print("DRY RUN: would remove %s" % target)
        print("Nothing was changed. Re-run with --apply.")
        return 0
    print(sess.cmd("import os; os.remove('%s'); print('removed')" % target))
    still = sess.cmd("import os; print('%s'.rsplit('/',1)[1] in os.listdir('%s'))"
                     % (target, target.rsplit("/", 1)[0]))
    print("still present: %s" % still)
    return 0 if "False" in still else 1


def do_upload(sess, local, target, apply_it, force):
    with open(local, "rb") as fh:
        data = fh.read()
    want = sha_of(data)

    print("local   : %s  (%d bytes)" % (local, len(data)))
    print("target  : %s" % target)
    print("sha256  : %s" % want)

    err = check_target(target, force)
    if err:
        print(err)
        return 2

    directory, leaf = target.rsplit("/", 1)
    print("exists  : %s" % hub_path_exists(sess, target))

    free = sess.cmd("import os; s=os.statvfs('/flash'); print(s[0]*s[3])")
    print("free    : %s bytes" % free)

    nchunks = (len(data) + CHUNK - 1) // CHUNK
    if not apply_it:
        print()
        print("DRY RUN — nothing was written.")
        print("  would ensure directory %s exists" % directory)
        print("  would write %d chunk(s) of up to %d bytes" % (nchunks, CHUNK))
        print("  would read the file back and compare SHA-256")
        print()
        print("Re-run with --apply to write it.")
        return 0

    if directory != "/flash":
        leaf = directory.rsplit("/", 1)[1]
        r = sess.cmd("import os; print('%s' in os.listdir('/flash'))" % leaf)
        if "True" not in r:
            print("creating %s" % directory)
            print("  " + sess.cmd("import os; os.mkdir('%s'); print('made')" % directory))

    print("writing %d chunk(s)..." % nchunks)
    import binascii
    r = sess.cmd("import binascii; _f=open('%s','wb'); print('open')" % target)
    if "open" not in r:
        print("FAILED to open the file on the hub: %s" % r)
        return 1
    for i in range(nchunks):
        blob = data[i * CHUNK:(i + 1) * CHUNK]
        b64 = binascii.b2a_base64(blob).decode("ascii").strip()
        r = sess.cmd("_f.write(binascii.a2b_base64('%s'))" % b64, timeout=8.0)
        if "Traceback" in r or "Error" in r:
            print("FAILED on chunk %d: %s" % (i, r))
            sess.cmd("_f.close()")
            return 1
    sess.cmd("_f.close(); print('closed')")

    # Verify by hashing the file ON THE HUB and comparing to the local hash.
    # A one-liner, not a REPL loop: multi-line blocks put the REPL into
    # continuation mode and the parsing gets fragile for no benefit. Our files
    # are a few KB against 32 MB free, so reading one whole is fine.
    print("verifying by hashing it on the hub...")
    got = sess.cmd(
        "import hashlib, binascii; "
        "print(binascii.hexlify(hashlib.sha256(open('%s','rb').read()).digest()).decode())"
        % target, timeout=10.0)
    got = got.strip().splitlines()[-1].strip() if got.strip() else ""

    print("hub sha : %s" % got)
    if got == want:
        print()
        print("VERIFIED: the file on the hub hashes identically to the local file.")
        return 0
    print()
    print("VERIFY FAILED: hub hash does not match local. Do not trust this upload.")
    return 1


def main(argv):
    apply_it = "--apply" in argv
    force = "--force" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]

    target = None
    if "--to" in argv:
        target = argv[argv.index("--to") + 1]

    try:
        import serial
    except ImportError:
        print("NO_PYSERIAL: python3 -m pip install pyserial")
        return 5

    port = _hubio.find_port()
    if port is None:
        print("UNKNOWN: no /dev/spike or /dev/ttyACM0 — hub not enumerated.")
        return 3

    try:
        sess = Session(port, serial)
    except Exception as exc:
        print("BUSY_OR_DENIED: %s: %s" % (port, exc))
        return 4

    try:
        if not sess.wake():
            print("No '>>>' prompt. The hub is not presenting a REPL; refusing to write.")
            return 3

        if "--list" in argv:
            return do_list(sess)

        if "--remove" in argv:
            return do_remove(sess, argv[argv.index("--remove") + 1], apply_it)

        if not args:
            print(__doc__.split("HOW IT WORKS")[0].strip())
            return 64

        local = args[0]
        if not os.path.exists(local):
            print("no such local file: %s" % local)
            return 64
        if target is None:
            target = "%s/%s" % (DEFAULT_DIR, os.path.basename(local))
        return do_upload(sess, local, target, apply_it, force)
    finally:
        sess.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
