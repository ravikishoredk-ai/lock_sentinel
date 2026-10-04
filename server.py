import os
import requests
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import asyncio

app = FastAPI(title="Lock Sentinel Security System")

system_state = {"state": "SAFE", "image_url": ""}

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "YOUR_BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "YOUR_VERIFIED_SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "YOUR_RECEIVER_EMAIL")

cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "YOUR_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY", "YOUR_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET", "YOUR_API_SECRET")
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await websocket.send_json(system_state)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

def send_grace_email_alert():
    try:
        app_url = os.getenv("RENDER_EXTERNAL_URL", "https://lock-sentinel.onrender.com")
        disarm_link = f"{app_url}/api/disarm"
        url = "https://api.brevo.com/v3/smtp/email"
        
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; text-align: center; padding: 20px;">
            <h2 style="color: #f57c00;">⚠️ Notice: Door Opened</h2>
            <p>The 55-second entry grace period has started.</p>
            <p>Would you like to DISARM the system before the alarm triggers?</p>
            <br>
            <a href="{disarm_link}" style="padding: 14px 28px; background-color: #388e3c; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; font-size: 18px;">DISARM NOW</a>
          </body>
        </html>
        """
        payload = {
            "sender": {"name": "Lock Sentinel", "email": SENDER_EMAIL},
            "to": [{"email": RECEIVER_EMAIL, "name": "System Admin"}],
            "subject": "⚠️ Notice: Door Opened (Grace Period Active)",
            "htmlContent": html_content
        }
        headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print("Grace email error:", e)

def send_email_alert():
    try:
        app_url = os.getenv("RENDER_EXTERNAL_URL", "https://lock-sentinel.onrender.com")
        disarm_link = f"{app_url}/api/disarm"
        url = "https://api.brevo.com/v3/smtp/email"
        
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; text-align: center; padding: 20px;">
            <h2 style="color: #d32f2f;">🚨 ALARM TRIGGERED: Breach Detected!</h2>
            <p>The 55-second grace period expired without authorization.</p>
            <p><a href="{app_url}/" style="color: #1976d2; font-weight: bold; font-size: 16px;">View Live Dashboard & Camera</a></p>
            <br>
            <a href="{disarm_link}" style="padding: 14px 28px; background-color: #388e3c; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; font-size: 18px;">SILENCE ALARM & DISARM</a>
          </body>
        </html>
        """
        payload = {
            "sender": {"name": "Lock Sentinel", "email": SENDER_EMAIL},
            "to": [{"email": RECEIVER_EMAIL, "name": "System Admin"}],
            "subject": "🚨 SECURITY ALERT: Lock Sentinel Alarm Triggered!",
            "htmlContent": html_content
        }
        headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print("Email error:", e)

@app.post("/api/esp/grace-period")
async def trigger_grace_period():
    system_state["state"] = "GRACE_PERIOD"
    send_grace_email_alert()
    await manager.broadcast(system_state)
    return JSONResponse(status_code=200, content={"status": "success"})

@app.post("/api/esp/door-opened")
async def door_opened_trigger():
    system_state["state"] = "TRIGGERED"
    send_email_alert()
    await manager.broadcast(system_state)
    return JSONResponse(status_code=200, content={"status": "success"})

@app.post("/api/esp/upload-snapshot")
async def upload_snapshot(file: UploadFile = File(...)):
    try:
        result = cloudinary.uploader.upload(file.file)
        system_state["image_url"] = result.get("secure_url")
        await manager.broadcast(system_state)
        return JSONResponse(status_code=200, content={"status": "success"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/esp/status")
async def check_status():
    return JSONResponse(status_code=200, content={"state": system_state["state"]})

@app.post("/api/app/verify")
async def disarm_from_dashboard():
    system_state["state"] = "SAFE"
    system_state["image_url"] = ""
    await manager.broadcast(system_state)
    return JSONResponse(status_code=200, content={"status": "success"})

@app.get("/api/disarm", response_class=HTMLResponse)
async def disarm_from_email():
    system_state["state"] = "SAFE"
    system_state["image_url"] = ""
    await manager.broadcast(system_state)
    return HTMLResponse(content="""
    <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: #059669; font-size: 2.5em;">System Disarmed</h1>
        <p style="font-size: 1.2em;">Dashboard reset to SAFE mode. The physical alarm will silence shortly.</p>
        <a href="/" style="font-size: 1.2em; color: #3b82f6;">Return to Dashboard</a>
    </body></html>
    """)

@app.post("/api/esp/reset")
async def reset_system():
    system_state["state"] = "SAFE"
    system_state["image_url"] = ""
    await manager.broadcast(system_state)
    return JSONResponse(status_code=200, content={"status": "success"})

@app.get("/")
async def serve_dashboard():
    return FileResponse("index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
