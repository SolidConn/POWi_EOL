# EOL — working brief (updated 2026-07-10, end of day)

You are in `D:\Solid Connectivity APPS\powi-eol` — the EOL project home.
Read `EOL-PLAN.md` (canonical plan) and `README.md` (repo split) first.

**SELF-CONTAINED BY DESIGN** — Eduard may continue from a different account:
everything needed lives in the repos, none of it in session memory. Doc map:
- This file + `EOL-PLAN.md` (canonical plan) — here.
- Admin repo `EOL.md` — the /eol module AS-BUILT (schema, status machine, QR
  token format, APIs, pages, admin ops, Phase-2 provisioning contract, deploy).
- Firmware repo `HANDOFF.md` §"EOL provisioning + self-test" — FW-A/B/C
  as-built (NV identity, GATT c1a50060/61 opcodes, eoltest, adv naming).
- Build/flash/deploy procedures — app repo `SESSION-HANDOFF-2026-07-06.md` §1.

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
- Feedback rounds same day (all deployed, latest admin commit `c2cd4f3`):
  per-DEVICE activity feed (expandable step history, batch steps merged in);
  admin adjust/edit/delete everywhere (status override = audited ADMIN_ADJUST;
  batch edit modal; deletes admin-gated); `eol_batches.external_ref` = Inventory
  build ref (manual now, auto-fill via INVENTORY_INTEGRATION.md inbox later,
  M5 stock-in keys on it); 📷 phone-as-scanner (in-page camera QR, continuous,
  BarcodeDetector/jsQR); station-cards print CSS fix; **per-serial PINs
  generated + printed + exported** (lib/pin.ts — closes the PIN-in-QR open
  decision: QR/label/CSV carry the real per-device PIN).
- Full as-built reference: admin repo `EOL.md`.
- TODO before factory use: operator dry run (phone camera or scanner); print +
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
- ✅ BENCH-VALIDATED over RTT 2026-07-10 (flashed on 2625016): fresh flash came
  up unprovisioned (serial unset/locked 0/default PIN); `eoltest 0` emitted the
  full EOL: walk (chipid=18e68de320bc798d, vbat 11.7 V, temp 34.2 °C, OUT1/2
  ST ok, OUT4 1535 mA real load; OUT3 = SETTLING because the bench unit has a
  persisted PWM config — chopped channels are deliberately distrusted; virgin
  units are static → fine, but the M3 agent/limits must treat a chopped
  channel as "skip", or eoltest could force static first); `prov set 2625016
  12345` + `prov lock` restored identity and it SURVIVED a cold reset.
  Validation used pylink RTT (scratch script = seed of the M3 agent's RTT
  layer; pylink needs lib=JLink_V824\JLink_x64.dll — bundled DLL too old for
  nRF54L15). STILL TO VERIFY (needs phone, probe unplugged): app finds/pairs
  "2625016" with PIN 012345, DIS serial reads 2625016, and a Web-Bluetooth/
  nRF-Connect look at the "POWi-XXXX" unprovisioned advertising on a virgin
  flash. ⚠️ CAN leg of eoltest untested (no PCAN attached — ran `eoltest 0`).
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

## Cross-repo state as of 2026-07-10 (end of day)
- firmware: `eol-provisioning` @ 7af850c (EOL work, NOT flashed) on top of
  `control-page-gestures` @ 71f7c54 (what IS flashed on 2625016).
- admin: `feat/eol-m1` @ c2cd4f3 DEPLOYED to app.solidconnectivity.com.
- app: `control-ux-and-can-sync` @ defaab8. None merged to main.
  OTA bins stale (bump to 1.0.5 before OTA).
- Vehicle-capture feature: Audi real-data capture pending this week.
