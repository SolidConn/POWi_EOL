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

**M2 — ✅ CODE COMPLETE 2026-07-10, build-verified, NOT FLASHED** (firmware
branch `eol-provisioning` @ b716afa, pushed; RAM 88.36% bench build):
- FW-A `src/provision.c/h`: NV identity "prov/id" (serial + per-device passkey
  + lock; survives customer factory reset). GATT svc c1a50060/61 — read =
  ver/locked/serial; writes 0x01 stage / 0x02 lock / 0x03 clear-bonds
  (WRITE_AUTHEN; stage/lock rejected once locked). `prov` shell cmd
  (show/set/lock/wipe) = RTT rework/bench path. DIS serial settings-backed
  (CONFIG_BT_DIS_SETTINGS, "bt/dis/serial"). ONE image serves every unit.
- FW-B: `eoltest [can_wait_s]` in main.c — EOL:key=value walk (fw, FICR
  chipid, serial/locked, vbat_mv, temp_dc, out1/2 ST-while-ON, out3/4 on_ma +
  fault + is_mv, can_rx after waiting for the agent's PCAN traffic) + EOL:done=1.
  ST carries info ONLY while steady-ON on this PCB (no Vbb->OUT pull-ups).
- FW-C: unprovisioned name "POWi-XXXX" (identity-addr tail); provisioned =
  bare serial (unchanged app contract). Adv name element rebuilt at each adv
  start, so a lock applies without reboot. Phase-2 page: filter namePrefix
  "POWi-", then confirm locked==0 by reading c1a50061 after connect.
- ⚠️ BENCH VALIDATION PENDING (needs hardware): flash → expect "POWi-XXXX"
  adv + PIN 012345 → `prov set 2625016 12345` + `prov lock` → verify serial
  adv, app reconnect, DIS serial → `eoltest 5` with PCAN TX → check EOL: lines.
  ⚠️ Flashing DEPROVISIONS the bench unit until prov set/lock is run.
- Build/flash: procedure in app repo `SESSION-HANDOFF-2026-07-06.md` §1a
  (RTT viewer must be closed to flash; UNPLUG probe for functional tests).

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
