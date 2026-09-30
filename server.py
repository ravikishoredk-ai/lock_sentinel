import asyncio
import os
import shutil
import time
from enum import Enum
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

STATIC_DIR = BASE_DIR / "static"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class SystemState(str, Enum):
    IDLE = "IDLE"
    PENDING_AUTH = "PENDING"
    AUTHENTICATED = "VERIFIED"
    ALARM_ACTIVE = "ALARM"

current_system_state = SystemState.IDLE
grace_period_start_time = 0.0
GRACE_PERIOD_DURATION = 10.0

grace_timer_task = None
connected_websockets: list[WebSocket] = []

def get_grace_seconds_remaining():
    if current_system_state == SystemState.PENDING_AUTH:
        elapsed = time.time() - grace_period_start_time
        return int(max(0, GRACE_PERIOD_DURATION - elapsed))
    return 0

async def notify_clients_of_state_change():
    state_data = {
        "state": current_system_state.value,
        "grace_seconds_left": get_grace_seconds_remaining(),
        "door_img": "/static/door.jpg" if (STATIC_DIR / "door.jpg").exists() else "",
        "indoor_img": "/static/indoor.jpg" if (STATIC_DIR / "indoor.jpg").exists() else ""
    }
    
    dead_sockets = []
    for ws in connected_websockets:
        try:
            await ws.send_json(state_data)
        except Exception:
            dead_sockets.append(ws)
            
    for dead in dead_sockets:
        connected_websockets.remove(dead)

async def start_grace_period_countdown():
    global current_system_state
    while current_system_state == SystemState.PENDING_AUTH:
        remaining = get_grace_seconds_remaining()
        await notify_clients_of_state_change()
        
        if remaining <= 0:
            print("[SERVER] Grace period expired! Transitioning to ALARM.")
            current_system_state = SystemState.ALARM_ACTIVE
            await notify_clients_of_state_change()
            break
            
        await asyncio.sleep(1)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    html_path = BASE_DIR / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return f"<h1>index.html not found!</h1><p>Looking in: {html_path}</p>"

@app.post("/api/esp/door-opened")
async def esp_door_opened():
    global current_system_state, grace_period_start_time, grace_timer_task
    if current_system_state != SystemState.IDLE:
        return {"status": "ignored"}
    
    print("[ESP32] Door Opened! Grace Period Initiated.")
    current_system_state = SystemState.PENDING_AUTH
    grace_period_start_time = time.time()
    
    if grace_timer_task and not grace_timer_task.done():
        grace_timer_task.cancel()
        
    grace_timer_task = asyncio.create_task(start_grace_period_countdown())
    return {"status": "ok"}

@app.post("/api/esp/upload-snapshot")
async def esp_upload_snapshot(file: UploadFile = File(...)):
    file_location = STATIC_DIR / "door.jpg"
    with open(file_location, "wb+") as f:
        shutil.copyfileobj(file.file, f)
    
    shutil.copyfile(file_location, STATIC_DIR / "indoor.jpg")
    await notify_clients_of_state_change()
    return {"info": "snapshot uploaded"}

@app.get("/api/esp/poll-status")
async def esp_poll_status():
    return {"verified": (current_system_state == SystemState.AUTHENTICATED)}

@app.post("/api/app/verify")
async def verify_user():
    global current_system_state, grace_timer_task
    print("[DASHBOARD] User Authenticated!")
    
    if grace_timer_task and not grace_timer_task.done():
        grace_timer_task.cancel()
        
    current_system_state = SystemState.AUTHENTICATED
    await notify_clients_of_state_change()
    
    asyncio.create_task(reset_demo_state(5))
    return {"status": "verified"}

async def reset_demo_state(delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    global current_system_state
    current_system_state = SystemState.IDLE
    
    door_file = STATIC_DIR / "door.jpg"
    indoor_file = STATIC_DIR / "indoor.jpg"
    if door_file.exists(): os.remove(door_file)
    if indoor_file.exists(): os.remove(indoor_file)
    
    await notify_clients_of_state_change()
    print("[SERVER] Reset to IDLE.")

@app.websocket("/ws")
@app.websocket("/ws/app-updates")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    
    await websocket.send_json({
        "state": current_system_state.value,
        "grace_seconds_left": get_grace_seconds_remaining(),
        "door_img": "/static/door.jpg" if (STATIC_DIR / "door.jpg").exists() else "",
        "indoor_img": "/static/indoor.jpg" if (STATIC_DIR / "indoor.jpg").exists() else ""
    })
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)