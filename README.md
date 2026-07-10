# POWi EOL — end-of-line jig project

Home of the EOL station work: the **jig agent** (Python: SWD flash via
pynrfjprog, RTT parse, PCAN stimulus via python-can), jig fixture docs, test
limit definitions, and EOL-specific scripts.

**Read `EOL-PLAN.md` first** — full architecture, both station flows (Phase 1
pre-overmould / Phase 2 post-overmould), firmware blockers, milestones, and
open decisions.

## Split of responsibilities (agreed 2026-07-10)

| Piece | Lives in |
|---|---|
| Jig agent, jig docs, limits authoring | **this repo** |
| EOL web UI (`/eol` pages), API, D1 schema (units/batches/unit_events) | `D:\Solid Connectivity APPS\solidconnectivity-admin` (deployed to app.solidconnectivity.com) |
| FW-A provisioning, FW-B `eoltest`, FW-C unprovisioned-adv flag | `D:\powifirmware` |

A session anchored here can (and will) edit the admin and firmware repos by
absolute path — commits go to each repo separately.

## Suggested layout (to be created as work starts)

```
eol-agent/          Python agent: nrfjprog + RTT + PCAN + ws://localhost:9151
  agent.py
  jlink.py rtt.py canstim.py api.py
docs/               fixture wiring, station setup, operator instructions
limits/             parameter limit tables (source of truth = admin DB; drafts here)
```

## Related context
- Device: bench unit serial 2625016, PIN 012345, J-Link SNR 1057750992.
- Firmware build/flash procedure: app repo `SESSION-HANDOFF-2026-07-06.md` §1a.
- PCAN on a 2-node bus with the listen-only module needs TX self-acknowledge.
- Do NOT print real per-device PINs until FW-A (provisioned passkey) ships.
