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

import websockets

from eol_run import run_pipeline

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

        else:
            await ws.send(json.dumps({"event": "error", "message": f"unknown cmd '{cmd}'"}))


async def main():
    print(f"EOL jig agent v{VERSION} — ws://localhost:{PORT}")
    async with websockets.serve(handle, "localhost", PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
