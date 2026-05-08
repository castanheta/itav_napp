"""Local xApp tester for invoker scaling callbacks."""
import threading
import time

import httpx
import uvicorn
from fastapi import FastAPI, Request

CALLBACK_HOST = "0.0.0.0"
CALLBACK_PORT = 8004
CALLBACK_ENDPOINT = "/receive-scaling"
INVOKER_URL = "http://localhost:8008/invoker-app/v1/scaling-operation/user"

app = FastAPI()


@app.post(CALLBACK_ENDPOINT)
async def receive(request: Request):
    payload = await request.json()
    print(f"[xApp callback] Received terminal status: {payload}")
    return {"ok": True}


def _start_server():
    uvicorn.run(app, host=CALLBACK_HOST, port=CALLBACK_PORT, log_level="info")


def send_scale_request():
    payload = {
        "action": "SCALE_UP",
        "imsis": ["001010000000001"],
        "uplinkKbps": 500,
        "downlinkKbps": 1000,
        "notificationDestination": f"http://host.docker.internal:{CALLBACK_PORT}{CALLBACK_ENDPOINT}",
        "requestId": "xapp-test-1",
    }
    print(f"[xApp client] POST {INVOKER_URL} with payload: {payload}")
    response = httpx.post(
        INVOKER_URL,
        json=payload,
        headers={"accept": "application/json", "content-type": "application/json"},
        timeout=30,
    )
    print(f"[xApp client] Initial response: {response.status_code} {response.text}")


if __name__ == "__main__":
    threading.Thread(target=_start_server, daemon=True).start()
    time.sleep(1)
    send_scale_request()
    print("[xApp client] Waiting for callback...")
    while True:
        time.sleep(1)
