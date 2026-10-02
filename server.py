import asyncio
import os
from fastapi import FastAPI, WebSocket, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse
import cloudinary
import cloudinary.uploader

# Configure Cloudinary (Make sure to set these Environment Variables in your Render dashboard)
cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "YOUR_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY", "YOUR_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET", "YOUR_API_SECRET") 
)

app = FastAPI()
clients = set()

system_state = "SAFE" # Options: SAFE, GRACE_PERIOD, TRIGGERED
GRACE_PERIOD_DURATION = 55.0
latest_image_url = ""

async def broadcast_state():
    """Sends the current alarm state and latest photo URL to all connected web pages."""
    message = {"state": system_state, "image_url": latest_image_url}
    for client in clients.copy():
        try:
            await client.send_json(message)
        except Exception:
            clients.remove(client)

async def grace_period_timer():
    """Waits 55 seconds, then triggers the alarm if not manually disarmed."""
    global system_state
    await asyncio.sleep(GRACE_PERIOD_DURATION)
    # If the timer finishes and the system hasn't been disarmed back to SAFE, trigger it
    if system_state == "GRACE_PERIOD":
        system_state = "TRIGGERED"
        await broadcast_state()

@app.get("/")
async def get_index():
    with open("index.html", "r") as f:
        return HTMLResponse(f.read())

@app.post("/api/esp/door-opened")
async def door_opened(background_tasks: BackgroundTasks):
    global system_state
    if system_state == "SAFE":
        system_state = "GRACE_PERIOD"
        background_tasks.add_task(grace_period_timer)
        await broadcast_state()
    return {"status": "Timer started"}

@app.post("/api/esp/upload-snapshot")
async def upload_snapshot(file: UploadFile = File(...)):
    global latest_image_url
    try:
        # Upload the JPEG to Cloudinary and grab the secure URL
        result = cloudinary.uploader.upload(file.file)
        latest_image_url = result.get("secure_url")
        
        # Instantly update the web dashboard with the new photo
        await broadcast_state()
        return {"status": "uploaded", "url": latest_image_url}
    except Exception as e:
        return {"error": str(e)}

# --- NEW: Handles the Web Dashboard Disarm Button ---
@app.post("/api/app/verify")
async def verify_user():
    global system_state
    # Instantly reset the system back to normal
    system_state = "SAFE"
    await broadcast_state()
    return {"status": "System disarmed and reset to SAFE"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    # Send current state and photo to the newly connected user
    await websocket.send_json({"state": system_state, "image_url": latest_image_url})
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        clients.remove(websocket)
