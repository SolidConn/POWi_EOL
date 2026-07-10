# EOL — first working session brief (written 2026-07-10)

You are in `D:\Solid Connectivity APPS\powi-eol` — the EOL project home.
Read `EOL-PLAN.md` (canonical plan) and `README.md` (repo split) first.

## Where to start

**M1 — ✅ SHIPPED + DEPLOYED 2026-07-10** (admin branch `feat/eol-m1` @ 1c95ec5,
remote D1 migrated). What exists:
- Tables `eol_units` / `eol_batches` / `eol_events` (migration `0024_eol.sql`).
  Units have nullable-unique chip_id AND serial — a serial scanned before the
  jig exists auto-creates its unit at 'overmoulded'. Batch `stage` covers the
  bulk coat/mould steps. EOL transitions write through to serial_numbers.status.
- `lib/eol.ts`: status machine + HMAC action tokens `SCEOL:<ACTION>:<sig10>`
  (secret auto-generated into app_settings `eol_qr_secret`); batch cards
  `SCEOLB:<code>`. EOL_PASS/REJECT double as manual test verdicts until M3/M4.
- Pages: `/eol` scan hub (keyboard-wedge input, PASS/FAIL flash, desktop action
  buttons), `/eol/batches` (create + batch QR print), `/eol/cards` (print the
  signed station cards). APIs under `/api/eol/*` (session-auth).
- TODO before factory use: operator smoke test in a logged-in browser; print +
  laminate station cards; decide whether to merge `feat/eol-m1` to main.

**M2 — next up** (independent of M1):

**M2 — firmware blockers (firmware repo `D:\powifirmware`)**
- FW-A: NV serial + per-device passkey + lock flag; provisioning BLE char
  (writable only unlocked); locked → passkey replaces fixed 012345.
- FW-B: `eoltest` shell cmd — channel walk emitting `EOL:key=value` + `EOL:done`
  over RTT (VBAT, temp, OUT3/4 IS mA per state, OUT1/2 ST-while-ON, CAN-frame
  seen). Note: ST carries info ONLY while steady-ON on current PCB (no OFF-state
  open-load — no Vbb->OUT pull-ups; see fw main.c matrix comment near st_poll).
- FW-C: unprovisioned-advertising flag so Phase-2 web can find virgin modules.
- Build/flash: exact procedure in app repo `SESSION-HANDOFF-2026-07-06.md` §1a
  (env vars, west build, nrfjprog; RTT viewer must be closed to flash;
  UNPLUG the probe for functional tests — attached probe can hold module dead).

**M3 — jig agent (this repo)** — after or alongside M2:
- Python; pynrfjprog (flash + RTT), python-can (PCAN, TX self-ACK on 2-node
  bus), WebSocket server localhost:9151, PyInstaller one-file exe.
- Contract with the /eol page: session open → program → chip-id → eoltest →
  limits verdict → POST results to admin API.

## Open decisions still needing Eduard (EOL-PLAN §8)
inventory system; PIN-in-QR content; label printing flow; Phase-1 second flash
(EOL image then production image — recommended yes); operator identity;
per-batch-only tracking through coating/overmould.

## Cross-repo state as of 2026-07-10
- firmware `control-page-gestures` @ 71f7c54 (flashed on 2625016), app
  `control-ux-and-can-sync` @ defaab8, admin `feat/recipe-binary-compiler`
  (deployed). None merged to main. OTA bins stale (bump to 1.0.5 before OTA).
- Vehicle-capture feature: Audi real-data capture pending this week.
