# EOL Station — Plan (drafted 2026-07-10)

End-of-line jig: program, test, provision (serial + PIN), and track every module
through production — pre-overmould (Phase 1) and post-overmould (Phase 2) — with
full status history through coating, overmould, quality, packing, and stock.

---

## 1. Architecture decision (RECOMMENDED)

**Hybrid: admin-webapp EOL module + a small local "jig agent" on the station PC.**

| Component | Lives where | Does what |
|---|---|---|
| **EOL web UI** | admin repo, new `/eol` section on app.solidconnectivity.com | Operator screens, QR-scan driven (scanners are keyboard-wedge → plain browser input), status workflow, big PASS/FAIL indicators, Phase-2 BLE via **Web Bluetooth** (Chrome) |
| **Jig agent** | admin repo, new `eol-agent/` folder; deployed as a single .exe on the station PC | Everything a browser cannot do: **SWD flash (nrfjprog) + RTT read/parse** (Phase 1) and **PCAN stimulus** (`python-can` over the PCAN-Basic DLL — both phases): transmits the recipe-function frames that drive the outputs, so the CAN→recipe→output path is tested end-to-end, not just forced. Exposes `ws://localhost:9151`; the EOL web page orchestrates it |
| **Database / API** | existing admin D1 + new endpoints | Single source of truth: units, statuses, measurements, audit trail |

Why not a pure Windows app: it would duplicate the DB/API/UI that the admin
already owns, and Phase 2 (BLE + DB + label checks) is natural web territory.
Why not pure web: SWD/RTT is physically impossible from a browser. The agent is
the smallest possible native footprint — no UI of its own beyond a tray/console
status; the browser drives it. (`ws://localhost` from an HTTPS page is allowed
by Chrome — localhost is a trustworthy origin.)

**Agent language: Python** — Nordic ships official bindings (`pynrfjprog`,
incl. RTT), and PyInstaller gives a one-file exe. Node would match the repo but
has no first-party J-Link story.

**Repo decision: no new repo.** EOL UI + API in the admin repo (it owns the DB),
agent in `eol-agent/` inside the same repo so API contract and agent version
move together. Firmware pieces go in the firmware repo as usual.

---

## 2. Identity model — the key design idea

A PCB has **no serial number until Phase 2**, but we still need traceability
from the first flash. Solution: the nRF54L15's **FICR device ID** (factory
unique chip ID, readable over SWD in Phase 1 and derivable from the BLE MAC in
Phase 2 — the static-random MAC comes from the FICR).

- Phase 1: agent reads the chip ID over SWD → creates the unit row keyed on it.
- Phase 2: Web Bluetooth reads the MAC → resolves the same unit → **binds the
  scanned serial to it**. Serial ↔ MAC ↔ chip ID ↔ full test history, no
  temporary stickers on bare PCBs.

---

## 3. Data model (admin D1)

- **units**: `chip_id` (PK from Phase 1), `serial` (null until Phase 2 bind),
  `pin`, `mac`, `variant` (decoded from serial), `status`, `batch_id`,
  `fw_version`, timestamps.
- **unit_events** (audit log): unit, station, operator, action/QR scanned,
  result, `measurements_json`, timestamp. Every status change is an event.
- **batches**: build order id, build size, variant mix, started/finished.
- **Status flow**:
  `pcb_programmed → pcb_test_pass | pcb_test_fail → coated → overmoulded
   → provisioning → testing → production_ok | rejected
   → quality_pass | quality_rejected → packed → in_stock → …existing customer statuses`
- **QR types**:
  1. **Unit label QR** — serial (+ PIN, same content the customer app scans).
  2. **Action QRs** — laminated cards at stations: `EOL:PASS`, `EOL:REJECT`,
     `COAT:DONE`, `MOULD:DONE`, `QA:PASS`, `QA:REJECT`, `PACK:DONE`. Signed
     short tokens so a random QR can't fake a transition.
  3. **Batch QR** — opens a Phase-1 session (this is the "dummy QR" — make it
     the batch/build-order card, so scanning it also captures the build side).

---

## 4. Phase 1 — bare PCB (SWD, fast, no BLE)

Station: fixture with pogo pins (power, SWD, 4 output terminals into fixed test
loads, CAN transceiver pair), J-Link, the agent PC, scanner.

1. Operator scans the **batch QR** → web page opens a Phase-1 session.
2. PCB onto fixture → operator hits Start (or auto-start on target detect).
3. Agent, fully automatic (~15–30 s target):
   a. `nrfjprog --recover` → program **bootloader + app** (merged hex) → reset.
   b. Read FICR chip ID → create/find unit row.
   c. Attach RTT → issue `eoltest` → firmware runs the self-test walk (see §6)
      emitting machine-parsable lines (`EOL:vbat_mv=11720`, `EOL:out3_ma=1980`, …).
      In parallel the agent transmits the **EOL test recipe's CAN frames via
      PCAN** (function ON/OFF per channel) — the outputs are activated the way
      a vehicle activates them, validating CAN RX + recipe engine + output
      stage in one pass (self-test force covers channels the recipe misses).
      NOTE: 2-node bus with a listen-only module → the PCAN node needs TX
      self-acknowledge, exactly like the dev bench.
   d. Agent checks every parameter against a limits table (versioned in the
      admin DB, not hardcoded) → verdict.
4. PASS → status `pcb_test_pass`, big green screen; FAIL → red + which
   parameter failed; measurements stored either way.
5. PCB moves on: **coating station** scans batch + `COAT:DONE` when cured;
   **overmould station** scans `MOULD:DONE` after inspection. (These stations
   need only a browser + scanner — no agent.) Open point: pre-serial units are
   tracked per-batch at these bulk steps, per-unit tracking resumes at Phase 2.

## 5. Phase 2 — overmoulded module (BLE, provisioning)

Station: browser + scanner + harness with test loads + PCAN (driven by the same
jig agent — Phase 2 uses only its CAN capability). No SWD.

1. Scan the **unit label QR** → admin checks: serial exists, status is
   `overmoulded`, label data matches DB (serial + PIN as printed) → proceed.
2. Web Bluetooth scan → find the unprovisioned module (advertises a
   "unprovisioned" flag/name) → read MAC → resolve chip ID → **bind serial**.
3. Firmware check: variant (decoded from serial) → latest released firmware →
   **BLE OTA** if the module is behind (the only update path post-overmould).
4. Functional test (status → `testing`): the module runs the **EOL test recipe**;
   the agent drives each function ON/OFF over PCAN while the browser reads the
   result over BLE telemetry (output active flags, OUT3/4 currents against the
   jig loads, OUT1/2 ST-while-ON, VBAT, temp) — full vehicle-equivalent path.
   BLE force/config chars cover anything CAN doesn't reach. Same limits-table
   pattern as Phase 1.
   **Monitoring without SWD**: everything Phase 1 reads via RTT already has a
   BLE equivalent — output-state notify (c1a50013), CS telemetry (OUT3/4 mA,
   OUT1/2 ST bits, VBAT, temp, thermal state, ~1 Hz), bus-status char, DIS.
   Known gap if we want it: live SG1/SG2 input levels aren't exposed over BLE —
   if post-overmould SG stimulus tests are wanted, add **FW-D: EOL diagnostic
   characteristic** (device-sequenced self-test returning the eoltest bundle
   over BLE). Start without it; add only if M4 hits a gap.
   A failed in-jig OTA is logged as its own rejection reason (`ota_fail`) —
   the EOL OTA doubles as a 100% test of the field-update path.
5. **Provision LAST** (answer to the pairing question — yes, avoid it):
   the whole test runs unprovisioned using the fixed default passkey. Only
   after PASS: write serial + per-device PIN + **lock** via the provisioning
   characteristic, factory-reset bonds so the station's pairing doesn't ship,
   verify the device now advertises provisioned. → `production_ok`.
   FAIL at any point → `rejected` (with the failing parameter logged).
6. **Quality**: inspector scans unit QR, then `QA:PASS` or `QA:REJECT` card.
7. **Packing**: scan unit QR + `PACK:DONE` → `packed`.
8. **Stock**: `in_stock` + inventory-system hook (see open questions).

---

## 6. Firmware prerequisites (firmware repo, blockers for everything above)

- **FW-A — provisioning**: NV fields for serial + passkey + lock flag; a
  provisioning BLE characteristic writable ONLY while unlocked; once locked,
  the per-device passkey replaces the fixed 012345 and the characteristic goes
  read-only. (This is the long-standing "fw passkey ships first" prerequisite —
  no real PINs on labels before this exists.)
- **FW-B — `eoltest` self-test**: shell command (Phase 1 uses the RTT build)
  that walks all channels, samples IS/VBAT/temp/ST, listens for the jig CAN
  frame, and prints `EOL:key=value` lines + `EOL:done`.
- **FW-C — unprovisioned advertising flag** so the Phase-2 page can find the
  right module and never grab a provisioned one.
- **Build policy**: Phase 1 flashes an **EOL/bench-style image** (shell+RTT) to
  run `eoltest`, then — decision needed — either (a) reflash the production
  image before coating, or (b) ship one image where the shell is present but
  provisioning-lock disables it. (a) is cleaner and cheap at the jig (one extra
  program cycle). Ties into the 1.1.0 hardening list (prod MCUboot key,
  FPROTECT, RTT off) — the key must be final before any pot.

---

## 7. Build order (suggested milestones)

1. **M1 — data model**: units/batches/events tables + status machine + minimal
   `/eol` pages (scan → status transitions). Coating/overmould/QA/packing flows
   work with just this — no hardware code.
2. **M2 — firmware FW-A/B/C** (provisioning + eoltest + adv flag).
3. **M3 — jig agent** (Python: nrfjprog + RTT + WebSocket) + Phase-1 page.
4. **M4 — Phase-2 page** (Web Bluetooth bind/test/provision).
5. **M5 — inventory hook + limits-table editor + reporting** (yield per batch,
   fail Pareto from unit_events).

M1 and M2 are independent and can go in parallel sessions.

---

## 8. Open decisions

1. **Inventory system** — which one? (Defines the M5 hook: API, webhook, CSV?)
2. **PIN in the label QR** alongside serial (customer-scan convenience, matches
   current app flow) vs serial-only QR + printed PIN — current app design
   assumes serial+PIN in QR; keep?
3. **Label printing** — where do labels come from? Natural fit: admin generates
   serial+PIN and renders the label PDF/ZPL at "batch label print" time (before
   Phase 2); then the DB is by construction the source the label is checked
   against.
4. **Phase-1 second flash** (EOL image → production image) — accept the extra
   ~10 s per unit? (Recommended yes.)
5. **Operator identity** — badge QR scan at session start, or per-station login?
6. Bulk steps (coating/overmould) tracked per-batch only, per-unit resumes at
   Phase 2 — acceptable?
