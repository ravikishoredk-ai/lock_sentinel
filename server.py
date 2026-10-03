import os
import requests
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List

app = FastAPI(title="Lock Sentinel Security System")

# ====================================================
# FAST2SMS CONFIGURATION
# ====================================================
FAST2SMS_API_KEY = "BMEk1yoSKlcCaWAUtgI248ZsV7ODGJdmQ0Pz3TfFjRYh5q6HNwuAa4FLy20PclYIwkWfzmVG3oN1qseJ"
YOUR_PHONE_NUMBER = "9363730659"

# ====================================================
# CLOUDINARY CONFIGURATION
# (Replace with your Cloudinary credentials if not using env vars)
# ====================================================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "w8jdhijo"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "439362228187961"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", "LK0eKy_c13qtBUdfqNRGhP8Q35c")
)

# System state and live snapshot holder
system_state = {"status": "Secure", "latest_image_url": ""}

# ====================================================
# WEBSOCKET MANAGER FOR LIVE FEED / ALERTS
# ====================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# ====================================================
# FAST2SMS HELPER FUNCTION
# ====================================================
def send_sms_alert():
    """Sends SMS breach alert via Fast2SMS Quick Route."""
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = {
        "route": "q",
        "message": "⚠️ SECURITY ALERT: Lock Sentinel detected a breach! Check the dashboard.",
        "language": "english",
        "flash": 0,
        "numbers": YOUR_PHONE_NUMBER
    }
    headers = {
        "authorization": FAST2SMS_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=10)
        print("Fast2SMS Response:", response.text)
    except Exception as e:
        print("Failed to send SMS:", e)

# ====================================================
# ESP32 HARDWARE ENDPOINTS
# ====================================================
@app.post("/api/esp/door-opened")
async def door_opened_trigger():
    system_state["status"] = "BREACH DETECTED"
    
    # 1. Send SMS alert
    send_sms_alert()
    
    # 2. Broadcast breach event to connected dashboard clients
    await manager.broadcast({
        "event": "breach",
        "status": system_state["status"]
    })
    
    return JSONResponse(status_code=200, content={"status": "success", "message": "Alert triggered and SMS sent"})

@app.post("/api/esp/upload-snapshot")
async def upload_snapshot(file: UploadFile = File(...)):
    try:
        # Upload directly to Cloudinary
        contents = await file.read()
        upload_result = cloudinary.uploader.upload(
            contents,
            folder="lock_sentinel"
        )
        image_url = upload_result.get("secure_url", "")
        system_state["latest_image_url"] = image_url

        # Broadcast new image to connected dashboard clients
        await manager.broadcast({
            "event": "new_snapshot",
            "image_url": image_url
        })

        return JSONResponse(status_code=200, content={"status": "success", "url": image_url})
    except Exception as e:
        print("Cloudinary upload failed:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/esp/reset")
async def reset_system():
    system_state["status"] = "Secure"
    await manager.broadcast({
        "event": "reset",
        "status": system_state["status"]
    })
    return JSONResponse(status_code=200, content={"status": "success", "message": "System reset to secure"})

# ====================================================
# WEBSOCKET ENDPOINT
# ====================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Send initial state on connection
    await websocket.send_json({
        "event": "init",
        "status": system_state["status"],
        "image_url": system_state["latest_image_url"]
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ====================================================
# HTML WEB DASHBOARD
# ====================================================
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Lock Sentinel Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #121212; color: #fff; text-align: center; padding: 40px; }
            .badge { font-size: 24px; padding: 15px 30px; border-radius: 8px; display: inline-block; margin-bottom: 25px; font-weight: bold; }
            .Secure { background-color: #2e7d32; }
            .BREACH { background-color: #d32f2f; animation: pulse 1s infinite alternate; }
            @keyframes pulse { from { opacity: 1; } to { opacity: 0.5; } }
            img { max-width: 80%; max-height: 500px; border: 2px solid #444; border-radius: 8px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>Lock Sentinel Security Hub</h1>
        <div id="statusBadge" class="badge Secure">Status: Secure</div>
        <br>
        <img id="cameraView" src="" alt="Awaiting camera snapshot..." onerror="this.style.display='none';">

        <script>
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(protocol + '//' + window.location.host + '/ws');
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                const badge = document.getElementById('statusBadge');
                const img = document.getElementById('cameraView');

                if (data.status) {
                    badge.innerText = 'Status: ' + data.status;
                    badge.className = 'badge ' + (data.status.includes('BREACH') ? 'BREACH' : 'Secure');
                }
                if (data.image_url) {
                    img.src = data.image_url;
                    img.style.display = 'inline-block';
                }
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
