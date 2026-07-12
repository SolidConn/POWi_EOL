"""Phase-2 EOL cycle over the station PC's own BLE radio (bleak) — fully
automatic: no picker, no pairing prompt (virgin modules are factory-open as of
firmware e962f12), no browser limits.

Sequence (provision LAST — a failed module stays virgin):
  1. scan for the unprovisioned module (name "POWi-*", strongest RSSI)
  2. read provisioning char -> require locked==0
  3. functional test: VBAT/temp baseline, OUT1/2 ST-while-ON, OUT3/4 load
     current, all-off check, CAN RX (CanStim transmits in-process)
  4. PASS -> stage serial+PIN, lock, verify read-back, clear bonds
Returns a report dict; never raises.

CLI test:  python phase2.py 2625016 012345 [--dry]   (--dry = test only)
"""
import argparse
import asyncio
import json
import struct
import time

from bleak import BleakClient, BleakScanner

from eol_run import CanStim

PROV_CHAR  = "c1a50061-5ca1-4b1e-9d2a-1b7f0c4e2a01"
CS_CHAR    = "c1a50002-5ca1-4b1e-9d2a-1b7f0c4e2a01"
FORCE_CHAR = "c1a50012-5ca1-4b1e-9d2a-1b7f0c4e2a01"
STATE_CHAR = "c1a50013-5ca1-4b1e-9d2a-1b7f0c4e2a01"
STAT_CHAR  = "c1a50021-5ca1-4b1e-9d2a-1b7f0c4e2a01"

LIMITS = {
    "vbat_mv": (9000, 15000), "temp_dc": (50, 600),
    "out3_ma": (250, 800), "out4_ma": (1200, 1900),
}


def _parse_cs(b: bytes):
    ch3_st, ch3_f, ch3_ma, ch3_is, ch4_st, ch4_f, ch4_ma, ch4_is = struct.unpack_from("<BBhhBBhh", b, 0)
    vbat, tmv, batt, tdc, therm, stf = struct.unpack_from("<HhBhBB", b, 12)
    return {"ch3_ma": ch3_ma, "ch4_ma": ch4_ma, "vbat_mv": vbat, "temp_dc": tdc,
            "batt": batt, "therm": therm, "st_fault": stf}


async def run_phase2(serial: str, pin: str, on_step=lambda n, m="": None, dry=False):
    t0 = time.time()
    report = {"serial": serial, "measurements": {}, "failures": []}
    meas, failures = report["measurements"], report["failures"]

    try:
        if not (pin.isdigit() and len(pin) == 6):
            raise RuntimeError(f"invalid PIN '{pin}' for serial {serial}")

        on_step("scan", "looking for an unprovisioned module (POWi-*)")
        candidates = {}
        seen = await BleakScanner.discover(timeout=6.0, return_adv=True)
        for dev, adv in seen.values():
            name = adv.local_name or dev.name or ""
            if name.startswith("POWi-"):
                candidates[dev.address] = (dev, adv.rssi, name)
        if not candidates:
            raise RuntimeError("no unprovisioned module (POWi-*) advertising")
        dev, rssi, name = max(candidates.values(), key=lambda c: c[1])
        if len(candidates) > 1:
            on_step("scan", f"{len(candidates)} modules in range — taking strongest ({name} @ {rssi} dBm)")
        on_step("connect", f"{name} ({dev.address}, {rssi} dBm)")

        async with BleakClient(dev, timeout=15.0) as client:
            st = await client.read_gatt_char(PROV_CHAR)
            locked = st[1] == 1
            cur = st[3:3 + st[2]].decode(errors="replace")
            if locked:
                raise RuntimeError(f"module already provisioned as '{cur}' — wrong module?")
            on_step("state", "virgin (locked=0)")

            # ── functional test ────────────────────────────────────────────
            base = _parse_cs(await client.read_gatt_char(CS_CHAR))
            meas["vbat_mv"], meas["temp_dc"] = base["vbat_mv"], base["temp_dc"]
            on_step("baseline", f"VBAT {base['vbat_mv']/1000:.2f} V / {base['temp_dc']/10:.1f} C")
            for k in ("vbat_mv", "temp_dc"):
                lo, hi = LIMITS[k]
                if not lo <= base[k] <= hi:
                    failures.append(f"{k}={base[k]}")
            if base["batt"] != 0:
                failures.append(f"batt_status={base['batt']}")
            if base["therm"] != 0:
                failures.append(f"therm_status={base['therm']}")

            for chn in (1, 2):   # ST diagnosis while steady-ON
                await client.write_gatt_char(FORCE_CHAR, bytes([chn, 6]), response=True)
                await asyncio.sleep(0.7)
                bit = (_parse_cs(await client.read_gatt_char(CS_CHAR))["st_fault"] >> (chn - 1)) & 1
                meas[f"out{chn}_st_fault"] = bit
                on_step(f"out{chn}", f"ON -> ST {'FAULT' if bit else 'ok'}")
                if bit:
                    failures.append(f"out{chn}_st")
                await client.write_gatt_char(FORCE_CHAR, bytes([chn, 7]), response=True)

            for chn in (3, 4):   # real load current
                await client.write_gatt_char(FORCE_CHAR, bytes([chn, 6]), response=True)
                # The CS loop samples ~1 Hz and reports 0 mA until a reading
                # settles (chopped/soft-start guard) — poll instead of racing it.
                ma = 0
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    await asyncio.sleep(0.5)
                    r = _parse_cs(await client.read_gatt_char(CS_CHAR))
                    ma = r["ch3_ma"] if chn == 3 else r["ch4_ma"]
                    if ma != 0:
                        break
                meas[f"out{chn}_ma"] = ma
                on_step(f"out{chn}", f"ON -> {ma} mA")
                lo, hi = LIMITS[f"out{chn}_ma"]
                if not lo <= ma <= hi:
                    failures.append(f"out{chn}_ma={ma}")
                await client.write_gatt_char(FORCE_CHAR, bytes([chn, 7]), response=True)

            for chn in (1, 2, 3, 4):   # ensure everything released/off
                await client.write_gatt_char(FORCE_CHAR, bytes([chn, 7]), response=True)
            await asyncio.sleep(0.4)
            if any(b == 1 for b in await client.read_gatt_char(STATE_CHAR)):
                failures.append("outputs_not_off")

            on_step("can", "stimulus running")
            stim = CanStim()
            stim.start()
            try:
                await asyncio.sleep(2.5)
                rate = struct.unpack_from("<H", await client.read_gatt_char(STAT_CHAR), 1)[0]
                meas["can_rx_rate"] = rate
                on_step("can", f"RX rate {rate}/s")
                if stim.error:
                    failures.append(f"can_stim: {stim.error}")
                elif rate < 1:
                    failures.append(f"can_rx_rate={rate}")
            finally:
                stim.stop_evt.set()
                stim.join(timeout=2)

            if failures:
                report["verdict"] = "FAIL"
                on_step("verdict", f"FAIL: {', '.join(failures)} — module stays virgin")
                return report

            if dry:
                report["verdict"] = "PASS"
                on_step("verdict", "PASS (dry run — NOT provisioned)")
                return report

            # ── provision LAST ─────────────────────────────────────────────
            on_step("provision", f"staging serial={serial}")
            sb = serial.encode()
            await client.write_gatt_char(
                PROV_CHAR, bytes([0x01]) + struct.pack("<I", int(pin)) + bytes([len(sb)]) + sb,
                response=True)
            await client.write_gatt_char(PROV_CHAR, bytes([0x02]), response=True)
            back = await client.read_gatt_char(PROV_CHAR)
            back_serial = back[3:3 + back[2]].decode(errors="replace")
            if back[1] != 1 or back_serial != serial:
                raise RuntimeError(f"verify failed: locked={back[1]} serial='{back_serial}'")
            on_step("provision", f"LOCKED as {back_serial}")
            try:
                await client.write_gatt_char(PROV_CHAR, bytes([0x03]), response=True)
            except Exception:      # noqa: BLE001 — clearing bonds may drop the link
                pass
            on_step("provision", "bonds cleared")
            report["verdict"] = "PASS"
            report["provisioned"] = True
            on_step("verdict", "PASS — provisioned + locked")

    except Exception as e:         # noqa: BLE001 — any failure is an ERROR verdict
        report["verdict"] = "ERROR"
        report["error"] = str(e)
        on_step("verdict", f"ERROR: {e}")

    report["elapsed_s"] = round(time.time() - t0, 1)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("serial")
    ap.add_argument("pin")
    ap.add_argument("--dry", action="store_true", help="test only, do not provision")
    a = ap.parse_args()

    def step(n, m=""):
        print(f"[{time.strftime('%H:%M:%S')}] {n}{': ' + m if m else ''}", flush=True)

    r = asyncio.run(run_phase2(a.serial, a.pin, step, dry=a.dry))
    print(json.dumps(r, indent=2))
