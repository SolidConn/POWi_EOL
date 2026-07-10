"""Minimal RTT shell driver: send commands to the POWi firmware shell over
J-Link RTT and print everything received. Proof-of-concept for the M3 jig
agent's RTT layer."""
import sys
import time
import pylink

CMDS = sys.argv[1:]  # commands to send, in order

lib = pylink.library.Library(r"C:\Program Files\SEGGER\JLink_V824\JLink_x64.dll")
jl = pylink.JLink(lib=lib)
jl.open()
jl.set_tif(pylink.enums.JLinkInterfaces.SWD)
jl.connect("nRF54L15_M33", speed=4000)
jl.rtt_start(None)

# Wait for the RTT control block to be located.
for _ in range(50):
    try:
        if jl.rtt_get_num_up_buffers() > 0:
            break
    except pylink.errors.JLinkRTTException:
        pass
    time.sleep(0.1)

def drain(seconds):
    end = time.time() + seconds
    out = []
    while time.time() < end:
        data = jl.rtt_read(0, 4096)
        if data:
            out.append(bytes(data).decode("utf-8", errors="replace"))
        else:
            time.sleep(0.05)
    return "".join(out)

print(drain(1.0))  # whatever is buffered (boot log tail)

for cmd in CMDS:
    payload = (cmd + "\n").encode()
    written = 0
    while written < len(payload):
        written += jl.rtt_write(0, list(payload[written:]))
        time.sleep(0.01)
    print(f"\n>>> {cmd}")
    print(drain(10.0 if cmd.startswith("eoltest") else 2.0))

jl.rtt_stop()
jl.close()
