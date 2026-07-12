"""M3 jig agent: exposes the Phase-1 pipeline on ws://localhost:9151 so the
/eol page (running in the station browser) can orchestrate it.

Protocol (JSON messages):
  -> {"cmd": "status"}
  <- {"event": "status", "busy": false, "version": "0.1"}
  -> {"cmd": "run", "flash": true, "recover": false, "can": true}
  <- {"event": "step", "name": "flash", "msg": "program bootloader ..."}   (streamed)
  <- {"event": "result", "report": { verdict, chip_id, measurements, ... }}

One run at a time (a jig has one probe); a `run` while busy returns
{"event":"error","message":"busy"}. Chrome allows ws://localhost from an
HTTPS page — localhost is a trustworthy origin (EOL-PLAN §1).

Run on the jig PC:  python agent.py
"""
import asyncio
import json
import threading
import time

import websockets

from eol_run import run_pipeline, CanStim
from phase2 import run_phase2

VERSION = "0.1"
PORT = 9151

run_lock = threading.Lock()


async def handle(ws):
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send(json.dumps({"event": "error", "message": "bad json"}))
            continue

        cmd = msg.get("cmd")
        if cmd == "status":
            await ws.send(json.dumps({"event": "status", "busy": run_lock.locked(), "version": VERSION}))

        elif cmd == "run":
            if not run_lock.acquire(blocking=False):
                await ws.send(json.dumps({"event": "error", "message": "busy"}))
                continue
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue = asyncio.Queue()

            def on_step(name, m=""):
                loop.call_soon_threadsafe(queue.put_nowait, {"event": "step", "name": name, "msg": m})

            def worker():
                try:
                    report = run_pipeline(
                        do_flash=bool(msg.get("flash", True)),
                        recover=bool(msg.get("recover", False)),
                        use_can=bool(msg.get("can", True)),
                        on_step=on_step,
                    )
                    loop.call_soon_threadsafe(queue.put_nowait, {"event": "result", "report": report})
                finally:
                    run_lock.release()
                    loop.call_soon_threadsafe(queue.put_nowait, None)   # end of stream

            threading.Thread(target=worker, daemon=True).start()
            while True:
                item = await queue.get()
                if item is None:
                    break
                await ws.send(json.dumps(item))

        elif cmd == "canstim":
            # CAN stimulus only (Phase 2: the page reads BLE telemetry while
            # the recipe frames flow). No probe involved.
            seconds = min(max(float(msg.get("seconds", 5)), 1), 30)
            if not run_lock.acquire(blocking=False):
                await ws.send(json.dumps({"event": "error", "message": "busy"}))
                continue
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue = asyncio.Queue()

            def can_worker():
                try:
                    stim = CanStim()
                    stim.start()
                    time.sleep(0.5)
                    if stim.error:
                        loop.call_soon_threadsafe(queue.put_nowait,
                            {"event": "canstim", "state": "error", "message": stim.error})
                    else:
                        loop.call_soon_threadsafe(queue.put_nowait,
                            {"event": "canstim", "state": "started"})
                        time.sleep(seconds)
                    stim.stop_evt.set()
                    stim.join(timeout=2)
                    loop.call_soon_threadsafe(queue.put_nowait,
                        {"event": "canstim", "state": "done", "sent": stim.sent,
                         "error": stim.error})
                finally:
                    run_lock.release()
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            threading.Thread(target=can_worker, daemon=True).start()
            while True:
                item = await queue.get()
                if item is None:
                    break
                await ws.send(json.dumps(item))

        elif cmd == "phase2":
            # Full Phase-2 cycle over the PC's own BLE radio: test -> verdict ->
            # provision on PASS. Fully automatic (no picker/pairing).
            if not run_lock.acquire(blocking=False):
                await ws.send(json.dumps({"event": "error", "message": "busy"}))
                continue
            try:
                q: asyncio.Queue = asyncio.Queue()

                def on_step(n, m=""):
                    q.put_nowait({"event": "step", "name": n, "msg": m})

                task = asyncio.create_task(run_phase2(
                    str(msg.get("serial", "")), str(msg.get("pin", "")),
                    on_step, dry=bool(msg.get("dry", False))))
                while not (task.done() and q.empty()):
                    try:
                        item = await asyncio.wait_for(q.get(), timeout=0.2)
                        await ws.send(json.dumps(item))
                    except asyncio.TimeoutError:
                        pass
                await ws.send(json.dumps({"event": "result", "report": task.result()}))
            finally:
                run_lock.release()

        else:
            await ws.send(json.dumps({"event": "error", "message": f"unknown cmd '{cmd}'"}))


async def main():
    print(f"EOL jig agent v{VERSION} — ws://localhost:{PORT}")
    async with websockets.serve(handle, "localhost", PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
