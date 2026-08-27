# examples/light_matrix_and_buttons.py - the hub's own operator interface, verbosely.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/light_matrix_and_buttons.py --seconds 75
#
# [UNVERIFIED] NEVER RUN ON REAL HARDWARE, on our hub or any other, as of
# 2026-08-27. Every NAME below was read off our own hub
# (docs/archives/hub-baseline/03-api-surface.txt), so nothing here is invented --
# but no CALL below has been made, so no signature, unit or range is a
# measurement yet. Delete this block once it has run and paste the real output
# into docs/findings/.
#
# IT NEVER COMMANDS A MOTOR, never writes a file, never touches firmware. It
# writes only to the matrix, the status LED and the speaker.
#
# Purpose: DISCOVERY. The robot has no screen and blind teleoperation is
# permitted, so the matrix, the status light and a beep are its whole report to
# a Builder standing next to it. src/hub_ui.py was written against assumptions;
# this corrects them. What it DERIVES rather than assumes:
#   * the brightness range set_pixel() accepts -- write, read back, and BRACKET
#     the ceiling. hub_ui.py assumes 0-100 on the strength of nothing.
#   * whether show()'s flat list of 25 is ROW-MAJOR -- light one, scan it back.
#   * which physical edge is the TOP row -- the operator eyeballs one pixel.
#   * whether write() BLOCKS while it scrolls: a blocking banner stalls the tick.
#   * what button.pressed() returns -- a bool, or milliseconds held.
#
# CONNECT is never polled or prompted for: pressing it drives the hub's own
# Bluetooth pairing, and initiating a pairing is blacklisted (CLAUDE.md rule 5).
#
# MicroPython: no f-strings, no statistics, no numpy. % formatting, plain loops.

import time
import hub
import color

BUTTON_WAIT_MS = 8000     # how long to wait for the operator on each button
EYEBALL_MS = 4000         # how long one lit pixel is held up to be looked at
LEVELS = (0, 1, 5, 9, 10, 50, 100, 101, 255)   # brightness probes, past the assumed top
BEEP_HZ = 880             # A5 -- carries across a classroom
BEEP_MS = 150             # short: this is a state report, not an alarm
BEEP_VOLUME = 20          # QUIET on purpose. Raise only if it cannot be heard.

lm = hub.light_matrix
led = hub.light
btn = hub.button
snd = hub.sound


# Call fn(), print what it returned OR how it failed, and say which. Discovery
# scripts must survive a wrong guess about a signature and keep going.
def attempt(label, fn):
    try:
        print("  %-32s -> %r" % (label, fn()))
        return True
    except Exception as exc:
        print("  %-32s !! %r" % (label, exc))
        return False


print("=" * 62)
print("OPERATOR INTERFACE DISCOVERY -- matrix, light, buttons, sound")
print("=" * 62)

print("\n--- 1. WHAT EXISTS ---")
for label, obj in (("light_matrix", lm), ("light", led), ("button", btn), ("sound", snd)):
    names = [a for a in dir(obj) if not a.startswith("_")]
    plain = [a for a in names if not a.startswith("IMAGE_")]
    print("  %-12s %s" % (label, ", ".join(plain)))
    if len(names) != len(plain):
        print("  %-12s + %d IMAGE_* constants (section 5)" % ("", len(names) - len(plain)))

print("\n--- 2. THE HUB STATUS LIGHT ---")
print("  constants: POWER=%r CONNECT=%r" % (led.POWER, led.CONNECT))
was = None
try:
    was = led.color(led.POWER)
    if was is None:
        print("  led.color(POWER) returned None -- SETTER ONLY, not a getter.")
    else:
        print("  led.color(POWER) returned %r -- it reads back, so it is a getter too" % (was,))
except Exception as exc:
    print("  led.color(POWER) with one argument: %r" % (exc,))
# UNVERIFIED that hub.light accepts constants from the `color` module.
set_ok = attempt("led.color(POWER, color.AZURE)", lambda: led.color(led.POWER, color.AZURE))
time.sleep_ms(1200)
if set_ok and isinstance(was, int):
    attempt("led.color(POWER, original)", lambda: led.color(led.POWER, was))
else:
    print("  NOT restored -- the original could not be read, or the setter was")
    print("  refused. Whatever the LED shows now is the truth; nothing is guessed.")

print("\n--- 3. BRIGHTNESS RANGE, derived by write-then-read ---")
accepted = []
for v in LEVELS:
    try:
        lm.set_pixel(0, 0, v)
        got = lm.get_pixel(0, 0)
        print("    wrote %3d  ->  get_pixel reads %r" % (v, got))
        if got == v:
            accepted.append(v)
    except Exception as exc:
        print("    wrote %3d  ->  REJECTED %r" % (v, exc))
print("  A value reading back SMALLER than written is clamped -- and what it")
print("  clamps TO is the ceiling.")
lit_ok = [v for v in accepted if v > 0]
top = max(lit_ok) if lit_ok else -1
if top == max(LEVELS):
    print("  => %d round-tripped, the TOP of the probe list: the ceiling was" % top)
    print("     NOT bracketed and is still unknown. Suspect get_pixel echoes what")
    print("     was written rather than reflecting the panel. Re-run with a")
    print("     higher LEVELS entry before believing any range.")
elif top >= 100:
    nxt = min([v for v in LEVELS if v > top])   # the next value actually PROBED, not top+1
    print("  => %d survives the round trip and %d does not, so the ceiling is" % (top, nxt))
    print("     somewhere in [%d, %d). hub_ui.py's 0-100 holds." % (top, nxt))
elif top > 0:
    print("  => highest value surviving the round trip is %d, NOT 100." % top)
    print("     hub_ui.py writes 100 for a lit pixel and must be corrected.")
else:
    print("  => INCONCLUSIVE: nothing above 0 round-tripped. Read the rows by hand.")

print("\n--- 4. WHOLE-FRAME show() AND WHICH WAY IS UP ---")
attempt("lm.get_orientation()", lm.get_orientation)
bright = top if top > 0 else 100
# Clear FIRST: section 3 left (0,0) written. Without this, a show() that throws
# would leave section 3's pixel on the panel and it would be read as show()'s doing.
attempt("lm.clear()", lm.clear)
frame = [0] * 25
frame[1] = bright
attempt("lm.show(list of 25 ints)", lambda: lm.show(frame))
lit = []
for y in range(5):
    row = []
    for x in range(5):
        try:
            got = lm.get_pixel(x, y)
        except Exception:
            got = -1
        row.append(got)
        if got > 0:
            lit.append((x, y))
    print("    arg2=%d  %r" % (y, row))
print("  flat index 1 came back lit at (arg1, arg2) = %r" % (lit,))
if lit == [(1, 0)]:
    print("  => show() is ROW-MAJOR, index = arg2*5 + arg1. hub_ui.show_frame() is right.")
elif lit == [(0, 1)]:
    print("  => show() is COLUMN-MAJOR, index = arg1*5 + arg2. hub_ui.show_frame() is WRONG.")
elif not lit:
    print("  => NOTHING lit. show() did not take a flat list of 25, or it needs")
    print("     runloop to drive it. Nothing about the ordering was learned.")
else:
    print("  => INCONCLUSIVE. Work the mapping out from the grid above by hand.")
print("  NOW LOOK AT THE MATRIX. One pixel is lit. With the ports facing you,")
print("  write down which corner it sits by: that fixes the TOP row for good.")
time.sleep_ms(EYEBALL_MS)

print("\n--- 5. BUILT-IN IMAGES AND TEXT ---")
images = [a for a in dir(lm) if a.startswith("IMAGE_")]
print("  %d IMAGE_* constants, including: %s" % (len(images), ", ".join(images[:5])))
attempt("lm.show_image(IMAGE_HEART)", lambda: lm.show_image(lm.IMAGE_HEART))
time.sleep_ms(1000)
t0 = time.ticks_ms()
attempt("lm.write('7')  one digit", lambda: lm.write("7"))
one_ms = time.ticks_diff(time.ticks_ms(), t0)
time.sleep_ms(1000)
t0 = time.ticks_ms()
attempt("lm.write('SYS 301')  scrolling", lambda: lm.write("SYS 301"))
seven_ms = time.ticks_diff(time.ticks_ms(), t0)
print("  write() took %d ms for 1 character and %d ms for 7." % (one_ms, seven_ms))
if seven_ms > one_ms + 500:
    print("  => write() BLOCKS for the whole scroll. Never call it in a control")
    print("     tick -- a state banner would stall the sweep.")
else:
    print("  => write() returned at once for both: asynchronous, or it did")
    print("     nothing. If no text scrolled, it needs runloop to drive it.")
time.sleep_ms(3000)

print("\n--- 6. SOUND: one short quiet beep ---")
attempt("snd.volume()", snd.volume)
if not attempt("snd.beep(hz, ms, volume)", lambda: snd.beep(BEEP_HZ, BEEP_MS, BEEP_VOLUME)):
    attempt("snd.beep(hz, ms)", lambda: snd.beep(BEEP_HZ, BEEP_MS))
time.sleep_ms(600)
print("  Nothing heard => the call returned an awaitable and needs runloop. One")
print("  beep per found mine is the Builder's tally, independent of the matrix,")
print("  so a silent beep loses the best evidence the demo produces.")


# Poll one button until it is pressed and released, or the wait runs out.
# Returns the peak reading, or None if pressed() could not be called at all.
def watch(label, which, timeout_ms):
    print("\n  Press and HOLD the %s button for about a second." % label)
    t0 = time.ticks_ms()
    first = None
    peak = 0
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        try:
            v = btn.pressed(which)
        except Exception as exc:
            print("    %-8s btn.pressed(constant) raised %r" % (label, exc))
            print("    %-8s -- the signature is not pressed(<constant>). Stop here." % label)
            return None
        if v:
            if first is None:
                first = v
            if v > peak:
                peak = v
        elif first is not None:
            break
        time.sleep_ms(20)
    if first is None:
        print("    %-8s nothing in %d ms -- not pressed, or not readable" % (label, timeout_ms))
    else:
        print("    %-8s first %r   peak %r" % (label, first, peak))
    return peak


print("\n--- 7. BUTTONS (interactive) ---")
print("  constants: LEFT=%r RIGHT=%r CONNECT=%r POWER=%r"
      % (btn.LEFT, btn.RIGHT, btn.CONNECT, btn.POWER))
print("  POWER and CONNECT are deliberately NOT polled and NOT prompted for:")
print("  CONNECT drives the hub's own Bluetooth pairing (blacklisted to initiate).")
peak = watch("LEFT", btn.LEFT, BUTTON_WAIT_MS)
if peak is not None:
    right = watch("RIGHT", btn.RIGHT, BUTTON_WAIT_MS)   # polled even if LEFT was missed
    if right is not None and right > peak:
        peak = right
if peak is None:
    print("\n  => pressed() could not be called with a button constant. What it")
    print("     DOES take is unknown; hub_ui.py's `pressed(...) > 0` is unproven.")
elif peak > 1:
    print("\n  => pressed() returns MILLISECONDS HELD, not a bool. hub_ui.py's")
    print("     `pressed(...) > 0` is correct, and a long-press gesture is free.")
elif peak == 1:
    print("\n  => pressed() returned 1/True: a plain boolean, no hold duration.")
else:
    print("\n  => no press was seen at all. Re-run and press when prompted.")

attempt("lm.clear()", lm.clear)
print("\nDONE.")
