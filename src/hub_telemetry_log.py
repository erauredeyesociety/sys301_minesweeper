"""Persistent telemetry logging for hub-run programs.

This module is deliberately small: a slot program can create a CsvLog, call append(line) with the
existing telemetry.record_line(...) output or any other CSV row, and later the host can pull the file
from /flash over USB.
"""
try:
    import os as _os
except ImportError:  # pragma: no cover - host and hub both have os, but keep import failure loud.
    _os = None

DEFAULT_LOG_DIR = "/flash/tmp/telemetry"


def _join(directory, leaf):
    if directory.endswith("/"):
        return directory + leaf
    return directory + "/" + leaf


def ensure_dir(path):
    """Create a one-level-or-deeper directory path if it is missing."""
    if _os is None:
        raise RuntimeError("os module unavailable")
    parts = [p for p in path.split("/") if p]
    current = "/" if path.startswith("/") else ""
    for part in parts:
        current = _join(current.rstrip("/"), part) if current else part
        try:
            _os.mkdir(current)
        except OSError:
            pass
    return path


def timestamp_name(prefix, now_ms, suffix=".csv"):
    return "%s-%010d%s" % (prefix, int(now_ms), suffix)


class CsvLog(object):
    """Line-oriented CSV logger with periodic flushes."""

    def __init__(self, header, directory=DEFAULT_LOG_DIR, prefix="run", now_ms=0, flush_every=10):
        ensure_dir(directory)
        self.path = _join(directory, timestamp_name(prefix, now_ms))
        self.flush_every = max(1, int(flush_every))
        self.count = 0
        self._fh = open(self.path, "w")
        if isinstance(header, (list, tuple)):
            for line in header:
                self._fh.write(str(line).rstrip("\n") + "\n")
        else:
            self._fh.write(str(header).rstrip("\n") + "\n")
        self._fh.flush()

    def append(self, line):
        self._fh.write(line.rstrip("\n") + "\n")
        self.count += 1
        if self.count % self.flush_every == 0:
            self._fh.flush()

    def close(self):
        self._fh.flush()
        self._fh.close()
