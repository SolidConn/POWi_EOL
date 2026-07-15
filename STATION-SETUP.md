# EOL Station Setup — new laptop / jig PC from scratch

Everything needed to run the full EOL flow (Phase 1 program+test, Phase 2
provision, SWD wipe/rework) on a fresh Windows machine. The station has **no
credentials of its own** — firmware and identity all flow through the operator's
admin login in the browser; the agent only touches local hardware.

## 1. Hardware on the bench

| Item | Purpose |
|---|---|
| SEGGER **J-Link** probe (SWD to the PCB/jig pogo pins) | flash, RTT `eoltest`, SWD wipe |
| **PEAK PCAN-USB** on the bench CAN bus (2-node, self-ACK) | CAN stimulus / RX check |
| **Bluetooth radio** (built-in or USB dongle) | Phase-2 provisioning over BLE (`bleak`) |
| 12 V bench supply to the module | power (VBAT sense expects 9–15 V) |

> ⚠️ An attached probe can hold the module in a dead state — **unplug the
> probe for functional/pairing tests** (Phase 2, phone checks).

## 2. Software installs (once, admin rights)

1. **SEGGER J-Link Software** — V8.24 or newer
   (<https://www.segger.com/downloads/jlink/>). The agent loads the DLL from
   `C:\Program Files\SEGGER\JLink_V824\JLink_x64.dll` — if you install a
   different version, update `JLINK_DLL` in `eol-agent/eol_run.py` (and
   `rtt_shell.py`). Older DLLs (< V8.x) don't know the nRF54L15 — don't rely
   on the copy pylink bundles.
2. **nRF Command Line Tools** (`nrfjprog`) —
   <https://www.nordicsemi.com/Products/Development-tools/nrf-command-line-tools>.
   Tick the bundled SEGGER option if asked. Verify: `nrfjprog --version` in a
   fresh terminal (must be on PATH).
3. **PEAK PCAN drivers** — <https://www.peak-system.com/> (PCAN-USB device
   driver). The agent expects channel `PCAN_USBBUS1` (first PCAN-USB plugged
   in); a different channel goes in `PCAN_CHANNEL` in `eol-agent/eol_run.py`.
4. **Python 3.11+** — python.org or Microsoft Store. Then:
   ```powershell
   cd powi-eol
   pip install -r eol-agent\requirements.txt
   ```
5. **Chrome or Edge** — the /eol page needs Web Bluetooth + `ws://localhost`.

## 3. Get the repo

```powershell
git clone https://github.com/SolidConn/POWi_EOL.git powi-eol
```

Station-specific knobs live at the top of `eol-agent/eol_run.py`
(`JLINK_DLL`, `DEVICE`, `PCAN_CHANNEL`) — defaults match the original bench.
`FW_DIR`/`BOOT_HEX`/`APP_HEX` are only fallbacks for standalone CLI runs; in
normal operation the **/eol page stages the published firmware from the admin**
into `eol-agent/fw_cache/` automatically (sha-verified, no local firmware repo
needed).

## 4. Run it

```powershell
cd powi-eol
python eol-agent\agent.py        # leaves "EOL jig agent v0.x — ws://localhost:9151"
```

Then in Chrome/Edge on the **same machine**: log in to
<https://app.solidconnectivity.com> (your own user; role admin/engineer for
rework, any EOL-enabled role for testing) → **EOL**.

- **Phase 1**: scan the batch card (stage `phase1`) → the "Jig agent connected"
  block appears → *▶ Program + Test PCB*. Firmware versions shown come from the
  admin's published lines.
- **Phase 2**: scan a unit label → *Test + Provision + Lock* (agent path uses
  the PC radio automatically; browser Bluetooth is the fallback).
- **Wipe / rework**: EOL → *Rework* (admin/engineer) — BLE re-serial, or the
  SWD wipe buttons (identity wipe / full chip erase) which run through this
  agent.

The agent block only appears while the page can reach `ws://localhost:9151`,
i.e. only on the machine actually running `agent.py` — a remote admin browser
never sees it.

## 5. Smoke test (5 min, no admin needed)

```powershell
cd powi-eol\eol-agent
python rtt_shell.py "prov show"     # probe + RTT + shell alive → prints identity
python can_stim.py                  # PCAN transmits (Ctrl-C to stop)
python eol_run.py --wipe            # identity wipe (safe on a virgin module)
python eol_run.py --flash           # full Phase-1 cycle (needs staged/local fw)
```

Common failures:
- `Could not connect to the target` → board unpowered or SWD cable loose
  (hardware, always — reseat and retry).
- RTT garbage / no shell → production image flashed (no shell); use
  `--erase` / *Full chip erase* then reflash.
- pylink DLL errors → wrong/old J-Link DLL; point `JLINK_DLL` at the V8.24+
  install.
- PCAN `Bus error` → wrong channel or the bus has no second node/self-ACK.
- Flashing fails while RTT Viewer is open → close it (it holds the probe).
