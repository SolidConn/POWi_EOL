"""EOL CAN stimulus: transmit the active recipe's frames on a loop so the
firmware's recipe decoder registers live traffic (eoltest -> can_rx=1) and the
CAN->recipe->output path is exercised. Proof-of-concept for the M3 jig agent's
CAN layer (sibling to rtt_shell.py).

Tuned to the embedded Amarok recipe: classical CAN @ 500k, standard 8-byte IDs.
Payload bytes are set to satisfy the recipe function rules, so if channels are
mapped to functions the outputs activate; on a virgin (unmapped) unit the frames
still drive the decoder, which is what eoltest's can_rx counter needs.

Usage:  python can_stim.py [seconds]   (default: run until Ctrl-C)
On a 2-node bus with a silent/listen-only module, PCAN needs to see its own
frames acknowledged; receive_own_messages=True + normal mode is the dev-bench
setup. If TX errors on missing ACK, the module isn't ACKing -> see notes.
"""
import sys
import time
import can

PERIOD_S = 0.05          # 20 Hz per frame — well inside the 5000 ms recipe timeout
CHANNEL = "PCAN_USBBUS1"
BITRATE = 500000         # classical CAN, matches embedded Amarok recipe

# Recipe frames (id -> 8 data bytes), payloads chosen to assert the rules:
#   0x3C3 b0=0x03 (R1/R5/R6), b4=0xC8 (R0)
#   0x083 b5=0x04 (R2)
#   0x3B3 b0=0x07 (R4/R9/R10)
#   0x3D8 b7=0x0B (R3/R8)
#   0x203 b0=0x40 (R7)
FRAMES = {
    0x083: [0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00],
    0x203: [0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    0x3B3: [0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    0x3C3: [0x03, 0x00, 0x00, 0x00, 0xC8, 0x00, 0x00, 0x00],
    0x3D8: [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0B],
}

run_s = float(sys.argv[1]) if len(sys.argv) > 1 else None

bus = can.Bus(interface="pcan", channel=CHANNEL, bitrate=BITRATE,
              fd=False, receive_own_messages=True)

msgs = [can.Message(arbitration_id=i, data=bytes(d), is_extended_id=False, is_fd=False)
        for i, d in FRAMES.items()]

print(f"CAN stim on {CHANNEL} @ {BITRATE} classical — {len(msgs)} frames @ {1/PERIOD_S:.0f} Hz"
      + (f" for {run_s}s" if run_s else " until Ctrl-C"))
sent = 0
t0 = time.time()
try:
    while run_s is None or (time.time() - t0) < run_s:
        for m in msgs:
            bus.send(m)
            sent += 1
        time.sleep(PERIOD_S)
except KeyboardInterrupt:
    pass
except can.CanError as e:
    print(f"CAN TX error after {sent} frames: {e}")
    print("If this is a missing-ACK error, the module isn't acknowledging — "
          "it may be in listen-only mode. Frames still hit the wire; retry eoltest.")
finally:
    bus.shutdown()
    print(f"stopped — {sent} frames sent in {time.time()-t0:.1f}s")
