"""Phase-1 EOL pipeline — the M3 jig agent's core.

One command does what the operator did by hand tonight:
  1. flash    : nrfjprog recover(optional) + program bootloader & signed app + reset
  2. can      : start recipe-frame TX on PCAN (BEFORE eoltest — the sampling
                window must overlap live traffic; validated 2026-07-10)
  3. eoltest  : RTT `eoltest <wait>` -> parse EOL:key=value until EOL:done=1
  4. verdict  : every value against limits.json -> PASS/FAIL + failing keys
Result is a JSON report on stdout (the future WebSocket payload).

Usage:
  python eol_run.py                 # test only (board already flashed)
  python eol_run.py --flash         # program first, then test
  python eol_run.py --recover       # full recover+program, then test
  python eol_run.py --no-can        # skip CAN stimulus (eoltest 0)
"""
import argparse
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent

# ── Station configuration (jig-specific; agent config file later) ─────────────
JLINK_DLL   = r"C:\Program Files\SEGGER\JLink_V824\JLink_x64.dll"
DEVICE      = "nRF54L15_M33"
FW_DIR      = Path(r"D:\powifirmware\build")
BOOT_HEX    = FW_DIR / "mcuboot" / "zephyr" / "zephyr.hex"
APP_HEX     = FW_DIR / "powifirmware" / "zephyr" / "zephyr.signed.hex"   # NOT merged.hex — NV must stay blank
PCAN_CHANNEL = "PCAN_USBBUS1"
CAN_BITRATE  = 500000
CAN_WAIT_S   = 5
EOLTEST_TIMEOUT_S = 40

# Recipe frames (embedded Amarok recipe) — see can_stim.py for the rule mapping.
CAN_FRAMES = {
    0x083: [0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00],
    0x203: [0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    0x3B3: [0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    0x3C3: [0x03, 0x00, 0x00, 0x00, 0xC8, 0x00, 0x00, 0x00],
    0x3D8: [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0B],
}


def step(name, msg=""):
    print(f"[{time.strftime('%H:%M:%S')}] {name}{': ' + msg if msg else ''}", flush=True)


# ── 1. Flash ──────────────────────────────────────────────────────────────────

def nrfjprog(*args, timeout=120):
    r = subprocess.run(["nrfjprog", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"nrfjprog {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def flash(recover=False, on_step=step, boot_hex=None, app_hex=None):
    boot = Path(boot_hex) if boot_hex else BOOT_HEX
    app = Path(app_hex) if app_hex else APP_HEX
    if recover:
        on_step("flash", "recover (full erase)")
        nrfjprog("--recover")
    on_step("flash", f"program bootloader {boot.name}")
    nrfjprog("--program", str(boot), "--sectorerase", "--verify")
    on_step("flash", f"program app {app.name}")
    nrfjprog("--program", str(app), "--sectorerase", "--verify")
    on_step("flash", "reset")
    nrfjprog("--reset")
    time.sleep(2.0)   # let the app boot before RTT attach


# ── 2. CAN stimulus (background thread) ───────────────────────────────────────

class CanStim(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop_evt = threading.Event()
        self.error = None
        self.sent = 0

    def run(self):
        try:
            import can
            bus = can.Bus(interface="pcan", channel=PCAN_CHANNEL, bitrate=CAN_BITRATE,
                          fd=False, receive_own_messages=True)
            msgs = [can.Message(arbitration_id=i, data=bytes(d), is_extended_id=False, is_fd=False)
                    for i, d in CAN_FRAMES.items()]
            try:
                while not self.stop_evt.is_set():
                    for m in msgs:
                        bus.send(m)
                        self.sent += 1
                    time.sleep(0.05)
            finally:
                bus.shutdown()
        except Exception as e:            # noqa: BLE001 — surface any CAN failure in the report
            self.error = str(e)


# ── 3. eoltest over RTT ───────────────────────────────────────────────────────

def run_eoltest(can_wait_s):
    import pylink
    lib = pylink.library.Library(JLINK_DLL)
    jl = pylink.JLink(lib=lib)
    jl.open()
    jl.set_tif(pylink.enums.JLinkInterfaces.SWD)
    jl.connect(DEVICE, speed=4000)
    jl.rtt_start(None)
    for _ in range(50):
        try:
            if jl.rtt_get_num_up_buffers() > 0:
                break
        except pylink.errors.JLinkRTTException:
            pass
        time.sleep(0.1)

    cmd = f"eoltest {can_wait_s}\n".encode()
    written = 0
    while written < len(cmd):
        written += jl.rtt_write(0, list(cmd[written:]))
        time.sleep(0.01)

    # Read until EOL:done=1 (or timeout). Firmware log lines interleave — only
    # EOL:key=value lines are the result.
    buf = ""
    values = {}
    deadline = time.time() + EOLTEST_TIMEOUT_S
    done = False
    while time.time() < deadline and not done:
        data = jl.rtt_read(0, 4096)
        if data:
            buf += bytes(data).decode("utf-8", errors="replace")
            # strip ANSI escapes before parsing
            clean = re.sub(r"\x1b\[[0-9;]*m|\r", "", buf)
            for line in clean.split("\n"):
                m = re.match(r"^EOL:([a-z0-9_]+)=(.*)$", line.strip())
                if m:
                    values[m.group(1)] = m.group(2).strip()
                    if m.group(1) == "done":
                        done = True
        else:
            time.sleep(0.05)

    jl.rtt_stop()
    jl.close()
    if not done:
        raise RuntimeError(f"eoltest did not finish within {EOLTEST_TIMEOUT_S}s (got {len(values)} values)")
    return values


# ── 4. Limits verdict ─────────────────────────────────────────────────────────

def check_limits(values, limits):
    failures = []
    skipped = []
    for key in limits.get("required_keys", []):
        if key not in values:
            failures.append({"key": key, "reason": "missing", "value": None})

    for key, rule in limits["checks"].items():
        if key not in values:
            failures.append({"key": key, "reason": "missing", "value": None})
            continue
        v = values[key]
        if v in rule.get("skip_values", []):
            skipped.append(key)          # e.g. chopped channels: deliberately distrusted
            continue
        if "equals" in rule:
            if v != rule["equals"]:
                failures.append({"key": key, "reason": f"expected {rule['equals']}", "value": v})
            continue
        try:
            n = float(v)
        except ValueError:
            failures.append({"key": key, "reason": "not numeric", "value": v})
            continue
        if "min" in rule and n < rule["min"]:
            failures.append({"key": key, "reason": f"below min {rule['min']}", "value": v})
        if "max" in rule and n > rule["max"]:
            failures.append({"key": key, "reason": f"above max {rule['max']}", "value": v})
    return failures, skipped


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(do_flash=False, recover=False, use_can=True, on_step=step,
                 boot_hex=None, app_hex=None, fw_version=None):
    """Full Phase-1 cycle. Returns the report dict; never raises — any error
    becomes verdict=ERROR with the reason. `on_step(name, msg)` streams progress.
    boot_hex/app_hex override the local default images (admin-staged firmware)."""
    t0 = time.time()
    limits = json.loads((HERE / "limits.json").read_text())
    report = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "limits_version": limits["version"]}

    try:
        if do_flash or recover:
            flash(recover=recover, on_step=on_step, boot_hex=boot_hex, app_hex=app_hex)
            report["flashed"] = True
            if fw_version:
                report["fw_version"] = fw_version

        can_thread = None
        can_wait = CAN_WAIT_S if use_can else 0
        if use_can:
            on_step("can", f"stimulus on {PCAN_CHANNEL} @ {CAN_BITRATE}")
            can_thread = CanStim()
            can_thread.start()
            time.sleep(1.0)              # traffic flowing BEFORE eoltest starts
            if can_thread.error:
                raise RuntimeError(f"CAN stimulus failed: {can_thread.error}")

        on_step("eoltest", f"running (can_wait={can_wait})")
        values = run_eoltest(can_wait)

        if can_thread:
            can_thread.stop_evt.set()
            can_thread.join(timeout=2)
            report["can_frames_sent"] = can_thread.sent
            if can_thread.error:
                raise RuntimeError(f"CAN stimulus failed mid-test: {can_thread.error}")

        report["measurements"] = values
        report["chip_id"] = values.get("chipid")
        failures, skipped = check_limits(values, limits)
        report["failures"] = failures
        report["skipped"] = skipped
        report["verdict"] = "PASS" if not failures else "FAIL"

    except Exception as e:               # noqa: BLE001 — any pipeline error is a FAIL with reason
        report["verdict"] = "ERROR"
        report["error"] = str(e)

    report["elapsed_s"] = round(time.time() - t0, 1)
    on_step("verdict", report["verdict"])
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flash", action="store_true", help="program bootloader+app before testing")
    ap.add_argument("--recover", action="store_true", help="full recover (erase) + program + test")
    ap.add_argument("--no-can", action="store_true", help="skip CAN stimulus (eoltest 0)")
    args = ap.parse_args()

    report = run_pipeline(do_flash=args.flash, recover=args.recover, use_can=not args.no_can)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
