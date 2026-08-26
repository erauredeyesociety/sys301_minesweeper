#!/usr/bin/env bash
# setup-host.sh — prepare this Ubuntu machine to talk to the SPIKE Prime over USB.
# Touches the hub? NO. This only changes the host, and the hub does not need to be plugged in.
# Timeout: none needed — no network, no serial reads.
#
#   ./scripts/setup-host.sh           show what would change, change nothing
#   ./scripts/setup-host.sh --apply   make the changes (prompts for sudo where required)
#
# Idempotent: safe to run repeatedly. It reports what it CHANGED versus what was ALREADY in place,
# because a script that prints "OK" either way hides the fact that it just modified your system.
#
# Why this exists: ModemManager probes any new /dev/ttyACM* with AT commands. On a MicroPython REPL
# that arrives as keystrokes and corrupts the first session — and it looks exactly like broken
# hardware, which is how a class period gets lost. Clear it BEFORE the hub is ever plugged in.
# See docs/findings/host-environment.md and docs/runbooks/upload-to-hub.md.
set -euo pipefail

APPLY=0
case "${1:-}" in
  --apply) APPLY=1 ;;
  "")      ;;
  *)       sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 64 ;;
esac

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UDEV_RULE=/etc/udev/rules.d/99-lego-spike.rules
LEGO_VID=0694
LEGO_PID=0009

changed=0; already=0; manual=0

ok()      { printf '  ALREADY  %s\n' "$*"; already=$((already+1)); }
did()     { printf '  CHANGED  %s\n' "$*"; changed=$((changed+1)); }
would()   { printf '  WOULD    %s\n' "$*"; changed=$((changed+1)); }
todo()    { printf '  ACTION   %s\n' "$*"; manual=$((manual+1)); }
note()    { printf '           %s\n' "$*"; }

act() {  # act <description> <command...>
  local desc="$1"; shift
  if (( APPLY )); then "$@" >/dev/null 2>&1 && did "$desc" || { printf '  FAILED   %s\n' "$desc"; return 1; }
  else would "$desc"; fi
}

echo "SPIKE Prime host setup — $( ((APPLY)) && echo 'APPLYING' || echo 'DRY RUN (pass --apply to change anything)')"
echo

# --- 1. serial port permissions -------------------------------------------
echo "1. Serial port access"
if id -nG "$USER" | tr ' ' '\n' | grep -qx dialout; then
  ok "$USER is in the 'dialout' group"
else
  act "add $USER to 'dialout'" sudo usermod -aG dialout "$USER" || true
  note "You must LOG OUT AND BACK IN for this to take effect — a new terminal is not enough."
  note "Do NOT work around it with sudo: that leaves root-owned lock files behind."
fi

# --- 2. ModemManager ------------------------------------------------------
echo
echo "2. ModemManager (the one that corrupts the first hub session)"
if ! command -v systemctl >/dev/null 2>&1; then
  note "no systemctl — skipping"
elif systemctl is-enabled ModemManager >/dev/null 2>&1 || systemctl is-active ModemManager >/dev/null 2>&1; then
  note "ModemManager is $(systemctl is-active ModemManager 2>/dev/null || echo unknown)/$(systemctl is-enabled ModemManager 2>/dev/null || echo unknown)."
  note "It will probe /dev/ttyACM0 with AT commands and corrupt the MicroPython session."
  act "disable and stop ModemManager" sudo systemctl disable --now ModemManager || true
  note "Reversible: sudo systemctl enable --now ModemManager"
else
  ok "ModemManager is not running"
fi

# --- 3. udev rule ---------------------------------------------------------
echo
echo "3. udev rule for the hub (stable /dev/spike symlink + group)"
if [ -f "$UDEV_RULE" ] && grep -q "$LEGO_VID" "$UDEV_RULE" 2>/dev/null; then
  ok "$UDEV_RULE exists and matches VID $LEGO_VID"
else
  if (( APPLY )); then
    sudo tee "$UDEV_RULE" >/dev/null <<RULE
# LEGO Education SPIKE Prime Technic Large Hub — CDC ACM
# VID/PID from docs/research/spike-prime-linux-toolchain.md
SUBSYSTEM=="tty", ATTRS{idVendor}=="$LEGO_VID", ATTRS{idProduct}=="$LEGO_PID", \\
  MODE="0660", GROUP="dialout", SYMLINK+="spike", ENV{ID_MM_DEVICE_IGNORE}="1"
RULE
    sudo udevadm control --reload-rules >/dev/null 2>&1 || true
    sudo udevadm trigger >/dev/null 2>&1 || true
    did "wrote $UDEV_RULE and reloaded udev"
  else
    would "write $UDEV_RULE (gives a stable /dev/spike and sets the dialout group)"
  fi
fi

# --- 4. tooling -----------------------------------------------------------
echo
echo "4. Serial tooling"
have_term=0
for t in tio picocom screen; do
  command -v "$t" >/dev/null 2>&1 && { ok "$t is installed"; have_term=1; }
done
if (( ! have_term )); then
  act "install a serial terminal (tio)" sudo apt-get install -y tio || true
fi
if python3 -c 'import serial' >/dev/null 2>&1; then
  ok "pyserial is installed ($(python3 -c 'import serial;print(serial.__version__)' 2>/dev/null))"
else
  act "install pyserial" sudo apt-get install -y python3-serial || true
fi

# --- 5. what this script deliberately does NOT do -------------------------
echo
echo "5. Not done here, on purpose"
todo "Identify the Hub OS — READ-ONLY, and it must not trigger an update prompt."
note "docs/runbooks/hub-identification.md. Do this BEFORE opening any LEGO app."
todo "Install the VS Code uploader — the version depends on the Hub OS you just identified."
note "v2.x+ is Hub OS 3 only; v1.x for Hub OS 2. docs/runbooks/upload-to-hub.md"

# --- summary --------------------------------------------------------------
echo
if (( APPLY )); then
  echo "Summary: $changed changed, $already already in place, $manual manual step(s) remaining."
else
  echo "Summary: $changed would change, $already already in place, $manual manual step(s) remaining."
  echo "Nothing was modified. Re-run with --apply to make the changes."
fi
echo
echo "Then, with the hub plugged in:  ./find_spike_prime.py --verbose"
