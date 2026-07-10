# EOL — first working session brief (written 2026-07-10)

You are in `D:\Solid Connectivity APPS\powi-eol` — the EOL project home.
Read `EOL-PLAN.md` (canonical plan) and `README.md` (repo split) first.

## Where to start

M1 and M2 are independent — pick per Eduard's priority that day:

**M1 — data model + status pages (admin repo, no hardware needed)**
- New D1 tables: `units` (chip_id PK, serial nullable, pin, mac, variant,
  status, batch_id, fw_version, timestamps), `batches`, `unit_events`
  (unit, station, operator, action, result, measurements_json, ts).
- Status machine per EOL-PLAN §3 (extend the existing serials/status list —
  today's serials table has the customer-facing statuses; decide merge vs
  separate-table linking).
- Minimal `/eol` pages: scan field (QR scanner = keyboard) → unit card →
  action-QR transitions (COAT:DONE, MOULD:DONE, QA:PASS/REJECT, PACK:DONE)
  with signed tokens. This alone makes coating/overmould/QA/packing live.
- Deploy: `npm run db:migrate:remote` then `npm run cf:deploy` from the admin
  repo (see its docs; ~27 pre-existing D1Database tsc errors are harmless).

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
